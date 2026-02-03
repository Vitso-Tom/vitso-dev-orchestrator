"""
Candidate Authority Module - Heuristic identification of vendor-authoritative URLs

This module identifies URLs that LOOK LIKE authoritative vendor sources
(trust centers, security pages, docs) based on URL structure patterns.

CRITICAL DISTINCTION:
- source_type (from source_classifier.py): DETERMINISTIC, registry-based, authoritative
- candidate_status (from this module): HEURISTIC, pattern-based, requires confirmation

A URL can be:
- source_type="third_party" AND is_candidate=True
  → "Treat as third-party, but flag for potential registry addition"

This module NEVER affects source_type. It only provides signals for workflow.

DESIGN PRINCIPLES:
1. Pure functions - no network, no LLM, no database, no side effects
2. Pattern-based heuristics - subdomain and path analysis
3. Does NOT use vendor name substring matching for identification
4. All candidates require confirmation before registry addition
5. Fully testable offline

USAGE:
    from candidate_authority import analyze_candidate, CandidateType
    
    result = analyze_candidate("https://trust.example.com/compliance")
    if result.is_candidate:
        print(f"Candidate {result.candidate_type.value} with confidence {result.confidence}")
"""

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse
from enum import Enum

# Reuse normalize_domain from source_classifier for consistency
from source_classifier import normalize_domain


class CandidateType(Enum):
    """
    Types of candidate authoritative vendor pages.
    
    Maps to VendorRegistry URL fields:
    - TRUST_CENTER → trust_center_url
    - SECURITY_PAGE → security_page_url
    - PRIVACY_PAGE → privacy_page_url
    - DOCS → docs_url
    - STATUS_PAGE → (not promotable - excluded from get_all_urls)
    - PRICING_PAGE → pricing_page_url
    """
    TRUST_CENTER = "trust_center"
    SECURITY_PAGE = "security_page"
    PRIVACY_PAGE = "privacy_page"
    PRICING_PAGE = "pricing_page"
    DOCS = "docs"
    STATUS_PAGE = "status_page"
    UNKNOWN = "unknown"


class CandidateStatus(Enum):
    """
    Status of a candidate vendor URL in the confirmation workflow.
    
    State transitions:
    - PENDING: Newly identified, awaiting review
    - CONFIRMED: Reviewed and confirmed as authoritative
    - REJECTED: Reviewed and rejected as non-authoritative
    - PROMOTED: Added to VendorRegistry
    """
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    PROMOTED = "promoted"


@dataclass(frozen=True)
class CandidateResult:
    """
    Result of candidate authority analysis.
    
    Attributes:
        is_candidate: Whether URL matches authoritative patterns
        candidate_type: Type of authoritative page (trust_center, security_page, etc.)
        confidence: Confidence score 0.0-1.0
        match_reason: Why this was/wasn't identified as candidate
        normalized_domain: The domain extracted from URL (for grouping)
        subdomain_match: The subdomain pattern that matched (if any)
        path_match: The path pattern that matched (if any)
    
    Note: is_candidate=True does NOT mean source_type="vendor".
    Candidates must be confirmed and added to VendorRegistry first.
    """
    is_candidate: bool
    candidate_type: CandidateType
    confidence: float
    match_reason: str
    normalized_domain: Optional[str] = None
    subdomain_match: Optional[str] = None
    path_match: Optional[str] = None


# =============================================================================
# URL PATTERNS FOR CANDIDATE IDENTIFICATION
# =============================================================================

# Subdomain patterns that suggest authoritative vendor pages
# Key: subdomain prefix, Value: candidate type
SUBDOMAIN_PATTERNS = {
    "trust": CandidateType.TRUST_CENTER,
    "security": CandidateType.SECURITY_PAGE,
    "docs": CandidateType.DOCS,
    "documentation": CandidateType.DOCS,
    "status": CandidateType.STATUS_PAGE,
    "privacy": CandidateType.PRIVACY_PAGE,
    "help": CandidateType.DOCS,
    "support": CandidateType.DOCS,
    "api": CandidateType.DOCS,
}

