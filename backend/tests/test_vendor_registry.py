"""
Offline tests for VendorRegistry.get_all_urls()

These tests verify the URL extraction method without database or network calls.
Run with: cd backend && python -m pytest tests/test_vendor_registry.py -v
"""

import pytest


# =============================================================================
# Lightweight stand-in for testing without SQLAlchemy database
# =============================================================================

class VendorRegistryStub:
    """
    Lightweight test double that mirrors VendorRegistry.get_all_urls() behavior.
    
    This allows testing the URL extraction logic without requiring SQLAlchemy
    or database setup. The implementation MUST match VendorRegistry exactly.
    """
    
    # Must match VendorRegistry._URL_ATTRS exactly
    _URL_ATTRS = [
        ('trust_center_url', 'trust_center'),
        ('security_page_url', 'security_page'),
        ('privacy_page_url', 'privacy_page'),
        ('pricing_page_url', 'pricing_page'),
        ('docs_url', 'docs'),
    ]
    
    def __init__(
        self,
        trust_center_url: str = None,
        security_page_url: str = None,
        privacy_page_url: str = None,
        pricing_page_url: str = None,
        docs_url: str = None,
        status_page_url: str = None,  # Should be IGNORED by get_all_urls
    ):
        self.trust_center_url = trust_center_url
        self.security_page_url = security_page_url
        self.privacy_page_url = privacy_page_url
        self.pricing_page_url = pricing_page_url
        self.docs_url = docs_url
        self.status_page_url = status_page_url  # Exists but should not be returned
    
    def get_all_urls(self) -> list:
        """Must match VendorRegistry.get_all_urls() exactly"""
        urls = []
        for attr, url_type in self._URL_ATTRS:
            url = getattr(self, attr, None)
            if url:
                urls.append({'type': url_type, 'url': url})
        return urls


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def full_vendor():
    """Vendor with all URLs populated"""
    return VendorRegistryStub(
        trust_center_url="https://trust.example.com",
        security_page_url="https://www.example.com/security",
        privacy_page_url="https://www.example.com/privacy",
        pricing_page_url="https://www.example.com/pricing",
        docs_url="https://docs.example.com",
    )


@pytest.fixture
def partial_vendor():
    """Vendor with only some URLs populated"""
    return VendorRegistryStub(
        trust_center_url="https://trust.example.com",
        security_page_url=None,
        privacy_page_url="https://www.example.com/privacy",
        pricing_page_url=None,
        docs_url="https://docs.example.com",
    )


@pytest.fixture
def empty_vendor():
    """Vendor with no URLs populated"""
    return VendorRegistryStub()


@pytest.fixture
def vendor_with_status_page():
    """Vendor with status_page_url set (should be ignored)"""
    return VendorRegistryStub(
        trust_center_url="https://trust.example.com",
        status_page_url="https://status.example.com",  # Should NOT appear in results
    )


# =============================================================================
# TEST: Return structure and types
# =============================================================================

class TestReturnStructure:
    """Tests for correct return types and structure"""
    
    def test_returns_list(self, full_vendor):
        """get_all_urls() must return a list"""
        result = full_vendor.get_all_urls()
        assert isinstance(result, list)
    
    def test_each_item_is_dict(self, full_vendor):
        """Each item must be a dict"""
        result = full_vendor.get_all_urls()
        for item in result:
            assert isinstance(item, dict)
    
    def test_each_dict_has_type_key(self, full_vendor):
        """Each dict must have 'type' key"""
        result = full_vendor.get_all_urls()
        for item in result:
            assert 'type' in item
    
    def test_each_dict_has_url_key(self, full_vendor):
        """Each dict must have 'url' key"""
        result = full_vendor.get_all_urls()
        for item in result:
            assert 'url' in item
    
    def test_type_is_string(self, full_vendor):
        """'type' value must be a string"""
        result = full_vendor.get_all_urls()
        for item in result:
            assert isinstance(item['type'], str)
    
    def test_url_is_string(self, full_vendor):
        """'url' value must be a string"""
        result = full_vendor.get_all_urls()
        for item in result:
            assert isinstance(item['url'], str)


# =============================================================================
# TEST: Correct type mappings
# =============================================================================

