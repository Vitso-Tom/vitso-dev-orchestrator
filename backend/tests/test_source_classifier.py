"""
Offline tests for source_classifier.py

These tests verify deterministic source classification without network or LLM calls.
Run with: cd backend && python -m pytest tests/test_source_classifier.py -v
"""

import pytest
from source_classifier import classify_source, ClassificationResult, normalize_domain


# =============================================================================
# FIXTURES: Sample vendor URL configurations (mirrors VendorRegistry.get_all_urls())
# =============================================================================

@pytest.fixture
def tabnine_urls():
    """Tabnine vendor URLs from registry"""
    return [
        {"type": "trust_center", "url": "https://trust.tabnine.com"},
        {"type": "security_page", "url": "https://www.tabnine.com/security"},
        {"type": "privacy_page", "url": "https://www.tabnine.com/privacy"},
        {"type": "pricing_page", "url": "https://www.tabnine.com/pricing"},
        {"type": "docs", "url": "https://docs.tabnine.com"},
    ]


@pytest.fixture
def anthropic_urls():
    """Anthropic vendor URLs from registry"""
    return [
        {"type": "trust_center", "url": "https://trust.anthropic.com"},
        {"type": "security_page", "url": "https://www.anthropic.com/security"},
        {"type": "privacy_page", "url": "https://privacy.anthropic.com"},
        {"type": "pricing_page", "url": "https://www.anthropic.com/pricing"},
        {"type": "docs", "url": "https://docs.anthropic.com"},
    ]


@pytest.fixture
def microsoft_urls():
    """Microsoft vendor URLs from registry"""
    return [
        {"type": "trust_center", "url": "https://www.microsoft.com/en-us/trust-center"},
        {"type": "security_page", "url": "https://azure.microsoft.com/en-us/explore/security"},
        {"type": "privacy_page", "url": "https://privacy.microsoft.com"},
        {"type": "pricing_page", "url": "https://azure.microsoft.com/en-us/pricing"},
        {"type": "docs", "url": "https://docs.microsoft.com"},
    ]


@pytest.fixture
def empty_urls():
    """Empty vendor URLs (unknown vendor)"""
    return []


# =============================================================================
# TEST: normalize_domain() helper function
# =============================================================================

class TestNormalizeDomain:
    """Tests for domain normalization"""
    
    def test_strips_www(self):
        assert normalize_domain("https://www.example.com/path") == "example.com"
    
    def test_preserves_subdomain(self):
        assert normalize_domain("https://trust.example.com") == "trust.example.com"
    
    def test_strips_www_from_subdomain(self):
        # www.trust.example.com -> trust.example.com (www stripped from front)
        assert normalize_domain("https://www.trust.example.com") == "trust.example.com"
    
    def test_lowercase(self):
        assert normalize_domain("https://WWW.EXAMPLE.COM/PATH") == "example.com"
    
    def test_strips_trailing_slash(self):
        domain = normalize_domain("https://example.com/")
        assert domain == "example.com"
    
    def test_handles_http(self):
        assert normalize_domain("http://example.com") == "example.com"
    
    def test_handles_port(self):
        # Ports should be stripped for domain comparison
        assert normalize_domain("https://example.com:8080/path") == "example.com"
    
    def test_empty_string(self):
        assert normalize_domain("") is None
    
    def test_none(self):
        assert normalize_domain(None) is None
    
    def test_invalid_url(self):
        assert normalize_domain("not a url") is None
    
    def test_url_without_scheme(self):
        # URLs without scheme should still work
        assert normalize_domain("example.com/path") == "example.com"


# =============================================================================
# TEST: Exact domain matching (CORE FUNCTIONALITY)
# =============================================================================

