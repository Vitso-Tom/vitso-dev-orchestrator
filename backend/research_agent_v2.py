"""
Research Agent V2 - Enhanced vendor research with caching and verification

Three-phase research flow:
1. DATABASE LOOKUP - Check for cached, verified facts
2. SOURCE RECHECK - Verify stale facts by re-fetching original URLs  
3. NEW RESEARCH - Direct fetch + web search for missing facts

This agent:
- Caches verified facts across assessments
- Rechecks sources instead of re-searching
- Direct-fetches known vendor trust centers
- Falls back to web search for discovery
- Tracks full audit trail of verification
- Supports multiple AI backends (Claude, OpenAI) for cost optimization
- Uses deterministic source classification via source_classifier module
"""

import json
import httpx
import asyncio
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Literal
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse
import anthropic
from openai import OpenAI

from research_models_v2 import (
    VendorFact, VendorRegistry, FactVerificationLog,
    CRITICAL_FIELDS, get_ttl_for_field, get_priority_for_field
)
from vendor_registry_seed import lookup_vendor
from source_classifier import classify_source
from vendor_authority_bootstrap import collect_candidates_from_urls
from candidate_authority import CandidateType
from assurance_keywords import get_snippet_keywords, get_certification_fields

try:
    import xml.etree.ElementTree as ET
except ImportError:
    ET = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


# =============================================================================
# PIPELINE DATACLASSES - Index First, Ingest Later Architecture
# =============================================================================
# Design principles:
# 1. Every object must be explainable (why did we look at this page?)
# 2. Discovery, validation, ranking, extraction are separate concerns
# 3. Cost containment depends on traceability
# 4. Persistence-friendly (JSON serializable)

@dataclass(frozen=True)
class DiscoveredURL:
    """A URL that exists in the vendor's universe, but has not been validated."""
    url: str
    source: str  # "sitemap", "robots", "search"
    discovered_via: str  # e.g. "sitemap.xml", "site: trust query", "hipaa query"
    lastmod: Optional[str] = None


@dataclass(frozen=True)
class ValidatedURL:
    """A URL confirmed to exist and be fetchable."""
    original_url: str
    final_url: str
    status_code: int
    content_type: Optional[str]
    reachable: bool
    redirect_chain: Tuple[str, ...]  # Tuple for frozen hashability


@dataclass(frozen=True)
class RankedURL:
    """A validated URL with authority context."""
    validated: ValidatedURL
    score: float
    authority_tier: int  # 1 = trust/security, 2 = legal/privacy, 3 = docs, 4 = blog
    reasons: Tuple[str, ...]  # Tuple for frozen hashability


@dataclass(frozen=True)
class PageSnippets:
    """Curated content ready for LLM extraction."""
    url: str
    final_url: str
    content_type: str  # "text/html" or "application/pdf"
    title: Optional[str]
    h1: Optional[str]
    snippets: Tuple[str, ...]  # Tuple for frozen hashability
    keyword_hits: Dict[str, int]  # Can't be frozen, but we won't mutate
    extracted_at: str
    authority_tier: int  # Carried forward from RankedURL

    def __hash__(self):
        return hash((self.url, self.final_url, self.extracted_at))


@dataclass(frozen=True)
class Fact:
    """A single extracted fact with full provenance."""
    category: str  # e.g. "certification", "security", "data_handling"
    key: str  # e.g. "soc2_status", "hipaa_baa"
    value: str  # e.g. "SOC 2 Type II certified"
    snippet: str  # EXACT supporting text
    source_url: str
    confidence: float
    authority_tier: int  # Carried forward from RankedURL


# =============================================================================
# KEYWORD PATTERNS FOR FILTERING AND SNIPPET EXTRACTION
# =============================================================================

SECURITY_URL_PATTERNS = [
    "security", "trust", "trust-center", "trustcenter", "compliance",
    "certification", "certifications", "attestation", "soc", "iso"
]

PRIVACY_URL_PATTERNS = [
    "privacy", "legal", "dpa", "gdpr", "subprocessor", "subprocessors",
    "data-processing"
]

HEALTHCARE_URL_PATTERNS = [
    "hipaa", "baa", "business-associate", "phi", "healthcare", "health"
]

# NEW: AI/ML Policy patterns - helps reduce AI Model Risk score
AI_ML_URL_PATTERNS = [
    "ai", "artificial-intelligence", "machine-learning", "ml",
    "data-usage", "training", "model", "llm",
    "ai-policy", "ai-principles", "responsible-ai",
    "data-retention", "retention"
]

# NEW: Integration/Partner patterns - reveals subprocessors and data flow
INTEGRATION_URL_PATTERNS = [
    "partner", "partners", "partnership",
    "integration", "integrations", "ecosystem",
    "marketplace", "apps", "connect",
    "technology-partners", "tech-partners",
    "subprocessor", "subprocessors", "sub-processor",
    "vendor", "vendors", "third-party"
]

ALL_URL_PATTERNS = SECURITY_URL_PATTERNS + PRIVACY_URL_PATTERNS + HEALTHCARE_URL_PATTERNS + AI_ML_URL_PATTERNS + INTEGRATION_URL_PATTERNS

# Keywords for snippet extraction - DYNAMICALLY LOADED from assurance_programs.json
# This ensures VDO extraction uses the same keywords as AITGP matching.
# Edit assurance_programs.json to add new certifications - no code changes needed.
#
# Source: /home/temlock/aitgp-app/job-53/config/assurance_programs.json
# Override path via: ASSURANCE_PROGRAMS_PATH environment variable
#
# The loader combines:
# 1. All aliases from assurance_programs.json (certifications, frameworks)
# 2. Supplementary keywords (security terms, cloud providers, etc.)
#
SNIPPET_KEYWORDS = get_snippet_keywords()


# =============================================================================
# PIPELINE CLASSES
# =============================================================================

# Browser-like headers to avoid 403s from bot protection
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


# Subdomains to probe for security/trust content in V3 pipeline
PIPELINE_SECURITY_SUBDOMAINS = [
    "trust",
    "security", 
    "docs",
    "help",
    "support",
]


class VendorIndexer:
    """Discovers URLs in a vendor's universe without crawling content."""
    
    def __init__(self, http_client: httpx.AsyncClient = None):
        self.http_client = http_client or httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=BROWSER_HEADERS)
    
    async def _discover_sitemaps_for_base(self, base_url: str) -> List[str]:
        """
        Find sitemap URLs for a single base URL.
        Checks robots.txt and common sitemap locations.
        Returns list of sitemap URLs found.
        """
        sitemap_urls = []
        
        # Check robots.txt for sitemap directives
        try:
            response = await self.http_client.get(f"{base_url}/robots.txt")
            if response.status_code == 200:
                for line in response.text.splitlines():
                    if line.lower().startswith("sitemap:"):
                        sitemap_url = line.split(":", 1)[1].strip()
                        if sitemap_url:
                            sitemap_urls.append(sitemap_url)
        except Exception:
            pass
        
        # Check common sitemap locations
        common_locations = [
            f"{base_url}/sitemap.xml",
            f"{base_url}/sitemap_index.xml",
            f"{base_url}/sitemap-index.xml",
            f"{base_url}/sitemaps/sitemap.xml",
        ]
        
        for loc in common_locations:
            if loc not in sitemap_urls:
                try:
                    response = await self.http_client.head(loc)
                    if response.status_code == 200:
                        sitemap_urls.append(loc)
                except Exception:
                    pass
        
        return sitemap_urls
    
    async def _probe_subdomain(self, subdomain: str, domain: str) -> Tuple[List[str], bool, Optional[Dict[str, str]]]:
        """
        Probe a subdomain to check if it's live and has sitemaps.
        Uses GET instead of HEAD because many trust centers (SafeBase, Vanta, etc.) block HEAD requests.
        
        Returns:
            Tuple of (sitemap_urls, is_live, blocked_info)
            - sitemap_urls: List of sitemap URLs found on this subdomain
            - is_live: Whether subdomain is accessible and crawlable
            - blocked_info: {"url": "...", "reason": "safebase"} if bot-blocked, else None
        """
        subdomain_url = f"https://{subdomain}.{domain}"
        
        try:
            # Use GET instead of HEAD - many trust centers block HEAD requests
            response = await self.http_client.get(subdomain_url, timeout=8.0)
            
            # Success - subdomain responded
            if response.status_code in [200, 301, 302, 303, 307, 308]:
                # Check for bot protection in response body (Cloudflare, SafeBase, etc.)
                protection = detect_bot_protection(response.text, response.status_code)
                if protection:
                    print(f"[PIPELINE] Subdomain {subdomain}.{domain} blocked by {protection}")
                    return [], False, {"url": subdomain_url, "reason": protection}
                
                print(f"[PIPELINE] Found live subdomain: {subdomain}.{domain}")
                sitemaps = await self._discover_sitemaps_for_base(subdomain_url)
                return sitemaps, True, None
            
            # 403/401 - likely bot protection or access denied
            elif response.status_code in [403, 401]:
                # Try to detect what kind of protection from response body
                protection = detect_bot_protection(response.text, response.status_code) or "access_denied"
                print(f"[PIPELINE] Subdomain {subdomain}.{domain} returned {response.status_code} ({protection})")
                return [], False, {"url": subdomain_url, "reason": protection}
            
            # Other non-success codes - subdomain exists but not useful
            else:
                return [], False, None
                
        except Exception as e:
            # Connection failed - subdomain doesn't exist or is unreachable
            return [], False, None
    
    async def discover_sitemaps(self, domain: str) -> Tuple[List[str], List[str], List[Dict[str, str]]]:
        """
        Find sitemap URLs for a domain AND its common subdomains.
        
        Probes:
        - Main domain (e.g., vendor.com)
        - www.vendor.com
        - trust.vendor.com, security.vendor.com, docs.vendor.com, etc.
        
        This ensures we discover content on subdomains like trust.tabnine.com
        that aren't linked from the main sitemap.
        
        Returns:
            Tuple of (sitemap_urls, live_subdomains_without_sitemaps, blocked_subdomains)
            - sitemap_urls: All sitemap URLs found
            - live_subdomains_without_sitemaps: Base URLs of live subdomains that
              don't have sitemaps (e.g., "https://trust.vendor.com") - these should
              still be crawled directly.
            - blocked_subdomains: List of subdomains blocked by bot protection
              Format: [{"url": "https://trust.vendor.com", "reason": "safebase"}, ...]
        """
        all_sitemap_urls = []
        live_subdomains_no_sitemap = []
        blocked_subdomains = []
        
        # Normalize domain
        domain = domain.lower().strip().rstrip("/")
        if domain.startswith("http"):
            domain = urlparse(domain).netloc
        if domain.startswith("www."):
            domain = domain[4:]
        
        # 1. Main domain sitemaps
        main_base_url = f"https://{domain}"
        main_sitemaps = await self._discover_sitemaps_for_base(main_base_url)
        all_sitemap_urls.extend(main_sitemaps)
        
        # 2. www subdomain (some sites only have sitemaps on www)
        www_base_url = f"https://www.{domain}"
        www_sitemaps = await self._discover_sitemaps_for_base(www_base_url)
        for sm in www_sitemaps:
            if sm not in all_sitemap_urls:
                all_sitemap_urls.append(sm)
        
        # 3. Security-related subdomains (trust, docs, security, help, support)
        # Probe in parallel for speed
        subdomain_tasks = [
            self._probe_subdomain(subdomain, domain)
            for subdomain in PIPELINE_SECURITY_SUBDOMAINS
        ]
        subdomain_results = await asyncio.gather(*subdomain_tasks, return_exceptions=True)
        
        for idx, result in enumerate(subdomain_results):
            if isinstance(result, tuple) and len(result) == 3:
                sitemaps, is_live, blocked_info = result
                subdomain_name = PIPELINE_SECURITY_SUBDOMAINS[idx]
                subdomain_base = f"https://{subdomain_name}.{domain}"
                
                if blocked_info:
                    # Subdomain exists but is blocked by bot protection
                    blocked_subdomains.append(blocked_info)
                elif sitemaps:
                    # Found sitemaps on this subdomain
                    for sm in sitemaps:
                        if sm not in all_sitemap_urls:
                            all_sitemap_urls.append(sm)
                elif is_live:
                    # Subdomain is live but has no sitemap - track for direct crawl
                    live_subdomains_no_sitemap.append(subdomain_base)
                    print(f"[PIPELINE] Subdomain {subdomain_name}.{domain} is live but has no sitemap")
        
        return all_sitemap_urls, live_subdomains_no_sitemap, blocked_subdomains
    
    async def index_from_sitemaps(self, sitemap_urls: List[str]) -> List[DiscoveredURL]:
        """
        Parse sitemap(s) and extract all URLs.
        Handles sitemap index files that point to child sitemaps.
        """
        discovered = []
        processed_sitemaps = set()
        
        async def parse_sitemap(url: str):
            if url in processed_sitemaps:
                return
            processed_sitemaps.add(url)
            
            try:
                response = await self.http_client.get(url)
                if response.status_code != 200:
                    return
                
                if ET is None:
                    return
                
                root = ET.fromstring(response.text)
                ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
                
                # Check if this is a sitemap index
                for sitemap in root.findall(".//sm:sitemap", ns):
                    loc = sitemap.find("sm:loc", ns)
                    if loc is not None and loc.text:
                        await parse_sitemap(loc.text)  # Recurse into child sitemap
                
                # Extract URLs from urlset
                for url_elem in root.findall(".//sm:url", ns):
                    loc = url_elem.find("sm:loc", ns)
                    lastmod_elem = url_elem.find("sm:lastmod", ns)
                    
                    if loc is not None and loc.text:
                        discovered.append(DiscoveredURL(
                            url=loc.text,
                            source="sitemap",
                            discovered_via=url,
                            lastmod=lastmod_elem.text if lastmod_elem is not None else None
                        ))
            except Exception:
                pass
        
        for sitemap_url in sitemap_urls:
            await parse_sitemap(sitemap_url)
        
        return discovered
    
    async def discover_via_search(
        self, 
        domain: str, 
        vendor_name: Optional[str] = None,
        anthropic_client: anthropic.Anthropic = None
    ) -> List[DiscoveredURL]:
        """
        Use site: searches as a fallback index when sitemap is missing/sparse.
        Two query packs: trust/compliance and hipaa/legal.
        Returns URLs only - no content extraction.
        """
        if anthropic_client is None:
            return []
        
        discovered = []
        domain = domain.lower().strip()
        if domain.startswith("http"):
            domain = urlparse(domain).netloc
        if domain.startswith("www."):
            domain = domain[4:]
        
        # Two focused query packs
        query_packs = [
            {
                "query": f"site:{domain} (security OR trust OR compliance OR privacy OR legal)",
                "via": "site: trust/compliance query"
            },
            {
                "query": f"site:{domain} (hipaa OR baa OR \"business associate\" OR subprocessor OR dpa)",
                "via": "site: hipaa/legal query"
            }
        ]
        
        for pack in query_packs:
            prompt = f"""Search for: {pack['query']}

Return ONLY a JSON array of URLs found. No analysis, no extraction.
Example: ["https://example.com/security", "https://example.com/privacy"]

If no results, return empty array: []"""
            
            try:
                # Use Claude with web search for URL discovery
                # This is cheap - we only ask for URLs, not content extraction
                response = await asyncio.to_thread(
                    anthropic_client.messages.create,
                    model="claude-sonnet-4-20250514",
                    max_tokens=1024,
                    tools=[{"type": "web_search_20250305", "name": "web_search"}],
                    messages=[{"role": "user", "content": prompt}]
                )
                
                for block in response.content:
                    if hasattr(block, 'text') and block.text:
                        text = block.text
                        try:
                            start = text.find('[')
                            end = text.rfind(']') + 1
                            if start != -1 and end > start:
                                urls = json.loads(text[start:end])
                                for url in urls:
                                    if isinstance(url, str) and url.startswith("http"):
                                        discovered.append(DiscoveredURL(
                                            url=url,
                                            source="search",
                                            discovered_via=pack["via"]
                                        ))
                        except (json.JSONDecodeError, ValueError):
                            pass
            except Exception:
                pass
        
        # Dedupe by URL
        seen = set()
        deduped = []
        for d in discovered:
            if d.url not in seen:
                seen.add(d.url)
                deduped.append(d)
        
        return deduped


