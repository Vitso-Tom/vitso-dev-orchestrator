"""
Offline tests for candidate authority and bootstrap workflow.

These tests verify:
1. Candidate URL pattern detection (subdomain, path)
2. Candidate collection from discovered URLs
3. Registry entry building from confirmed candidates
4. Workflow state transitions
5. Anti-hallucination guarantees are preserved
6. STATUS_PAGE is non-promotable

Run with: cd backend && python -m pytest tests/test_candidate_authority.py -v
"""

import pytest
from datetime import datetime

from candidate_authority import (
    analyze_candidate, 
    CandidateResult, 
    CandidateType, 
    CandidateStatus,
    is_candidate_authority,
    get_candidate_type,
    get_registry_field_for_candidate_type,
    CONFIDENCE_SUBDOMAIN_AND_PATH,
    CONFIDENCE_SUBDOMAIN_ONLY,
    CONFIDENCE_PATH_ONLY,
)

from vendor_authority_bootstrap import (
    CandidateVendorUrl,
    collect_candidates_from_urls,
    build_registry_entry_from_candidates,
)


# =============================================================================
# TEST: Subdomain pattern detection
# =============================================================================

class TestSubdomainPatterns:
    """Tests for subdomain-based candidate identification"""
    
    def test_trust_subdomain(self):
        """trust.* subdomain should be candidate trust_center"""
        result = analyze_candidate("https://trust.example.com")
        assert result.is_candidate is True
        assert result.candidate_type == CandidateType.TRUST_CENTER
        assert result.match_reason == "subdomain"
        assert result.subdomain_match == "trust"
    
    def test_security_subdomain(self):
        """security.* subdomain should be candidate security_page"""
        result = analyze_candidate("https://security.example.com")
        assert result.is_candidate is True
        assert result.candidate_type == CandidateType.SECURITY_PAGE
    
    def test_docs_subdomain(self):
        """docs.* subdomain should be candidate docs"""
        result = analyze_candidate("https://docs.example.com")
        assert result.is_candidate is True
        assert result.candidate_type == CandidateType.DOCS
    
    def test_status_subdomain(self):
        """status.* subdomain should be candidate status_page"""
        result = analyze_candidate("https://status.example.com")
        assert result.is_candidate is True
        assert result.candidate_type == CandidateType.STATUS_PAGE
    
    def test_privacy_subdomain(self):
        """privacy.* subdomain should be candidate privacy_page"""
        result = analyze_candidate("https://privacy.example.com")
        assert result.is_candidate is True
        assert result.candidate_type == CandidateType.PRIVACY_PAGE
    
    def test_help_subdomain(self):
        """help.* subdomain should be candidate docs"""
        result = analyze_candidate("https://help.example.com")
        assert result.is_candidate is True
        assert result.candidate_type == CandidateType.DOCS
    
    def test_www_subdomain_ignored(self):
        """www.* subdomain should not be a candidate"""
        result = analyze_candidate("https://www.example.com")
        assert result.is_candidate is False
        assert result.match_reason == "no_patterns_match"
    
    def test_subdomain_confidence(self):
        """Subdomain-only match should have correct confidence"""
        result = analyze_candidate("https://trust.example.com")
        assert result.confidence == CONFIDENCE_SUBDOMAIN_ONLY


# =============================================================================
# TEST: WWW stripping (matches source_classifier.normalize_domain behavior)
# =============================================================================

class TestWwwStripping:
    """Tests that www is stripped consistently with source_classifier"""
    
    def test_www_trust_subdomain(self):
        """www.trust.example.com should detect trust subdomain after www strip"""
        result = analyze_candidate("https://www.trust.example.com")
        assert result.is_candidate is True
        assert result.candidate_type == CandidateType.TRUST_CENTER
        assert result.subdomain_match == "trust"
        # Domain should have www stripped
        assert result.normalized_domain == "trust.example.com"
    
    def test_www_only_not_candidate(self):
        """www.example.com (www stripped = example.com) should not be candidate"""
        result = analyze_candidate("https://www.example.com")
        assert result.is_candidate is False
        assert result.normalized_domain == "example.com"
    
    def test_www_docs_subdomain(self):
        """www.docs.example.com should detect docs subdomain"""
        result = analyze_candidate("https://www.docs.example.com")
        assert result.is_candidate is True
        assert result.candidate_type == CandidateType.DOCS
        assert result.subdomain_match == "docs"


