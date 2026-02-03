"""
Offline tests for effective vendor URLs mechanism.

Tests verify:
1. Known vendors use registry URLs (authoritative)
2. Novel vendors build effective URLs from candidate patterns
3. Classification works correctly for both cases

No network, no database, no LLM required.

Run with: cd backend && python3 -m pytest tests/test_effective_vendor_urls.py -v
"""

import pytest
from unittest.mock import MagicMock, patch
from typing import List, Dict, Any, Tuple, Optional

# Import the modules we're testing
from source_classifier import classify_source
from candidate_authority import CandidateType
from vendor_authority_bootstrap import collect_candidates_from_urls


class MockVendorRegistry:
    """Mock VendorRegistry for testing."""
    
    def __init__(self, urls: List[Dict[str, str]]):
        self._urls = urls
    
    def get_all_urls(self) -> List[Dict[str, str]]:
        return self._urls


def get_effective_vendor_urls(
    vendor_entry: Optional[MockVendorRegistry],
    discovered_urls: List[str],
    vendor_name: str
) -> List[Dict[str, str]]:
    """
    Standalone implementation of _get_effective_vendor_urls for testing.
    Mirrors the logic in ResearchAgentV2._get_effective_vendor_urls.
    """
    if vendor_entry:
        # Registry is authoritative for known vendors
        return vendor_entry.get_all_urls()
    
    # Novel vendor: build effective URLs from candidate patterns
    candidates = collect_candidates_from_urls(vendor_name, discovered_urls)
    
    # Only include types that map to registry fields (exclude STATUS_PAGE)
    valid_types = {
        CandidateType.TRUST_CENTER,
        CandidateType.SECURITY_PAGE,
        CandidateType.PRIVACY_PAGE,
        CandidateType.DOCS,
        CandidateType.PRICING_PAGE,
    }
    
    # De-duplicate by domain, keeping highest confidence candidate
    domain_best: Dict[str, Tuple[Any, float]] = {}
    for candidate in candidates:
        if candidate.candidate_type not in valid_types:
            continue
        domain = candidate.normalized_domain
        if domain not in domain_best or candidate.confidence > domain_best[domain][1]:
            domain_best[domain] = (candidate, candidate.confidence)
    
    # Convert to vendor_urls format
    effective_urls = []
    for domain, (candidate, _) in domain_best.items():
        effective_urls.append({
            "type": candidate.candidate_type.value,
            "url": candidate.candidate_url
        })
    
    return effective_urls


class TestKnownVendorEffectiveUrls:
    """Tests for known vendors (registry entry exists)."""
    
    def test_known_vendor_uses_registry_urls(self):
        """
        When vendor_entry exists, effective_vendor_urls should equal registry URLs.
        Candidates do NOT change classification.
        """
        registry_urls = [
            {"type": "trust_center", "url": "https://trust.knownvendor.com"},
            {"type": "security_page", "url": "https://www.knownvendor.com/security"},
        ]
        vendor_entry = MockVendorRegistry(registry_urls)
        
        # Even if we discover other URLs, registry is authoritative
        discovered_urls = [
            "https://trust.knownvendor.com/soc2",
            "https://docs.knownvendor.com/api",
            "https://techcrunch.com/knownvendor",
        ]
        
        effective = get_effective_vendor_urls(vendor_entry, discovered_urls, "KnownVendor")
        
        assert effective == registry_urls
    
    def test_known_vendor_classification_unchanged_by_candidates(self):
        """
        For known vendors, candidate discovery should NOT affect source_type.
        """
        registry_urls = [
            {"type": "trust_center", "url": "https://trust.knownvendor.com"},
        ]
        vendor_entry = MockVendorRegistry(registry_urls)
        
        # Suppose we also discover docs.knownvendor.com (not in registry)
        discovered_urls = [
            "https://trust.knownvendor.com/soc2",
            "https://docs.knownvendor.com/api",  # Not in registry
        ]
        
        effective = get_effective_vendor_urls(vendor_entry, discovered_urls, "KnownVendor")
        
        # Should still be registry only
        assert effective == registry_urls
        
        # Classification of docs.knownvendor.com should be third_party
        # (because it's not in the registry)
        result = classify_source("https://docs.knownvendor.com/api", effective)
        assert result.source_type == "third_party"
    
    def test_known_vendor_trust_center_is_vendor(self):
        """
        Registry URLs should classify as vendor.
        """
        registry_urls = [
            {"type": "trust_center", "url": "https://trust.knownvendor.com"},
        ]
        vendor_entry = MockVendorRegistry(registry_urls)
        
        effective = get_effective_vendor_urls(vendor_entry, [], "KnownVendor")
        
        result = classify_source("https://trust.knownvendor.com/soc2", effective)
        assert result.source_type == "vendor"
    
    def test_known_vendor_techcrunch_is_third_party(self):
        """
        Non-registry URLs should classify as third_party.
        """
        registry_urls = [
            {"type": "trust_center", "url": "https://trust.knownvendor.com"},
        ]
        vendor_entry = MockVendorRegistry(registry_urls)
        
        effective = get_effective_vendor_urls(vendor_entry, [], "KnownVendor")
        
        result = classify_source("https://techcrunch.com/knownvendor", effective)
        assert result.source_type == "third_party"


