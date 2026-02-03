"""
Source Classification Module - Single Source of Truth

This module provides deterministic URL-to-source-type classification
using VendorRegistry URLs as the authoritative reference.

DESIGN PRINCIPLES:
1. Classification is deterministic - same input always produces same output
2. Classification happens in exactly one place - this module
3. Vendor authority is derived from VendorRegistry URLs, not guessing
4. NO substring URL matching - exact domain comparison only
5. Pure functions - no network, no LLM, no database, no side effects

USAGE:
    from source_classifier import classify_source
    
    # Get vendor URLs from VendorRegistry.get_all_urls()
    vendor_urls = [
        {"type": "trust_center", "url": "https://trust.vendor.com"},
        {"type": "security_page", "url": "https://www.vendor.com/security"},
    ]
    
    result = classify_source("https://trust.vendor.com/soc2", vendor_urls)
    # result.source_type == "vendor"
    # result.match_reason == "exact_domain_match"
    # result.matched_url_type == "trust_center"
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from urllib.parse import urlparse


@dataclass(frozen=True)
class ClassificationResult:
    """
    Result of source classification.
    
    Attributes:
        source_type: "vendor" or "third_party" (only these two values)
        match_reason: Diagnostic info explaining the classification
            - "exact_domain_match": URL domain matches a registered vendor domain
            - "no_match": URL domain does not match any registered vendor domain
            - "no_url": Input URL was empty or None
            - "invalid_url": Input URL could not be parsed
            - "no_registry_urls": No vendor URLs provided for comparison
        matched_url_type: Type of URL matched (e.g., "trust_center", "security_page")
                          None if source_type is "third_party"
        matched_domain: The vendor domain that matched, None if no match
    """
    source_type: str
    match_reason: str
    matched_url_type: Optional[str] = None
    matched_domain: Optional[str] = None


def normalize_domain(url: str) -> Optional[str]:
    """
    Extract and normalize domain from URL for comparison.
    
    Normalization:
    - Lowercase
    - Remove www. prefix
    - Remove port
    - Handle URLs without scheme
    
    Args:
        url: URL string to normalize
        
    Returns:
        Normalized domain string, or None if URL is invalid/empty
    """
    if not url:
        return None
    
    url = url.strip()
    if not url:
        return None
    
    # Add scheme if missing (needed for urlparse)
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split('/')[0]
        
        if not domain:
            return None
        
        # Remove port if present
        if ':' in domain:
            domain = domain.split(':')[0]
        
        # Lowercase
        domain = domain.lower()
        
        # Remove www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Validate we have something left
        if not domain or '.' not in domain:
            return None
        
        return domain
        
    except Exception:
        return None


def _build_domain_index(vendor_urls: List[Dict[str, str]]) -> Dict[str, str]:
    """
    Build a lookup index from normalized domains to URL types.
    
    Args:
        vendor_urls: List of dicts with 'type' and 'url' keys
        
    Returns:
        Dict mapping normalized domain -> url_type
    """
    index = {}
    
    for entry in vendor_urls:
        url = entry.get('url')
        url_type = entry.get('type')
        
        if not url:
            continue
        
        domain = normalize_domain(url)
        if domain:
            # First match wins (preserves original registry order priority)
            if domain not in index:
                index[domain] = url_type
    
    return index


def classify_source(
    url: str,
    vendor_urls: Optional[List[Dict[str, str]]]
) -> ClassificationResult:
    """
    Classify a source URL as vendor or third_party.
    
    This is a pure function with no side effects. Classification is based
    solely on exact domain matching against the provided vendor URLs.
    
    Args:
        url: The URL to classify
        vendor_urls: List of dicts with 'type' and 'url' keys,
                     typically from VendorRegistry.get_all_urls()
    
    Returns:
        ClassificationResult with source_type ("vendor" or "third_party")
        and diagnostic information in match_reason.
    
    Examples:
        >>> vendor_urls = [{"type": "trust_center", "url": "https://trust.vendor.com"}]
        >>> classify_source("https://trust.vendor.com/soc2", vendor_urls)
        ClassificationResult(source_type='vendor', match_reason='exact_domain_match', ...)
        
        >>> classify_source("https://example.com", vendor_urls)
        ClassificationResult(source_type='third_party', match_reason='no_match', ...)
    """
    # Handle missing/empty URL
    if not url:
        return ClassificationResult(
            source_type="third_party",
            match_reason="no_url"
        )
    
    # Handle missing/empty vendor URLs
    if not vendor_urls:
        return ClassificationResult(
            source_type="third_party",
            match_reason="no_registry_urls"
        )
    
    # Normalize the input URL domain
    input_domain = normalize_domain(url)
    
    if not input_domain:
        return ClassificationResult(
            source_type="third_party",
            match_reason="invalid_url"
        )
    
    # Build domain index from vendor URLs
    domain_index = _build_domain_index(vendor_urls)
    
    if not domain_index:
        return ClassificationResult(
            source_type="third_party",
            match_reason="no_registry_urls"
        )
    
    # EXACT domain match - no substring matching
    if input_domain in domain_index:
        return ClassificationResult(
            source_type="vendor",
            match_reason="exact_domain_match",
            matched_url_type=domain_index[input_domain],
            matched_domain=input_domain
        )
    
    # No match found
    return ClassificationResult(
        source_type="third_party",
        match_reason="no_match"
    )


# =============================================================================
# Convenience functions for common patterns
# =============================================================================

def is_vendor_source(url: str, vendor_urls: Optional[List[Dict[str, str]]]) -> bool:
    """
    Quick check if URL is from vendor.
    
    Args:
        url: URL to check
        vendor_urls: Vendor's registered URLs
        
    Returns:
        True if URL is from vendor, False otherwise
    """
    return classify_source(url, vendor_urls).source_type == "vendor"


def get_source_type(url: str, vendor_urls: Optional[List[Dict[str, str]]]) -> str:
    """
    Get just the source_type string.
    
    Args:
        url: URL to classify
        vendor_urls: Vendor's registered URLs
        
    Returns:
        "vendor" or "third_party"
    """
    return classify_source(url, vendor_urls).source_type
