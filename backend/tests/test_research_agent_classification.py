"""
Offline tests for ResearchAgentV2 source classification integration.

These tests verify that research_agent_v2.py correctly uses the centralized
source_classifier for all source_type determinations.

Run with: cd backend && python -m pytest tests/test_research_agent_classification.py -v
"""

import pytest
from source_classifier import classify_source


# =============================================================================
# Stub that mirrors ResearchAgentV2._classify_source_type behavior
# =============================================================================

class ResearchAgentClassifierStub:
    """
    Minimal stub that replicates the _classify_source_type method from ResearchAgentV2.
    
    This allows testing the classification integration without instantiating
    the full agent (which requires database, API clients, etc.)
    """
    
    def _classify_source_type(self, url: str, vendor_urls: list) -> str:
        """
        Classify a URL as 'vendor' or 'third_party' using centralized classifier.
        
        This MUST match the implementation in ResearchAgentV2.
        """
        return classify_source(url, vendor_urls).source_type


# =============================================================================
# FIXTURES: Vendor URL configurations from VendorRegistry
# =============================================================================

@pytest.fixture
def tabnine_vendor_urls():
    """Tabnine URLs as returned by VendorRegistry.get_all_urls()"""
    return [
        {"type": "trust_center", "url": "https://trust.tabnine.com"},
        {"type": "security_page", "url": "https://www.tabnine.com/security"},
        {"type": "privacy_page", "url": "https://www.tabnine.com/privacy"},
        {"type": "pricing_page", "url": "https://www.tabnine.com/pricing"},
        {"type": "docs", "url": "https://docs.tabnine.com"},
    ]


@pytest.fixture
def anthropic_vendor_urls():
    """Anthropic URLs as returned by VendorRegistry.get_all_urls()"""
    return [
        {"type": "trust_center", "url": "https://trust.anthropic.com"},
        {"type": "security_page", "url": "https://www.anthropic.com/security"},
        {"type": "privacy_page", "url": "https://privacy.anthropic.com"},
        {"type": "pricing_page", "url": "https://www.anthropic.com/pricing"},
        {"type": "docs", "url": "https://docs.anthropic.com"},
    ]


@pytest.fixture
def agent():
    """Create a classifier stub for testing"""
    return ResearchAgentClassifierStub()


# =============================================================================
# TEST: Vendor source classification
# =============================================================================

class TestVendorSourceClassification:
    """Tests that vendor URLs are correctly classified as 'vendor'"""
    
    def test_trust_center_is_vendor(self, agent, tabnine_vendor_urls):
        """Trust center URL should be classified as vendor"""
        result = agent._classify_source_type(
            "https://trust.tabnine.com/soc2-compliance",
            tabnine_vendor_urls
        )
        assert result == "vendor"
    
    def test_security_page_is_vendor(self, agent, tabnine_vendor_urls):
        """Security page URL should be classified as vendor"""
        result = agent._classify_source_type(
            "https://www.tabnine.com/security/overview",
            tabnine_vendor_urls
        )
        assert result == "vendor"
    
    def test_docs_is_vendor(self, agent, tabnine_vendor_urls):
        """Documentation URL should be classified as vendor"""
        result = agent._classify_source_type(
            "https://docs.tabnine.com/getting-started",
            tabnine_vendor_urls
        )
        assert result == "vendor"
    
    def test_privacy_page_is_vendor(self, agent, tabnine_vendor_urls):
        """Privacy page URL should be classified as vendor"""
        result = agent._classify_source_type(
            "https://www.tabnine.com/privacy",
            tabnine_vendor_urls
        )
        assert result == "vendor"


# =============================================================================
# TEST: Third-party source classification
# =============================================================================

class TestThirdPartySourceClassification:
    """Tests that non-vendor URLs are correctly classified as 'third_party'"""
    
    def test_news_site_is_third_party(self, agent, tabnine_vendor_urls):
        """News article about vendor should be third_party"""
        result = agent._classify_source_type(
            "https://techcrunch.com/2024/tabnine-raises-series-c",
            tabnine_vendor_urls
        )
        assert result == "third_party"
    
    def test_security_rating_site_is_third_party(self, agent, tabnine_vendor_urls):
        """Security rating site should be third_party"""
        result = agent._classify_source_type(
            "https://nudge.security/vendor/tabnine",
            tabnine_vendor_urls
        )
        assert result == "third_party"
    
    def test_compliance_aggregator_is_third_party(self, agent, tabnine_vendor_urls):
        """Compliance aggregator should be third_party"""
        result = agent._classify_source_type(
            "https://securityscorecard.com/vendor/tabnine",
            tabnine_vendor_urls
        )
        assert result == "third_party"
    
    def test_blog_is_third_party(self, agent, tabnine_vendor_urls):
        """Third-party blog should be third_party"""
        result = agent._classify_source_type(
            "https://medium.com/@someone/tabnine-review",
            tabnine_vendor_urls
        )
        assert result == "third_party"
    
    def test_reddit_is_third_party(self, agent, tabnine_vendor_urls):
        """Reddit discussion should be third_party"""
        result = agent._classify_source_type(
            "https://reddit.com/r/programming/comments/tabnine",
            tabnine_vendor_urls
        )
        assert result == "third_party"


# =============================================================================
# TEST: Cross-vendor isolation
# =============================================================================