class CandidateFilter:
    """Filters and ranks discovered URLs."""
    
    def __init__(self, http_client: httpx.AsyncClient = None):
        self.http_client = http_client or httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=BROWSER_HEADERS)
    
    def candidate_match(self, urls: List[DiscoveredURL]) -> List[DiscoveredURL]:
        """
        Filter URLs by security/privacy/healthcare patterns.
        Pure string matching - no HTTP, no LLM.
        """
        matched = []
        
        for discovered in urls:
            url_lower = discovered.url.lower()
            
            # Check if URL contains any relevant pattern
            if any(pattern in url_lower for pattern in ALL_URL_PATTERNS):
                matched.append(discovered)
        
        return matched
    
    async def head_validate(self, urls: List[DiscoveredURL]) -> List[ValidatedURL]:
        """
        HEAD request to validate URLs exist.
        Records redirects, content type, reachability.
        """
        validated = []
        
        async def validate_one(discovered: DiscoveredURL) -> Optional[ValidatedURL]:
            redirect_chain = []
            try:
                # Use GET with stream to follow redirects but not download body
                async with self.http_client.stream("GET", discovered.url) as response:
                    # Collect redirect history
                    if hasattr(response, 'history'):
                        redirect_chain = [str(r.url) for r in response.history]
                    
                    content_type = response.headers.get("content-type", "").split(";")[0].strip()
                    
                    # Accept HTML and PDF
                    is_acceptable = content_type in ["text/html", "application/pdf", ""]
                    
                    return ValidatedURL(
                        original_url=discovered.url,
                        final_url=str(response.url),
                        status_code=response.status_code,
                        content_type=content_type or None,
                        reachable=response.status_code == 200 and is_acceptable,
                        redirect_chain=tuple(redirect_chain)
                    )
            except Exception:
                return ValidatedURL(
                    original_url=discovered.url,
                    final_url=discovered.url,
                    status_code=0,
                    content_type=None,
                    reachable=False,
                    redirect_chain=tuple()
                )
        
        # Validate in parallel with semaphore
        semaphore = asyncio.Semaphore(10)
        
        async def validate_with_sem(d: DiscoveredURL):
            async with semaphore:
                return await validate_one(d)
        
        results = await asyncio.gather(*[validate_with_sem(d) for d in urls])
        
        # Keep only reachable
        validated = [v for v in results if v is not None and v.reachable]
        
        return validated
    
    def authority_rank(self, urls: List[ValidatedURL]) -> List[RankedURL]:
        """
        Rank validated URLs by authority.
        Tier 1: trust/security/compliance pages (NOT news articles about them)
        Tier 2: legal/privacy/subprocessors/partners
        Tier 3: docs/help
        Tier 4: blog/news/articles/other
        
        IMPORTANT: We check path segments, not just substrings, to avoid
        ranking news articles about certifications as Tier 1.
        """
        ranked = []
        
        # Patterns that indicate authoritative pages (as path segments)
        tier1_path_segments = ["/trust", "/security", "/compliance", "/certification", 
                               "/trust-center", "/trustcenter", "/about/compliance",
                               "/about/security", "/about/trust"]
        tier2_path_segments = ["/privacy", "/legal", "/subprocessor", "/dpa", 
                               "/hipaa", "/baa", "/partner", "/partners",
                               "/about/partners", "/integrations"]
        tier3_path_segments = ["/docs", "/help", "/support", "/faq"]
        
        # Patterns that DEMOTE to Tier 4 (blog/news content)
        demote_patterns = ["/article", "/articles", "/blog", "/news", "/in-the-news",
                          "/press", "/press-release", "/media", "/podcast",
                          "/webinar", "/event", "/success", "/case-stud"]
        
        for validated in urls:
            url_lower = validated.final_url.lower()
            # Extract path for segment matching
            try:
                path = urlparse(url_lower).path
            except:
                path = url_lower
            
            reasons = []
            score = 0.0
            tier = 4  # Default to blog/other
            is_demoted = False
            
            # FIRST: Check for demote patterns (blog/news/articles)
            # These should NEVER be Tier 1 even if they mention "compliance"
            for pattern in demote_patterns:
                if pattern in path:
                    is_demoted = True
                    tier = 4
                    score -= 15  # Heavy penalty
                    reasons.append(f"demoted_{pattern.strip('/')}")
                    break
            
            # Only check tier 1-3 if not demoted
            if not is_demoted:
                # Check tier 1 (path segment matching)
                for pattern in tier1_path_segments:
                    if pattern in path:
                        tier = min(tier, 1)
                        score += 15  # Higher boost for authoritative paths
                        reasons.append(f"path_segment_{pattern.strip('/')}")
                
                # Check tier 2
                for pattern in tier2_path_segments:
                    if pattern in path:
                        tier = min(tier, 2)
                        score += 10
                        reasons.append(f"path_segment_{pattern.strip('/')}")
                
                # Check tier 3
                for pattern in tier3_path_segments:
                    if pattern in path:
                        tier = min(tier, 3)
                        score += 5
                        reasons.append(f"path_segment_{pattern.strip('/')}")
            
            # Boost for PDF (often authoritative documents)
            if validated.content_type == "application/pdf":
                score += 5
                reasons.append("is_pdf")
            
            # Boost for short, direct paths (e.g., /security vs /resources/docs/security/overview)
            path_depth = path.count("/")
            if path_depth <= 2:
                score += 3
                reasons.append("short_path")
            elif path_depth > 4:
                score -= (path_depth - 4)
                reasons.append(f"deep_path_{path_depth}")
            
            ranked.append(RankedURL(
                validated=validated,
                score=score,
                authority_tier=tier,
                reasons=tuple(reasons)
            ))
        
        # Sort by tier (ascending) then score (descending)
        ranked.sort(key=lambda r: (r.authority_tier, -r.score))
        
        return ranked