# Path patterns that suggest authoritative vendor pages
# Key: path prefix, Value: candidate type
PATH_PATTERNS = {
    "/trust": CandidateType.TRUST_CENTER,
    "/trust-center": CandidateType.TRUST_CENTER,
    "/trustcenter": CandidateType.TRUST_CENTER,
    "/security": CandidateType.SECURITY_PAGE,
    "/compliance": CandidateType.TRUST_CENTER,
    "/privacy": CandidateType.PRIVACY_PAGE,
    "/privacy-policy": CandidateType.PRIVACY_PAGE,
    "/docs": CandidateType.DOCS,
    "/documentation": CandidateType.DOCS,
    "/pricing": CandidateType.PRICING_PAGE,
    "/plans": CandidateType.PRICING_PAGE,
}

# Confidence scores for different match types
CONFIDENCE_SUBDOMAIN_AND_PATH = 0.9
CONFIDENCE_SUBDOMAIN_ONLY = 0.8
CONFIDENCE_PATH_ONLY = 0.6


def _extract_subdomain(domain: str) -> Optional[str]:
    """
    Extract the subdomain from a normalized domain.
    
    IMPORTANT: Assumes domain has already been normalized via
    source_classifier.normalize_domain (lowercase, www stripped, port stripped).
    
    Examples:
        trust.example.com → trust
        example.com → None
        docs.api.example.com → docs
    """
    if not domain:
        return None
    
    parts = domain.split('.')
    
    # Need at least 3 parts for a subdomain (sub.domain.tld)
    if len(parts) < 3:
        return None
    
    return parts[0]


def _match_path_pattern(path: str) -> Optional[tuple]:
    """
    Check if path matches any known patterns.
    
    Returns (matched_pattern, CandidateType) or None.
    """
    if not path:
        return None
    
    path_lower = path.lower()
    
    # Sort patterns by length (longest first) for best match
    sorted_patterns = sorted(PATH_PATTERNS.keys(), key=len, reverse=True)
    
    for pattern in sorted_patterns:
        if path_lower.startswith(pattern):
            return (pattern, PATH_PATTERNS[pattern])
    
    return None


