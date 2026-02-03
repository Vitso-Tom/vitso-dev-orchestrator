"""
Assurance Keywords Loader

Dynamically builds SNIPPET_KEYWORDS from assurance_programs.json.
This ensures VDO extraction and AITGP matching use the same authoritative source.

Single Source of Truth: assurance_programs.json
- Editable by user without code changes
- Automatically picks up new certifications/aliases
- Shared between VDO (extraction) and AITGP (matching)
"""

import json
import os
from typing import List, Set
from pathlib import Path


# Default path to assurance_programs.json
# Can be overridden via environment variable
DEFAULT_ASSURANCE_CONFIG_PATH = os.environ.get(
    "ASSURANCE_PROGRAMS_PATH",
    "/home/temlock/aitgp-app/job-53/config/assurance_programs.json"
)

# Additional keywords NOT in assurance_programs.json
# These are security/compliance terms that aren't formal certifications
# but are important for snippet extraction
SUPPLEMENTARY_KEYWORDS = [
    # Security controls
    "encryption", "aes-256", "aes 256", "tls 1.2", "tls 1.3",
    "penetration test", "pentest", "pen test",
    "vulnerability", "security audit",
    
    # Identity & Access
    "sso", "single sign-on", "saml", "scim", "mfa", "2fa",
    "multi-factor", "two-factor", "oauth", "oidc",
    "okta", "auth0", "azure ad", "entra", "onelogin", "ping identity",
    
    # Data handling
    "data retention", "data residency", "data deletion",
    "subprocessor", "sub-processor", "data processing agreement",
    "phi", "protected health information", "pii",
    
    # AI/ML Policy (critical for AI Model Risk scoring)
    "training", "model training", "train on", "trained on",
    "customer data", "user data", "your data",
    "opt-out", "opt out", "privacy mode",
    "zero retention", "no retention",
    "ai model", "machine learning", "llm", "large language model",
    "openai", "anthropic", "azure openai", "gpt", "claude",
    "fine-tune", "fine tune", "finetune",
    "not use", "never use", "do not use", "does not use",
    "improve our", "improve the", "improve model",
    
    # Cloud providers (subprocessor detection)
    "aws", "amazon web services", "azure", "microsoft azure",
    "google cloud", "gcp", "snowflake", "databricks",
    
    # AI providers (subprocessor detection)
    "vertex ai", "bedrock", "hugging face", "cohere", "mistral",
    
    # Healthcare integrations
    "epic", "cerner", "allscripts", "meditech", "athenahealth",
    "hl7", "fhir", "ehr", "emr",
    
    # Contractual
    "business associate", "baa",
    
    # General compliance
    "trust center", "security page", "compliance page",
    "certification", "certified", "compliant", "compliance",
    "attestation", "audit report", "third-party audit",
]


def load_assurance_programs(config_path: str = None) -> dict:
    """
    Load assurance_programs.json from disk.
    
    Args:
        config_path: Path to JSON file. Uses DEFAULT_ASSURANCE_CONFIG_PATH if not provided.
        
    Returns:
        Parsed JSON as dict, or empty dict if file not found.
    """
    path = config_path or DEFAULT_ASSURANCE_CONFIG_PATH
    
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[ASSURANCE_KEYWORDS] Warning: {path} not found, using supplementary keywords only")
        return {}
    except json.JSONDecodeError as e:
        print(f"[ASSURANCE_KEYWORDS] Warning: Invalid JSON in {path}: {e}")
        return {}


def extract_keywords_from_assurance_programs(config: dict) -> Set[str]:
    """
    Extract all searchable keywords from assurance_programs.json.
    
    Extracts:
    - canonical_name (lowercased)
    - All aliases
    - All level names
    - All level aliases
    
    Args:
        config: Parsed assurance_programs.json
        
    Returns:
        Set of lowercase keywords
    """
    keywords = set()
    
    programs = config.get("programs", [])
    
    for program in programs:
        # Add canonical name
        canonical = program.get("canonical_name", "")
        if canonical:
            keywords.add(canonical.lower())
        
        # Add all aliases
        for alias in program.get("aliases", []):
            if alias:
                keywords.add(alias.lower())
        
        # Add level names and aliases
        for level in program.get("levels", []):
            level_name = level.get("name", "")
            if level_name:
                keywords.add(level_name.lower())
            
            for level_alias in level.get("aliases", []):
                if level_alias:
                    keywords.add(level_alias.lower())
    
    return keywords


def build_snippet_keywords(config_path: str = None) -> List[str]:
    """
    Build the complete SNIPPET_KEYWORDS list from:
    1. assurance_programs.json (authoritative certification keywords)
    2. SUPPLEMENTARY_KEYWORDS (security terms not in the JSON)
    
    This is the main entry point for VDO's snippet extraction.
    
    Args:
        config_path: Optional path to assurance_programs.json
        
    Returns:
        List of keywords for snippet extraction
    """
    # Load from JSON
    config = load_assurance_programs(config_path)
    
    # Extract certification keywords
    cert_keywords = extract_keywords_from_assurance_programs(config)
    
    # Combine with supplementary keywords
    all_keywords = cert_keywords.union(set(k.lower() for k in SUPPLEMENTARY_KEYWORDS))
    
    # Sort for consistency
    return sorted(list(all_keywords))


def get_certification_fields() -> List[str]:
    """
    Get list of certification field keys for RESEARCH_CATEGORIES.
    
    Extracts program IDs from assurance_programs.json and converts to
    snake_case field names (e.g., "NIST_CSF" -> "nist_csf").
    
    Returns:
        List of certification field keys
    """
    config = load_assurance_programs()
    
    fields = []
    for program in config.get("programs", []):
        program_id = program.get("id", "")
        if program_id:
            # Convert to snake_case lowercase
            field_key = program_id.lower()
            fields.append(field_key)
    
    return fields


# Pre-build keywords on module load for efficiency
# VDO can import SNIPPET_KEYWORDS directly
_cached_keywords = None

def get_snippet_keywords() -> List[str]:
    """Get cached snippet keywords, building if needed."""
    global _cached_keywords
    if _cached_keywords is None:
        _cached_keywords = build_snippet_keywords()
        print(f"[ASSURANCE_KEYWORDS] Loaded {len(_cached_keywords)} keywords from assurance_programs.json")
    return _cached_keywords


# For direct import compatibility with existing code
SNIPPET_KEYWORDS = None  # Lazy-loaded on first access


def __getattr__(name):
    """Lazy load SNIPPET_KEYWORDS on first access."""
    if name == "SNIPPET_KEYWORDS":
        return get_snippet_keywords()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == "__main__":
    # Test/debug: print all extracted keywords
    keywords = build_snippet_keywords()
    print(f"Total keywords: {len(keywords)}")
    print("\nCertification keywords from JSON:")
    
    config = load_assurance_programs()
    cert_keywords = extract_keywords_from_assurance_programs(config)
    for kw in sorted(cert_keywords):
        print(f"  - {kw}")
    
    print(f"\nSupplementary keywords: {len(SUPPLEMENTARY_KEYWORDS)}")
    print(f"\nCertification fields for RESEARCH_CATEGORIES:")
    for field in get_certification_fields():
        print(f"  - {field}")
