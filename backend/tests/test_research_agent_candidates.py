"""
Offline tests for research_agent_v2 candidate discovery integration.

These tests verify:
1. Candidate collection from discovered URLs
2. Filtering: candidates include ONLY third_party URLs (not already-vendor URLs)
3. Candidate collection does NOT affect source_type classification
4. Status is "pending" by default

Run with: cd backend && python -m pytest tests/test_research_agent_candidates.py -v
"""

import pytest
from datetime import datetime
from dataclasses import field
from typing import List, Dict, Any

# Import the dataclass and function we're testing
from vendor_authority_bootstrap import collect_candidates_from_urls, CandidateVendorUrl
from candidate_authority import CandidateType, CandidateStatus
from source_classifier import classify_source


# =============================================================================
# TEST: Candidate collection from discovered URLs
# =============================================================================

class TestCandidateCollectionIntegration:
    """Tests for candidate collection during research"""
    
    def test_collect_candidates_returns_list(self):
        """collect_candidates_from_urls should return a list"""
        urls = ["https://trust.example.com"]
        result = collect_candidates_from_urls("Example", urls)
        assert isinstance(result, list)
    
    def test_collect_candidates_identifies_trust_center(self):
        """Should identify trust center URL as candidate"""
        urls = [
            "https://trust.newvendor.com/security",
            "https://www.newvendor.com/about",
        ]
        
        candidates = collect_candidates_from_urls("NewVendor", urls)
        
        assert len(candidates) == 1
        assert candidates[0].candidate_type == CandidateType.TRUST_CENTER
        assert candidates[0].candidate_url == "https://trust.newvendor.com/security"
    
    def test_collect_candidates_identifies_multiple_types(self):
        """Should identify multiple candidate types"""
        urls = [
            "https://trust.newvendor.com",
            "https://docs.newvendor.com/api",
            "https://status.newvendor.com",
            "https://newvendor.com/security",
            "https://newvendor.com/privacy",
        ]
        
        candidates = collect_candidates_from_urls("NewVendor", urls)
        
        types = {c.candidate_type for c in candidates}
        assert CandidateType.TRUST_CENTER in types
        assert CandidateType.DOCS in types
        assert CandidateType.STATUS_PAGE in types
        assert CandidateType.SECURITY_PAGE in types
        assert CandidateType.PRIVACY_PAGE in types
    
    def test_collect_candidates_default_status_pending(self):
        """All collected candidates should have status=pending"""
        urls = ["https://trust.example.com", "https://docs.example.com"]
        
        candidates = collect_candidates_from_urls("Example", urls)
        
        for candidate in candidates:
            assert candidate.status == CandidateStatus.PENDING
    
    def test_collect_candidates_preserves_vendor_name(self):
        """Candidates should have correct vendor_name"""
        candidates = collect_candidates_from_urls(
            "Tabnine",
            ["https://trust.tabnine.com"]
        )
        
        assert candidates[0].vendor_name == "Tabnine"
    
    def test_collect_candidates_filters_non_candidates(self):
        """Should filter out non-candidate URLs"""
        urls = [
            "https://www.example.com/about",
            "https://blog.example.com/post",
            "https://techcrunch.com/article",
        ]
        
        candidates = collect_candidates_from_urls("Example", urls)
        
        assert len(candidates) == 0


# =============================================================================
# TEST: Candidate to_dict format
# =============================================================================