def analyze_candidate(url: str) -> CandidateResult:
    """
    Analyze a URL to determine if it's a candidate authoritative vendor source.
    
    This function uses URL structure patterns (subdomain, path) to identify
    URLs that LOOK LIKE vendor-authoritative pages (trust centers, security
    pages, documentation, etc.).
    
    IMPORTANT: This is a HEURISTIC for workflow purposes only.
    - It does NOT affect source_type classification
    - It does NOT use vendor name matching
    - Candidates require confirmation before registry addition
    
    Args:
        url: URL to analyze
        
    Returns:
        CandidateResult with is_candidate, candidate_type, and confidence.
        
    Examples:
        >>> analyze_candidate("https://trust.example.com/compliance")
        CandidateResult(is_candidate=True, candidate_type=TRUST_CENTER, confidence=0.9, ...)
        
        >>> analyze_candidate("https://example.com/blog/post")
        CandidateResult(is_candidate=False, candidate_type=UNKNOWN, confidence=0.0, ...)
    """
    # Handle empty/None URL
    if not url:
        return CandidateResult(
            is_candidate=False,
            candidate_type=CandidateType.UNKNOWN,
            confidence=0.0,
            match_reason="no_url"
        )
    
    # Normalize URL to lowercase for consistent parsing
    url = url.lower()
    
    # Normalize domain using shared function from source_classifier
    # This ensures consistent behavior: lowercase, strip port, strip www
    domain = normalize_domain(url)
    if not domain:
        return CandidateResult(
            is_candidate=False,
            candidate_type=CandidateType.UNKNOWN,
            confidence=0.0,
            match_reason="invalid_url"
        )
    
    # Parse URL for path
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        parsed = urlparse(url)
        path = parsed.path
    except Exception:
        return CandidateResult(
            is_candidate=False,
            candidate_type=CandidateType.UNKNOWN,
            confidence=0.0,
            match_reason="parse_error",
            normalized_domain=domain
        )
    
    # Extract subdomain from normalized domain
    subdomain = _extract_subdomain(domain)
    
    # Check for subdomain match
    subdomain_match_type = None
    if subdomain and subdomain in SUBDOMAIN_PATTERNS:
        subdomain_match_type = SUBDOMAIN_PATTERNS[subdomain]
    
    # Check for path match
    path_match_result = _match_path_pattern(path)
    path_match_type = path_match_result[1] if path_match_result else None
    path_pattern = path_match_result[0] if path_match_result else None
    
    # Determine result based on matches
    if subdomain_match_type and path_match_type:
        # Both subdomain and path match - highest confidence
        # Prefer subdomain type as it's more specific
        return CandidateResult(
            is_candidate=True,
            candidate_type=subdomain_match_type,
            confidence=CONFIDENCE_SUBDOMAIN_AND_PATH,
            match_reason="subdomain_and_path",
            normalized_domain=domain,
            subdomain_match=subdomain,
            path_match=path_pattern
        )
    
    elif subdomain_match_type:
        # Only subdomain matches - high confidence
        return CandidateResult(
            is_candidate=True,
            candidate_type=subdomain_match_type,
            confidence=CONFIDENCE_SUBDOMAIN_ONLY,
            match_reason="subdomain",
            normalized_domain=domain,
            subdomain_match=subdomain,
            path_match=None
        )
    
    elif path_match_type:
        # Only path matches - medium confidence
        return CandidateResult(
            is_candidate=True,
            candidate_type=path_match_type,
            confidence=CONFIDENCE_PATH_ONLY,
            match_reason="path",
            normalized_domain=domain,
            subdomain_match=None,
            path_match=path_pattern
        )
    
    else:
        # No patterns match
        return CandidateResult(
            is_candidate=False,
            candidate_type=CandidateType.UNKNOWN,
            confidence=0.0,
            match_reason="no_patterns_match",
            normalized_domain=domain
        )


def get_registry_field_for_candidate_type(candidate_type: CandidateType) -> Optional[str]:
    """
    Map CandidateType to VendorRegistry field name.
    
    Used when promoting a candidate to the registry.
    
    NOTE: STATUS_PAGE is intentionally excluded. VendorRegistry.get_all_urls()
    does not include status_page_url in its output (per contract), so promoting
    a STATUS_PAGE candidate would create orphan data that never participates
    in source_type classification.
    
    Args:
        candidate_type: The type of candidate
        
    Returns:
        VendorRegistry attribute name (e.g., "trust_center_url") or None
    """
    mapping = {
        CandidateType.TRUST_CENTER: "trust_center_url",
        CandidateType.SECURITY_PAGE: "security_page_url",
        CandidateType.PRIVACY_PAGE: "privacy_page_url",
        CandidateType.PRICING_PAGE: "pricing_page_url",
        CandidateType.DOCS: "docs_url",
        # STATUS_PAGE intentionally omitted - not in VendorRegistry.get_all_urls() contract
    }
    return mapping.get(candidate_type)


# =============================================================================
# Convenience functions
# =============================================================================

def is_candidate_authority(url: str) -> bool:
    """
    Quick check if URL matches candidate authority patterns.
    
    Returns True if URL has subdomain or path patterns suggesting
    it's an authoritative vendor page.
    """
    return analyze_candidate(url).is_candidate


def get_candidate_type(url: str) -> CandidateType:
    """
    Get the candidate type for a URL.
    
    Returns CandidateType.UNKNOWN if not a candidate.
    """
    return analyze_candidate(url).candidate_type