# =============================================================================
# TEST: Path pattern detection
# =============================================================================

class TestPathPatterns:
    """Tests for path-based candidate identification"""
    
    def test_trust_path(self):
        """URL with /trust path should be candidate trust_center"""
        result = analyze_candidate("https://example.com/trust")
        assert result.is_candidate is True
        assert result.candidate_type == CandidateType.TRUST_CENTER
        assert result.match_reason == "path"
        assert result.path_match == "/trust"
    
    def test_trust_center_path(self):
        """/trust-center path should be candidate trust_center"""
        result = analyze_candidate("https://example.com/trust-center")
        assert result.is_candidate is True
        assert result.candidate_type == CandidateType.TRUST_CENTER
    
    def test_security_path(self):
        """/security path should be candidate security_page"""
        result = analyze_candidate("https://example.com/security")
        assert result.is_candidate is True
        assert result.candidate_type == CandidateType.SECURITY_PAGE
    
    def test_compliance_path(self):
        """/compliance path should be candidate trust_center"""
        result = analyze_candidate("https://example.com/compliance")
        assert result.is_candidate is True
        assert result.candidate_type == CandidateType.TRUST_CENTER
    
    def test_privacy_path(self):
        """/privacy path should be candidate privacy_page"""
        result = analyze_candidate("https://example.com/privacy")
        assert result.is_candidate is True
        assert result.candidate_type == CandidateType.PRIVACY_PAGE
    
    def test_docs_path(self):
        """/docs path should be candidate docs"""
        result = analyze_candidate("https://example.com/docs")
        assert result.is_candidate is True
        assert result.candidate_type == CandidateType.DOCS
    
    def test_pricing_path(self):
        """/pricing path should be candidate pricing_page"""
        result = analyze_candidate("https://example.com/pricing")
        assert result.is_candidate is True
        assert result.candidate_type == CandidateType.PRICING_PAGE
    
    def test_path_with_subpath(self):
        """Path pattern should match even with deeper paths"""
        result = analyze_candidate("https://example.com/security/overview")
        assert result.is_candidate is True
        assert result.candidate_type == CandidateType.SECURITY_PAGE
    
    def test_path_confidence(self):
        """Path-only match should have correct confidence"""
        result = analyze_candidate("https://example.com/trust")
        assert result.confidence == CONFIDENCE_PATH_ONLY


# =============================================================================
# TEST: Combined subdomain and path patterns
# =============================================================================

class TestCombinedPatterns:
    """Tests for URLs with both subdomain and path patterns"""
    
    def test_subdomain_and_path_highest_confidence(self):
        """Subdomain + path match should have highest confidence"""
        result = analyze_candidate("https://trust.example.com/compliance")
        assert result.is_candidate is True
        assert result.candidate_type == CandidateType.TRUST_CENTER
        assert result.match_reason == "subdomain_and_path"
        assert result.confidence == CONFIDENCE_SUBDOMAIN_AND_PATH
    
    def test_security_subdomain_with_security_path(self):
        """security.example.com/security should match with high confidence"""
        result = analyze_candidate("https://security.example.com/security")
        assert result.is_candidate is True
        assert result.confidence == CONFIDENCE_SUBDOMAIN_AND_PATH
    
    def test_subdomain_takes_precedence(self):
        """When subdomain and path types differ, subdomain wins"""
        # trust subdomain but security path
        result = analyze_candidate("https://trust.example.com/security")
        assert result.is_candidate is True
        assert result.candidate_type == CandidateType.TRUST_CENTER  # subdomain wins
        assert result.subdomain_match == "trust"
        assert result.path_match == "/security"


# =============================================================================
# TEST: Non-candidates (no patterns match)
# =============================================================================