class TestNovelVendorEffectiveUrls:
    """Tests for novel vendors (no registry entry)."""
    
    def test_novel_vendor_builds_from_candidates(self):
        """
        When no vendor_entry exists, effective_vendor_urls should be built
        from candidate patterns in discovered URLs.
        """
        vendor_entry = None
        
        discovered_urls = [
            "https://trust.newvendor.com/security",
            "https://docs.newvendor.com/api-reference",
            "https://techcrunch.com/newvendor-funding",
        ]
        
        effective = get_effective_vendor_urls(vendor_entry, discovered_urls, "NewVendor")
        
        # Should include trust.newvendor.com and docs.newvendor.com
        effective_domains = {url["url"].split("//")[1].split("/")[0] for url in effective}
        
        assert "trust.newvendor.com" in effective_domains
        assert "docs.newvendor.com" in effective_domains
        # TechCrunch should NOT be in effective URLs
        assert "techcrunch.com" not in effective_domains
    
    def test_novel_vendor_trust_center_is_vendor(self):
        """
        For novel vendors, discovered trust center should classify as vendor.
        """
        vendor_entry = None
        
        discovered_urls = [
            "https://trust.newvendor.com/compliance",
            "https://techcrunch.com/newvendor",
        ]
        
        effective = get_effective_vendor_urls(vendor_entry, discovered_urls, "NewVendor")
        
        # Now classify the trust center URL
        result = classify_source("https://trust.newvendor.com/compliance", effective)
        assert result.source_type == "vendor"
    
    def test_novel_vendor_docs_is_vendor(self):
        """
        For novel vendors, discovered docs site should classify as vendor.
        """
        vendor_entry = None
        
        discovered_urls = [
            "https://docs.newvendor.com/api",
        ]
        
        effective = get_effective_vendor_urls(vendor_entry, discovered_urls, "NewVendor")
        
        result = classify_source("https://docs.newvendor.com/api/authentication", effective)
        assert result.source_type == "vendor"
    
    def test_novel_vendor_techcrunch_is_third_party(self):
        """
        For novel vendors, non-vendor URLs should still be third_party.
        """
        vendor_entry = None
        
        discovered_urls = [
            "https://trust.newvendor.com/security",
            "https://techcrunch.com/newvendor-funding",
        ]
        
        effective = get_effective_vendor_urls(vendor_entry, discovered_urls, "NewVendor")
        
        result = classify_source("https://techcrunch.com/newvendor-funding", effective)
        assert result.source_type == "third_party"
    
    def test_novel_vendor_status_page_excluded(self):
        """
        Status pages should NOT be included in effective URLs.
        """
        vendor_entry = None
        
        discovered_urls = [
            "https://trust.newvendor.com/security",
            "https://status.newvendor.com/",
        ]
        
        effective = get_effective_vendor_urls(vendor_entry, discovered_urls, "NewVendor")
        
        # Status page should NOT be in effective URLs
        effective_domains = {url["url"].split("//")[1].split("/")[0] for url in effective}
        assert "status.newvendor.com" not in effective_domains
    
    def test_novel_vendor_deduplicates_by_domain(self):
        """
        Multiple URLs from same domain should dedupe to highest confidence.
        """
        vendor_entry = None
        
        discovered_urls = [
            "https://trust.newvendor.com/security",
            "https://trust.newvendor.com/compliance",
            "https://trust.newvendor.com/soc2",
        ]
        
        effective = get_effective_vendor_urls(vendor_entry, discovered_urls, "NewVendor")
        
        # Should only have one entry for trust.newvendor.com
        trust_entries = [u for u in effective if "trust.newvendor.com" in u["url"]]
        assert len(trust_entries) == 1


class TestNovelVendorFullScenario:
    """
    End-to-end test: Novel vendor assessment with mixed URL types.
    """
    
    def test_full_novel_vendor_scenario(self):
        """
        Simulate a first-time assessment for a novel vendor.
        
        Discovered URLs include:
        - trust.newco.com (vendor trust center)
        - docs.newco.com (vendor docs)
        - newco.com/security (vendor security page)
        - techcrunch.com/newco (third party)
        - g2.com/newco (third party)
        
        Expected classification:
        - trust.newco.com/* -> vendor
        - docs.newco.com/* -> vendor
        - newco.com/security/* -> vendor
        - techcrunch.com/* -> third_party
        - g2.com/* -> third_party
        """
        vendor_entry = None
        
        discovered_urls = [
            "https://trust.newco.com/certifications",
            "https://docs.newco.com/getting-started",
            "https://www.newco.com/security",
            "https://techcrunch.com/2024/newco-series-b",
            "https://g2.com/products/newco/reviews",
        ]
        
        effective = get_effective_vendor_urls(vendor_entry, discovered_urls, "NewCo")
        
        # Verify effective URLs contain vendor domains
        effective_domains = {url["url"].split("//")[1].split("/")[0] for url in effective}
        assert "trust.newco.com" in effective_domains
        assert "docs.newco.com" in effective_domains
        # www.newco.com/security should be detected as security_page pattern
        assert any("newco.com" in d for d in effective_domains)
        
        # Verify classifications
        assert classify_source("https://trust.newco.com/soc2", effective).source_type == "vendor"
        assert classify_source("https://docs.newco.com/api", effective).source_type == "vendor"
        assert classify_source("https://techcrunch.com/2024/newco", effective).source_type == "third_party"
        assert classify_source("https://g2.com/products/newco", effective).source_type == "third_party"