class SnippetExtractor:
    """Fetches pages and extracts keyword-relevant snippets. No LLM."""
    
    def __init__(self, http_client: httpx.AsyncClient = None):
        self.http_client = http_client or httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=BROWSER_HEADERS)
    
    async def fetch_and_parse(self, ranked: RankedURL) -> Optional[PageSnippets]:
        """
        Fetch HTML page and extract title, h1, keyword-containing snippets.
        No LLM - pure HTML parsing.
        """
        try:
            response = await self.http_client.get(ranked.validated.final_url)
            if response.status_code != 200:
                return None
            
            content = response.text
            content_lower = content.lower()
            
            # Extract title
            title = None
            title_match = content.find("<title>")
            if title_match != -1:
                title_end = content.find("</title>", title_match)
                if title_end != -1:
                    title = content[title_match + 7:title_end].strip()
            
            # Extract h1
            h1 = None
            h1_match = content_lower.find("<h1")
            if h1_match != -1:
                h1_start = content.find(">", h1_match) + 1
                h1_end = content_lower.find("</h1>", h1_start)
                if h1_end != -1:
                    h1 = content[h1_start:h1_end].strip()
                    # Strip HTML tags from h1
                    import re
                    h1 = re.sub(r'<[^>]+>', '', h1)
            
            # Extract keyword-containing snippets
            snippets = []
            keyword_hits = {}
            
            # Split into paragraphs/sections
            import re
            # Split on paragraph, div, section, li tags
            chunks = re.split(r'<(?:p|div|section|li|td)[^>]*>', content, flags=re.IGNORECASE)
            
            for chunk in chunks:
                # Clean HTML
                clean = re.sub(r'<[^>]+>', ' ', chunk)
                clean = re.sub(r'\s+', ' ', clean).strip()
                
                if len(clean) < 20 or len(clean) > 2000:
                    continue
                
                chunk_lower = clean.lower()
                
                # Check for keyword hits
                for keyword in SNIPPET_KEYWORDS:
                    if keyword in chunk_lower:
                        if keyword not in keyword_hits:
                            keyword_hits[keyword] = 0
                        keyword_hits[keyword] += 1
                        
                        if clean not in snippets:
                            snippets.append(clean)
                        break  # One snippet per chunk
            
            # Also check title and h1 for keywords
            for text in [title, h1]:
                if text:
                    text_lower = text.lower()
                    for keyword in SNIPPET_KEYWORDS:
                        if keyword in text_lower:
                            if keyword not in keyword_hits:
                                keyword_hits[keyword] = 0
                            keyword_hits[keyword] += 1
            
            if not snippets and not keyword_hits:
                return None
            
            return PageSnippets(
                url=ranked.validated.original_url,
                final_url=ranked.validated.final_url,
                content_type="text/html",
                title=title,
                h1=h1,
                snippets=tuple(snippets[:20]),  # Cap at 20 snippets
                keyword_hits=keyword_hits,
                extracted_at=datetime.utcnow().isoformat(),
                authority_tier=ranked.authority_tier
            )
            
        except Exception:
            return None
    
    async def extract_pdf_snippets(self, ranked: RankedURL) -> Optional[PageSnippets]:
        """
        Fetch PDF and extract keyword-containing text snippets.
        Uses pdfplumber for local extraction - no LLM.
        """
        if pdfplumber is None:
            return None
        
        try:
            response = await self.http_client.get(ranked.validated.final_url)
            if response.status_code != 200:
                return None
            
            # Write to temp file for pdfplumber
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(response.content)
                temp_path = f.name
            
            try:
                snippets = []
                keyword_hits = {}
                title = None
                
                with pdfplumber.open(temp_path) as pdf:
                    # Get title from metadata if available
                    if pdf.metadata and pdf.metadata.get("Title"):
                        title = pdf.metadata["Title"]
                    
                    for page in pdf.pages[:10]:  # Cap at 10 pages
                        text = page.extract_text()
                        if not text:
                            continue
                        
                        # Split into paragraphs
                        paragraphs = text.split("\n\n")
                        
                        for para in paragraphs:
                            para = para.strip()
                            if len(para) < 20 or len(para) > 2000:
                                continue
                            
                            para_lower = para.lower()
                            
                            for keyword in SNIPPET_KEYWORDS:
                                if keyword in para_lower:
                                    if keyword not in keyword_hits:
                                        keyword_hits[keyword] = 0
                                    keyword_hits[keyword] += 1
                                    
                                    if para not in snippets:
                                        snippets.append(para)
                                    break
                
                if not snippets and not keyword_hits:
                    return None
                
                return PageSnippets(
                    url=ranked.validated.original_url,
                    final_url=ranked.validated.final_url,
                    content_type="application/pdf",
                    title=title,
                    h1=None,
                    snippets=tuple(snippets[:20]),
                    keyword_hits=keyword_hits,
                    extracted_at=datetime.utcnow().isoformat(),
                    authority_tier=ranked.authority_tier
                )
            finally:
                import os
                os.unlink(temp_path)
                
        except Exception:
            return None


class FactExtractor:
    """Extracts structured facts from snippets. THIS is where LLM is called."""
    
    def __init__(
        self, 
        anthropic_client: anthropic.Anthropic = None,
        openai_client: OpenAI = None,
        model: str = "gpt-4o-mini"
    ):
        self.anthropic_client = anthropic_client
        self.openai_client = openai_client
        self.model = model
    
    async def extract_facts(self, pages: List[PageSnippets], vendor_name: str) -> List[Fact]:
        """
        Extract structured facts from pre-curated snippets.
        This is the ONLY place LLM tokens are spent on content.
        """
        if not pages:
            return []
        
        # Build consolidated prompt with all snippets
        snippets_text = ""
        for page in pages:
            snippets_text += f"\n\n--- Source: {page.final_url} (Tier {page.authority_tier}) ---\n"
            if page.title:
                snippets_text += f"Title: {page.title}\n"
            if page.h1:
                snippets_text += f"H1: {page.h1}\n"
            snippets_text += "\nSnippets:\n"
            for snippet in page.snippets:
                snippets_text += f"- {snippet}\n"
        
        prompt = f"""Extract security and compliance facts for {vendor_name} from these page snippets.

{snippets_text}

For each fact found, return JSON array:
[
  {{
    "category": "certification|security|data_handling|integration|company",
    "key": "soc2_status|hipaa_baa|iso27001|hitrust|encryption|sso|scim|etc",
    "value": "the specific finding",
    "snippet": "EXACT text from above that supports this",
    "source_url": "url where found",
    "confidence": 0.0-1.0
  }}
]

RULES:
- Only extract facts with EXPLICIT supporting text
- snippet must be VERBATIM from the source
- Higher confidence for tier 1-2 sources
- Include negative findings ("does NOT offer BAA")
- If no facts found, return []"""
        
        try:
            if self.model.startswith("gpt"):
                response = await asyncio.to_thread(
                    self.openai_client.chat.completions.create,
                    model=self.model,
                    max_tokens=2048,
                    messages=[{"role": "user", "content": prompt}]
                )
                text = response.choices[0].message.content or ""
            else:
                response = await asyncio.to_thread(
                    self.anthropic_client.messages.create,
                    model=self.model,
                    max_tokens=2048,
                    messages=[{"role": "user", "content": prompt}]
                )
                text = ""
                for block in response.content:
                    if hasattr(block, 'text'):
                        text = block.text
                        break
            
            # Parse JSON response
            facts = []
            start = text.find('[')
            end = text.rfind(']') + 1
            if start != -1 and end > start:
                parsed = json.loads(text[start:end])
                
                # Find authority tier for each fact's source
                url_to_tier = {p.final_url: p.authority_tier for p in pages}
                url_to_tier.update({p.url: p.authority_tier for p in pages})
                
                for item in parsed:
                    source_url = item.get("source_url", "")
                    tier = url_to_tier.get(source_url, 4)
                    
                    facts.append(Fact(
                        category=item.get("category", "unknown"),
                        key=item.get("key", ""),
                        value=item.get("value", ""),
                        snippet=item.get("snippet", ""),
                        source_url=source_url,
                        confidence=float(item.get("confidence", 0.5)),
                        authority_tier=tier
                    ))
            
            return facts
            
        except Exception:
            return []


class VendorAssessmentPipeline:
    """
    Orchestrates the full index-first, ingest-later research pipeline.
    Single entry point for vendor security research.
    """
    
    def __init__(
        self,
        anthropic_client: anthropic.Anthropic = None,
        openai_client: OpenAI = None,
        cost_mode: str = "economy"
    ):
        self.http_client = httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=BROWSER_HEADERS)
        self.anthropic_client = anthropic_client
        self.openai_client = openai_client
        self.cost_mode = cost_mode
        
        # Initialize pipeline components
        self.indexer = VendorIndexer(self.http_client)
        self.filter = CandidateFilter(self.http_client)
        self.snippet_extractor = SnippetExtractor(self.http_client)
        
        # Use cheapest model for extraction in economy mode
        extraction_model = "gpt-4o-mini" if cost_mode == "economy" else "gpt-4o-mini"
        self.fact_extractor = FactExtractor(
            anthropic_client=anthropic_client,
            openai_client=openai_client,
            model=extraction_model
        )
    
    async def run(
        self, 
        domain: str, 
        vendor_name: Optional[str] = None,
        max_pages: int = 15
    ) -> Tuple[List[Fact], Dict[str, Any]]:
        """
        Run the full research pipeline.
        
        Returns:
            Tuple of (facts, metadata) where metadata includes pipeline stats.
        """
        vendor_name = vendor_name or domain
        stats = {
            "domain": domain,
            "vendor_name": vendor_name,
            "sitemap_urls_found": 0,
            "urls_from_sitemap": 0,
            "urls_from_search": 0,
            "urls_after_pattern_filter": 0,
            "urls_after_validation": 0,
            "urls_after_ranking": 0,
            "pages_fetched": 0,
            "facts_extracted": 0,
        }
        
        # STEP 1: Discover sitemaps (now also probes subdomains)
        print(f"[PIPELINE] Step 1: Discovering sitemaps for {domain}...")
        sitemap_urls, live_subdomains_no_sitemap, blocked_subdomains = await self.indexer.discover_sitemaps(domain)
        stats["sitemap_urls_found"] = len(sitemap_urls)
        stats["live_subdomains_no_sitemap"] = len(live_subdomains_no_sitemap)
        stats["blocked_subdomains"] = blocked_subdomains
        
        if blocked_subdomains:
            print(f"[PIPELINE] ⚠️ {len(blocked_subdomains)} subdomain(s) blocked by bot protection:")
            for blocked in blocked_subdomains:
                print(f"    - {blocked['url']} ({blocked['reason']})")
            print(f"[PIPELINE] These will be flagged for manual review in the report.")
        
        # STEP 2: Index from sitemaps
        discovered_urls = []
        if sitemap_urls:
            print(f"[PIPELINE] Step 2: Indexing from {len(sitemap_urls)} sitemap(s)...")
            discovered_urls = await self.indexer.index_from_sitemaps(sitemap_urls)
            stats["urls_from_sitemap"] = len(discovered_urls)
        
        # STEP 2a: Add live subdomains without sitemaps as discovered URLs
        # These are subdomains like trust.vendor.com that are live but have no sitemap
        # We add them directly so they can be crawled
        if live_subdomains_no_sitemap:
            print(f"[PIPELINE] Step 2a: Adding {len(live_subdomains_no_sitemap)} live subdomains without sitemaps...")
            for subdomain_base in live_subdomains_no_sitemap:
                # Add the root URL of the subdomain
                discovered_urls.append(DiscoveredURL(
                    url=subdomain_base,
                    source="subdomain_probe",
                    discovered_via="live_subdomain_no_sitemap"
                ))
                # Also add common security paths on this subdomain
                for path in ["/security", "/compliance", "/privacy", "/trust"]:
                    discovered_urls.append(DiscoveredURL(
                        url=f"{subdomain_base}{path}",
                        source="subdomain_probe",
                        discovered_via=f"live_subdomain_common_path:{path}"
                    ))
        
        # STEP 2b: Supplement with search if sitemap sparse
        if len(discovered_urls) < 10:
            print(f"[PIPELINE] Step 2b: Sitemap sparse ({len(discovered_urls)} URLs), using search...")
            search_urls = await self.indexer.discover_via_search(
                domain, vendor_name, self.anthropic_client
            )
            stats["urls_from_search"] = len(search_urls)
            
            # Merge, dedupe
            seen = {d.url for d in discovered_urls}
            for su in search_urls:
                if su.url not in seen:
                    discovered_urls.append(su)
                    seen.add(su.url)
        
        if not discovered_urls:
            print(f"[PIPELINE] No URLs discovered for {domain}")
            return [], stats
        
        print(f"[PIPELINE] Total discovered URLs: {len(discovered_urls)}")
        
        # STEP 3: Filter by patterns
        print(f"[PIPELINE] Step 3: Filtering by security/privacy patterns...")
        candidates = self.filter.candidate_match(discovered_urls)
        stats["urls_after_pattern_filter"] = len(candidates)
        print(f"[PIPELINE] Candidates after pattern filter: {len(candidates)}")
        
        if not candidates:
            print(f"[PIPELINE] No candidates match patterns")
            return [], stats
        
        # STEP 4: HEAD validate
        print(f"[PIPELINE] Step 4: Validating {len(candidates)} candidates...")
        validated = await self.filter.head_validate(candidates)
        stats["urls_after_validation"] = len(validated)
        print(f"[PIPELINE] Validated URLs: {len(validated)}")
        
        if not validated:
            print(f"[PIPELINE] No URLs passed validation")
            return [], stats
        
        # STEP 5: Authority rank and cap
        print(f"[PIPELINE] Step 5: Ranking by authority...")
        ranked = self.filter.authority_rank(validated)
        ranked = ranked[:max_pages]  # Cap
        stats["urls_after_ranking"] = len(ranked)
        print(f"[PIPELINE] Top {len(ranked)} ranked URLs:")
        for r in ranked[:5]:
            print(f"  Tier {r.authority_tier}: {r.validated.final_url}")
        
        # STEP 6: Fetch and parse snippets
        print(f"[PIPELINE] Step 6: Extracting snippets from {len(ranked)} pages...")
        pages = []
        for r in ranked:
            if r.validated.content_type == "application/pdf":
                page = await self.snippet_extractor.extract_pdf_snippets(r)
            else:
                page = await self.snippet_extractor.fetch_and_parse(r)
            
            if page:
                pages.append(page)
        
        stats["pages_fetched"] = len(pages)
        print(f"[PIPELINE] Extracted snippets from {len(pages)} pages")
        
        if not pages:
            print(f"[PIPELINE] No snippets extracted")
            return [], stats
        
        # STEP 7: LLM fact extraction (only LLM cost)
        print(f"[PIPELINE] Step 7: Extracting facts via LLM...")
        facts = await self.fact_extractor.extract_facts(pages, vendor_name)
        stats["facts_extracted"] = len(facts)
        print(f"[PIPELINE] Extracted {len(facts)} facts")
        
        return facts, stats