class TestCandidateToDict:
    """Tests for CandidateVendorUrl.to_dict() format"""
    
    def test_to_dict_has_required_fields(self):
        """to_dict should have all required fields for ResearchResult"""
        candidates = collect_candidates_from_urls(
            "Example",
            ["https://trust.example.com"]
        )
        
        d = candidates[0].to_dict()
        
        # These fields must exist in ResearchResult.candidate_vendor_urls
        assert "vendor_name" in d
        assert "candidate_url" in d
        assert "candidate_type" in d
        assert "confidence" in d
        assert "match_reason" in d
        assert "normalized_domain" in d
        assert "status" in d
        assert "discovered_at" in d
    
    def test_to_dict_status_is_string(self):
        """status in to_dict should be string, not enum"""
        candidates = collect_candidates_from_urls(
            "Example",
            ["https://trust.example.com"]
        )
        
        d = candidates[0].to_dict()
        
        assert d["status"] == "pending"
        assert isinstance(d["status"], str)
    
    def test_to_dict_candidate_type_is_string(self):
        """candidate_type in to_dict should be string, not enum"""
        candidates = collect_candidates_from_urls(
            "Example",
            ["https://trust.example.com"]
        )
        
        d = candidates[0].to_dict()
        
        assert d["candidate_type"] == "trust_center"
        assert isinstance(d["candidate_type"], str)


# =============================================================================
# TEST: Candidate does NOT affect source_type
# =============================================================================

class TestCandidateSourceTypeIsolation:
    """Tests ensuring candidates don't affect source_type classification"""
    
    def test_candidate_url_still_third_party_without_registry(self):
        """
        CRITICAL: A candidate URL must be source_type='third_party'
        if not in VendorRegistry, regardless of candidate status.
        """
        # Novel vendor - no registry
        vendor_urls = []
        
        # URL that looks like a trust center
        url = "https://trust.newvendor.com/soc2"
        
        # It IS a candidate
        candidates = collect_candidates_from_urls("NewVendor", [url])
        assert len(candidates) == 1
        assert candidates[0].candidate_type == CandidateType.TRUST_CENTER
        
        # BUT source_type is still third_party
        classification = classify_source(url, vendor_urls)
        assert classification.source_type == "third_party"
    
    def test_high_confidence_candidate_still_third_party(self):
        """High confidence candidate must still be third_party without registry"""
        vendor_urls = []
        
        # URL with both subdomain and path match (highest confidence)
        url = "https://trust.newvendor.com/compliance"
        
        candidates = collect_candidates_from_urls("NewVendor", [url])
        assert candidates[0].confidence == 0.9  # High confidence
        
        # Still third_party
        classification = classify_source(url, vendor_urls)
        assert classification.source_type == "third_party"
    
    def test_candidate_collection_is_independent_of_classification(self):
        """
        Candidate collection and source_type classification
        are completely independent operations.
        """
        # Known vendor with registry
        vendor_urls = [
            {"type": "trust_center", "url": "https://trust.knownvendor.com"},
        ]
        
        discovered_urls = [
            "https://trust.knownvendor.com/soc2",      # In registry
            "https://trust.novelvendor.com/security",  # Not in registry
        ]
        
        # Candidate collection works on URL patterns only
        candidates = collect_candidates_from_urls("KnownVendor", discovered_urls)
        
        # Both URLs match candidate patterns
        assert len(candidates) == 2
        
        # But classification is registry-based:
        # Known vendor URL → vendor
        assert classify_source(discovered_urls[0], vendor_urls).source_type == "vendor"
        # Novel vendor URL → third_party
        assert classify_source(discovered_urls[1], vendor_urls).source_type == "third_party"


# =============================================================================
# TEST: Filtering - candidates include ONLY third_party URLs
# =============================================================================