class TestNonCandidates:
    """Tests for URLs that should NOT be candidates"""
    
    def test_blog_not_candidate(self):
        """Blog URL should not be candidate"""
        result = analyze_candidate("https://blog.example.com/post")
        assert result.is_candidate is False
        assert result.match_reason == "no_patterns_match"
    
    def test_www_not_candidate(self):
        """www URL should not be candidate"""
        result = analyze_candidate("https://www.example.com/about")
        assert result.is_candidate is False
    
    def test_random_path_not_candidate(self):
        """/about path should not be candidate"""
        result = analyze_candidate("https://example.com/about")
        assert result.is_candidate is False
    
    def test_news_site_not_candidate(self):
        """News site URL should not be candidate"""
        result = analyze_candidate("https://techcrunch.com/article/vendor-funding")
        assert result.is_candidate is False
    
    def test_social_media_not_candidate(self):
        """Social media URL should not be candidate"""
        result = analyze_candidate("https://twitter.com/vendorname")
        assert result.is_candidate is False


# =============================================================================
# TEST: Edge cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases"""
    
    def test_empty_url(self):
        """Empty URL should return is_candidate=False"""
        result = analyze_candidate("")
        assert result.is_candidate is False
        assert result.match_reason == "no_url"
    
    def test_none_url(self):
        """None URL should return is_candidate=False"""
        result = analyze_candidate(None)
        assert result.is_candidate is False
        assert result.match_reason == "no_url"
    
    def test_invalid_url(self):
        """Invalid URL should return is_candidate=False"""
        result = analyze_candidate("not a url")
        assert result.is_candidate is False
    
    def test_url_without_scheme(self):
        """URL without scheme should still work"""
        result = analyze_candidate("trust.example.com")
        assert result.is_candidate is True
        assert result.candidate_type == CandidateType.TRUST_CENTER
    
    def test_uppercase_url(self):
        """Uppercase URL should be normalized"""
        result = analyze_candidate("HTTPS://TRUST.EXAMPLE.COM/SECURITY")
        assert result.is_candidate is True
    
    def test_url_with_port(self):
        """URL with port should work"""
        result = analyze_candidate("https://trust.example.com:8443/compliance")
        assert result.is_candidate is True


# =============================================================================
# TEST: Convenience functions
# =============================================================================

class TestConvenienceFunctions:
    """Tests for convenience functions"""
    
    def test_is_candidate_authority_true(self):
        """is_candidate_authority should return True for candidates"""
        assert is_candidate_authority("https://trust.example.com") is True
    
    def test_is_candidate_authority_false(self):
        """is_candidate_authority should return False for non-candidates"""
        assert is_candidate_authority("https://blog.example.com") is False
    
    def test_get_candidate_type_valid(self):
        """get_candidate_type should return correct type"""
        assert get_candidate_type("https://trust.example.com") == CandidateType.TRUST_CENTER
    
    def test_get_candidate_type_unknown(self):
        """get_candidate_type should return UNKNOWN for non-candidates"""
        assert get_candidate_type("https://blog.example.com") == CandidateType.UNKNOWN


# =============================================================================
# TEST: Registry field mapping
# =============================================================================

class TestRegistryFieldMapping:
    """Tests for mapping CandidateType to VendorRegistry fields"""
    
    def test_trust_center_mapping(self):
        """TRUST_CENTER should map to trust_center_url"""
        assert get_registry_field_for_candidate_type(CandidateType.TRUST_CENTER) == "trust_center_url"
    
    def test_security_page_mapping(self):
        """SECURITY_PAGE should map to security_page_url"""
        assert get_registry_field_for_candidate_type(CandidateType.SECURITY_PAGE) == "security_page_url"
    
    def test_privacy_page_mapping(self):
        """PRIVACY_PAGE should map to privacy_page_url"""
        assert get_registry_field_for_candidate_type(CandidateType.PRIVACY_PAGE) == "privacy_page_url"
    
    def test_docs_mapping(self):
        """DOCS should map to docs_url"""
        assert get_registry_field_for_candidate_type(CandidateType.DOCS) == "docs_url"
    
    def test_pricing_page_mapping(self):
        """PRICING_PAGE should map to pricing_page_url"""
        assert get_registry_field_for_candidate_type(CandidateType.PRICING_PAGE) == "pricing_page_url"
    
    def test_unknown_mapping(self):
        """UNKNOWN should map to None"""
        assert get_registry_field_for_candidate_type(CandidateType.UNKNOWN) is None
    
    def test_status_page_mapping_is_none(self):
        """STATUS_PAGE should map to None (non-promotable)"""
        assert get_registry_field_for_candidate_type(CandidateType.STATUS_PAGE) is None


