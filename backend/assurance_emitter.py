"""
Assurance Emitter Module for VDO v3
Emits assurance_findings[] and blocked_access[] from structured_data

This module is ADDITIVE ONLY. It does not modify any existing VDO behavior.
It reads from structured_data and optionally synthesized_report (blocked_access only).

Reference: v3-vdo-assurance-contract.md, v3-assurance-emitter-plan.md
"""

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse


# =============================================================================
# CONFIGURATION
# =============================================================================

# Path to assurance_programs.json (relative to this module or absolute)
PROGRAMS_JSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "policies",
    "assurance_programs.json"
)

# Known auditor/registry domains for verification (per plan §Step 6)
AUTHORITATIVE_DOMAINS = [
    # Official registries
    "marketplace.fedramp.gov",
    "cloudsecurityalliance.org",
    "hitrustalliance.net",
    # Certification body portals
    "schellman.com",
    "coalfire.com",
    "a-lign.com",
    "kpmg.com",
    "deloitte.com",
    "ey.com",
    "pwc.com",
    "bsigroup.com",
    "dnv.com",
]

# TUV domains use wildcard pattern
AUTHORITATIVE_DOMAIN_PATTERNS = [
    r"tuv.*\.com",
    r"tuv.*\.de",
]

# Aggregator domains (low reliability)
AGGREGATOR_DOMAINS = [
    "nudgesecurity.com",
    "securityscorecard.com",
    "safetydetectives.com",
    "g2.com",
    "capterra.com",
]

# Inherited compliance filter patterns (per plan §Step 3)
INHERITED_PATTERNS = [
    "inherited",
    "aws compliance",
    "gcp compliance",
    "azure compliance",
    "cloud provider",
]

# Filtered key patterns (per plan §Step 3)
FILTERED_KEY_PATTERNS = [
    "infrastructure",
    "cloud_provider",
]


# =============================================================================
# NORMALIZATION INDEX
# =============================================================================

_programs_index_cache: Optional[Dict] = None