class TestCandidateFilteringWithRegistry:
    """
    Tests for filtering candidates to exclude already-vendor URLs.
    
    This simulates the Phase 5 logic in research():
    - If vendor_urls exists, filter discovered_urls to only third_party
    - If vendor_urls is empty/None, analyze all discovered_urls
    """
    
    def test_known_vendor_excludes_registry_urls_from_candidates(self):
        """
        When vendor_entry has registry URLs, candidate_vendor_urls should
        include ONLY the third_party candidates, not already-vendor URLs.
        
        Simulates: Tabnine has trust.tabnine.com in registry.
        Discovered: trust.tabnine.com (vendor) + security.nudge.com (third_party)
        Expected candidates: ONLY security.nudge.com
        """
        # Tabnine registry
        vendor_urls = [
            {"type": "trust_center", "url": "https://trust.tabnine.com"},
            {"type": "security_page", "url": "https://www.tabnine.com/security"},
        ]
        
        # URLs discovered during research
        discovered_urls = [
            "https://trust.tabnine.com/soc2",           # Already vendor (in registry)
            "https://www.tabnine.com/security/overview", # Already vendor (in registry)
            "https://security.nudge.com/tabnine",        # Third-party security rating site
            "https://techcrunch.com/article/tabnine",    # Third-party news (not candidate pattern)
        ]
        
        # Simulate Phase 5 filtering logic from research()
        candidate_urls = [
            url for url in discovered_urls
            if classify_source(url, vendor_urls).source_type == "third_party"
        ]
        
        # Verify filtering
        assert "https://trust.tabnine.com/soc2" not in candidate_urls
        assert "https://www.tabnine.com/security/overview" not in candidate_urls
        assert "https://security.nudge.com/tabnine" in candidate_urls
        assert "https://techcrunch.com/article/tabnine" in candidate_urls
        
        # Now collect candidates from filtered URLs
        candidates = collect_candidates_from_urls("Tabnine", candidate_urls)
        
        # Only security.nudge.com matches candidate patterns
        assert len(candidates) == 1
        assert candidates[0].candidate_url == "https://security.nudge.com/tabnine"
        assert candidates[0].candidate_type == CandidateType.SECURITY_PAGE
        
        # Verify the excluded URLs are NOT in candidates
        candidate_urls_in_result = [c.candidate_url for c in candidates]
        assert "https://trust.tabnine.com/soc2" not in candidate_urls_in_result
        assert "https://www.tabnine.com/security/overview" not in candidate_urls_in_result
    
    def test_novel_vendor_includes_all_candidate_patterns(self):
        """
        When vendor_entry is None (novel vendor), candidate_vendor_urls
        should include all URLs matching candidate patterns.
        
        Simulates: NewVendor has no registry.
        Discovered: trust.newvendor.com + example.com/blog
        Expected candidates: ONLY trust.newvendor.com (matches pattern)
        """
        # No registry - novel vendor
        vendor_urls = []
        
        # URLs discovered during research
        discovered_urls = [
            "https://trust.newvendor.com/security",   # Matches trust_center pattern
            "https://docs.newvendor.com/api",          # Matches docs pattern
            "https://example.com/blog",                # No candidate pattern
            "https://www.newvendor.com/about",         # No candidate pattern
        ]
        
        # With empty vendor_urls, no filtering needed - all are third_party
        # (This is the else branch in Phase 5)
        if vendor_urls:
            candidate_urls = [
                url for url in discovered_urls
                if classify_source(url, vendor_urls).source_type == "third_party"
            ]
        else:
            candidate_urls = discovered_urls
        
        # All URLs pass through (no registry to filter against)
        assert len(candidate_urls) == 4
        
        # Collect candidates
        candidates = collect_candidates_from_urls("NewVendor", candidate_urls)
        
        # Only pattern-matching URLs become candidates
        assert len(candidates) == 2
        
        candidate_urls_in_result = [c.candidate_url for c in candidates]
        assert "https://trust.newvendor.com/security" in candidate_urls_in_result
        assert "https://docs.newvendor.com/api" in candidate_urls_in_result
        
        # Non-pattern URLs excluded by collect_candidates_from_urls
        assert "https://example.com/blog" not in candidate_urls_in_result
        assert "https://www.newvendor.com/about" not in candidate_urls_in_result
    
    def test_mixed_vendor_and_third_party_urls(self):
        """
        Test with a mix of vendor and third-party URLs that match candidate patterns.
        Only third-party should appear in candidates.
        """
        # Anthropic registry
        vendor_urls = [
            {"type": "trust_center", "url": "https://trust.anthropic.com"},
            {"type": "docs", "url": "https://docs.anthropic.com"},
        ]
        
        discovered_urls = [
            "https://trust.anthropic.com/compliance",    # Vendor (in registry)
            "https://docs.anthropic.com/api",            # Vendor (in registry)
            "https://trust.competitor.com/security",     # Third-party trust center
            "https://docs.competitor.com/integration",   # Third-party docs
            "https://status.competitor.com",             # Third-party status page
        ]
        
        # Filter to third_party only
        candidate_urls = [
            url for url in discovered_urls
            if classify_source(url, vendor_urls).source_type == "third_party"
        ]
        
        # Only competitor URLs remain
        assert len(candidate_urls) == 3
        assert "https://trust.anthropic.com/compliance" not in candidate_urls
        assert "https://docs.anthropic.com/api" not in candidate_urls
        
        # Collect candidates
        candidates = collect_candidates_from_urls("Anthropic", candidate_urls)
        
        # All three match candidate patterns
        assert len(candidates) == 3
        
        types = {c.candidate_type for c in candidates}
        assert CandidateType.TRUST_CENTER in types
        assert CandidateType.DOCS in types
        assert CandidateType.STATUS_PAGE in types