class ResearchMode(Enum):
    FULL = "full"              # No cache, full research
    CACHED = "cached"          # Use cache, recheck stale, research missing
    CACHE_ONLY = "cache_only"  # Only return cached, no new research


class CostMode(Enum):
    """Cost optimization modes for AI backend selection"""
    ECONOMY = "economy"        # GPT-4o-mini for everything (cheapest)
    BALANCED = "balanced"      # GPT for research, Claude for synthesis (recommended)
    QUALITY = "quality"        # Claude for everything (most expensive)


# Backend configuration per cost mode
BACKEND_CONFIG = {
    CostMode.ECONOMY: {
        "discovery": "gpt-4o-mini",
        "extraction": "gpt-4o-mini",
        "verification": "gpt-4o-mini",
        "synthesis": "gpt-4o-mini",
    },
    CostMode.BALANCED: {
        "discovery": "gpt-4o-mini",
        "extraction": "gpt-4o-mini",
        "verification": "gpt-4o-mini",
        "synthesis": "claude-sonnet-4-20250514",
    },
    CostMode.QUALITY: {
        "discovery": "claude-sonnet-4-20250514",
        "extraction": "claude-sonnet-4-20250514",
        "verification": "claude-sonnet-4-20250514",
        "synthesis": "claude-sonnet-4-20250514",
    },
}


@dataclass
class FactResult:
    """A fact with its source and verification status"""
    category: str
    key: str
    value: str
    source_url: str
    source_title: str = ""
    source_snippet: str = ""
    source_type: str = "third_party"  # vendor, third_party
    confidence: float = 0.5
    verification_status: str = "pending"
    from_cache: bool = False
    from_recheck: bool = False


@dataclass
class ResearchResult:
    """Complete result from research agent"""
    vendor_name: str
    product_name: str
    facts: List[FactResult]
    synthesized_report: str
    structured_data: Dict[str, Any] = field(default_factory=dict)  # For reconciliation
    
    # Source breakdown
    facts_from_cache: int = 0
    facts_from_recheck: int = 0
    facts_from_direct_fetch: int = 0
    facts_from_path_probe: int = 0  # Deterministic HTTP path probing
    facts_from_web_search: int = 0
    
    # Performance
    cache_hit_rate: float = 0.0
    research_mode: str = "full"
    cost_mode: str = "balanced"
    duration_seconds: float = 0.0
    
    # Blocked sources (Cloudflare, bot protection, etc.)
    blocked_sources: List[Dict[str, str]] = field(default_factory=list)
    # Format: [{"url": "https://trust.vendor.com", "reason": "cloudflare", "manual_link": "https://..."}]
    
    # Candidate vendor URLs (for novel vendor bootstrap)
    # These are URLs that LOOK LIKE authoritative vendor sources but are NOT in VendorRegistry
    # They require confirmation before being promoted to registry
    # Format: [{"vendor_name", "candidate_url", "candidate_type", "confidence", "match_reason", "normalized_domain", "status", "discovered_at"}]
    candidate_vendor_urls: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    research_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    model_used: str = "claude-sonnet-4-20250514"


# Categories and fields we look for
RESEARCH_CATEGORIES = {
    "company": ["founded", "headquarters", "employees", "customers", "leadership"],
    "funding": ["valuation", "funding_total", "funding_round", "investors", "revenue"],
    "certification": ["soc2", "soc2_status", "iso27001", "hitrust", "fedramp", "hipaa_baa", "pci_dss", "nist_csf", "nist_800_53"],
    "security": ["trust_center", "breach_history", "bug_bounty", "pentest", "security_team", "security_incidents"],
    "data_handling": ["training_policy", "data_retention", "encryption", "data_residency"],
    "integration": [
        "sso", "scim", "api", "audit_logs", "rbac",
        # NEW: Expanded integration fields
        "sso_providers",          # Which SSO providers supported (Okta, Azure AD, etc.)
        "identity_provider",      # Primary IdP integration
        "api_documentation",      # Is API documented?
        "webhook_support",        # Event-driven integrations
        "ehr_integrations",       # Epic, Cerner, etc. (healthcare-specific)
        "fhir_support",           # FHIR API compliance
    ],
    # NEW: Partners/Subprocessors - critical for data flow analysis
    "partners": [
        "cloud_provider",         # AWS, Azure, GCP, Snowflake
        "ai_provider",            # OpenAI, Anthropic, etc.
        "data_subprocessors",     # List of data subprocessors
        "technology_partners",    # Integration ecosystem
        "subprocessor_list_url",  # Link to subprocessor list
        "healthcare_partners",    # Healthcare-specific partners (HealthEdge, etc.)
    ],
    # NEW: AI/ML Policy - impacts AI Model Risk score (currently 80 when unknown)
    "ai_ml": [
        "ai_training_policy",      # Does vendor train on customer data?
        "ai_data_retention",       # How long is data retained for AI processing?
        "ai_opt_out",              # Can customers opt out of AI features?
        "ai_model_provider",       # OpenAI, Anthropic, Azure, self-hosted?
        "ai_subprocessors",        # Third-party AI services used
        "ai_data_sharing",         # Is data shared with AI providers?
    ],
}

# Web search queries - used when no cached data exists
# 
# NOTE: The discovery prompt instructs the agent to:
# 1. Discover the vendor domain
# 2. Execute site: operator searches within that domain
# 3. Find trust center, security, compliance pages
#
# These queries serve as fallback/supplementary searches.
# The main discovery work is done by the comprehensive prompt in _execute_discovery_search.
WEB_SEARCH_QUERIES = [
    # PHASE 1: Discovery - The prompt instructs site: searches, these are fallbacks
    {"query": "{vendor} trust center security", "purpose": "Vendor trust center discovery", "priority": 1, "find_vendor_source": True},
    {"query": "{vendor} security compliance page", "purpose": "Vendor security page discovery", "priority": 1, "find_vendor_source": True},
    {"query": "{vendor} compliance certifications SOC HIPAA", "purpose": "Vendor compliance certifications", "priority": 1, "find_vendor_source": True},
    # PHASE 2: Specific compliance searches
    {"query": "{vendor} {product} SOC 2 Type II certification", "purpose": "SOC 2 certification status", "priority": 2},
    {"query": "{vendor} {product} HIPAA BAA business associate agreement", "purpose": "Healthcare compliance", "priority": 2},
    {"query": "{vendor} {product} ISO 27001 certification", "purpose": "ISO certification status", "priority": 2},
    {"query": "{vendor} {product} HITRUST certification", "purpose": "HITRUST certification status", "priority": 2},
    # PHASE 3: Supplementary info
    {"query": "{vendor} funding valuation investors", "purpose": "Company stability/funding", "priority": 3},
    {"query": "{vendor} {product} data breach security incident", "purpose": "Security incident history", "priority": 3},
    {"query": "{vendor} {product} enterprise SSO SCIM", "purpose": "Enterprise integrations", "priority": 3},
    {"query": "{vendor} {product} AI training data policy privacy", "purpose": "AI data handling", "priority": 3},
]

# Anti-hallucination certification prompt (shared across backends)
CERTIFICATION_EXTRACTION_RULES = """
CRITICAL RULES FOR CERTIFICATIONS:
1. ONLY claim a certification if you see EXPLICIT text stating the vendor HAS it
2. You MUST provide an exact quote (snippet) from the source for ANY certification claim
3. If a certification is mentioned in a blog post or marketing material but NOT on the trust center, mark confidence as 0.5 or lower
4. NEVER infer certifications - "HIPAA compliant" does NOT mean they have SOC 2
5. NEVER claim FedRAMP, HITRUST, CSTAR unless you see explicit certification statements
6. Common FALSE POSITIVES to avoid:
   - "HIPAA compliant" does NOT mean they sign BAAs
   - "SOC 2 compliant" without Type I/II specified is UNVERIFIED
   - Mentioning a framework does NOT mean certification
7. If you cannot find explicit proof, return the certification with value "Not confirmed" or omit it entirely
8. For BAA: distinguish between "offers BAA" vs "signs BAA on request" vs "BAA on Enterprise plan only"
"""


# =============================================================================
# DETERMINISTIC PATH PROBING
# =============================================================================
# These paths are probed via HTTP GET after discovering the vendor domain.
# This is MORE RELIABLE than asking an LLM to do site: searches because:
# 1. We control the HTTP requests directly
# 2. No reliance on search indexing
# 3. Finds pages that aren't well-indexed but exist
#
# ~35 paths at ~0.3s each = ~10-12 seconds of probing (acceptable for reliability)

COMMON_SECURITY_PATHS = [
    # Trust/Security direct paths
    "/security",
    "/trust",
    "/trust-center",
    "/trustcenter",
    "/compliance",
    "/privacy",
    
    # Certification variations (per user feedback)
    "/certifications",
    "/certificates",
    "/certified",
    "/certification",
    
    # About section (where Alivia's /about/compliance-and-security was)
    "/about/security",
    "/about/compliance",
    "/about/compliance-and-security",
    "/about/security-and-compliance",
    "/about/trust",
    "/about/certifications",
    "/about/privacy",
    
    # Company section
    "/company/security",
    "/company/compliance",
    "/company/trust",
    
    # Legal section
    "/legal/security",
    "/legal/compliance",
    "/legal/privacy",
    
    # Resources section
    "/resources/security",
    "/resources/compliance",
    "/resources/trust",
    
    # Hyphen variations
    "/security-compliance",
    "/compliance-security",
    "/privacy-security",
    "/trust-security",
    
    # Enterprise/Business
    "/enterprise/security",
    "/business/security",
    
    # Platform-specific
    "/platform/security",
    "/product/security",
    
    # HIPAA-specific (healthcare vendors)
    "/hipaa",
    "/hipaa-compliance",
    "/healthcare",
    "/healthcare-compliance",
    "/baa",
    
    # AI/ML Policy paths (NEW - for AI Model Risk assessment)
    "/ai",
    "/ai-policy",
    "/ai-principles",
    "/responsible-ai",
    "/machine-learning",
    "/data-usage",
    "/about/ai",
    "/legal/ai",
    "/privacy/ai",
    "/trust/ai",
    
    # Integration/Partner paths (NEW - reveals subprocessors)
    "/partners",
    "/about/partners",
    "/integrations",
    "/ecosystem",
    "/marketplace",
    "/apps",
    "/technology-partners",
    "/subprocessors",
    "/legal/subprocessors",
    "/privacy/subprocessors",
]

# Subdomains to check (prepended to base domain)
COMMON_SECURITY_SUBDOMAINS = [
    "trust",
    "security",
    "docs",
]


# =============================================================================
# BOT PROTECTION DETECTION
# =============================================================================