# =============================================================================
# TEST: STATUS_PAGE non-promotable
# =============================================================================

class TestStatusPageNonPromotable:
    """Tests ensuring STATUS_PAGE candidates cannot be promoted to registry"""
    
    def test_status_page_is_candidate(self):
        """status.* should still be identified as a candidate"""
        result = analyze_candidate("https://status.example.com")
        assert result.is_candidate is True
        assert result.candidate_type == CandidateType.STATUS_PAGE
    
    def test_status_page_no_registry_field(self):
        """STATUS_PAGE should have no registry field mapping"""
        field = get_registry_field_for_candidate_type(CandidateType.STATUS_PAGE)
        assert field is None
    
    def test_status_page_excluded_from_build_registry(self):
        """STATUS_PAGE candidates should not produce any registry field"""
        candidates = [
            CandidateVendorUrl(
                vendor_name="Example",
                candidate_url="https://status.example.com",
                candidate_type=CandidateType.STATUS_PAGE,
                confidence=0.8,
                match_reason="subdomain",
                status=CandidateStatus.CONFIRMED,
            ),
        ]
        
        entry = build_registry_entry_from_candidates("Example", candidates)
        
        # Should only have vendor_name, no URL fields
        assert entry == {"vendor_name": "Example"}
        assert "status_page_url" not in entry
    
    def test_status_page_mixed_with_promotable(self):
        """STATUS_PAGE should be skipped while other types are promoted"""
        candidates = [
            CandidateVendorUrl(
                vendor_name="Example",
                candidate_url="https://trust.example.com",
                candidate_type=CandidateType.TRUST_CENTER,
                confidence=0.9,
                match_reason="subdomain",
                status=CandidateStatus.CONFIRMED,
            ),
            CandidateVendorUrl(
                vendor_name="Example",
                candidate_url="https://status.example.com",
                candidate_type=CandidateType.STATUS_PAGE,
                confidence=0.8,
                match_reason="subdomain",
                status=CandidateStatus.CONFIRMED,
            ),
        ]
        
        entry = build_registry_entry_from_candidates("Example", candidates)
        
        assert entry["trust_center_url"] == "https://trust.example.com"
        assert "status_page_url" not in entry


# =============================================================================
# TEST: Collect candidates from URLs
# =============================================================================

class TestCollectCandidates:
    """Tests for collect_candidates_from_urls function"""
    
    def test_collect_from_mixed_urls(self):
        """Should collect only candidate URLs from a list"""
        urls = [
            "https://trust.example.com",
            "https://www.example.com/about",
            "https://docs.example.com/api",
            "https://blog.example.com/post",
            "https://example.com/security",
        ]
        
        candidates = collect_candidates_from_urls("Example Corp", urls)
        
        assert len(candidates) == 3
        
        # Check types
        types = [c.candidate_type for c in candidates]
        assert CandidateType.TRUST_CENTER in types
        assert CandidateType.DOCS in types
        assert CandidateType.SECURITY_PAGE in types
    
    def test_collect_preserves_vendor_name(self):
        """Collected candidates should have correct vendor_name"""
        candidates = collect_candidates_from_urls(
            "Tabnine",
            ["https://trust.tabnine.com"]
        )
        
        assert len(candidates) == 1
        assert candidates[0].vendor_name == "Tabnine"
    
    def test_collect_empty_list(self):
        """Empty URL list should return empty candidates"""
        candidates = collect_candidates_from_urls("Example", [])
        assert candidates == []
    
    def test_collect_no_candidates(self):
        """URLs with no candidates should return empty list"""
        urls = [
            "https://www.example.com",
            "https://blog.example.com",
        ]
        candidates = collect_candidates_from_urls("Example", urls)
        assert candidates == []


# =============================================================================
# TEST: Build registry entry from candidates
# =============================================================================