# =============================================================================
# TEST: Edge cases
# =============================================================================

class TestCandidateEdgeCases:
    """Tests for edge cases in candidate collection"""
    
    def test_empty_url_list(self):
        """Empty URL list should return empty candidates"""
        candidates = collect_candidates_from_urls("Example", [])
        assert candidates == []
    
    def test_none_urls_handled(self):
        """None URLs in list should be handled gracefully"""
        urls = [None, "https://trust.example.com", None]
        
        candidates = collect_candidates_from_urls("Example", urls)
        
        # Should only get 1 candidate from valid URL
        assert len(candidates) == 1
    
    def test_invalid_urls_handled(self):
        """Invalid URLs should be handled gracefully"""
        urls = [
            "not a url",
            "https://trust.example.com",
            "",
        ]
        
        candidates = collect_candidates_from_urls("Example", urls)
        
        assert len(candidates) == 1
    
    def test_all_urls_already_vendor(self):
        """If all discovered URLs are vendor, candidates should be empty"""
        vendor_urls = [
            {"type": "trust_center", "url": "https://trust.vendor.com"},
            {"type": "docs", "url": "https://docs.vendor.com"},
        ]
        
        discovered_urls = [
            "https://trust.vendor.com/soc2",
            "https://docs.vendor.com/api",
        ]
        
        # Filter to third_party
        candidate_urls = [
            url for url in discovered_urls
            if classify_source(url, vendor_urls).source_type == "third_party"
        ]
        
        # All filtered out
        assert len(candidate_urls) == 0
        
        candidates = collect_candidates_from_urls("Vendor", candidate_urls)
        assert len(candidates) == 0


# =============================================================================
# TEST: ResearchResult structure (simulated)
# =============================================================================

class TestResearchResultCandidateField:
    """Tests simulating ResearchResult.candidate_vendor_urls field"""
    
    def test_simulated_research_result_structure(self):
        """
        Simulate how candidates would appear in ResearchResult.
        This mirrors the actual integration in research().
        """
        # Simulate discovered URLs during research
        discovered_urls = [
            "https://trust.newvendor.com/security",
            "https://docs.newvendor.com/api",
            "https://www.newvendor.com/about",  # Not a candidate
            "https://techcrunch.com/article",    # Not a candidate
        ]
        
        # No registry (novel vendor)
        vendor_urls = []
        
        # Deduplicate (as done in research())
        unique_urls = list(set(discovered_urls))
        
        # Filter if vendor_urls exists (as done in research())
        if vendor_urls:
            candidate_urls = [
                url for url in unique_urls
                if classify_source(url, vendor_urls).source_type == "third_party"
            ]
        else:
            candidate_urls = unique_urls
        
        # Collect candidates (as done in research())
        candidates = collect_candidates_from_urls("NewVendor", candidate_urls)
        
        # Convert to dicts (as done in research())
        candidate_vendor_urls = [c.to_dict() for c in candidates]
        
        # Verify structure
        assert len(candidate_vendor_urls) == 2
        
        for entry in candidate_vendor_urls:
            assert isinstance(entry, dict)
            assert entry["vendor_name"] == "NewVendor"
            assert entry["status"] == "pending"
            assert entry["candidate_type"] in ["trust_center", "docs"]