class TestExactDomainMatching:
    """Tests for exact domain matching - the core classification logic"""
    
    def test_exact_trust_center_match(self, tabnine_urls):
        """Trust center URL should match as vendor"""
        result = classify_source("https://trust.tabnine.com/compliance", tabnine_urls)
        assert result.source_type == "vendor"
        assert result.match_reason == "exact_domain_match"
        assert result.matched_url_type == "trust_center"
        assert result.matched_domain == "trust.tabnine.com"
    
    def test_exact_security_page_match(self, tabnine_urls):
        """Security page URL should match as vendor"""
        result = classify_source("https://www.tabnine.com/security/overview", tabnine_urls)
        assert result.source_type == "vendor"
        assert result.match_reason == "exact_domain_match"
        assert result.matched_url_type == "security_page"
    
    def test_exact_docs_match(self, tabnine_urls):
        """Docs URL should match as vendor"""
        result = classify_source("https://docs.tabnine.com/getting-started", tabnine_urls)
        assert result.source_type == "vendor"
        assert result.match_reason == "exact_domain_match"
        assert result.matched_url_type == "docs"
    
    def test_different_path_same_domain(self, tabnine_urls):
        """Different path on same domain should still match"""
        result = classify_source("https://trust.tabnine.com/some/deep/path/here", tabnine_urls)
        assert result.source_type == "vendor"
        assert result.match_reason == "exact_domain_match"
    
    def test_query_params_same_domain(self, tabnine_urls):
        """URL with query params on same domain should match"""
        result = classify_source("https://trust.tabnine.com?section=soc2&lang=en", tabnine_urls)
        assert result.source_type == "vendor"
        assert result.match_reason == "exact_domain_match"


# =============================================================================
# TEST: Third-party classification
# =============================================================================

class TestThirdPartyClassification:
    """Tests for URLs that should be classified as third_party"""
    
    def test_completely_different_domain(self, tabnine_urls):
        """Completely unrelated domain should be third_party"""
        result = classify_source("https://techcrunch.com/article/tabnine-funding", tabnine_urls)
        assert result.source_type == "third_party"
        assert result.match_reason == "no_match"
    
    def test_news_site(self, tabnine_urls):
        """News article about vendor should be third_party"""
        result = classify_source("https://www.reuters.com/technology/tabnine-security", tabnine_urls)
        assert result.source_type == "third_party"
        assert result.match_reason == "no_match"
    
    def test_blog_post(self, anthropic_urls):
        """Third-party blog should be third_party"""
        result = classify_source("https://medium.com/anthropic-claude-review", anthropic_urls)
        assert result.source_type == "third_party"
        assert result.match_reason == "no_match"
    
    def test_compliance_aggregator(self, tabnine_urls):
        """Compliance aggregator sites should be third_party"""
        result = classify_source("https://securityscorecard.com/vendor/tabnine", tabnine_urls)
        assert result.source_type == "third_party"
        assert result.match_reason == "no_match"


# =============================================================================
# TEST: Substring attack prevention (SECURITY CRITICAL)
# =============================================================================

class TestSubstringAttackPrevention:
    """Tests ensuring substring matching does NOT happen"""
    
    def test_vendor_domain_as_subdomain_of_attacker(self, tabnine_urls):
        """tabnine.com.evil.com should NOT match tabnine.com"""
        result = classify_source("https://tabnine.com.evil.com/trust", tabnine_urls)
        assert result.source_type == "third_party"
        assert result.match_reason == "no_match"
    
    def test_vendor_domain_in_path(self, tabnine_urls):
        """evil.com/tabnine.com should NOT match"""
        result = classify_source("https://evil.com/tabnine.com/trust", tabnine_urls)
        assert result.source_type == "third_party"
        assert result.match_reason == "no_match"
    
    def test_vendor_domain_in_query(self, tabnine_urls):
        """evil.com?redirect=tabnine.com should NOT match"""
        result = classify_source("https://evil.com?redirect=https://trust.tabnine.com", tabnine_urls)
        assert result.source_type == "third_party"
        assert result.match_reason == "no_match"
    
    def test_similar_domain_name(self, tabnine_urls):
        """tabnine-security.com should NOT match tabnine.com"""
        result = classify_source("https://tabnine-security.com/trust", tabnine_urls)
        assert result.source_type == "third_party"
        assert result.match_reason == "no_match"
    
    def test_typosquat_domain(self, tabnine_urls):
        """tabniine.com (typo) should NOT match tabnine.com"""
        result = classify_source("https://trust.tabniine.com/compliance", tabnine_urls)
        assert result.source_type == "third_party"
        assert result.match_reason == "no_match"
    
    def test_vendor_name_different_tld(self, tabnine_urls):
        """tabnine.io should NOT match tabnine.com"""
        result = classify_source("https://trust.tabnine.io/compliance", tabnine_urls)
        assert result.source_type == "third_party"
        assert result.match_reason == "no_match"
    
    def test_partial_subdomain_match(self, anthropic_urls):
        """notrust.anthropic.com should NOT match trust.anthropic.com"""
        # This tests that we match the FULL domain, not just check if it contains the vendor domain
        result = classify_source("https://notrust.anthropic.com", anthropic_urls)
        # This SHOULD match because the base domain anthropic.com is in vendor URLs
        # Wait - let me reconsider. The vendor URLs are:
        # - trust.anthropic.com
        # - www.anthropic.com  
        # - privacy.anthropic.com
        # - docs.anthropic.com
        # notrust.anthropic.com is NOT in that list - but it IS a subdomain of anthropic.com
        # The question is: should ANY subdomain of a vendor domain match?
        # 
        # Design decision: We match EXACT domains from the registry only.
        # If vendor has www.anthropic.com registered, then notrust.anthropic.com does NOT match.
        assert result.source_type == "third_party"
        assert result.match_reason == "no_match"