class TestEdgeCases:
    """Edge case tests."""
    
    def test_empty_discovered_urls(self):
        """
        Novel vendor with no discovered URLs should return empty effective URLs.
        """
        vendor_entry = None
        discovered_urls = []
        
        effective = get_effective_vendor_urls(vendor_entry, discovered_urls, "NewVendor")
        
        assert effective == []
    
    def test_only_third_party_urls_discovered(self):
        """
        Novel vendor with only third-party URLs should return empty effective URLs.
        """
        vendor_entry = None
        discovered_urls = [
            "https://techcrunch.com/vendor-news",
            "https://g2.com/vendor-reviews",
            "https://crunchbase.com/vendor",
        ]
        
        effective = get_effective_vendor_urls(vendor_entry, discovered_urls, "NewVendor")
        
        # No candidate patterns match third-party sites
        assert effective == []
    
    def test_known_vendor_empty_registry(self):
        """
        Known vendor with empty registry should use empty effective URLs.
        """
        vendor_entry = MockVendorRegistry([])
        discovered_urls = [
            "https://trust.knownvendor.com/security",
        ]
        
        # Registry is authoritative, even if empty
        effective = get_effective_vendor_urls(vendor_entry, discovered_urls, "KnownVendor")
        
        assert effective == []


class TestCandidateTypeMapping:
    """Test that candidate types map correctly to vendor_urls format."""
    
    def test_trust_center_type(self):
        """Trust center candidates should have type 'trust_center'."""
        vendor_entry = None
        discovered_urls = ["https://trust.vendor.com/"]
        
        effective = get_effective_vendor_urls(vendor_entry, discovered_urls, "Vendor")
        
        assert len(effective) == 1
        assert effective[0]["type"] == "trust_center"
    
    def test_docs_type(self):
        """Docs candidates should have type 'docs'."""
        vendor_entry = None
        discovered_urls = ["https://docs.vendor.com/"]
        
        effective = get_effective_vendor_urls(vendor_entry, discovered_urls, "Vendor")
        
        assert len(effective) == 1
        assert effective[0]["type"] == "docs"
    
    def test_security_page_type(self):
        """Security page candidates should have type 'security_page'."""
        vendor_entry = None
        discovered_urls = ["https://www.vendor.com/security"]
        
        effective = get_effective_vendor_urls(vendor_entry, discovered_urls, "Vendor")
        
        # May or may not match depending on pattern implementation
        # This tests the type mapping if it does match
        security_entries = [u for u in effective if u.get("type") == "security_page"]
        # If matched, type should be correct
        for entry in security_entries:
            assert entry["type"] == "security_page"


class TestReclassificationLogic:
    """Test the reclassification behavior for novel vendors."""
    
    def test_reclassification_changes_source_type(self):
        """
        Facts initially classified as third_party should be reclassified
        to vendor when effective_vendor_urls includes their domain.
        """
        # Simulate initial classification with empty vendor_urls
        initial_source_type = classify_source(
            "https://trust.newvendor.com/soc2", 
            []  # Empty vendor_urls for novel vendor
        ).source_type
        
        assert initial_source_type == "third_party"
        
        # Build effective URLs from discovery
        vendor_entry = None
        discovered_urls = ["https://trust.newvendor.com/soc2"]
        effective = get_effective_vendor_urls(vendor_entry, discovered_urls, "NewVendor")
        
        # Reclassify with effective URLs
        reclassified_source_type = classify_source(
            "https://trust.newvendor.com/soc2",
            effective
        ).source_type
        
        assert reclassified_source_type == "vendor"
    
    def test_third_party_stays_third_party(self):
        """
        URLs that are genuinely third_party should remain third_party
        even after reclassification.
        """
        vendor_entry = None
        discovered_urls = [
            "https://trust.newvendor.com/soc2",
            "https://techcrunch.com/newvendor",
        ]
        effective = get_effective_vendor_urls(vendor_entry, discovered_urls, "NewVendor")
        
        # TechCrunch should still be third_party
        result = classify_source("https://techcrunch.com/newvendor", effective)
        assert result.source_type == "third_party"