def load_programs_index() -> Dict:
    """
    Load assurance_programs.json and build lookup structures.
    Returns dict with:
        - alias_to_program: {lowercase_alias: program_id}
        - program_meta: {program_id: {canonical_name, levels, assurance_type}}
    """
    global _programs_index_cache
    
    if _programs_index_cache is not None:
        return _programs_index_cache
    
    try:
        with open(PROGRAMS_JSON_PATH, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        # Return empty index if file not found - don't crash
        return {"alias_to_program": {}, "program_meta": {}}
    
    alias_to_program = {}
    program_meta = {}
    
    for program in data.get("programs", []):
        program_id = program.get("id")
        if not program_id:
            continue
        
        canonical_name = program.get("canonical_name", program_id)
        
        program_meta[program_id] = {
            "canonical_name": canonical_name,
            "levels": program.get("levels", []),
            "assurance_type": program.get("assurance_type"),
        }
        
        # Index all aliases (lowercase)
        for alias in program.get("aliases", []):
            alias_to_program[alias.lower()] = program_id
        
        # Also index canonical name
        alias_to_program[canonical_name.lower()] = program_id
        
        # Index level aliases
        for level in program.get("levels", []):
            for level_alias in level.get("aliases", []):
                alias_to_program[level_alias.lower()] = program_id
    
    _programs_index_cache = {
        "alias_to_program": alias_to_program,
        "program_meta": program_meta,
    }
    
    return _programs_index_cache


# =============================================================================
# FILTERING (Plan §Step 3)
# =============================================================================

def is_filtered(key: str, fact: Dict) -> bool:
    """
    Check if a fact should be filtered out.
    Returns True if fact should be skipped.
    """
    key_lower = key.lower()
    value = fact.get("value", "")
    value_lower = value.lower() if value else ""
    source = fact.get("source", "")
    
    # Skip if no value
    if not value:
        return True
    
    # Skip if no source (no attribution possible)
    if not source:
        return True
    
    # Skip infrastructure/cloud_provider keys
    for pattern in FILTERED_KEY_PATTERNS:
        if pattern in key_lower:
            return True
    
    # Skip inherited compliance values
    for pattern in INHERITED_PATTERNS:
        if pattern in value_lower:
            return True
    
    return False


# =============================================================================
# NORMALIZATION (Plan §Step 4)
# =============================================================================

def normalize_to_program(key: str, value: str, index: Dict) -> Tuple[Optional[str], Optional[str]]:
    """
    Attempt to normalize a fact key/value to a program_id.
    Returns (program_id, level) or (None, None) if no match.
    """
    alias_map = index.get("alias_to_program", {})
    
    key_lower = key.lower().replace("_", " ")
    value_lower = value.lower() if value else ""
    
    program_id = None
    
    # Try key-based matching first
    for alias, pid in alias_map.items():
        if alias in key_lower:
            program_id = pid
            break
    
    # Then try value-based matching
    if not program_id:
        for alias, pid in alias_map.items():
            if alias in value_lower:
                program_id = pid
                break
    
    if not program_id:
        return None, None
    
    # Extract level from value
    level = extract_level(value_lower, program_id, index)
    
    return program_id, level


def extract_level(value_lower: str, program_id: str, index: Dict) -> Optional[str]:
    """Extract certification level from value text."""
    program_meta = index.get("program_meta", {}).get(program_id, {})
    levels = program_meta.get("levels", [])
    
    # Check for level aliases in value
    for level_def in levels:
        level_name = level_def.get("name")
        for level_alias in level_def.get("aliases", []):
            if level_alias.lower() in value_lower:
                return level_name
    
    # Fallback: check for common patterns
    if "type ii" in value_lower or "type 2" in value_lower:
        return "Type II"
    if "type i" in value_lower or "type 1" in value_lower:
        # Avoid matching "type ii" as "type i"
        if "type ii" not in value_lower and "type 2" not in value_lower:
            return "Type I"
    if "level 2" in value_lower:
        return "Level 2"
    if "level 1" in value_lower:
        return "Level 1"
    
    return None


# =============================================================================
# EVIDENCE KIND CLASSIFICATION (Plan §Step 5)
# =============================================================================

# Patterns ordered by specificity (first match wins)
EVIDENCE_PATTERNS = [
    # registry_listing
    (["registry", "marketplace", "listed on", "appears in"], "registry_listing"),
    # attestation_statement - Block 3.3: Tightened to require specific phrases
    (["soc 2 report", "type ii report", "type 2 report", "independent auditor", 
      "attestation report", "download report", "report available", "audit report",
      "audited by", "audit completed"], "attestation_statement"),
    # explicit_cert_statement (requires possession/completion language)
    (["is certified", "has completed", "achieved certification", "holds certification", 
      "certification available", "certified with", "attained"], "explicit_cert_statement"),
    # policy_statement
    (["alignment", "aligned", "follows", "adheres to", "compliant"], "policy_statement"),
    # marketing_claim
    (["enterprise-grade", "robust security", "industry-leading", "best-in-class"], "marketing_claim"),
]


def classify_evidence(value: str) -> str:
    """
    Classify evidence_kind based on value text.
    Default: policy_statement (conservative per plan)
    """
    value_lower = value.lower() if value else ""
    
    for patterns, evidence_kind in EVIDENCE_PATTERNS:
        for pattern in patterns:
            if pattern in value_lower:
                return evidence_kind
    
    # Conservative default per plan §Step 5
    return "policy_statement"


# =============================================================================
# SOURCE TYPE HELPERS
# =============================================================================

def get_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except:
        return ""


def is_authoritative_domain(url: str) -> bool:
    """Check if URL domain is a known auditor/registry."""
    domain = get_domain(url)
    
    # Check exact matches
    for auth_domain in AUTHORITATIVE_DOMAINS:
        if auth_domain in domain:
            return True
    
    # Check patterns (e.g., tuv*.com)
    for pattern in AUTHORITATIVE_DOMAIN_PATTERNS:
        if re.search(pattern, domain):
            return True
    
    return False


def is_aggregator_domain(url: str) -> bool:
    """Check if URL domain is a known aggregator."""
    domain = get_domain(url)
    for agg_domain in AGGREGATOR_DOMAINS:
        if agg_domain in domain:
            return True
    return False


# =============================================================================
# SOURCE TYPE CLASSIFICATION (Block 3.4 - Deterministic URL-based)
# =============================================================================

def classify_source_type_from_url(url: str, vendor_name: str) -> str:
    """
    Deterministically classify source_type from URL domain.
    
    Block 3.4: This is the authoritative source_type classifier.
    The source_type from structured_data is ADVISORY ONLY and may be wrong.
    
    Priority order:
    1. If domain matches vendor name -> "vendor"
    2. If domain is in AUTHORITATIVE_DOMAINS -> "auditor"
    3. If domain is in AGGREGATOR_DOMAINS -> "aggregator"
    4. Otherwise -> "third_party"
    """
    domain = get_domain(url)
    if not domain:
        return "third_party"
    
    # Normalize vendor name for matching
    vendor_lower = vendor_name.lower().replace(" ", "").replace("-", "").replace("_", "")
    domain_lower = domain.lower()
    
    # Check vendor domain (most specific first)
    # Handle subdomains like trust.tabnine.com, docs.tabnine.com
    domain_parts = domain_lower.split(".")
    for part in domain_parts:
        if vendor_lower in part or part in vendor_lower:
            if len(part) >= 4:  # Avoid false positives on short strings
                return "vendor"
    
    # Also check if vendor name appears anywhere in domain
    if vendor_lower in domain_lower:
        return "vendor"
    
    # Check authoritative domains
    if is_authoritative_domain(url):
        return "auditor"
    
    # Check aggregator domains
    if is_aggregator_domain(url):
        return "aggregator"
    
    return "third_party"


# Inline self-check for source classification
def _self_check_source_classification():
    """
    Block 3.4: Inline test proving vendor URL classification works.
    This runs at module load to catch regressions.
    """
    test_cases = [
        ("https://www.tabnine.com/security", "Tabnine", "vendor"),
        ("https://trust.tabnine.com/", "Tabnine", "vendor"),
        ("https://docs.tabnine.com/main/welcome", "Tabnine", "vendor"),
        ("https://www.augmentcode.com/review", "Tabnine", "third_party"),
        ("https://www.nudgesecurity.com/profile", "Tabnine", "aggregator"),
        ("https://marketplace.fedramp.gov/listing", "Tabnine", "auditor"),
        ("https://cloudsecurityalliance.org/star/registry", "Tabnine", "auditor"),
    ]
    
    for url, vendor, expected in test_cases:
        result = classify_source_type_from_url(url, vendor)
        if result != expected:
            raise AssertionError(
                f"Source classification failed: {url} for {vendor} "
                f"expected {expected}, got {result}"
            )
    
    return True


# Run self-check at module load (comment out in production if needed)
try:
    _self_check_source_classification()
except AssertionError as e:
    import warnings
    warnings.warn(f"Assurance emitter self-check failed: {e}")


# =============================================================================
# HARD SUPPRESSION FOR HIGH-RISK PROGRAMS (Block 3.4)
# =============================================================================

# Programs that require authoritative evidence to reach "verified" status
# Without authoritative evidence, these can only be "claimed" with caveat
HIGH_RISK_PROGRAMS = [
    "FEDRAMP",
    "PCI_DSS", 
    "CSA_STAR",
    "HITRUST_CSF",
    "CMMC",
    "STATE_RAMP",
]

# Sources that indicate inherited/generic compliance (not vendor-specific)
INHERITED_SOURCE_INDICATORS = [
    "aws compliance",
    "gcp compliance",
    "azure compliance",
    "cloud provider",
    "inherited",
    "hosting provider",
]


def is_inherited_or_aggregator_only(sources: List[Dict], values: List[str]) -> bool:
    """
    Check if all sources are either inherited compliance or aggregator-only.
    
    Block 3.4: These sources cannot support "confirmed" certification status.
    """
    if not sources:
        return True
    
    # Check values for inherited language
    for value in values:
        value_lower = value.lower() if value else ""
        for indicator in INHERITED_SOURCE_INDICATORS:
            if indicator in value_lower:
                return True
    
    # Check if all sources are aggregator
    all_aggregator = all(
        s.get("source_type") == "aggregator" or is_aggregator_domain(s.get("url", ""))
        for s in sources
    )
    
    return all_aggregator


def check_high_risk_suppression(program_id: str, sources: List[Dict], values: List[str]) -> Tuple[bool, Optional[str]]:
    """
    Check if a high-risk program should have its status downgraded.
    
    Block 3.4: High-risk programs (FedRAMP, PCI DSS, CSA STAR, etc.) cannot
    reach "verified" status without authoritative evidence from non-vendor,
    non-aggregator sources.
    
    Returns: (should_downgrade, note_to_add)
    """
    if program_id not in HIGH_RISK_PROGRAMS:
        return False, None
    
    # Check if sources are inherited/aggregator only
    is_inherited = is_inherited_or_aggregator_only(sources, values)
    
    if is_inherited:
        return True, "Third-party listing only; no authoritative evidence."
    
    # Check if we have any authoritative evidence
    has_authoritative = has_authoritative_evidence(sources)
    
    if not has_authoritative:
        return True, "Mentioned in sources; authoritative evidence not found."
    
    return False, None


def map_source_type(source_type_from_data: str, url: str, vendor_name: str = "") -> str:
    """
    Map source_type from structured_data to contract enum.
    
    Block 3.4: If vendor_name is provided, use deterministic URL-based classification.
    The source_type_from_data is ADVISORY ONLY and may be incorrect.
    """
    # If vendor_name provided, use deterministic classification
    if vendor_name:
        return classify_source_type_from_url(url, vendor_name)
    
    # Fallback to advisory-based classification (legacy behavior)
    st = source_type_from_data.lower() if source_type_from_data else "third_party"
    
    # Normalize to contract values
    if st in ["vendor", "auditor", "third_party", "aggregator"]:
        # Check if domain suggests aggregator
        if is_aggregator_domain(url):
            return "aggregator"
        return st
    
    return "third_party"


# =============================================================================
# STATUS RESOLUTION (Plan §Step 6 - Rule-Based)
# =============================================================================

# Denial patterns
DENIAL_PATTERNS = [
    "does not hold",
    "is not certified",
    "refused",
    "no longer certified",
    "certification lapsed",
    "does not offer",
    "not available",
    "will not sign",
    "no baa",
]

# Assertion patterns (for conflicting detection)
ASSERTION_PATTERNS = [
    "certified",
    "compliant",
    "completed",
    "achieved",
    "holds",
    "offers",
    "available",
]


def has_denial(values: List[str]) -> bool:
    """Check if any value contains denial language."""
    for value in values:
        value_lower = value.lower() if value else ""
        for pattern in DENIAL_PATTERNS:
            if pattern in value_lower:
                return True
    return False


def has_assertion(values: List[str]) -> bool:
    """Check if any value contains assertion language."""
    for value in values:
        value_lower = value.lower() if value else ""
        for pattern in ASSERTION_PATTERNS:
            if pattern in value_lower:
                return True
    return False


def has_authoritative_verification(sources: List[Dict]) -> bool:
    """
    Check if any source qualifies as authoritative verification.
    Requires: evidence_kind in {registry_listing, attestation_statement}
              AND source URL from known auditor/registry domain
    """
    for source in sources:
        evidence_kind = source.get("evidence_kind", "")
        url = source.get("url", "")
        
        if evidence_kind in ["registry_listing", "attestation_statement"]:
            if is_authoritative_domain(url):
                return True
    
    return False


def resolve_status(sources: List[Dict], values: List[str], trust_portal_blocked: bool) -> str:
    """
    Rule-based status resolution per plan §Step 6.
    Order matters - first matching rule wins.
    """
    # Rule 1: Explicit denial
    if has_denial(values):
        # Check if this is the ONLY signal (pure denial)
        if not has_assertion(values):
            return "denied"
        # If both denial and assertion exist, it's conflicting
        return "conflicting"
    
    # Rule 2: Conflicting (assertion + denial already handled above)
    # Additional check: different sources with contradictory claims
    # For now, we only detect explicit denial + assertion conflict
    
    # Rule 3: Verified
    if has_authoritative_verification(sources):
        return "verified"
    
    # Rule 4: Evidence gated
    if trust_portal_blocked and has_assertion(values):
        return "evidence_gated"
    
    # Rule 5: Default to claimed
    return "claimed"


# =============================================================================
# CONFIDENCE DETERMINATION (Plan §Step 7)
# =============================================================================

def has_authoritative_evidence(sources: List[Dict]) -> bool:
    """
    Check if any source qualifies as authoritative evidence.
    Block 3.2: Required for "high" confidence.
    Block 3.3: Vendor sources cannot self-upgrade to authoritative.
    
    Authoritative if:
    - source domain matches AUTHORITATIVE_DOMAINS, OR
    - evidence_kind is registry_listing or attestation_statement AND source is NOT vendor-domain
    """
    for source in sources:
        evidence_kind = source.get("evidence_kind", "")
        url = source.get("url", "")
        
        # Check domain first - authoritative domains always count
        if is_authoritative_domain(url):
            return True
        
        # Block 3.3: For evidence_kind upgrade, must NOT be vendor domain
        # We check this by looking for common vendor patterns
        # Note: We don't have vendor_name here, so we check source_type
        source_type = source.get("source_type", "")
        is_vendor_source = source_type == "vendor"
        
        if evidence_kind in ["registry_listing", "attestation_statement"]:
            if not is_vendor_source:
                return True
    
    return False


def determine_confidence(sources: List[Dict]) -> str:
    """
    Deterministic confidence based on source count and diversity.
    No math - rule-based per plan.
    
    Block 3.2: Confidence capped at "medium" unless authoritative evidence exists.
    """
    if not sources:
        return "low"
    
    # Check for all-marketing override
    all_marketing = all(s.get("evidence_kind") == "marketing_claim" for s in sources)
    if all_marketing:
        return "low"
    
    # Check for all-aggregator
    all_aggregator = all(is_aggregator_domain(s.get("url", "")) for s in sources)
    if all_aggregator:
        return "low"
    
    # Count unique domains
    domains = set()
    for source in sources:
        domain = get_domain(source.get("url", ""))
        if domain:
            # Use root domain for comparison
            parts = domain.split(".")
            if len(parts) >= 2:
                root = ".".join(parts[-2:])
                domains.add(root)
            else:
                domains.add(domain)
    
    # Block 3.2: Check for authoritative evidence cap
    has_authoritative = has_authoritative_evidence(sources)
    
    # Apply rules
    if len(sources) >= 3 and len(domains) >= 2:
        # Block 3.2: Cap at medium if no authoritative evidence
        if has_authoritative:
            return "high"
        else:
            return "medium"
    elif len(sources) >= 2 and len(domains) >= 2:
        return "medium"
    else:
        return "low"


# =============================================================================
# NOTES BUILDER
# =============================================================================

def build_notes(status: str, values: List[str], sources: List[Dict]) -> Optional[str]:
    """Build explanatory notes when status requires context."""
    if status == "denied":
        return "Vendor explicitly does not offer this assurance."
    
    if status == "conflicting":
        return "Sources disagree on certification status."
    
    if status == "evidence_gated":
        return "Vendor trust portal gated; status based on indirect evidence."
    
    if status == "claimed":
        # Check if we have vendor source but no third-party
        vendor_sources = [s for s in sources if s.get("source_type") == "vendor"]
        non_vendor_sources = [s for s in sources if s.get("source_type") != "vendor"]
        
        if vendor_sources and not non_vendor_sources:
            return "Single vendor source; no third-party corroboration found."
        
        # Check for "not published" language
        for value in values:
            if value and ("not publish" in value.lower() or "not verified" in value.lower()):
                return "Vendor claims certification; public evidence not available."
    
    return None


# =============================================================================
# LEVEL RESOLUTION
# =============================================================================

def resolve_level(levels: List[Optional[str]]) -> Optional[str]:
    """
    Resolve final level from multiple sources.
    If sources disagree, return None.
    """
    unique_levels = set(l for l in levels if l is not None)
    
    if len(unique_levels) == 0:
        return None
    elif len(unique_levels) == 1:
        return unique_levels.pop()
    else:
        # Disagreement - return None
        return None


# =============================================================================
# EVIDENCE KEY HARVESTING (Block 3.1 Additive)
# =============================================================================

# Special evidence keys that provide cross-program meta-evidence
EVIDENCE_META_KEYS = [
    "public_certifications_evidence",
    "third_party_verification",
    "soc2_evidence_availability",
    "certification_publishing_status",
]

# Keys ending with these suffixes contain third-party claims
THIRD_PARTY_CLAIM_SUFFIXES = [
    "_third_party_claim",
]


def extract_evidence_sources(
    certification_data: Dict,
    compliance_data: Dict,
    program_id: str,
    index: Dict,
    vendor_name: str = ""
) -> List[Dict]:
    """
    Extract additional evidence sources from meta-evidence keys.
    Returns list of source entries for the given program_id.
    
    This is ADDITIVE - it supplements sources found in primary keys.
    Block 3.4: Added vendor_name for deterministic source_type classification.
    """
    additional_sources = []
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    # Get program aliases for matching
    program_meta = index.get("program_meta", {}).get(program_id, {})
    canonical_name = program_meta.get("canonical_name", program_id).lower()
    
    # Build list of terms to match for this program
    match_terms = [program_id.lower().replace("_", " "), canonical_name]
    alias_map = index.get("alias_to_program", {})
    for alias, pid in alias_map.items():
        if pid == program_id:
            match_terms.append(alias.lower())
    
    # Check all certification keys for meta-evidence
    for key, fact in certification_data.items():
        if not isinstance(fact, dict):
            continue
        
        value = fact.get("value", "")
        source_url = fact.get("source", "")
        source_type_raw = fact.get("source_type", "third_party")
        
        if not value or not source_url:
            continue
        
        key_lower = key.lower()
        value_lower = value.lower()
        
        # Check if this is a meta-evidence key
        is_meta_key = key_lower in EVIDENCE_META_KEYS
        is_third_party_claim = any(key_lower.endswith(suffix) for suffix in THIRD_PARTY_CLAIM_SUFFIXES)
        
        if not is_meta_key and not is_third_party_claim:
            continue
        
        # Check if this evidence relates to our program
        relates_to_program = False
        for term in match_terms:
            if term in key_lower or term in value_lower:
                relates_to_program = True
                break
        
        # For broad meta-evidence keys, check value content
        if is_meta_key and not relates_to_program:
            # Keys like public_certifications_evidence may mention multiple programs
            if any(t in value_lower for t in match_terms):
                relates_to_program = True
        
        if not relates_to_program:
            continue
        
        # Determine evidence_kind based on key type and value content
        if is_third_party_claim:
            evidence_kind = "third_party_summary"
        elif "not found" in value_lower or "not surfaced" in value_lower or "not publish" in value_lower:
            evidence_kind = "third_party_summary"  # Negative evidence
        elif "verified" in value_lower or "confirm" in value_lower:
            evidence_kind = "attestation_statement"
        else:
            evidence_kind = "third_party_summary"
        
        additional_sources.append({
            "url": source_url,
            "source_type": map_source_type(source_type_raw, source_url, vendor_name),
            "evidence_kind": evidence_kind,
            "retrieved_at": timestamp,
            "excerpt": value[:300] if value else None,
        })
    
    return additional_sources


def is_vendor_domain(url: str, vendor_name: str) -> bool:
    """Check if URL domain appears to be vendor-owned."""
    domain = get_domain(url)
    vendor_lower = vendor_name.lower().replace(" ", "")
    return vendor_lower in domain


# =============================================================================
# BLOCKED ACCESS DETECTION (Plan §Step 9)
# =============================================================================

BLOCKED_ACCESS_PATTERNS = [
    ("safebase", "safebase"),
    ("restricted", "other"),
    ("gated", "other"),
    ("access blocked", "other"),
    ("nda required", "auth_wall"),
    ("authentication required", "auth_wall"),
    ("login required", "auth_wall"),
]


def extract_blocked_access(
    vendor_name: str,
    synthesized_report: Optional[str],
    crawl_events: Optional[List[Dict]] = None
) -> List[Dict]:
    """
    Extract blocked_access entries.
    - From crawl_events if provided (future)
    - From synthesized_report heuristics (interim)
    
    This function NEVER creates assurance_findings.
    """
    blocked = []
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    # Future: Use crawl_events if provided
    if crawl_events:
        for event in crawl_events:
            if event.get("blocked"):
                blocked.append({
                    "url": event.get("url", ""),
                    "blocker_type": event.get("blocker_type", "other"),
                    "context": event.get("context", "vendor resource"),
                    "detected_at": event.get("detected_at", timestamp),
                })
    
    # Interim: Parse synthesized_report for blocked-access indicators
    if synthesized_report and not blocked:
        report_lower = synthesized_report.lower()
        vendor_lower = vendor_name.lower().replace(" ", "")
        
        # Look for trust portal mentions with blocking indicators
        trust_patterns = [
            f"trust.{vendor_lower}",
            f"security.{vendor_lower}",
            "trust center",
            "trust portal",
        ]
        
        for trust_pattern in trust_patterns:
            if trust_pattern in report_lower:
                # Check for blocking indicators
                for block_pattern, blocker_type in BLOCKED_ACCESS_PATTERNS:
                    if block_pattern in report_lower:
                        # Extract URL if possible (simplified)
                        url = f"https://trust.{vendor_lower}.com/"
                        
                        blocked.append({
                            "url": url,
                            "blocker_type": blocker_type,
                            "context": "vendor trust portal",
                            "detected_at": timestamp,
                        })
                        break
                break
    
    return blocked


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def build_assurance_section(
    vendor_name: str,
    product_name: str,
    structured_data: Dict,
    synthesized_report: Optional[str] = None,
    crawl_events: Optional[List[Dict]] = None,
) -> Dict:
    """
    Build the v3 assurance section from structured_data.
    
    Returns:
        {
            "assurance_findings": [...],
            "blocked_access": [...]
        }
    
    This function is ADDITIVE ONLY. It does not modify any inputs.
    It does not create findings from synthesized_report (only blocked_access).
    """
    # Load normalization index
    index = load_programs_index()
    
    # Get research timestamp for source entries
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    # Extract blocked_access first (needed for evidence_gated status)
    blocked_access = extract_blocked_access(vendor_name, synthesized_report, crawl_events)
    trust_portal_blocked = len(blocked_access) > 0
    
    # Pre-extract section data for evidence harvesting
    certification_data = structured_data.get("certification", {})
    compliance_data = structured_data.get("compliance", {})
    
    # Collect findings by program
    findings_by_program: Dict[str, Dict] = {}
    
    # Process certification and compliance sections
    for section in ["certification", "compliance"]:
        section_data = structured_data.get(section, {})
        if not isinstance(section_data, dict):
            continue
        
        for key, fact in section_data.items():
            if not isinstance(fact, dict):
                continue
            
            # Step 3: Filter
            if is_filtered(key, fact):
                continue
            
            value = fact.get("value", "")
            source_url = fact.get("source", "")
            source_type_raw = fact.get("source_type", "third_party")
            
            # Step 4: Normalize to program
            program_id, level = normalize_to_program(key, value, index)
            if not program_id:
                continue
            
            # Get canonical name
            program_meta = index.get("program_meta", {}).get(program_id, {})
            program_name = program_meta.get("canonical_name", program_id)
            
            # Step 5: Classify evidence
            evidence_kind = classify_evidence(value)
            
            # Build source entry (only if we have a URL)
            # Block 3.4: Pass vendor_name for deterministic source_type classification
            if source_url:
                source_entry = {
                    "url": source_url,
                    "source_type": map_source_type(source_type_raw, source_url, vendor_name),
                    "evidence_kind": evidence_kind,
                    "retrieved_at": timestamp,
                    "excerpt": value[:300] if value else None,
                }
            else:
                source_entry = None
            
            # Aggregate by program
            if program_id not in findings_by_program:
                findings_by_program[program_id] = {
                    "program_id": program_id,
                    "program_name": program_name,
                    "levels": [],
                    "sources": [],
                    "values": [],
                }
            
            if source_entry:
                findings_by_program[program_id]["sources"].append(source_entry)
            findings_by_program[program_id]["values"].append(value)
            if level:
                findings_by_program[program_id]["levels"].append(level)
    
    # Block 3.1: Harvest additional evidence from meta-evidence keys
    # Block 3.4: Pass vendor_name for deterministic source_type classification
    for program_id, data in findings_by_program.items():
        additional_sources = extract_evidence_sources(
            certification_data,
            compliance_data,
            program_id,
            index,
            vendor_name
        )
        # Deduplicate by URL before adding
        existing_urls = {s.get("url") for s in data["sources"]}
        for src in additional_sources:
            if src.get("url") not in existing_urls:
                data["sources"].append(src)
                existing_urls.add(src.get("url"))
    
    # Build final findings list
    assurance_findings = []
    
    for program_id, data in findings_by_program.items():
        sources = data["sources"]
        values = data["values"]
        
        # Block 3.1: Only emit if at least 1 source exists
        if not sources:
            continue
        
        # Check if we have third-party sources (for evidence_gated logic)
        has_third_party = any(
            s.get("source_type") in ["third_party", "aggregator"] or
            not is_vendor_domain(s.get("url", ""), vendor_name)
            for s in sources
        )
        
        # Block 3.2: Check if vendor-only (no third-party domains)
        vendor_only = not has_third_party
        
        # Step 6: Status resolution (rule-based)
        status = resolve_status(sources, values, trust_portal_blocked)
        
        # Block 3.2: HIPAA cannot be "verified" without authoritative evidence
        if program_id == "HIPAA" and status == "verified":
            if not has_authoritative_evidence(sources):
                status = "claimed"
        
        # Block 3.4: High-risk program suppression
        # FedRAMP, PCI DSS, CSA STAR etc. cannot reach verified/claimed without
        # authoritative evidence from non-vendor, non-aggregator sources
        should_suppress, suppression_note = check_high_risk_suppression(program_id, sources, values)
        if should_suppress:
            # Downgrade status to claimed (never verified) and add note
            if status == "verified":
                status = "claimed"
            # Additional note will be added later
        
        # Block 3.1: If trust portal blocked and has third-party sources,
        # prefer evidence_gated over claimed
        # Block 3.2: But NOT if vendor-only - keep as claimed with note
        if trust_portal_blocked and has_third_party and status == "claimed":
            status = "evidence_gated"
        
        # Step 7: Confidence
        confidence = determine_confidence(sources)
        
        # Resolve level
        level = resolve_level(data["levels"])
        
        # Build notes
        notes = build_notes(status, values, sources)
        
        # Block 3.2: HIPAA-specific note
        if program_id == "HIPAA":
            hipaa_note = "HIPAA is not a cert; this reflects alignment/claims, not certification."
            if notes:
                notes = notes + " " + hipaa_note
            else:
                notes = hipaa_note
        
        # Block 3.2: Vendor-only claim with trust portal blocked
        if trust_portal_blocked and vendor_only and status == "claimed":
            vendor_only_note = "Vendor-only claim; trust portal blocked prevents direct verification."
            if notes:
                notes = notes + " " + vendor_only_note
            else:
                notes = vendor_only_note
        
        # Block 3.1: Add trust portal blocked note if evidence_gated
        if status == "evidence_gated" and trust_portal_blocked:
            if notes:
                notes = notes + " Trust portal access blocked."
            else:
                notes = "Trust portal access blocked; status based on indirect evidence."
        
        # Block 3.4: Add high-risk suppression note
        if should_suppress and suppression_note:
            if notes:
                notes = notes + " " + suppression_note
            else:
                notes = suppression_note
        
        finding = {
            "program_id": program_id,
            "program_name": data["program_name"],
            "level": level,
            "status": status,
            "confidence": confidence,
            "sources": sources,
        }
        
        if notes:
            finding["notes"] = notes
        
        assurance_findings.append(finding)
    
    return {
        "assurance_findings": assurance_findings,
        "blocked_access": blocked_access,
    }


# =============================================================================
# NARRATIVE POST-PROCESSING (Block 3.4 - Certification Gating)
# =============================================================================

# Patterns that indicate "confirmed" certification language to rewrite
CONFIRMED_PATTERNS = [
    "Confirmed Certifications",
    "Confirmed certifications",
    "confirmed certifications",
    "Verified Certifications",
    "Verified certifications",
    "Active Certifications",
    "Current Certifications",
]

# Programs to scan for in narrative
NARRATIVE_PROGRAM_PATTERNS = [
    ("fedramp", "FEDRAMP"),
    ("fed-ramp", "FEDRAMP"),
    ("pci dss", "PCI_DSS"),
    ("pci-dss", "PCI_DSS"),
    ("pcidss", "PCI_DSS"),
    ("csa star", "CSA_STAR"),
    ("csa-star", "CSA_STAR"),
    ("cloud security alliance", "CSA_STAR"),
    ("hitrust", "HITRUST_CSF"),
    ("soc 2", "SOC_2"),
    ("soc2", "SOC_2"),
    ("soc 1", "SOC_1"),
    ("iso 27001", "ISO_IEC_27001"),
    ("iso27001", "ISO_IEC_27001"),
    ("iso 9001", "ISO_9001"),
    ("gdpr", "GDPR"),
    ("hipaa", "HIPAA"),
    ("ccpa", "CCPA"),
    ("cmmc", "CMMC"),
    ("stateramp", "STATE_RAMP"),
    ("state-ramp", "STATE_RAMP"),
]


def extract_programs_from_narrative(narrative: str) -> List[str]:
    """
    Extract program IDs mentioned in the narrative.
    Returns list of program_ids found.
    """
    found = set()
    narrative_lower = narrative.lower()
    
    for pattern, program_id in NARRATIVE_PROGRAM_PATTERNS:
        if pattern in narrative_lower:
            found.add(program_id)
    
    return list(found)


def post_process_narrative(
    synthesized_report: str,
    assurance_findings: List[Dict]
) -> str:
    """
    Post-process the synthesized narrative to enforce certification gating.
    
    Block 3.4: This function rewrites the narrative to:
    1. Replace "Confirmed Certifications" with "Evidence-based Findings"
    2. Add "Mentioned by third parties (unverified)" section for programs
       mentioned in narrative but not in assurance_findings
    
    This is ADDITIVE - it does not remove content, only relabels and reorganizes.
    """
    if not synthesized_report:
        return synthesized_report
    
    result = synthesized_report
    
    # Get set of program_ids in assurance_findings
    verified_programs = {f.get("program_id") for f in assurance_findings}
    
    # Extract programs mentioned in narrative
    mentioned_programs = extract_programs_from_narrative(synthesized_report)
    
    # Find programs mentioned but not verified
    unverified_programs = [p for p in mentioned_programs if p not in verified_programs]
    
    # Replace "Confirmed Certifications" headers
    for pattern in CONFIRMED_PATTERNS:
        if pattern in result:
            result = result.replace(pattern, "Evidence-based Findings")
    
    # If there are unverified programs, add a note section
    if unverified_programs:
        # Build the unverified section
        unverified_section = "\n\n### Mentioned by Third Parties (Unverified)\n"
        unverified_section += "The following frameworks were mentioned in third-party sources but lack authoritative evidence:\n"
        for pid in sorted(unverified_programs):
            # Get canonical name from index
            index = load_programs_index()
            program_meta = index.get("program_meta", {}).get(pid, {})
            canonical_name = program_meta.get("canonical_name", pid.replace("_", " "))
            unverified_section += f"- {canonical_name}\n"
        
        # Find where to insert - after Security Certifications section if it exists
        cert_section_markers = [
            "## Security Certifications",
            "### Security Certifications",
            "## Certifications",
            "### Certifications",
        ]
        
        inserted = False
        for marker in cert_section_markers:
            if marker in result:
                # Find the next section header or end of text
                marker_pos = result.find(marker)
                search_start = marker_pos + len(marker)
                next_section = result.find("\n##", search_start)
                
                if next_section == -1:
                    # No next section, append at end
                    result = result + unverified_section
                else:
                    # Insert before next section
                    result = result[:next_section] + unverified_section + result[next_section:]
                
                inserted = True
                break
        
        if not inserted:
            # No certification section found, append at end
            result = result + unverified_section
    
    return result


# =============================================================================
# INLINE TEST EXAMPLES (per task requirements)
# =============================================================================

"""
EXAMPLE 1: SOC 2 Claimed (Happy Path)
-------------------------------------
Input structured_data:
{
    "certification": {
        "soc2_status": {
            "value": "SOC 2 Type 2 compliant",
            "source": "https://www.tabnine.com/security",
            "source_type": "vendor"
        }
    }
}

Expected output:
{
    "assurance_findings": [
        {
            "program_id": "SOC_2",
            "program_name": "SOC 2",
            "level": "Type II",
            "status": "claimed",
            "confidence": "low",
            "sources": [{...}],
            "notes": "Single vendor source; no third-party corroboration found."
        }
    ],
    "blocked_access": []
}


EXAMPLE 2: Blocked Access (SafeBase)
------------------------------------
Input synthesized_report contains:
"Trust center lists SOC 2 but attestation access appears restricted via SafeBase"

Expected output includes:
{
    "blocked_access": [
        {
            "url": "https://trust.tabnine.com/",
            "blocker_type": "safebase",
            "context": "vendor trust portal",
            "detected_at": "..."
        }
    ]
}


EXAMPLE 3: Conflicting
----------------------
Input structured_data:
{
    "certification": {
        "soc2_claimed": {
            "value": "SOC 2 Type II certified",
            "source": "https://vendor.com/security",
            "source_type": "vendor"
        },
        "soc2_denied": {
            "value": "Vendor does not hold SOC 2 certification",
            "source": "https://thirdparty.com/review",
            "source_type": "third_party"
        }
    }
}

Expected status: "conflicting"
Expected notes: "Sources disagree on certification status."


EXAMPLE 4: Denied (BAA Refusal)
-------------------------------
Input structured_data:
{
    "certification": {
        "hipaa_baa": {
            "value": "Vendor will not sign a BAA",
            "source": "https://vendor.com/compliance",
            "source_type": "vendor"
        }
    }
}

Expected:
{
    "program_id": "BAA",
    "program_name": "Business Associate Agreement",
    "status": "denied",
    "notes": "Vendor explicitly does not offer this assurance."
}
"""