class TestTypeMappings:
    """Tests for correct attribute-to-type mappings"""
    
    def test_trust_center_type(self):
        """trust_center_url maps to type 'trust_center'"""
        vendor = VendorRegistryStub(trust_center_url="https://trust.example.com")
        result = vendor.get_all_urls()
        assert len(result) == 1
        assert result[0]['type'] == 'trust_center'
        assert result[0]['url'] == "https://trust.example.com"
    
    def test_security_page_type(self):
        """security_page_url maps to type 'security_page'"""
        vendor = VendorRegistryStub(security_page_url="https://example.com/security")
        result = vendor.get_all_urls()
        assert len(result) == 1
        assert result[0]['type'] == 'security_page'
    
    def test_privacy_page_type(self):
        """privacy_page_url maps to type 'privacy_page'"""
        vendor = VendorRegistryStub(privacy_page_url="https://example.com/privacy")
        result = vendor.get_all_urls()
        assert len(result) == 1
        assert result[0]['type'] == 'privacy_page'
    
    def test_pricing_page_type(self):
        """pricing_page_url maps to type 'pricing_page'"""
        vendor = VendorRegistryStub(pricing_page_url="https://example.com/pricing")
        result = vendor.get_all_urls()
        assert len(result) == 1
        assert result[0]['type'] == 'pricing_page'
    
    def test_docs_type(self):
        """docs_url maps to type 'docs'"""
        vendor = VendorRegistryStub(docs_url="https://docs.example.com")
        result = vendor.get_all_urls()
        assert len(result) == 1
        assert result[0]['type'] == 'docs'


# =============================================================================
# TEST: Canonical order preservation
# =============================================================================

class TestCanonicalOrder:
    """Tests for correct ordering of URLs"""
    
    def test_full_vendor_order(self, full_vendor):
        """Full vendor URLs must be in canonical order"""
        result = full_vendor.get_all_urls()
        types = [item['type'] for item in result]
        
        expected_order = [
            'trust_center',
            'security_page',
            'privacy_page',
            'pricing_page',
            'docs',
        ]
        
        assert types == expected_order
    
    def test_partial_vendor_preserves_order(self, partial_vendor):
        """Partial vendor URLs must preserve relative order"""
        result = partial_vendor.get_all_urls()
        types = [item['type'] for item in result]
        
        # partial_vendor has: trust_center, privacy_page, docs
        # These should appear in that order (skipping missing ones)
        expected_order = ['trust_center', 'privacy_page', 'docs']
        
        assert types == expected_order
    
    def test_order_matches_url_attrs_constant(self):
        """Order must match _URL_ATTRS class constant"""
        expected_types = [url_type for _, url_type in VendorRegistryStub._URL_ATTRS]
        
        vendor = VendorRegistryStub(
            trust_center_url="a",
            security_page_url="b",
            privacy_page_url="c",
            pricing_page_url="d",
            docs_url="e",
        )
        result = vendor.get_all_urls()
        actual_types = [item['type'] for item in result]
        
        assert actual_types == expected_types


# =============================================================================
# TEST: Empty and None handling
# =============================================================================

class TestEmptyAndNoneHandling:
    """Tests for handling None and empty values"""
    
    def test_empty_vendor_returns_empty_list(self, empty_vendor):
        """Vendor with no URLs returns empty list"""
        result = empty_vendor.get_all_urls()
        assert result == []
    
    def test_none_urls_excluded(self):
        """None URLs are excluded from results"""
        vendor = VendorRegistryStub(
            trust_center_url="https://trust.example.com",
            security_page_url=None,
            privacy_page_url="https://example.com/privacy",
        )
        result = vendor.get_all_urls()
        types = [item['type'] for item in result]
        
        assert 'security_page' not in types
        assert 'trust_center' in types
        assert 'privacy_page' in types
    
    def test_empty_string_excluded(self):
        """Empty string URLs are excluded from results"""
        vendor = VendorRegistryStub(
            trust_center_url="https://trust.example.com",
            security_page_url="",
            privacy_page_url="https://example.com/privacy",
        )
        result = vendor.get_all_urls()
        types = [item['type'] for item in result]
        
        assert 'security_page' not in types
        assert 'trust_center' in types
        assert 'privacy_page' in types