class TestBuildRegistryEntry:
    """Tests for build_registry_entry_from_candidates function"""
    
    def test_build_from_confirmed_candidates(self):
        """Should build registry entry from confirmed candidates"""
        candidates = [
            CandidateVendorUrl(
                vendor_name="Example",
                candidate_url="https://trust.example.com",
                candidate_type=CandidateType.TRUST_CENTER,
                confidence=0.9,
                match_reason="subdomain",
                status=CandidateStatus.CONFIRMED,
            ),
            CandidateVendorUrl(
                vendor_name="Example",
                candidate_url="https://docs.example.com",
                candidate_type=CandidateType.DOCS,
                confidence=0.8,
                match_reason="subdomain",
                status=CandidateStatus.CONFIRMED,
            ),
        ]
        
        entry = build_registry_entry_from_candidates("Example", candidates)
        
        assert entry["vendor_name"] == "Example"
        assert entry["trust_center_url"] == "https://trust.example.com"
        assert entry["docs_url"] == "https://docs.example.com"
    
    def test_build_excludes_pending(self):
        """Should exclude pending candidates"""
        candidates = [
            CandidateVendorUrl(
                vendor_name="Example",
                candidate_url="https://trust.example.com",
                candidate_type=CandidateType.TRUST_CENTER,
                confidence=0.9,
                match_reason="subdomain",
                status=CandidateStatus.PENDING,  # Not confirmed!
            ),
        ]
        
        entry = build_registry_entry_from_candidates("Example", candidates)
        
        assert "trust_center_url" not in entry
    
    def test_build_takes_highest_confidence(self):
        """Should take highest confidence candidate for each type"""
        candidates = [
            CandidateVendorUrl(
                vendor_name="Example",
                candidate_url="https://trust.example.com/old",
                candidate_type=CandidateType.TRUST_CENTER,
                confidence=0.6,
                match_reason="path",
                status=CandidateStatus.CONFIRMED,
            ),
            CandidateVendorUrl(
                vendor_name="Example",
                candidate_url="https://trust.example.com/new",
                candidate_type=CandidateType.TRUST_CENTER,
                confidence=0.9,
                match_reason="subdomain_and_path",
                status=CandidateStatus.CONFIRMED,
            ),
        ]
        
        entry = build_registry_entry_from_candidates("Example", candidates)
        
        assert entry["trust_center_url"] == "https://trust.example.com/new"


# =============================================================================
# TEST: CandidateVendorUrl dataclass
# =============================================================================

class TestCandidateVendorUrl:
    """Tests for CandidateVendorUrl dataclass"""
    
    def test_default_status_is_pending(self):
        """Default status should be PENDING"""
        candidate = CandidateVendorUrl(
            vendor_name="Example",
            candidate_url="https://trust.example.com",
            candidate_type=CandidateType.TRUST_CENTER,
            confidence=0.8,
            match_reason="subdomain",
        )
        assert candidate.status == CandidateStatus.PENDING
    
    def test_to_dict(self):
        """to_dict should produce correct structure"""
        candidate = CandidateVendorUrl(
            vendor_name="Example",
            candidate_url="https://trust.example.com",
            candidate_type=CandidateType.TRUST_CENTER,
            confidence=0.8,
            match_reason="subdomain",
            normalized_domain="trust.example.com",
        )
        
        d = candidate.to_dict()
        
        assert d["vendor_name"] == "Example"
        assert d["candidate_url"] == "https://trust.example.com"
        assert d["candidate_type"] == "trust_center"
        assert d["confidence"] == 0.8
        assert d["status"] == "pending"


# =============================================================================
# TEST: Novel vendor workflow (integration)
# =============================================================================