# =============================================================================
# TEST: URL normalization (www, scheme, case)
# =============================================================================

class TestURLNormalization:
    """Tests for URL normalization before matching"""
    
    def test_www_vs_no_www_match(self, tabnine_urls):
        """www.tabnine.com should match tabnine.com in registry"""
        # Registry has www.tabnine.com/security, test without www
        result = classify_source("https://tabnine.com/security", tabnine_urls)
        assert result.source_type == "vendor"
        assert result.match_reason == "exact_domain_match"
    
    def test_no_www_vs_www_match(self, tabnine_urls):
        """tabnine.com should match www.tabnine.com in registry"""
        # Registry has www.tabnine.com, test with www on a page that might not have it
        result = classify_source("https://www.tabnine.com/blog", tabnine_urls)
        assert result.source_type == "vendor"
    
    def test_https_vs_http(self, tabnine_urls):
        """http:// should match https:// registry entries"""
        result = classify_source("http://trust.tabnine.com/compliance", tabnine_urls)
        assert result.source_type == "vendor"
        assert result.match_reason == "exact_domain_match"
    
    def test_case_insensitive_domain(self, tabnine_urls):
        """TRUST.TABNINE.COM should match trust.tabnine.com"""
        result = classify_source("https://TRUST.TABNINE.COM/compliance", tabnine_urls)
        assert result.source_type == "vendor"
        assert result.match_reason == "exact_domain_match"
    
    def test_mixed_case(self, tabnine_urls):
        """TrUsT.TabNine.COM should match"""
        result = classify_source("https://TrUsT.TabNine.COM/path", tabnine_urls)
        assert result.source_type == "vendor"


# =============================================================================
# TEST: Edge cases and error handling
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling"""
    
    def test_empty_url(self, tabnine_urls):
        """Empty URL should return third_party with appropriate reason"""
        result = classify_source("", tabnine_urls)
        assert result.source_type == "third_party"
        assert result.match_reason == "no_url"
    
    def test_none_url(self, tabnine_urls):
        """None URL should return third_party with appropriate reason"""
        result = classify_source(None, tabnine_urls)
        assert result.source_type == "third_party"
        assert result.match_reason == "no_url"
    
    def test_invalid_url(self, tabnine_urls):
        """Invalid URL should return third_party with appropriate reason"""
        result = classify_source("not a valid url at all", tabnine_urls)
        assert result.source_type == "third_party"
        assert result.match_reason == "invalid_url"
    
    def test_empty_vendor_urls(self, empty_urls):
        """Empty vendor URLs (unknown vendor) should return third_party"""
        result = classify_source("https://trust.tabnine.com", empty_urls)
        assert result.source_type == "third_party"
        assert result.match_reason == "no_registry_urls"
    
    def test_none_vendor_urls(self):
        """None vendor URLs should return third_party"""
        result = classify_source("https://trust.tabnine.com", None)
        assert result.source_type == "third_party"
        assert result.match_reason == "no_registry_urls"
    
    def test_malformed_registry_entry(self, tabnine_urls):
        """Registry entry with None URL should be skipped"""
        urls_with_none = tabnine_urls + [{"type": "status_page", "url": None}]
        result = classify_source("https://trust.tabnine.com", urls_with_none)
        assert result.source_type == "vendor"
        assert result.match_reason == "exact_domain_match"
    
    def test_url_with_fragment(self, tabnine_urls):
        """URL with fragment should still match"""
        result = classify_source("https://trust.tabnine.com/compliance#soc2", tabnine_urls)
        assert result.source_type == "vendor"
        assert result.match_reason == "exact_domain_match"
    
    def test_url_with_port(self, tabnine_urls):
        """URL with port should match domain without port in registry"""
        result = classify_source("https://trust.tabnine.com:443/compliance", tabnine_urls)
        assert result.source_type == "vendor"


# =============================================================================
# TEST: Cross-vendor isolation
# =============================================================================

class TestCrossVendorIsolation:
    """Tests ensuring vendors don't cross-match"""
    
    def test_tabnine_url_with_anthropic_registry(self, anthropic_urls):
        """Tabnine URL should be third_party when checking against Anthropic registry"""
        result = classify_source("https://trust.tabnine.com", anthropic_urls)
        assert result.source_type == "third_party"
        assert result.match_reason == "no_match"
    
    def test_anthropic_url_with_tabnine_registry(self, tabnine_urls):
        """Anthropic URL should be third_party when checking against Tabnine registry"""
        result = classify_source("https://trust.anthropic.com", tabnine_urls)
        assert result.source_type == "third_party"
        assert result.match_reason == "no_match"