BOT_PROTECTION_INDICATORS = [
    # Cloudflare
    "cf-ray",
    "cloudflare",
    "checking your browser",
    "please wait while we verify",
    "enable javascript and cookies",
    "cf-browser-verification",
    "just a moment",
    "ray id",
    # Generic challenges
    "captcha",
    "verify you are human",
    "bot protection",
    "access denied",
    "please complete the security check",
    # Imperva/Incapsula
    "incapsula",
    "imperva",
    # Akamai
    "akamai",
    # PerimeterX
    "perimeterx",
    "px-captcha",
]


def detect_bot_protection(response_text: str, status_code: int = 200) -> Optional[str]:
    """
    Detect if a response is a bot protection challenge rather than actual content.
    
    Returns:
        str: Protection type detected (e.g., "cloudflare", "captcha") or None if legitimate content
    """
    if not response_text:
        return None
    
    # Status codes that often indicate blocking
    if status_code in [403, 503, 429]:
        return "access_blocked"
    
    text_lower = response_text.lower()
    
    # Check for very short responses that are likely challenges
    if len(response_text) < 5000:
        # Cloudflare specific
        if "cloudflare" in text_lower or "cf-ray" in text_lower:
            if "checking your browser" in text_lower or "just a moment" in text_lower:
                return "cloudflare"
        
        # Generic captcha
        if "captcha" in text_lower or "verify you are human" in text_lower:
            return "captcha"
        
        # Access denied
        if "access denied" in text_lower or "forbidden" in text_lower:
            return "access_denied"
    
    # Check for protection indicators in any size response
    for indicator in BOT_PROTECTION_INDICATORS:
        if indicator in text_lower:
            # Additional validation - these indicators in a real page might be coincidental
            # So also check for challenge-specific patterns
            if any(p in text_lower for p in ["challenge", "verify", "wait", "checking", "enable javascript"]):
                if "cloudflare" in text_lower:
                    return "cloudflare"
                elif "incapsula" in text_lower or "imperva" in text_lower:
                    return "imperva"
                elif "akamai" in text_lower:
                    return "akamai"
                elif "captcha" in text_lower:
                    return "captcha"
                else:
                    return "bot_protection"
    
    return None