class TestNovelVendorWorkflow:
    """Integration tests for the novel vendor bootstrap workflow"""
    
    def test_full_workflow_no_registry(self):
        """
        Test complete workflow for a novel vendor:
        1. Discover URLs
        2. Identify candidates
        3. Confirm candidates
        4. Build registry entry
        """
        # Step 1: Discovered URLs during research
        discovered_urls = [
            "https://trust.newvendor.com/security",
            "https://www.newvendor.com/about",
            "https://docs.newvendor.com/api",
            "https://techcrunch.com/article/newvendor",
            "https://newvendor.com/privacy-policy",
        ]
        
        # Step 2: Identify candidates
        candidates = collect_candidates_from_urls("NewVendor", discovered_urls)
        
        assert len(candidates) == 3  # trust, docs, privacy
        
        # Step 3: Confirm candidates (simulated review)
        for c in candidates:
            c.status = CandidateStatus.CONFIRMED
        
        # Step 4: Build registry entry
        entry = build_registry_entry_from_candidates("NewVendor", candidates)
        
        assert entry["vendor_name"] == "NewVendor"
        assert "trust_center_url" in entry
        assert "docs_url" in entry
        assert "privacy_page_url" in entry
    
    def test_candidate_does_not_affect_source_type(self):
        """
        CRITICAL: Candidate identification must NOT affect source_type.
        
        Even if a URL is identified as a candidate, source_type
        must still return "third_party" until promoted to registry.
        """
        from source_classifier import classify_source
        
        # Novel vendor with no registry entry
        vendor_urls = []  # Empty - novel vendor
        
        # URL that matches candidate patterns
        url = "https://trust.newvendor.com/soc2"
        
        # Candidate analysis says it looks like a trust center
        candidate_result = analyze_candidate(url)
        assert candidate_result.is_candidate is True
        assert candidate_result.candidate_type == CandidateType.TRUST_CENTER
        
        # BUT source_type classification says third_party
        classification = classify_source(url, vendor_urls)
        assert classification.source_type == "third_party"
        assert classification.match_reason == "no_registry_urls"
    
    def test_promoted_candidate_becomes_vendor(self):
        """
        After promotion, the URL should be classified as vendor.
        """
        from source_classifier import classify_source
        
        # Simulate promoted registry entry
        promoted_urls = [
            {"type": "trust_center", "url": "https://trust.newvendor.com"},
        ]
        
        # Now classification returns vendor
        classification = classify_source(
            "https://trust.newvendor.com/soc2",
            promoted_urls
        )
        assert classification.source_type == "vendor"
        assert classification.match_reason == "exact_domain_match"


# =============================================================================
# TEST: Anti-hallucination guarantees
# =============================================================================

class TestAntiHallucinationGuarantees:
    """Tests ensuring candidate system doesn't weaken anti-hallucination"""
    
    def test_candidate_confidence_never_affects_source_type(self):
        """High confidence candidates must still be third_party without registry"""
        from source_classifier import classify_source
        
        # High confidence candidate
        result = analyze_candidate("https://trust.example.com/compliance")
        assert result.confidence == CONFIDENCE_SUBDOMAIN_AND_PATH  # 0.9
        
        # Still third_party without registry
        classification = classify_source("https://trust.example.com/compliance", [])
        assert classification.source_type == "third_party"
    
    def test_substring_matching_not_used_in_candidates(self):
        """
        Candidate identification uses URL structure patterns,
        NOT vendor name substring matching.
        """
        # "tabnine" appears in URL but that's not how we identify it
        result = analyze_candidate("https://trust.tabnine.com")
        
        # It's a candidate because of "trust" subdomain pattern
        assert result.is_candidate is True
        assert result.subdomain_match == "trust"
        
        # Not because "tabnine" matched anything
        # (There's no vendor_name parameter to analyze_candidate)
    
    def test_fake_trust_subdomain_on_different_domain(self):
        """
        A malicious site with trust.* subdomain is still just a candidate.
        It becomes third_party when classified against any vendor.
        """
        from source_classifier import classify_source
        
        # Malicious site that happens to have trust subdomain
        evil_url = "https://trust.malicious-site.com/fake-compliance"
        
        # It IS identified as a candidate (based on URL structure)
        candidate = analyze_candidate(evil_url)
        assert candidate.is_candidate is True
        
        # But it's NOT classified as vendor for any real vendor
        tabnine_urls = [
            {"type": "trust_center", "url": "https://trust.tabnine.com"},
        ]
        classification = classify_source(evil_url, tabnine_urls)
        assert classification.source_type == "third_party"