# =============================================================================
# TEST: Complex vendor URLs (Microsoft/Azure)
# =============================================================================

class TestComplexVendorURLs:
    """Tests for vendors with complex URL patterns like Microsoft"""
    
    def test_azure_subdomain(self, microsoft_urls):
        """azure.microsoft.com should match"""
        result = classify_source("https://azure.microsoft.com/en-us/products/ai", microsoft_urls)
        assert result.source_type == "vendor"
        assert result.match_reason == "exact_domain_match"
    
    def test_docs_microsoft(self, microsoft_urls):
        """docs.microsoft.com should match"""
        result = classify_source("https://docs.microsoft.com/azure/security", microsoft_urls)
        assert result.source_type == "vendor"
    
    def test_privacy_microsoft(self, microsoft_urls):
        """privacy.microsoft.com should match"""
        result = classify_source("https://privacy.microsoft.com/privacystatement", microsoft_urls)
        assert result.source_type == "vendor"
    
    def test_unregistered_microsoft_subdomain(self, microsoft_urls):
        """random.microsoft.com (not in registry) should NOT match"""
        # Only registered subdomains should match
        result = classify_source("https://random.microsoft.com/page", microsoft_urls)
        assert result.source_type == "third_party"
        assert result.match_reason == "no_match"


# =============================================================================
# TEST: ClassificationResult dataclass
# =============================================================================

class TestClassificationResultDataclass:
    """Tests for ClassificationResult structure"""
    
    def test_result_has_required_fields(self, tabnine_urls):
        """Result should have all required fields"""
        result = classify_source("https://trust.tabnine.com", tabnine_urls)
        assert hasattr(result, 'source_type')
        assert hasattr(result, 'match_reason')
        assert hasattr(result, 'matched_url_type')
        assert hasattr(result, 'matched_domain')
    
    def test_result_source_type_values(self, tabnine_urls):
        """source_type should only be 'vendor' or 'third_party'"""
        result1 = classify_source("https://trust.tabnine.com", tabnine_urls)
        result2 = classify_source("https://example.com", tabnine_urls)
        
        assert result1.source_type in ("vendor", "third_party")
        assert result2.source_type in ("vendor", "third_party")
        assert result1.source_type == "vendor"
        assert result2.source_type == "third_party"
    
    def test_matched_url_type_none_for_third_party(self, tabnine_urls):
        """matched_url_type should be None for third_party"""
        result = classify_source("https://example.com", tabnine_urls)
        assert result.matched_url_type is None
    
    def test_matched_domain_none_for_third_party(self, tabnine_urls):
        """matched_domain should be None for third_party"""
        result = classify_source("https://example.com", tabnine_urls)
        assert result.matched_domain is None


# =============================================================================
# TEST: Determinism
# =============================================================================

class TestDeterminism:
    """Tests ensuring classification is deterministic"""
    
    def test_same_input_same_output(self, tabnine_urls):
        """Same inputs should always produce same outputs"""
        url = "https://trust.tabnine.com/compliance?v=2"
        
        results = [classify_source(url, tabnine_urls) for _ in range(10)]
        
        assert all(r.source_type == results[0].source_type for r in results)
        assert all(r.match_reason == results[0].match_reason for r in results)
        assert all(r.matched_url_type == results[0].matched_url_type for r in results)
    
    def test_order_independence(self, tabnine_urls):
        """URL order in registry should not affect result"""
        import random
        
        url = "https://trust.tabnine.com/compliance"
        
        # Shuffle registry order multiple times
        results = []
        for _ in range(5):
            shuffled = tabnine_urls.copy()
            random.shuffle(shuffled)
            results.append(classify_source(url, shuffled))
        
        assert all(r.source_type == "vendor" for r in results)
        assert all(r.match_reason == "exact_domain_match" for r in results)