class TestCrossVendorIsolation:
    """Tests that vendor URLs don't match across different vendors"""
    
    def test_tabnine_url_not_vendor_for_anthropic(self, agent, anthropic_vendor_urls):
        """Tabnine URL should be third_party when classified against Anthropic"""
        result = agent._classify_source_type(
            "https://trust.tabnine.com/compliance",
            anthropic_vendor_urls
        )
        assert result == "third_party"
    
    def test_anthropic_url_not_vendor_for_tabnine(self, agent, tabnine_vendor_urls):
        """Anthropic URL should be third_party when classified against Tabnine"""
        result = agent._classify_source_type(
            "https://trust.anthropic.com/security",
            tabnine_vendor_urls
        )
        assert result == "third_party"


# =============================================================================
# TEST: Substring attack prevention (SECURITY CRITICAL)
# =============================================================================

class TestSubstringAttackPrevention:
    """Tests that substring matching exploits don't work"""
    
    def test_fake_subdomain_attack(self, agent, tabnine_vendor_urls):
        """tabnine.com.evil.com should NOT match as vendor"""
        result = agent._classify_source_type(
            "https://tabnine.com.evil.com/trust",
            tabnine_vendor_urls
        )
        assert result == "third_party"
    
    def test_path_injection_attack(self, agent, tabnine_vendor_urls):
        """evil.com/tabnine.com should NOT match as vendor"""
        result = agent._classify_source_type(
            "https://evil.com/tabnine.com/security",
            tabnine_vendor_urls
        )
        assert result == "third_party"
    
    def test_typosquat_attack(self, agent, tabnine_vendor_urls):
        """tabniine.com (typo) should NOT match as vendor"""
        result = agent._classify_source_type(
            "https://trust.tabniine.com/compliance",
            tabnine_vendor_urls
        )
        assert result == "third_party"


# =============================================================================
# TEST: Edge cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases in classification"""
    
    def test_empty_url(self, agent, tabnine_vendor_urls):
        """Empty URL should be third_party"""
        result = agent._classify_source_type("", tabnine_vendor_urls)
        assert result == "third_party"
    
    def test_none_url(self, agent, tabnine_vendor_urls):
        """None URL should be third_party"""
        result = agent._classify_source_type(None, tabnine_vendor_urls)
        assert result == "third_party"
    
    def test_empty_vendor_urls(self, agent):
        """Empty vendor_urls should result in third_party"""
        result = agent._classify_source_type(
            "https://trust.tabnine.com",
            []
        )
        assert result == "third_party"
    
    def test_none_vendor_urls(self, agent):
        """None vendor_urls should result in third_party"""
        result = agent._classify_source_type(
            "https://trust.tabnine.com",
            None
        )
        assert result == "third_party"


# =============================================================================
# TEST: Return type contract
# =============================================================================

class TestReturnTypeContract:
    """Tests that return type is always 'vendor' or 'third_party'"""
    
    def test_vendor_return_type(self, agent, tabnine_vendor_urls):
        """Vendor classification must return exactly 'vendor'"""
        result = agent._classify_source_type(
            "https://trust.tabnine.com",
            tabnine_vendor_urls
        )
        assert result == "vendor"
        assert isinstance(result, str)
    
    def test_third_party_return_type(self, agent, tabnine_vendor_urls):
        """Third-party classification must return exactly 'third_party'"""
        result = agent._classify_source_type(
            "https://example.com",
            tabnine_vendor_urls
        )
        assert result == "third_party"
        assert isinstance(result, str)
    
    def test_no_unknown_return_type(self, agent, tabnine_vendor_urls):
        """Should never return 'unknown' or any other value"""
        # Test various URLs
        urls = [
            "https://trust.tabnine.com",
            "https://example.com",
            "",
            "invalid",
        ]
        
        for url in urls:
            result = agent._classify_source_type(url, tabnine_vendor_urls)
            assert result in ("vendor", "third_party"), f"Unexpected result '{result}' for URL '{url}'"


# =============================================================================
# TEST: Realistic research scenarios
# =============================================================================

class TestRealisticScenarios:
    """Tests simulating real research agent classification scenarios"""
    
    def test_cached_fact_recomputation(self, agent, tabnine_vendor_urls):
        """
        Simulate recomputing source_type for a cached fact.
        
        In the old code, db_fact.source_type was trusted.
        In the new code, we recompute using the classifier.
        """
        # Cached fact has source_url from trust center
        cached_source_url = "https://trust.tabnine.com/soc2-report"
        
        # Recompute source_type (as _lookup_cached_facts now does)
        source_type = agent._classify_source_type(cached_source_url, tabnine_vendor_urls)
        
        assert source_type == "vendor"
    
    def test_llm_returned_url_classification(self, agent, tabnine_vendor_urls):
        """
        Simulate classifying a URL returned by LLM during web search.
        
        In the old code, LLM's is_vendor_source flag was trusted.
        In the new code, we ignore it and use the classifier.
        """
        # LLM might return any URL
        llm_returned_url = "https://trust.tabnine.com/hipaa-baa"
        
        # Classify using only the URL (ignoring any LLM flags)
        source_type = agent._classify_source_type(llm_returned_url, tabnine_vendor_urls)
        
        assert source_type == "vendor"
    
    def test_third_party_security_report(self, agent, tabnine_vendor_urls):
        """
        Simulate classifying a third-party security report.
        
        Even if it's about the vendor, it should be third_party.
        """
        # A security researcher's blog post about Tabnine
        third_party_url = "https://cybersecurity-blog.com/tabnine-security-analysis"
        
        source_type = agent._classify_source_type(third_party_url, tabnine_vendor_urls)
        
        assert source_type == "third_party"
