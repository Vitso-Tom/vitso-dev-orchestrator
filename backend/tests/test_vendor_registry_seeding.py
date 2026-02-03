"""
Offline tests for vendor registry seeding at startup.

These tests verify:
1. VendorRegistry is seeded when empty
2. Seeding is idempotent (not called when rows exist)
3. No network or LLM required

Note: VendorRegistry uses PostgreSQL ARRAY type, so we mock the database layer
rather than using in-memory SQLite.

Run with: cd backend && python3 -m pytest tests/test_vendor_registry_seeding.py -v
"""

import pytest
from unittest.mock import MagicMock, patch


class TestVendorRegistrySeedingLogic:
    """Tests for vendor registry seeding logic."""
    
    def test_seed_called_when_registry_empty(self):
        """
        When VendorRegistry table has 0 rows, seed_vendor_registry should be called.
        """
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.count.return_value = 0  # Empty registry
        
        with patch('database.SessionLocal', return_value=mock_session):
            with patch('vendor_registry_seed.seed_vendor_registry') as mock_seed:
                mock_seed.return_value = {"added": 14, "updated": 0}
                
                # Import and call the function
                from database import _seed_vendor_registry_if_empty
                _seed_vendor_registry_if_empty()
                
                # Verify seed was called
                mock_seed.assert_called_once_with(mock_session)
    
    def test_seed_not_called_when_registry_has_rows(self):
        """
        When VendorRegistry table has rows, seed_vendor_registry should NOT be called.
        This ensures idempotency.
        """
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.count.return_value = 14  # Registry already populated
        
        with patch('database.SessionLocal', return_value=mock_session):
            with patch('vendor_registry_seed.seed_vendor_registry') as mock_seed:
                from database import _seed_vendor_registry_if_empty
                _seed_vendor_registry_if_empty()
                
                # Verify seed was NOT called
                mock_seed.assert_not_called()
    
    def test_session_closed_after_seeding(self):
        """Session should be closed even if seeding succeeds."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.count.return_value = 0
        
        with patch('database.SessionLocal', return_value=mock_session):
            with patch('vendor_registry_seed.seed_vendor_registry', return_value={"added": 14, "updated": 0}):
                from database import _seed_vendor_registry_if_empty
                _seed_vendor_registry_if_empty()
                
                mock_session.close.assert_called_once()
    
    def test_session_closed_on_exception(self):
        """Session should be closed even if an exception occurs."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.count.side_effect = Exception("DB error")
        
        with patch('database.SessionLocal', return_value=mock_session):
            from database import _seed_vendor_registry_if_empty
            
            with pytest.raises(Exception):
                _seed_vendor_registry_if_empty()
            
            mock_session.close.assert_called_once()


class TestVendorRegistrySeedData:
    """Tests for the seed data itself (no database required)."""
    
    def test_seed_data_has_vendors(self):
        """VENDOR_REGISTRY_SEED should contain vendor entries."""
        from vendor_registry_seed import VENDOR_REGISTRY_SEED
        
        assert len(VENDOR_REGISTRY_SEED) > 0, "Seed data should have vendors"
    
    def test_tabnine_in_seed_data(self):
        """Tabnine should be in the seed data."""
        from vendor_registry_seed import VENDOR_REGISTRY_SEED
        
        vendor_names = [v["vendor_name"] for v in VENDOR_REGISTRY_SEED]
        assert "Tabnine" in vendor_names, "Tabnine should be in seed data"
    
    def test_tabnine_has_trust_center_url(self):
        """Tabnine entry should have trust_center_url."""
        from vendor_registry_seed import VENDOR_REGISTRY_SEED
        
        tabnine = next((v for v in VENDOR_REGISTRY_SEED if v["vendor_name"] == "Tabnine"), None)
        assert tabnine is not None
        assert tabnine.get("trust_center_url") == "https://trust.tabnine.com"
    
    def test_all_vendors_have_required_fields(self):
        """All vendors should have vendor_name and at least one URL."""
        from vendor_registry_seed import VENDOR_REGISTRY_SEED
        
        url_fields = ["trust_center_url", "security_page_url", "privacy_page_url", "docs_url"]
        
        for vendor in VENDOR_REGISTRY_SEED:
            assert "vendor_name" in vendor, f"Vendor missing vendor_name: {vendor}"
            
            has_url = any(vendor.get(field) for field in url_fields)
            assert has_url, f"Vendor {vendor['vendor_name']} has no URLs"


class TestSeedFunctionContract:
    """Tests for seed_vendor_registry function contract."""
    
    def test_seed_function_exists(self):
        """seed_vendor_registry function should exist."""
        from vendor_registry_seed import seed_vendor_registry
        assert callable(seed_vendor_registry)
    
    def test_seed_function_returns_dict(self):
        """seed_vendor_registry should return dict with added/updated counts."""
        from vendor_registry_seed import seed_vendor_registry
        
        # Create a mock session that tracks adds
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value.first.return_value = None  # No existing vendors
        
        result = seed_vendor_registry(mock_session)
        
        assert isinstance(result, dict)
        assert "added" in result
        assert "updated" in result
        assert isinstance(result["added"], int)
        assert isinstance(result["updated"], int)


class TestClassifierWithVendorUrls:
    """Tests for classifier when vendor_urls are provided (no DB needed)."""
    
    def test_tabnine_trust_center_is_vendor(self):
        """With Tabnine URLs, trust.tabnine.com should classify as vendor."""
        from source_classifier import classify_source
        
        vendor_urls = [
            {"type": "trust_center", "url": "https://trust.tabnine.com"},
            {"type": "security_page", "url": "https://www.tabnine.com/security"},
        ]
        
        result = classify_source("https://trust.tabnine.com/soc2", vendor_urls)
        assert result.source_type == "vendor"
    
    def test_tabnine_security_page_is_vendor(self):
        """With Tabnine URLs, www.tabnine.com/security should classify as vendor."""
        from source_classifier import classify_source
        
        vendor_urls = [
            {"type": "trust_center", "url": "https://trust.tabnine.com"},
            {"type": "security_page", "url": "https://www.tabnine.com/security"},
        ]
        
        result = classify_source("https://www.tabnine.com/security/overview", vendor_urls)
        assert result.source_type == "vendor"
    
    def test_techcrunch_is_third_party(self):
        """TechCrunch should always be third_party regardless of vendor_urls."""
        from source_classifier import classify_source
        
        vendor_urls = [
            {"type": "trust_center", "url": "https://trust.tabnine.com"},
        ]
        
        result = classify_source("https://techcrunch.com/tabnine-funding", vendor_urls)
        assert result.source_type == "third_party"
    
    def test_empty_vendor_urls_returns_third_party(self):
        """With no vendor_urls, everything is third_party."""
        from source_classifier import classify_source
        
        result = classify_source("https://trust.tabnine.com", [])
        assert result.source_type == "third_party"