class ResearchAgentV2:
    """
    Enhanced research agent with caching, verification, and direct fetching.
    Supports multiple AI backends for cost optimization.
    Uses deterministic source classification via source_classifier module.
    """
    
    def __init__(
        self, 
        anthropic_client: anthropic.Anthropic, 
        db_session,
        openai_client: OpenAI = None,
        cost_mode: CostMode = CostMode.BALANCED
    ):
        self.anthropic_client = anthropic_client
        self.openai_client = openai_client or OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.db = db_session
        self.cost_mode = cost_mode
        self.backends = BACKEND_CONFIG[cost_mode]
        self.http_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    
    def _classify_source_type(self, url: str, vendor_urls: List[Dict[str, str]]) -> str:
        """
        Classify a URL as 'vendor' or 'third_party' using centralized classifier.
        
        This is the SINGLE location where source_type is determined.
        Uses exact domain matching against VendorRegistry URLs.
        NO substring matching. NO LLM flags.
        
        Args:
            url: The source URL to classify
            vendor_urls: List from VendorRegistry.get_all_urls()
            
        Returns:
            "vendor" or "third_party"
        """
        return classify_source(url, vendor_urls).source_type
    
    def _get_effective_vendor_urls(
        self, 
        vendor_entry: Optional[VendorRegistry], 
        discovered_urls: List[str], 
        vendor_name: str
    ) -> List[Dict[str, str]]:
        """
        Get effective vendor URLs for classification.
        
        For KNOWN vendors (registry entry exists): use authoritative registry URLs.
        For NOVEL vendors (no registry entry): build from candidate discovery patterns.
        
        This ensures novel vendors get proper vendor/third_party classification
        on their first assessment, without waiting for registry promotion.
        
        Args:
            vendor_entry: VendorRegistry entry if exists, None for novel vendors
            discovered_urls: All URLs discovered during research
            vendor_name: Name of vendor being researched
            
        Returns:
            List of vendor URLs in format [{"type": "trust_center", "url": "https://..."}]
        """
        if vendor_entry:
            # Registry is authoritative for known vendors
            return vendor_entry.get_all_urls()
        
        # Novel vendor: build effective URLs from candidate patterns
        # This is deterministic - based on URL patterns, not LLM judgment
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
    
    def _reclassify_facts_with_effective_urls(
        self, 
        facts: List[FactResult], 
        effective_vendor_urls: List[Dict[str, str]]
    ) -> None:
        """
        Re-classify all facts using effective vendor URLs.
        
        For novel vendors, facts are initially classified with empty vendor_urls
        (all third_party). After discovery, we build effective_vendor_urls from
        candidates and re-classify to get proper vendor/third_party distinction.
        
        Modifies facts in place.
        """
        for fact in facts:
            if fact.source_url:
                new_source_type = self._classify_source_type(fact.source_url, effective_vendor_urls)
                if new_source_type != fact.source_type:
                    fact.source_type = new_source_type
                    # Adjust confidence based on source type
                    if new_source_type == "vendor":
                        fact.confidence = max(fact.confidence, 0.85)
    
    def _get_model_for_task(self, task: str) -> str:
        """Get the appropriate model for a task based on cost mode"""
        return self.backends.get(task, "gpt-4o-mini")
    
    def _is_claude_model(self, model: str) -> bool:
        """Check if model is a Claude model"""
        return model.startswith("claude")
    
    async def _complete(self, task: str, prompt: str, max_tokens: int = 4096, tools: list = None) -> str:
        """
        Unified completion method that routes to appropriate backend.
        Returns the text response.
        """
        model = self._get_model_for_task(task)
        
        if self._is_claude_model(model):
            return await self._claude_complete(model, prompt, max_tokens, tools)
        else:
            return await self._openai_complete(model, prompt, max_tokens)
    
    async def _claude_complete(self, model: str, prompt: str, max_tokens: int, tools: list = None) -> str:
        """Execute completion via Claude API"""
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]
        }
        if tools:
            kwargs["tools"] = tools
        
        response = await asyncio.to_thread(
            self.anthropic_client.messages.create,
            **kwargs
        )
        
        # Extract text from response
        for block in response.content:
            if hasattr(block, 'text') and block.text:
                return block.text
        return ""
    
    async def _openai_complete(self, model: str, prompt: str, max_tokens: int) -> str:
        """Execute completion via OpenAI API"""
        response = await asyncio.to_thread(
            self.openai_client.chat.completions.create,
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.choices[0].message.content or ""
    
    async def research(
        self,
        vendor_name: str,
        product_name: str = None,
        mode: ResearchMode = ResearchMode.CACHED,
        force_fields: List[str] = None,
        research_log_id: int = None
    ) -> ResearchResult:
        """
        Execute vendor research with three-phase flow.
        """
        start_time = datetime.utcnow()
        product = product_name or vendor_name
        
        all_facts: List[FactResult] = []
        facts_from_cache = 0
        facts_from_recheck = 0
        facts_from_direct_fetch = 0
        facts_from_web_search = 0
        
        # Track all discovered URLs for candidate analysis
        # This is separate from source_type classification
        discovered_urls: List[str] = []
        
        # ========================================
        # LOOKUP VENDOR ENTRY FIRST FOR CLASSIFICATION
        # ========================================
        vendor_entry = lookup_vendor(self.db, vendor_name, product)
        
        # For KNOWN vendors: use registry URLs
        # For NOVEL vendors: discover domain FIRST, build vendor_urls BEFORE research
        if vendor_entry:
            vendor_urls = vendor_entry.get_all_urls()
            print(f"[RESEARCH] Known vendor '{vendor_name}' - {len(vendor_urls)} registry URLs")
        else:
            # NOVEL VENDOR: Discover domain first (cheap single search)
            print(f"[RESEARCH] Novel vendor '{vendor_name}' - discovering domain...")
            discovered_domain = await self._discover_vendor_domain(vendor_name, product)
            
            if discovered_domain:
                print(f"[RESEARCH] Discovered domain: {discovered_domain}")
                # Build vendor_urls from discovered domain
                # This enables proper classification DURING research, not after
                vendor_urls = [
                    {"type": "main_domain", "url": f"https://{discovered_domain}"},
                    {"type": "www_domain", "url": f"https://www.{discovered_domain}"},
                ]
                # Also add common subdomains
                for subdomain in ["trust", "security", "docs"]:
                    vendor_urls.append({"type": f"{subdomain}_subdomain", "url": f"https://{subdomain}.{discovered_domain}"})
            else:
                print(f"[RESEARCH] Could not discover domain for '{vendor_name}'")
                vendor_urls = []
        
        # ========================================
        # PHASE 1: DATABASE LOOKUP
        # ========================================
        if mode != ResearchMode.FULL:
            cached_facts, stale_facts, found_fields = await self._lookup_cached_facts(
                vendor_name, product, vendor_urls
            )
            
            if len(cached_facts) >= 30:
                all_facts = cached_facts
                facts_from_cache = len(cached_facts)
                structured_data = self._build_structured_data(all_facts)
                report = await self._synthesize_report(vendor_name, product, all_facts)
                duration = (datetime.utcnow() - start_time).total_seconds()
                
                return ResearchResult(
                    vendor_name=vendor_name,
                    product_name=product,
                    facts=all_facts,
                    synthesized_report=report,
                    structured_data=structured_data,
                    facts_from_cache=facts_from_cache,
                    cache_hit_rate=1.0,
                    research_mode="cache_hit",
                    cost_mode=self.cost_mode.value,
                    duration_seconds=duration,
                    candidate_vendor_urls=[],  # No new research, no candidates
                )
            
            for fact in cached_facts:
                all_facts.append(fact)
                facts_from_cache += 1
            
            # PHASE 2: SOURCE RECHECK
            if stale_facts and mode != ResearchMode.CACHE_ONLY:
                rechecked = await self._recheck_stale_facts(stale_facts, vendor_urls, research_log_id)
                for fact in rechecked:
                    all_facts.append(fact)
                    facts_from_recheck += 1
        
        # ========================================
        # PHASE 3: NEW RESEARCH
        # ========================================
        facts_from_path_probe = 0
        
        if len(all_facts) < 30 and mode != ResearchMode.CACHE_ONLY:
            # Track fields we still need
            needed_fields = self._get_all_fields()
            for fact in all_facts:
                needed_fields.discard(f"{fact.category}:{fact.key}")
            
            # PHASE 3a: Direct fetch from known vendor URLs (registry)
            if vendor_entry:
                direct_facts, direct_urls = await self._direct_fetch_vendor(vendor_entry, vendor_urls, needed_fields)
                for fact in direct_facts:
                    all_facts.append(fact)
                    facts_from_direct_fetch += 1
                    needed_fields.discard(f"{fact.category}:{fact.key}")
                discovered_urls.extend(direct_urls)
            
            # PHASE 3b: DETERMINISTIC PATH PROBING - DISABLED
            # The path probing was burning tokens without fixing the core classification issue.
            # Novel vendors still get all sources marked as "third_party" because the
            # classifier has no vendor_urls to match against until AFTER discovery.
            # TODO: Fix novel vendor classification first, then re-enable probing.
            #
            # if vendor_domain:
            #     probe_facts, probe_urls = await self._probe_common_security_paths(...)
            #
            
            # PHASE 3c: Web search for supplementary info (fallback)
            # Only search for fields not found via direct fetch or path probing
            search_facts, search_urls = await self._web_search_research(vendor_name, product, vendor_urls, needed_fields)
            for fact in search_facts:
                all_facts.append(fact)
                facts_from_web_search += 1
            discovered_urls.extend(search_urls)
        
        # ========================================
        # PHASE 4: BUILD EFFECTIVE VENDOR URLS & RECLASSIFY
        # ========================================
        # For KNOWN vendors: effective_vendor_urls = registry URLs (already set)
        # For NOVEL vendors: build from candidate patterns in discovered URLs
        #
        # This ensures novel vendors get proper vendor/third_party classification
        # on their first assessment. "third_party" means "not owned by the vendor",
        # NOT "vendor not in registry".
        unique_urls = list(set(discovered_urls))  # Deduplicate
        effective_vendor_urls = self._get_effective_vendor_urls(vendor_entry, unique_urls, vendor_name)
        
        # Re-classify all facts with effective vendor URLs
        # For known vendors: no change (vendor_urls == effective_vendor_urls)
        # For novel vendors: facts from vendor domains now correctly classified as "vendor"
        self._reclassify_facts_with_effective_urls(all_facts, effective_vendor_urls)
        
        # ========================================
        # PHASE 5: SYNTHESIZE REPORT
        # ========================================
        report = await self._synthesize_report(vendor_name, product, all_facts)
        structured_data = self._build_structured_data(all_facts)
        
        if mode != ResearchMode.CACHE_ONLY and (facts_from_direct_fetch > 0 or facts_from_web_search > 0):
            await self._save_facts_to_db(all_facts, vendor_name, product, research_log_id)
        
        # ========================================
        # PHASE 6: CANDIDATE DISCOVERY (for UI/workflow)
        # ========================================
        # Analyze discovered URLs for candidate vendor authority sources
        # This is separate from source_type classification:
        # - source_type uses effective_vendor_urls (deterministic)
        # - candidates are for UI display and future registry promotion
        #
        # IMPORTANT: Only include URLs that classify as third_party
        # using effective_vendor_urls. For novel vendors, this means
        # URLs that WEREN'T identified by candidate patterns.
        if effective_vendor_urls:
            # Filter to only third_party URLs - these are the true candidates
            candidate_urls = [
                url for url in unique_urls
                if classify_source(url, effective_vendor_urls).source_type == "third_party"
            ]
        else:
            # No effective URLs at all - all discovered URLs are potential candidates
            candidate_urls = unique_urls
        
        candidates = collect_candidates_from_urls(vendor_name, candidate_urls)
        candidate_vendor_urls = [c.to_dict() for c in candidates]
        
        total_facts = len(all_facts)
        cache_hit_rate = facts_from_cache / total_facts if total_facts > 0 else 0.0
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        return ResearchResult(
            vendor_name=vendor_name,
            product_name=product,
            facts=all_facts,
            synthesized_report=report,
            structured_data=structured_data,
            facts_from_cache=facts_from_cache,
            facts_from_recheck=facts_from_recheck,
            facts_from_direct_fetch=facts_from_direct_fetch,
            facts_from_path_probe=facts_from_path_probe,
            facts_from_web_search=facts_from_web_search,
            cache_hit_rate=cache_hit_rate,
            research_mode=mode.value,
            cost_mode=self.cost_mode.value,
            duration_seconds=duration,
            candidate_vendor_urls=candidate_vendor_urls,
        )
    
    def _get_all_fields(self) -> set:
        """Get all field identifiers we want to research"""
        fields = set()
        for category, keys in RESEARCH_CATEGORIES.items():
            for key in keys:
                fields.add(f"{category}:{key}")
        return fields
    
    async def _lookup_cached_facts(
        self, vendor_name: str, product_name: str, vendor_urls: List[Dict[str, str]]
    ) -> Tuple[List[FactResult], List[VendorFact], set]:
        """
        Look up cached facts from database.
        
        IMPORTANT: source_type is RECOMPUTED at runtime using the classifier,
        not trusted from db_fact.source_type.
        """
        fresh_facts = []
        stale_facts = []
        found_fields = set()
        
        db_facts = self.db.query(VendorFact).filter(
            VendorFact.vendor_name == vendor_name,
            VendorFact.verification_status.in_(['verified', 'stale', 'pending'])
        ).all()
        
        for db_fact in db_facts:
            field_key = f"{db_fact.fact_category}:{db_fact.fact_key}"
            found_fields.add(field_key)
            
            if db_fact.is_fresh() and db_fact.is_verified():
                # RECOMPUTE source_type using classifier - do NOT trust db value
                source_type = self._classify_source_type(db_fact.source_url or "", vendor_urls)
                
                fresh_facts.append(FactResult(
                    category=db_fact.fact_category,
                    key=db_fact.fact_key,
                    value=db_fact.fact_value,
                    source_url=db_fact.source_url or "",
                    source_title=db_fact.source_title or "",
                    source_snippet=db_fact.source_snippet or "",
                    source_type=source_type,
                    confidence=db_fact.confidence_score,
                    verification_status=db_fact.verification_status,
                    from_cache=True,
                ))
            elif db_fact.source_url:
                stale_facts.append(db_fact)
        
        return fresh_facts, stale_facts, found_fields
    
    async def _recheck_stale_facts(
        self, stale_facts: List[VendorFact], vendor_urls: List[Dict[str, str]], research_log_id: int = None
    ) -> List[FactResult]:
        """Recheck stale facts by fetching their original source URLs."""
        rechecked = []
        
        for db_fact in stale_facts:
            if not db_fact.source_url:
                continue
            
            try:
                response = await self.http_client.get(db_fact.source_url)
                
                if response.status_code == 200:
                    page_content = response.text[:10000]
                    verification = await self._verify_fact_from_content(
                        db_fact.fact_key, db_fact.fact_value, page_content, db_fact.source_url
                    )
                    
                    # RECOMPUTE source_type using classifier
                    source_type = self._classify_source_type(db_fact.source_url, vendor_urls)
                    
                    if verification.get("confirmed"):
                        db_fact.set_verified("source_recheck", research_log_id)
                        db_fact.record_recheck("accessible")
                        db_fact.confidence_score = db_fact.calculate_confidence()
                        
                        rechecked.append(FactResult(
                            category=db_fact.fact_category,
                            key=db_fact.fact_key,
                            value=db_fact.fact_value,
                            source_url=db_fact.source_url,
                            source_type=source_type,
                            confidence=db_fact.confidence_score,
                            verification_status="verified",
                            from_recheck=True,
                        ))
                    elif verification.get("changed"):
                        db_fact.fact_value = verification["new_value"]
                        db_fact.set_verified("source_recheck", research_log_id)
                        db_fact.record_recheck("changed")
                        
                        rechecked.append(FactResult(
                            category=db_fact.fact_category,
                            key=db_fact.fact_key,
                            value=verification["new_value"],
                            source_url=db_fact.source_url,
                            source_type=source_type,
                            confidence=db_fact.confidence_score,
                            verification_status="verified",
                            from_recheck=True,
                        ))
                    else:
                        db_fact.set_disputed()
                        db_fact.record_recheck("changed")
                else:
                    db_fact.record_recheck(f"http_{response.status_code}")
                    db_fact.set_stale()
                    
            except Exception as e:
                db_fact.record_recheck("error")
                db_fact.set_stale()
        
        self.db.commit()
        return rechecked
    
    async def _verify_fact_from_content(
        self, fact_key: str, fact_value: str, page_content: str, source_url: str
    ) -> Dict:
        """Ask AI to verify if a fact still exists in page content."""
        prompt = f"""Verify if this fact is still supported by the page content.

Fact to verify:
- Key: {fact_key}
- Value: {fact_value}

Page content from {source_url}:
{page_content[:5000]}

Respond in JSON only:
{{
    "confirmed": true/false,
    "changed": true/false,
    "new_value": "...",
    "quote": "..."
}}"""
        
        text = await self._complete("verification", prompt, max_tokens=500)
        
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])
        except (json.JSONDecodeError, IndexError):
            pass
        
        return {"confirmed": False, "changed": False}
    
    async def _direct_fetch_vendor(
        self, vendor_entry: VendorRegistry, vendor_urls: List[Dict[str, str]], needed_fields: set
    ) -> Tuple[List[FactResult], List[str]]:
        """Directly fetch vendor's trust center and other authoritative pages.
        
        Returns:
            Tuple of (facts, discovered_urls) where discovered_urls are all URLs
            encountered during fetching (for candidate analysis).
        """
        facts = []
        discovered_urls = []
        urls = vendor_entry.get_all_urls()
        
        for url_info in urls:
            url = url_info["url"]
            discovered_urls.append(url)  # Track for candidate analysis
            
            try:
                response = await self.http_client.get(url)
                if response.status_code == 200:
                    page_content = response.text[:15000]
                    extracted = await self._extract_facts_from_page(
                        page_content, 
                        url,
                        url_info["type"],
                        vendor_entry.vendor_name,
                        vendor_urls,
                        needed_fields
                    )
                    
                    for fact in extracted:
                        # source_type already set by _extract_facts_from_page via classifier
                        facts.append(fact)
                        needed_fields.discard(f"{fact.category}:{fact.key}")
                        
            except Exception as e:
                continue
        
        return facts, discovered_urls
    
    async def _extract_facts_from_page(
        self, content: str, url: str, page_type: str, vendor_name: str, 
        vendor_urls: List[Dict[str, str]], needed_fields: set
    ) -> List[FactResult]:
        """Extract facts from a fetched page."""
        fields_by_category = {}
        for field in needed_fields:
            if ":" in field:
                cat, key = field.split(":")
                if cat not in fields_by_category:
                    fields_by_category[cat] = []
                fields_by_category[cat].append(key)
        
        fields_prompt = json.dumps(fields_by_category, indent=2) if fields_by_category else "{}"
        
        prompt = f"""Extract facts from this {page_type} page for {vendor_name}.

Page URL: {url}
Page content:
{content[:8000]}

Fields we need (by category):
{fields_prompt}

{CERTIFICATION_EXTRACTION_RULES}

For each fact you find, return JSON array:
[
  {{
    "category": "<category>",
    "key": "<field_key>",
    "value": "<the value - be specific>",
    "snippet": "<EXACT quote from page supporting this - REQUIRED for certifications>"
  }}
]

Important:
- Only extract facts that are EXPLICITLY stated with supporting text
- For certifications: MUST include exact quote proving the certification
- Include negative facts (e.g., "does NOT sign BAAs")
- Return empty array [] if no relevant facts found with proof"""
        
        text = await self._complete("extraction", prompt)
        
        facts = []
        try:
            start = text.find('[')
            end = text.rfind(']') + 1
            if start != -1 and end > start:
                parsed = json.loads(text[start:end])
                for item in parsed:
                    # USE CLASSIFIER for source_type - no hardcoding
                    source_type = self._classify_source_type(url, vendor_urls)
                    
                    facts.append(FactResult(
                        category=item.get("category", "unknown"),
                        key=item.get("key", ""),
                        value=item.get("value", ""),
                        source_url=url,
                        source_title=f"{vendor_name} {page_type}",
                        source_snippet=item.get("snippet", ""),
                        source_type=source_type,
                        confidence=0.85 if source_type == "vendor" else 0.7,
                    ))
        except (json.JSONDecodeError, IndexError):
            pass
        
        return facts
    
    async def _probe_common_security_paths(
        self, 
        domain: str, 
        vendor_name: str,
        vendor_urls: List[Dict[str, str]], 
        needed_fields: set
    ) -> Tuple[List[FactResult], List[str]]:
        """
        Deterministically probe common security page paths via HTTP GET.
        
        This is MORE RELIABLE than LLM-based site: searches because:
        1. We control the HTTP requests directly - guaranteed execution
        2. No reliance on search engine indexing
        3. Finds pages that exist but aren't well-indexed (like Alivia's /about/compliance-and-security)
        
        Args:
            domain: The vendor's primary domain (e.g., "aliviaanalytics.com")
            vendor_name: Vendor name for page extraction
            vendor_urls: Known vendor URLs for source classification
            needed_fields: Fields we're still looking for
            
        Returns:
            Tuple of (facts, discovered_urls) where discovered_urls are all URLs
            that returned 200 OK (for candidate analysis and fact extraction).
        """
        facts = []
        discovered_urls = []
        blocked_urls = []  # Track bot-protected pages
        
        # Normalize domain (remove protocol, trailing slash)
        domain = domain.lower().strip()
        if domain.startswith("http://"):
            domain = domain[7:]
        if domain.startswith("https://"):
            domain = domain[8:]
        if domain.startswith("www."):
            domain = domain[4:]
        domain = domain.rstrip("/")
        
        # Build list of URLs to probe
        urls_to_probe = []
        
        # Main domain paths
        for path in COMMON_SECURITY_PATHS:
            urls_to_probe.append(f"https://{domain}{path}")
            urls_to_probe.append(f"https://www.{domain}{path}")  # Also try www variant
        
        # Subdomain variants
        for subdomain in COMMON_SECURITY_SUBDOMAINS:
            urls_to_probe.append(f"https://{subdomain}.{domain}")
            urls_to_probe.append(f"https://{subdomain}.{domain}/")
        
        # Deduplicate
        urls_to_probe = list(set(urls_to_probe))
        
        # Probe in parallel with semaphore to limit concurrency
        semaphore = asyncio.Semaphore(10)  # Max 10 concurrent requests
        
        async def probe_url(url: str) -> Optional[Tuple[str, str, str]]:
            """Probe a single URL. Returns (url, content, page_type) if successful."""
            async with semaphore:
                try:
                    response = await self.http_client.get(url, timeout=10.0)
                    
                    if response.status_code == 200:
                        content = response.text
                        
                        # Check for bot protection
                        protection = detect_bot_protection(content, response.status_code)
                        if protection:
                            blocked_urls.append({"url": url, "reason": protection})
                            return None
                        
                        # Determine page type from URL
                        url_lower = url.lower()
                        if "trust" in url_lower:
                            page_type = "Trust Center"
                        elif "compliance" in url_lower:
                            page_type = "Compliance Page"
                        elif "security" in url_lower:
                            page_type = "Security Page"
                        elif "privacy" in url_lower:
                            page_type = "Privacy Policy"
                        elif "hipaa" in url_lower or "baa" in url_lower:
                            page_type = "HIPAA Compliance"
                        elif "certif" in url_lower:
                            page_type = "Certifications Page"
                        else:
                            page_type = "Vendor Page"
                        
                        return (url, content[:15000], page_type)
                        
                except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError):
                    pass
                except Exception:
                    pass
                
                return None
        
        # Execute all probes in parallel
        results = await asyncio.gather(*[probe_url(url) for url in urls_to_probe])
        
        # Process successful probes
        successful_pages = [r for r in results if r is not None]
        
        for url, content, page_type in successful_pages:
            discovered_urls.append(url)
            
            # Extract facts from the page
            extracted = await self._extract_facts_from_page(
                content, url, page_type, vendor_name, vendor_urls, needed_fields
            )
            
            for fact in extracted:
                # Boost confidence for vendor sources found via direct probing
                if fact.source_type == "vendor":
                    fact.confidence = max(fact.confidence, 0.90)  # Higher than web search
                facts.append(fact)
                needed_fields.discard(f"{fact.category}:{fact.key}")
        
        # Log probing results for debugging
        if successful_pages:
            print(f"[PATH_PROBE] {domain}: Found {len(successful_pages)} security pages")
            for url, _, page_type in successful_pages:
                print(f"  ✓ {page_type}: {url}")
        
        if blocked_urls:
            print(f"[PATH_PROBE] {domain}: {len(blocked_urls)} pages blocked by bot protection")
        
        return facts, discovered_urls
    
    async def _discover_vendor_domain(
        self, 
        vendor_name: str, 
        product_name: str
    ) -> Optional[str]:
        """
        Discover the vendor's primary domain via a simple web search.
        
        This is Phase 1 of deterministic discovery:
        1. Search for vendor's official website
        2. Extract primary domain
        3. Return domain for path probing
        
        Returns:
            Primary domain (e.g., "aliviaanalytics.com") or None if not found
        """
        model = self._get_model_for_task("discovery")
        
        prompt = f"""Find the official website domain for: {vendor_name}

Search for "{vendor_name} official website" and return ONLY the primary domain.

Return JSON:
{{
    "domain": "vendorname.com",
    "confidence": 0.9
}}

Rules:
- Return the main corporate domain, not subdomains
- Do NOT include https:// or www.
- If multiple domains exist, return the primary one
- If unsure, return null for domain"""
        
        if self._is_claude_model(model):
            try:
                response = await asyncio.to_thread(
                    self.anthropic_client.messages.create,
                    model=model,
                    max_tokens=256,
                    tools=[{"type": "web_search_20250305", "name": "web_search"}],
                    messages=[{"role": "user", "content": prompt}]
                )
                
                for block in response.content:
                    if hasattr(block, 'text') and block.text:
                        text = block.text
                        try:
                            start = text.find('{')
                            end = text.rfind('}') + 1
                            if start != -1 and end > start:
                                parsed = json.loads(text[start:end])
                                domain = parsed.get("domain")
                                if domain and "." in domain:
                                    # Clean up domain
                                    domain = domain.lower().strip()
                                    if domain.startswith("www."):
                                        domain = domain[4:]
                                    return domain
                        except (json.JSONDecodeError, ValueError):
                            pass
            except Exception:
                pass
        else:
            # OpenAI fallback - no web search, use training data
            text = await self._complete("discovery", prompt, max_tokens=256)
            try:
                start = text.find('{')
                end = text.rfind('}') + 1
                if start != -1 and end > start:
                    parsed = json.loads(text[start:end])
                    domain = parsed.get("domain")
                    if domain and "." in domain:
                        domain = domain.lower().strip()
                        if domain.startswith("www."):
                            domain = domain[4:]
                        return domain
            except (json.JSONDecodeError, ValueError):
                pass
        
        return None

    async def _web_search_research(
        self, vendor_name: str, product_name: str, vendor_urls: List[Dict[str, str]], needed_fields: set
    ) -> Tuple[List[FactResult], List[str]]:
        """Web search research with vendor source discovery.
        
        Returns:
            Tuple of (facts, discovered_urls) where discovered_urls are all URLs
            encountered during web search (for candidate analysis).
        """
        facts = []
        discovered_vendor_urls = set()
        all_discovered_urls = []  # Track ALL URLs for candidate analysis
        
        # NO MORE vendor_domains list for substring matching
        # Classification is done via _classify_source_type using vendor_urls
        
        priority_1 = [q for q in WEB_SEARCH_QUERIES if q.get("priority") == 1]
        priority_2 = [q for q in WEB_SEARCH_QUERIES if q.get("priority") == 2]
        priority_3 = [q for q in WEB_SEARCH_QUERIES if q.get("priority") == 3]
        
        # PHASE 1: Discovery
        for query_template in priority_1:
            query = query_template["query"].format(vendor=vendor_name, product=product_name)
            result = await self._execute_discovery_search(query, query_template["purpose"], vendor_urls)
            if isinstance(result, dict):
                # Track vendor URLs for direct fetch
                discovered_vendor_urls.update(result.get("vendor_urls", []))
                # Track ALL URLs for candidate analysis
                all_discovered_urls.extend(result.get("all_urls", []))
                for fact in result.get("facts", []):
                    facts.append(fact)
                    # Also track fact source URLs
                    if fact.source_url:
                        all_discovered_urls.append(fact.source_url)
        
        # PHASE 2: Direct fetch discovered URLs
        for url in discovered_vendor_urls:
            all_discovered_urls.append(url)  # Track for candidate analysis
            try:
                response = await self.http_client.get(url)
                if response.status_code == 200:
                    page_content = response.text[:15000]
                    
                    if "trust" in url.lower():
                        page_type = "Trust Center"
                    elif "security" in url.lower():
                        page_type = "Security Page"
                    elif "privacy" in url.lower():
                        page_type = "Privacy Policy"
                    else:
                        page_type = "Vendor Page"
                    
                    extracted = await self._extract_facts_from_page(
                        page_content, url, page_type, vendor_name, vendor_urls, needed_fields
                    )
                    
                    for fact in extracted:
                        # source_type already set by _extract_facts_from_page via classifier
                        # Boost confidence if vendor source
                        if fact.source_type == "vendor":
                            fact.confidence = max(fact.confidence, 0.85)
                        facts.append(fact)
                        
            except Exception:
                continue
        
        # PHASE 3: Supplementary searches
        for query_template in priority_2 + priority_3:
            query = query_template["query"].format(vendor=vendor_name, product=product_name)
            result = await self._execute_web_search_with_source_classification(
                query, query_template["purpose"], vendor_urls, needed_fields
            )
            if isinstance(result, list):
                for fact in result:
                    facts.append(fact)
                    # Track fact source URLs for candidate analysis
                    if fact.source_url:
                        all_discovered_urls.append(fact.source_url)
        
        return facts, all_discovered_urls
    
    async def _execute_discovery_search(
        self, query: str, purpose: str, vendor_urls: List[Dict[str, str]]
    ) -> Dict:
        """Execute a discovery search to find vendor trust center URLs.
        
        Returns dict with:
            - vendor_urls: URLs classified as vendor sources (for direct fetch)
            - all_urls: ALL URLs discovered (for candidate analysis)
            - facts: Extracted facts
        """
        discovered_urls = []
        all_urls = []  # Track ALL URLs for candidate analysis
        facts = []
        
        model = self._get_model_for_task("discovery")
        
        # Extract vendor name for site: queries (handle "Alivia Analytics" -> "aliviaanalytics")
        vendor_slug = query.split()[0].lower().replace(" ", "").replace("-", "").replace("_", "")
        
        prompt = f"""Role: Act as a Senior Third-Party Risk Analyst.

Task: Locate the official security, compliance, and privacy documentation for the vendor.

Search Query Context: {query}
Purpose: {purpose}

## SEARCH PROTOCOL - Execute These Specific Searches In Order:

### 1. Domain Discovery (if vendor domain unknown)
First, search to identify the vendor's primary website domain:
- Search: `{query.split()[0]} official website`
- Look for the main corporate domain (e.g., vendorname.com)

### 2. Direct Domain Searches (CRITICAL - Execute ALL of these)
Once you have the vendor domain, run these SPECIFIC searches using the site: operator:

```
site:{{vendor_domain}} "Trust Center"
site:{{vendor_domain}} security compliance
site:{{vendor_domain}} "SOC 2" OR "ISO 27001"
site:{{vendor_domain}} "HIPAA" OR "BAA" OR "Business Associate"
site:{{vendor_domain}} "subprocessors" OR "privacy policy"
site:{{vendor_domain}} compliance certifications
site:{{vendor_domain}} about security
site:{{vendor_domain}} about compliance
```

### 3. Document Discovery
Search for authoritative PDF compliance documents:
```
site:{{vendor_domain}} filetype:pdf compliance
site:{{vendor_domain}} filetype:pdf security
site:{{vendor_domain}} filetype:pdf SOC
```

### 4. Subdomain Discovery
Check for dedicated trust/security subdomains:
```
trust.{{vendor_domain}}
security.{{vendor_domain}}
```

### 5. Fallback Searches (if site: searches yield no results)
Some sites block indexing. If site: searches fail, use:
```
{query.split()[0]} security trust center
{query.split()[0]} compliance portal SOC 2
{query.split()[0]} HIPAA BAA healthcare
```

## VERIFICATION REQUIREMENTS

1. **Authoritative Source Only**: Only accept results where the URL matches the vendor's domain or a known subdomain (e.g., trust.vendor.com, docs.vendor.com)
2. **Evidence Required**: For EVERY certification claim, you MUST provide:
   - The direct URL to the source page
   - An exact quote from that page proving the claim

{CERTIFICATION_EXTRACTION_RULES}

## OUTPUT FORMAT

Return JSON with discovered URLs and extracted facts:
{{
    "vendor_domain": "vendorname.com",
    "vendor_urls": [
        "https://vendorname.com/about/compliance-and-security",
        "https://vendorname.com/security",
        "https://trust.vendorname.com",
        "https://vendorname.com/privacy-policy"
    ],
    "key_facts": [
        {{
            "category": "certification",
            "key": "soc2_status",
            "value": "SOC 2 Type II certified",
            "source_url": "https://vendorname.com/security",
            "source_title": "Security & Compliance",
            "source_snippet": "EXACT quote from page proving this claim"
        }},
        {{
            "category": "certification",
            "key": "hipaa_baa",
            "value": "BAA available upon request",
            "source_url": "https://vendorname.com/compliance",
            "source_title": "Compliance",
            "source_snippet": "We execute Business Associate Agreements with all customers"
        }}
    ]
}}

## CRITICAL REMINDERS

- Execute the site: operator searches - they constrain results to the vendor's domain
- Security pages are often at /security, /trust, /compliance, /about/security, /about/compliance-and-security
- If a site: search returns no results, the page may not be indexed - try alternate paths
- Return ALL security-relevant URLs discovered on the vendor domain
- Do NOT include third-party sources (news articles, review sites) in vendor_urls

Note: We will classify source types ourselves. Just provide the URLs and facts found."""
        
        if self._is_claude_model(model):
            # Use Claude with web search tool
            try:
                response = await asyncio.to_thread(
                    self.anthropic_client.messages.create,
                    model=model,
                    max_tokens=2048,
                    tools=[{"type": "web_search_20250305", "name": "web_search"}],
                    messages=[{"role": "user", "content": prompt}]
                )
                
                for block in response.content:
                    if hasattr(block, 'text') and block.text:
                        text = block.text
                        try:
                            start = text.find('{')
                            end = text.rfind('}') + 1
                            if start != -1 and end > start:
                                parsed = json.loads(text[start:end])
                                
                                # Collect discovered URLs for later fetching
                                for url in parsed.get("vendor_urls", []):
                                    discovered_urls.append(url)
                                    all_urls.append(url)  # Track for candidate analysis
                                
                                for item in parsed.get("key_facts", []):
                                    source_url = item.get('source_url', '')
                                    # USE CLASSIFIER - ignore any is_vendor_source from LLM
                                    source_type = self._classify_source_type(source_url, vendor_urls)
                                    
                                    facts.append(FactResult(
                                        category=item.get('category', 'unknown'),
                                        key=item.get('key', ''),
                                        value=item.get('value', ''),
                                        source_url=source_url,
                                        source_title=item.get('source_title', ''),
                                        source_snippet=item.get('source_snippet', ''),
                                        source_type=source_type,
                                        confidence=0.85 if source_type == "vendor" else 0.7,
                                    ))
                        except (json.JSONDecodeError, ValueError):
                            pass
            except Exception:
                pass
        else:
            # OpenAI path
            text = await self._complete("discovery", prompt, max_tokens=2048)
            try:
                start = text.find('{')
                end = text.rfind('}') + 1
                if start != -1 and end > start:
                    parsed = json.loads(text[start:end])
                    
                    for url in parsed.get("vendor_urls", []):
                        discovered_urls.append(url)
                        all_urls.append(url)  # Track for candidate analysis
                    
                    for item in parsed.get("key_facts", []):
                        source_url = item.get('source_url', '')
                        # USE CLASSIFIER - no substring matching
                        source_type = self._classify_source_type(source_url, vendor_urls)
                        
                        facts.append(FactResult(
                            category=item.get('category', 'unknown'),
                            key=item.get('key', ''),
                            value=item.get('value', ''),
                            source_url=source_url,
                            source_title=item.get('source_title', ''),
                            source_snippet=item.get('source_snippet', ''),
                            source_type=source_type,
                            confidence=0.85 if source_type == "vendor" else 0.7,
                        ))
            except (json.JSONDecodeError, ValueError):
                pass
        
        # Filter discovered URLs to only include vendor sources (for direct fetch)
        vendor_discovered = [url for url in discovered_urls 
                            if self._classify_source_type(url, vendor_urls) == "vendor"]
        
        return {"vendor_urls": vendor_discovered, "all_urls": all_urls, "facts": facts}
    
    async def _execute_web_search_with_source_classification(
        self, query: str, purpose: str, vendor_urls: List[Dict[str, str]], needed_fields: set
    ) -> List[FactResult]:
        """Execute web search with source classification (vendor vs third-party)."""
        facts = []
        model = self._get_model_for_task("extraction")
        
        prompt = f"""Search for: {query}

Purpose: {purpose}

{CERTIFICATION_EXTRACTION_RULES}

Extract ALL factual claims. For each fact, provide:
- category: one of {list(RESEARCH_CATEGORIES.keys())}
- key: specific attribute (e.g., "soc2_status", "hipaa_baa", "valuation")
- value: the factual value found
- source_url: where you found it
- source_title: title of the source
- source_snippet: EXACT text supporting this fact (REQUIRED for certifications)
- confidence: 0.0-1.0

Return as JSON array. Include negative findings like "does not offer HIPAA BAA".
Note: We will classify source types ourselves based on the URLs."""
        
        if self._is_claude_model(model):
            try:
                response = await asyncio.to_thread(
                    self.anthropic_client.messages.create,
                    model=model,
                    max_tokens=4096,
                    tools=[{"type": "web_search_20250305", "name": "web_search"}],
                    messages=[{"role": "user", "content": prompt}]
                )
                
                for block in response.content:
                    if hasattr(block, 'text') and block.text:
                        text = block.text
                        try:
                            start = text.find('[')
                            end = text.rfind(']') + 1
                            if start != -1 and end > start:
                                parsed = json.loads(text[start:end])
                                for item in parsed:
                                    source_url = item.get('source_url', '')
                                    # USE CLASSIFIER - no substring matching
                                    source_type = self._classify_source_type(source_url, vendor_urls)
                                    
                                    facts.append(FactResult(
                                        category=item.get('category', 'unknown'),
                                        key=item.get('key', ''),
                                        value=item.get('value', ''),
                                        source_url=source_url,
                                        source_title=item.get('source_title', ''),
                                        source_snippet=item.get('source_snippet', ''),
                                        source_type=source_type,
                                        confidence=0.85 if source_type == "vendor" else float(item.get('confidence', 0.7)),
                                    ))
                        except (json.JSONDecodeError, ValueError):
                            pass
            except Exception:
                pass
        else:
            # OpenAI path
            text = await self._complete("extraction", prompt)
            try:
                start = text.find('[')
                end = text.rfind(']') + 1
                if start != -1 and end > start:
                    parsed = json.loads(text[start:end])
                    for item in parsed:
                        source_url = item.get('source_url', '')
                        # USE CLASSIFIER - no substring matching
                        source_type = self._classify_source_type(source_url, vendor_urls)
                        
                        facts.append(FactResult(
                            category=item.get('category', 'unknown'),
                            key=item.get('key', ''),
                            value=item.get('value', ''),
                            source_url=source_url,
                            source_title=item.get('source_title', ''),
                            source_snippet=item.get('source_snippet', ''),
                            source_type=source_type,
                            confidence=0.85 if source_type == "vendor" else float(item.get('confidence', 0.7)),
                        ))
            except (json.JSONDecodeError, ValueError):
                pass
        
        return facts
    
    async def _synthesize_report(
        self, vendor_name: str, product_name: str, facts: List[FactResult]
    ) -> str:
        """Create synthesized markdown report from all facts."""
        report_date = datetime.utcnow().strftime("%B %d, %Y")
        
        facts_json = json.dumps([{
            "category": f.category,
            "key": f.key,
            "value": f.value,
            "source_url": f.source_url,
            "source_title": f.source_title or "Source",
            "source_type": f.source_type,
            "confidence": f.confidence,
            "source_snippet": f.source_snippet,
            "from_cache": f.from_cache,
        } for f in facts], indent=2)
        
        unique_sources = {}
        for f in facts:
            if f.source_url and f.source_url not in unique_sources:
                unique_sources[f.source_url] = {
                    "title": f.source_title or "Source",
                    "type": f.source_type,
                    "url": f.source_url
                }
        sources_list = json.dumps(list(unique_sources.values()), indent=2)
        
        prompt = f"""Create a vendor security research report for {vendor_name} ({product_name}).

Report Date: {report_date}

Facts gathered (includes source URLs, snippets, and confidence):
{facts_json}

Unique sources for appendix:
{sources_list}

{CERTIFICATION_EXTRACTION_RULES}

Create a professional markdown report with these sections:
1. Company Overview
2. Funding & Stability
3. Security Certifications (SOC 2, ISO, HIPAA BAA status, etc.)
4. Data Handling & Privacy
5. Security Incidents
6. Enterprise Integration
7. Cloud Infrastructure
8. Risk Summary for Healthcare Use
9. **SOURCES APPENDIX**

CRITICAL REQUIREMENTS:
- For certifications: ONLY report those with source_snippet evidence. Mark others as "Unverified" or omit.
- If a certification has low confidence (<0.7) or no snippet, mark as "Claimed but unverified"
- Use numbered citations [1], [2], etc.
- Distinguish "Not found" vs "Confirmed not available"
- Flag conflicting information between sources
- Sources section: show [Title](url) - Vendor Source OR Third Party

Report date: {report_date}"""
        
        return await self._complete("synthesis", prompt)
    
    def _build_structured_data(self, facts: List[FactResult]) -> dict:
        """Build structured data dictionary from facts for reconciliation."""
        structured = {}
        
        for fact in facts:
            category = fact.category
            key = fact.key
            
            if category not in structured:
                structured[category] = {}
            
            existing = structured[category].get(key)
            if existing is None or fact.confidence > existing.get('confidence', 0):
                structured[category][key] = {
                    'value': fact.value,
                    'source': fact.source_url,
                    'source_type': fact.source_type,
                    'confidence': fact.confidence
                }
        
        return structured
    
    async def _save_facts_to_db(
        self, facts: List[FactResult], vendor_name: str, product_name: str, research_log_id: int
    ):
        """Save or update facts in the database."""
        unique_facts: Dict[str, FactResult] = {}
        for fact in facts:
            if fact.from_cache:
                continue
            
            key = f"{fact.category}:{fact.key}"
            existing = unique_facts.get(key)
            
            if existing is None:
                unique_facts[key] = fact
            else:
                if fact.source_type == "vendor" and existing.source_type != "vendor":
                    unique_facts[key] = fact
                elif fact.source_type == existing.source_type and fact.confidence > existing.confidence:
                    unique_facts[key] = fact
        
        for fact in unique_facts.values():
            existing_db = self.db.query(VendorFact).filter(
                VendorFact.vendor_name == vendor_name,
                VendorFact.product_name == product_name,
                VendorFact.fact_category == fact.category,
                VendorFact.fact_key == fact.key
            ).first()
            
            if existing_db:
                if (fact.confidence > existing_db.confidence_score or 
                    (fact.source_type == "vendor" and existing_db.source_type != "vendor")):
                    existing_db.fact_value = fact.value
                    existing_db.source_url = fact.source_url
                    existing_db.source_title = fact.source_title
                    existing_db.source_snippet = fact.source_snippet
                    existing_db.source_type = fact.source_type
                    existing_db.confidence_score = fact.confidence
                    existing_db.set_verified("research_agent", research_log_id)
            else:
                ttl = get_ttl_for_field(fact.category, fact.key)
                priority = get_priority_for_field(fact.category, fact.key)
                
                new_fact = VendorFact(
                    vendor_name=vendor_name,
                    product_name=product_name,
                    fact_category=fact.category,
                    fact_key=fact.key,
                    fact_value=fact.value,
                    source_url=fact.source_url,
                    source_title=fact.source_title,
                    source_snippet=fact.source_snippet,
                    source_type=fact.source_type,
                    confidence_score=fact.confidence,
                    ttl_days=ttl,
                    recheck_priority=priority,
                    first_found_by_research_log_id=research_log_id,
                )
                new_fact.set_verified("research_agent", research_log_id)
                self.db.add(new_fact)
        
        self.db.commit()


# Convenience function
async def research_vendor_v2(
    client: anthropic.Anthropic,
    db_session,
    vendor_name: str,
    product_name: str = None,
    mode: ResearchMode = ResearchMode.CACHED,
    force_refresh: bool = False,
    cost_mode: CostMode = CostMode.BALANCED,
    openai_client: OpenAI = None
) -> ResearchResult:
    """Convenience function to run vendor research."""
    agent = ResearchAgentV2(
        anthropic_client=client, 
        db_session=db_session,
        openai_client=openai_client,
        cost_mode=cost_mode
    )
    research_mode = ResearchMode.FULL if force_refresh else mode
    return await agent.research(vendor_name, product_name, research_mode)