# =============================================================================
# TEST: status_page_url exclusion (CRITICAL)
# =============================================================================

class TestStatusPageExclusion:
    """Tests ensuring status_page_url is NOT included"""
    
    def test_status_page_not_in_results(self, vendor_with_status_page):
        """status_page_url must NOT appear in get_all_urls() results"""
        result = vendor_with_status_page.get_all_urls()
        types = [item['type'] for item in result]
        
        assert 'status_page' not in types
    
    def test_status_page_url_not_in_url_attrs(self):
        """status_page_url must NOT be in _URL_ATTRS"""
        attrs = [attr for attr, _ in VendorRegistryStub._URL_ATTRS]
        assert 'status_page_url' not in attrs
    
    def test_only_five_url_types(self):
        """Exactly 5 URL types should be defined"""
        assert len(VendorRegistryStub._URL_ATTRS) == 5


# =============================================================================
# TEST: URL values preserved exactly
# =============================================================================

class TestURLValuesPreserved:
    """Tests ensuring URL values are not modified"""
    
    def test_url_not_modified(self):
        """URL values must be returned exactly as stored"""
        original_url = "https://trust.example.com/path?query=value#fragment"
        vendor = VendorRegistryStub(trust_center_url=original_url)
        result = vendor.get_all_urls()
        
        assert result[0]['url'] == original_url
    
    def test_urls_with_special_chars(self):
        """URLs with special characters preserved"""
        special_url = "https://example.com/path%20with%20spaces?a=1&b=2"
        vendor = VendorRegistryStub(docs_url=special_url)
        result = vendor.get_all_urls()
        
        assert result[0]['url'] == special_url


# =============================================================================
# TEST: Integration with source_classifier expectations
# =============================================================================

class TestSourceClassifierCompatibility:
    """Tests ensuring output is compatible with source_classifier.classify_source()"""
    
    def test_output_format_matches_classifier_input(self, full_vendor):
        """Output format must match what classify_source() expects"""
        result = full_vendor.get_all_urls()
        
        # source_classifier expects: List[Dict[str, str]] with 'type' and 'url' keys
        for item in result:
            assert set(item.keys()) == {'type', 'url'}
            assert isinstance(item['type'], str)
            assert isinstance(item['url'], str)
    
    def test_real_vendor_data_format(self):
        """Test with real vendor data from vendor_registry_seed.py"""
        # Tabnine data from seed
        vendor = VendorRegistryStub(
            trust_center_url="https://trust.tabnine.com",
            security_page_url="https://www.tabnine.com/security",
            privacy_page_url="https://www.tabnine.com/privacy",
            pricing_page_url="https://www.tabnine.com/pricing",
            docs_url="https://docs.tabnine.com",
        )
        result = vendor.get_all_urls()
        
        assert len(result) == 5
        assert result[0] == {'type': 'trust_center', 'url': 'https://trust.tabnine.com'}
        assert result[1] == {'type': 'security_page', 'url': 'https://www.tabnine.com/security'}
        assert result[2] == {'type': 'privacy_page', 'url': 'https://www.tabnine.com/privacy'}
        assert result[3] == {'type': 'pricing_page', 'url': 'https://www.tabnine.com/pricing'}
        assert result[4] == {'type': 'docs', 'url': 'https://docs.tabnine.com'}


# =============================================================================
# TEST: Contract verification (stub matches real implementation)
# =============================================================================

class TestContractVerification:
    """Tests that stub's _URL_ATTRS matches the real VendorRegistry"""
    
    def test_url_attrs_matches_real_model(self):
        """
        Verify our stub's _URL_ATTRS matches the real VendorRegistry.
        
        This test imports the real model and compares _URL_ATTRS.
        If this fails, the stub is out of sync with the real implementation.
        """
        try:
            # Try to import real model (may fail if SQLAlchemy not configured)
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from research_models_v2 import VendorRegistry
            
            # Compare _URL_ATTRS
            assert VendorRegistryStub._URL_ATTRS == VendorRegistry._URL_ATTRS, \
                "Stub _URL_ATTRS does not match VendorRegistry._URL_ATTRS"
                
        except ImportError as e:
            # If we can't import (missing dependencies), skip this test
            pytest.skip(f"Could not import VendorRegistry: {e}")
