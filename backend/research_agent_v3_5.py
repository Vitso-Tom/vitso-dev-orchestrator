"""
Research Agent V3.5 - Tool-Calling Architecture

DESIGN PHILOSOPHY:
- Let the LLM see everything, don't pre-filter
- Use Claude's tool-calling (function calling) for web access
- LLM decides when to probe vs fetch (economic)
- Simple pipeline with fewer failure points
- Accuracy over token efficiency

KEY CHANGES FROM V2:
- REMOVED: SnippetExtractor, SNIPPET_KEYWORDS, keyword filtering
- REMOVED: Multi-stage extraction pipeline
- ADDED: Tool-calling pattern (probe_url, fetch_content)
- ADDED: Agentic loop - Claude decides tool execution order

PIPELINE:
1. URL DISCOVERY (free) - sitemaps, path probing, registry
2. URL RANKING (free) - prioritize trust/security pages
3. AGENT EXTRACTION (tokens) - Claude calls probe/fetch tools as needed
4. SYNTHESIS (tokens) - combine facts into report

TOOL PATTERN (same as Gemini's approach):
- probe_url: HEAD request, low cost, checks if page exists
- fetch_content: GET request, returns full content for analysis

This matches Gemini's proven pattern but uses Claude's tool-use API.

=============================================================================
GOLD PATTERNS (Proven Reliable - Do Not Modify Without Testing)
=============================================================================

1. NOVEL VENDOR CLASSIFICATION (from v3)
   Location: ResearchAgentV35.research()
   Pattern: Build vendor_urls from discovered domain BEFORE extraction
   Why: Without this, classify_source() has no vendor URLs to match against,
        so all sources become "third_party" even from vendor's own site.
   Code:
       if vendor_entry:
           vendor_urls = vendor_entry.get_all_urls()
       else:
           domain = await self._discover_domain(vendor_name)
           vendor_urls = [
               {"type": "main_domain", "url": f"https://{domain}"},
               {"type": "www_domain", "url": f"https://www.{domain}"},
           ]
           for subdomain in ["trust", "security", "docs"]:
               vendor_urls.append({...})

2. SOURCE CLASSIFICATION (from source_classifier.py)
   Location: source_classifier.classify_source()
   Pattern: Exact domain matching, no substring matching, no LLM flags
   Why: Deterministic, auditable, single source of truth
   
3. TOOL-CALLING EXTRACTION
   Location: AgenticExtractor.extract_from_urls()
   Pattern: probe_url first, then fetch_content, follow security_links
   Why: Economical (probe is cheap), thorough (follows discovered links)

=============================================================================
"""

import json
import httpx
import asyncio
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse
import anthropic

from research_models_v2 import (
    VendorFact, VendorRegistry,
    get_ttl_for_field, get_priority_for_field
)
from vendor_registry_seed import lookup_vendor
from source_classifier import classify_source

try:
    import xml.etree.ElementTree as ET
except ImportError:
    ET = None


# =============================================================================
# CONFIGURATION
# =============================================================================

# Load certification types from assurance_programs.json for extraction prompts
def load_certification_types() -> List[str]:
    """Load certification/framework names from assurance_programs.json."""
    config_path = os.environ.get(
        "ASSURANCE_PROGRAMS_PATH",
        "/home/temlock/aitgp-app/job-53/config/assurance_programs.json"
    )
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            return [p.get("canonical_name", "") for p in config.get("programs", [])]
    except Exception:
        return [
            "SOC 2", "SOC 1", "ISO 27001", "HITRUST CSF", "HIPAA", "BAA",
            "NIST CSF", "NIST 800-53", "FedRAMP", "PCI DSS", "GDPR", "CCPA",
            "Cyber Essentials", "ISO 27701", "CSA STAR"
        ]

CERTIFICATION_TYPES = load_certification_types()

# Browser headers for httpx
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# URL patterns
SECURITY_URL_PATTERNS = [
    "security", "trust", "trust-center", "trustcenter", "compliance",
    "certification", "certifications", "attestation", "soc", "iso"
]
PRIVACY_URL_PATTERNS = [
    "privacy", "legal", "dpa", "gdpr", "subprocessor", "subprocessors"
]
HEALTHCARE_URL_PATTERNS = [
    "hipaa", "baa", "business-associate", "phi", "healthcare"
]
ALL_URL_PATTERNS = SECURITY_URL_PATTERNS + PRIVACY_URL_PATTERNS + HEALTHCARE_URL_PATTERNS

# Common security paths to probe
COMMON_SECURITY_PATHS = [
    "/security", "/trust", "/trust-center", "/compliance", "/privacy",
    "/certifications", "/about/security", "/about/compliance",
    "/about/compliance-and-security", "/about/security-and-compliance",
    "/about/trust", "/about/certifications", "/company/security",
    "/legal/security", "/legal/privacy", "/hipaa", "/baa",
]
SECURITY_SUBDOMAINS = ["trust", "security", "docs"]


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class DiscoveredURL:
    url: str
    source: str
    discovered_via: str


@dataclass
class RankedURL:
    url: str
    final_url: str
    authority_tier: int
    reasons: List[str]


@dataclass
class ExtractedFact:
    category: str
    key: str
    value: str
    source_url: str
    source_snippet: str
    source_type: str
    confidence: float


@dataclass
class ResearchResult:
    vendor_name: str
    product_name: str
    facts: List[ExtractedFact]
    synthesized_report: str
    structured_data: Dict[str, Any]
    urls_discovered: int = 0
    urls_processed: int = 0
    facts_extracted: int = 0
    tool_calls: Dict[str, int] = field(default_factory=dict)
    duration_seconds: float = 0.0
    research_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    pipeline_version: str = "3.5"


class ResearchMode(Enum):
    FULL = "full"
    CACHED = "cached"
    CACHE_ONLY = "cache_only"


# =============================================================================
# TOOL FUNCTIONS (Called by Claude via tool-use)
# =============================================================================

def probe_url(url: str) -> str:
    """
    Checks the status code and headers of a URL to see if it's valid.
    Use this first to verify a URL exists before fetching full content.
    Low token cost - just returns status info.
    """
    try:
        with httpx.Client(headers=BROWSER_HEADERS, follow_redirects=True, timeout=10.0) as client:
            response = client.head(url)
            return json.dumps({
                "status": response.status_code,
                "content_type": response.headers.get('Content-Type', 'unknown'),
                "final_url": str(response.url),
                "accessible": response.status_code == 200
            })
    except httpx.TimeoutException:
        return json.dumps({"error": "Timeout", "accessible": False})
    except Exception as e:
        return json.dumps({"error": str(e), "accessible": False})


def fetch_content(url: str) -> str:
    """
    Fetches the full text content of a URL.
    Use this after probe_url confirms the URL exists and is accessible.
    Returns cleaned text content AND discovered links for navigation.
    """
    try:
        with httpx.Client(headers=BROWSER_HEADERS, follow_redirects=True, timeout=20.0) as client:
            response = client.get(url)
            
            if response.status_code != 200:
                return json.dumps({"error": f"HTTP {response.status_code}", "content": None, "links": []})
            
            html = response.text
            base_url = str(response.url)
            
            # Extract links BEFORE stripping HTML
            # Find all href attributes
            raw_links = re.findall(r'href=["\']([^"\'\']+)["\']', html, re.IGNORECASE)
            
            # Filter and normalize links - keep security/compliance/privacy/trust related
            security_keywords = ['security', 'compliance', 'privacy', 'trust', 'soc', 'hipaa', 
                                 'gdpr', 'iso', 'hitrust', 'certification', 'legal', 'dpa',
                                 'baa', 'nist', 'fedramp', 'data-protection', 'safeguard']
            
            relevant_links = []
            seen_links = set()
            
            for link in raw_links:
                # Skip anchors, javascript, mailto
                if link.startswith('#') or link.startswith('javascript:') or link.startswith('mailto:'):
                    continue
                
                # Normalize relative URLs
                if link.startswith('/'):
                    # Get base domain
                    parsed = urlparse(base_url)
                    link = f"{parsed.scheme}://{parsed.netloc}{link}"
                elif not link.startswith('http'):
                    # Relative path
                    link = f"{base_url.rstrip('/')}/{link}"
                
                # Check if link contains security-related keywords
                link_lower = link.lower()
                if any(kw in link_lower for kw in security_keywords):
                    if link not in seen_links:
                        seen_links.add(link)
                        relevant_links.append(link)
            
            # Strip script/style tags and their content
            html_clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html_clean = re.sub(r'<style[^>]*>.*?</style>', '', html_clean, flags=re.DOTALL | re.IGNORECASE)
            html_clean = re.sub(r'<nav[^>]*>.*?</nav>', '', html_clean, flags=re.DOTALL | re.IGNORECASE)
            html_clean = re.sub(r'<footer[^>]*>.*?</footer>', '', html_clean, flags=re.DOTALL | re.IGNORECASE)
            html_clean = re.sub(r'<header[^>]*>.*?</header>', '', html_clean, flags=re.DOTALL | re.IGNORECASE)
            
            # Strip remaining HTML tags
            text = re.sub(r'<[^>]+>', ' ', html_clean)
            
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text).strip()
            
            # Limit to ~15k chars to manage tokens while getting full content
            return json.dumps({
                "url": url,
                "content": text[:15000],
                "truncated": len(text) > 15000,
                "security_links": relevant_links[:20]  # Cap at 20 most relevant links
            })
            
    except httpx.TimeoutException:
        return json.dumps({"error": "Timeout", "content": None, "links": []})
    except Exception as e:
        return json.dumps({"error": str(e), "content": None, "links": []})


# Tool definitions for Claude API
TOOLS = [
    {
        "name": "probe_url",
        "description": "Checks the status code and headers of a URL to see if it's valid. Use this FIRST to verify a URL exists before fetching full content. Returns status code, content type, and accessibility. Low cost operation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to probe"
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "fetch_content",
        "description": "Fetches the full text content of a URL. Use this AFTER probe_url confirms the URL exists (status 200). Returns: 1) cleaned text content, 2) security_links array containing URLs found on the page related to security/compliance/privacy. IMPORTANT: Use the security_links to discover and probe additional relevant pages rather than guessing paths.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch content from"
                }
            },
            "required": ["url"]
        }
    }
]

# Function mapping for execution
TOOL_FUNCTIONS = {
    "probe_url": probe_url,
    "fetch_content": fetch_content
}


# =============================================================================
# URL DISCOVERY (FREE - No LLM tokens)
# =============================================================================

class URLDiscovery:
    """Discovers vendor URLs via sitemaps, probing, and registry."""
    
    def __init__(self):
        self.http_client = httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers=BROWSER_HEADERS
        )
    
    async def discover(
        self,
        vendor_name: str,
        vendor_entry: Optional[VendorRegistry] = None,
        domain: Optional[str] = None
    ) -> List[DiscoveredURL]:
        """Discover all relevant URLs for a vendor."""
        discovered = []
        
        # 1. Registry URLs
        if vendor_entry:
            for url_info in vendor_entry.get_all_urls():
                discovered.append(DiscoveredURL(
                    url=url_info["url"],
                    source="registry",
                    discovered_via=f"registry:{url_info['type']}"
                ))
        
        # Get domain
        if not domain and vendor_entry:
            for url_info in vendor_entry.get_all_urls():
                try:
                    parsed = urlparse(url_info["url"])
                    domain = parsed.netloc.replace("www.", "")
                    break
                except:
                    pass
        
        if not domain:
            print(f"[DISCOVERY] No domain for {vendor_name}")
            return discovered
        
        # Normalize domain
        domain = domain.lower().strip()
        if domain.startswith("http"):
            domain = urlparse(domain).netloc
        if domain.startswith("www."):
            domain = domain[4:]
        
        # 2. Sitemap
        sitemap_urls = await self._discover_from_sitemap(domain)
        for url in sitemap_urls:
            if self._matches_security_pattern(url):
                discovered.append(DiscoveredURL(
                    url=url,
                    source="sitemap",
                    discovered_via=f"sitemap:{domain}"
                ))
        
        # 3. Path probing
        for path in COMMON_SECURITY_PATHS:
            for base in [f"https://{domain}", f"https://www.{domain}"]:
                url = f"{base}{path}"
                if await self._url_exists(url):
                    discovered.append(DiscoveredURL(
                        url=url,
                        source="probe",
                        discovered_via=f"path_probe:{path}"
                    ))
        
        # 4. Subdomain probing
        for subdomain in SECURITY_SUBDOMAINS:
            subdomain_url = f"https://{subdomain}.{domain}"
            if await self._url_exists(subdomain_url):
                discovered.append(DiscoveredURL(
                    url=subdomain_url,
                    source="probe",
                    discovered_via=f"subdomain_probe:{subdomain}"
                ))
        
        # Deduplicate
        seen = set()
        deduped = []
        for d in discovered:
            normalized = d.url.rstrip("/").lower()
            if normalized not in seen:
                seen.add(normalized)
                deduped.append(d)
        
        print(f"[DISCOVERY] Found {len(deduped)} unique URLs for {vendor_name}")
        return deduped
    
    async def _discover_from_sitemap(self, domain: str) -> List[str]:
        urls = []
        for sitemap_url in [f"https://{domain}/sitemap.xml", f"https://www.{domain}/sitemap.xml"]:
            try:
                response = await self.http_client.get(sitemap_url)
                if response.status_code == 200 and ET:
                    root = ET.fromstring(response.text)
                    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
                    for url_elem in root.findall(".//sm:url/sm:loc", ns):
                        if url_elem.text:
                            urls.append(url_elem.text)
            except:
                pass
        return urls
    
    async def _url_exists(self, url: str) -> bool:
        try:
            response = await self.http_client.head(url, timeout=5.0)
            return response.status_code in [200, 301, 302, 307, 308]
        except:
            return False
    
    def _matches_security_pattern(self, url: str) -> bool:
        url_lower = url.lower()
        return any(pattern in url_lower for pattern in ALL_URL_PATTERNS)
    
    def rank_urls(self, urls: List[DiscoveredURL]) -> List[RankedURL]:
        """Rank URLs by authority tier."""
        ranked = []
        
        for discovered in urls:
            url_lower = discovered.url.lower()
            tier = 4
            reasons = []
            
            if any(p in url_lower for p in ["/trust", "/security", "/compliance", "trust."]):
                tier = 1
                reasons.append("trust_security_page")
            elif any(p in url_lower for p in ["/privacy", "/legal", "/hipaa", "/baa"]):
                tier = 2
                reasons.append("privacy_legal_page")
            elif any(p in url_lower for p in ["/docs", "/about", "/help"]):
                tier = 3
                reasons.append("docs_about_page")
            
            if any(p in url_lower for p in ["/blog", "/news", "/article", "/press"]):
                tier = 4
                reasons.append("demoted_blog_news")
            
            if discovered.source == "registry":
                tier = max(1, tier - 1)
                reasons.append("registry_boost")
            
            ranked.append(RankedURL(
                url=discovered.url,
                final_url=discovered.url,
                authority_tier=tier,
                reasons=reasons
            ))
        
        ranked.sort(key=lambda r: r.authority_tier)
        return ranked


# =============================================================================
# AGENTIC EXTRACTOR (Claude + Tool Calling)
# =============================================================================

class AgenticExtractor:
    """
    Uses Claude's tool-calling to intelligently fetch and extract from URLs.
    
    Pattern (same as Gemini):
    1. Claude receives list of URLs to check
    2. Claude calls probe_url to check if pages exist
    3. Claude calls fetch_content for accessible pages
    4. Claude extracts certifications from fetched content
    5. Returns structured facts with evidence
    """
    
    def __init__(self, anthropic_client: anthropic.Anthropic):
        self.client = anthropic_client
        self.tool_call_counts = {"probe_url": 0, "fetch_content": 0}
    
    def _execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """Execute a tool function and return result."""
        self.tool_call_counts[tool_name] = self.tool_call_counts.get(tool_name, 0) + 1
        
        if tool_name in TOOL_FUNCTIONS:
            return TOOL_FUNCTIONS[tool_name](**tool_input)
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    
    def extract_from_urls(
        self,
        urls: List[RankedURL],
        vendor_name: str,
        vendor_urls: List[Dict[str, str]],
        max_urls: int = 10
    ) -> List[ExtractedFact]:
        """
        Run agentic extraction on a list of URLs.
        Claude decides which to probe, which to fetch, and extracts facts.
        """
        # Take top-ranked URLs
        urls_to_process = urls[:max_urls]
        url_list = "\n".join([f"- {u.url} (Tier {u.authority_tier})" for u in urls_to_process])
        
        cert_list = ", ".join(CERTIFICATION_TYPES[:15])
        
        # Build the prompt - ANTI-HALLUCINATION version
        # DO NOT list certifications to look for - this primes hallucination
        prompt = f"""You are a security analyst extracting ONLY EXPLICIT security claims from {vendor_name}'s web pages.

## URLs to Investigate
{url_list}

## Your Task
1. Use probe_url to check which URLs are accessible (start with Tier 1 pages)
2. For accessible URLs (status 200), use fetch_content to get the page content
3. IMPORTANT: When fetch_content returns security_links, probe and fetch those discovered links too
4. Extract ONLY security certifications and compliance claims that are EXPLICITLY STATED on the pages
5. Return structured findings

## CRITICAL ANTI-HALLUCINATION RULES
- ONLY report certifications/frameworks that appear VERBATIM in the page text
- If the page says "SOC 2 Type 2" - report it. If the page doesn't mention it - DO NOT report it.
- DO NOT assume common certifications exist (ISO 27001, SOC 1, SOC 3 are often assumed but not stated)
- DO NOT infer certifications from related claims (e.g., "secure" does not mean "SOC 2 certified")
- The snippet field MUST contain the EXACT text from the page that proves the claim
- If you cannot provide a verbatim quote, DO NOT include the finding
- It is BETTER to report fewer findings than to report unverified claims
- An empty findings array is acceptable if nothing explicit is found

## Output Format
After investigating, provide your findings as a JSON object:
```json
{{
    "vendor": "{vendor_name}",
    "findings": [
        {{
            "category": "certification",
            "key": "soc_2_type_ii",
            "value": "Certified",
            "source_url": "https://actual-page-url",
            "snippet": "VERBATIM quote from page: 'Company maintains SOC 2 Type II certification...'"
        }}
    ],
    "pages_checked": ["list of URLs actually fetched"],
    "pages_blocked": ["list of URLs that returned 403/blocked"]
}}
```

## What Counts as Valid Evidence
✅ "We maintain SOC 2 Type 2 compliance" → report SOC 2 Type II
✅ "HITRUST CSF r2 Certified" → report HITRUST r2
✅ "ISO/IEC 27001:2013 certified" → report ISO 27001
❌ "We follow industry best practices" → DO NOT report any certification
❌ "Enterprise-grade security" → DO NOT report any certification
❌ "We take security seriously" → DO NOT report any certification

## Conditional Findings
If a capability depends on tier/plan, report it accurately:
- "BAA available for Enterprise customers only" → value: "Available (Enterprise only)"
- "SSO available on Pro and Enterprise plans" → value: "Available (Pro+ plans)"

Start by probing the Tier 1 URLs to see which are accessible."""

        messages = [{"role": "user", "content": prompt}]
        
        # Agentic loop
        max_iterations = 20  # Safety limit
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                tools=TOOLS,
                messages=messages
            )
            
            # Check if Claude wants to use tools
            if response.stop_reason == "tool_use":
                tool_results = []
                
                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        
                        print(f"  [TOOL] {tool_name}({tool_input.get('url', '')[:60]}...)")
                        
                        result = self._execute_tool(tool_name, tool_input)
                        
                        # Log result summary
                        try:
                            result_data = json.loads(result)
                            if "status" in result_data:
                                print(f"         → Status: {result_data.get('status')}, Accessible: {result_data.get('accessible')}")
                            elif "content" in result_data:
                                content_len = len(result_data.get("content", "") or "")
                                links_found = len(result_data.get("security_links", []))
                                print(f"         → Fetched {content_len} chars, {links_found} security links found")
                                if links_found > 0:
                                    for link in result_data.get("security_links", [])[:5]:
                                        print(f"            • {link}")
                                    if links_found > 5:
                                        print(f"            ... and {links_found - 5} more")
                            elif "error" in result_data:
                                print(f"         → Error: {result_data.get('error')}")
                        except:
                            pass
                        
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result
                        })
                
                # Add to conversation
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
                
            else:
                # Claude is done - extract final response
                final_text = ""
                for block in response.content:
                    if hasattr(block, 'text'):
                        final_text += block.text
                
                # Parse findings
                return self._parse_findings(final_text, vendor_urls)
        
        print(f"  [WARN] Max iterations ({max_iterations}) reached")
        return []
    
    def _parse_findings(
        self,
        response_text: str,
        vendor_urls: List[Dict[str, str]]
    ) -> List[ExtractedFact]:
        """Parse Claude's final response into ExtractedFact objects with verification."""
        facts = []
        
        try:
            # Find JSON in response
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            
            if start != -1 and end > start:
                parsed = json.loads(response_text[start:end])
                
                # Log blocked pages for transparency
                blocked = parsed.get("pages_blocked", [])
                if blocked:
                    print(f"  [BLOCKED] {len(blocked)} pages returned 403: {blocked[:3]}")
                
                for item in parsed.get("findings", []):
                    key = item.get("key", "")
                    value = item.get("value", "")
                    snippet = item.get("snippet", "")
                    source_url = item.get("source_url", "")
                    
                    # VERIFICATION: Check if snippet actually supports the claim
                    # This catches hallucinations where Claude invents snippets
                    if not self._verify_snippet(key, value, snippet):
                        print(f"  [SKIP] '{key}' - snippet doesn't support claim: {snippet[:80]}...")
                        continue
                    
                    source_type = classify_source(source_url, vendor_urls).source_type
                    
                    facts.append(ExtractedFact(
                        category=item.get("category", "unknown"),
                        key=key,
                        value=value,
                        source_url=source_url,
                        source_snippet=snippet,
                        source_type=source_type,
                        confidence=0.95 if source_type == "vendor" else 0.85
                    ))
                    print(f"  [FACT] {key}: {value} (source_type={source_type})")
                    
        except (json.JSONDecodeError, ValueError) as e:
            print(f"  [WARN] Failed to parse findings: {e}")
        
        return facts
    
    def _verify_snippet(self, key: str, value: str, snippet: str) -> bool:
        """
        Verify that the snippet actually contains evidence of the claimed certification.
        Returns False if this looks like a hallucination.
        """
        if not snippet or len(snippet) < 10:
            return False
        
        snippet_lower = snippet.lower()
        key_lower = key.lower().replace("_", " ")
        
        # Build verification patterns from the key
        # e.g., "soc_2_type_ii" -> ["soc 2", "type ii", "type 2"]
        patterns = []
        
        if "soc" in key_lower:
            if "1" in key_lower:
                patterns.extend(["soc 1", "soc1"])
            elif "2" in key_lower:
                patterns.extend(["soc 2", "soc2"])
            elif "3" in key_lower:
                patterns.extend(["soc 3", "soc3"])
        
        if "iso" in key_lower:
            if "27001" in key_lower:
                patterns.extend(["iso 27001", "iso/iec 27001", "27001"])
            elif "27701" in key_lower:
                patterns.extend(["iso 27701", "27701"])
            elif "9001" in key_lower:
                patterns.extend(["iso 9001", "9001"])
        
        if "hitrust" in key_lower:
            patterns.extend(["hitrust", "hit trust"])
        
        if "hipaa" in key_lower:
            patterns.extend(["hipaa"])
        
        if "baa" in key_lower or "business_associate" in key_lower:
            patterns.extend(["baa", "business associate agreement", "business associate"])
        
        if "gdpr" in key_lower:
            patterns.extend(["gdpr", "general data protection"])
        
        if "fedramp" in key_lower:
            patterns.extend(["fedramp", "fed ramp"])
        
        if "pci" in key_lower:
            patterns.extend(["pci", "payment card"])
        
        if "nist" in key_lower:
            patterns.extend(["nist"])
        
        # If no specific patterns, use the key itself
        if not patterns:
            patterns = [key_lower.replace("_", " ")]
        
        # Check if ANY pattern appears in snippet
        for pattern in patterns:
            if pattern in snippet_lower:
                return True
        
        # Snippet doesn't contain expected evidence
        return False


# =============================================================================
# REPORT SYNTHESIS
# =============================================================================

class ReportSynthesizer:
    """Synthesizes extracted facts into a structured report."""
    
    def __init__(self, anthropic_client: anthropic.Anthropic):
        self.client = anthropic_client
    
    def synthesize(
        self,
        vendor_name: str,
        product_name: str,
        facts: List[ExtractedFact]
    ) -> str:
        """Generate markdown report from extracted facts."""
        
        if not facts:
            return f"# {vendor_name} Security Assessment\n\nNo security or compliance information found."
        
        facts_json = json.dumps([{
            "category": f.category,
            "key": f.key,
            "value": f.value,
            "source_url": f.source_url,
            "source_type": f.source_type,
            "snippet": f.source_snippet,
            "confidence": f.confidence
        } for f in facts], indent=2)
        
        prompt = f"""Create a security assessment report for {vendor_name} ({product_name}).

EXTRACTED FACTS (verified from web pages):
{facts_json}

REPORT STRUCTURE:
1. Executive Summary
2. Security Certifications
3. Healthcare Compliance (HIPAA, BAA status)
4. Data Handling & Privacy
5. Risk Summary for Healthcare Use
6. Sources

## CRITICAL RULES - READ CAREFULLY
- ONLY include certifications/frameworks that appear in the EXTRACTED FACTS above
- DO NOT add certifications that are not in the facts (no ISO 27001 unless it's in the facts)
- DO NOT assume or infer certifications
- If a certification is missing from the facts, it means we could not verify it
- Use "Source (Vendor)" or "Source (Third-party)" based on source_type in facts
- Include exact quotes (snippets) where available
- If important security pages were blocked (403), note this as a limitation

## What to do if certifications are missing
- If SOC 2 is not in facts, do NOT mention SOC 2 in the report
- If ISO 27001 is not in facts, do NOT mention ISO 27001
- If BAA is not in facts, say "BAA availability could not be verified"
- It is better to have a short report than to include unverified claims

Report date: {datetime.utcnow().strftime("%B %d, %Y")}"""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        
        for block in response.content:
            if hasattr(block, 'text'):
                return block.text
        
        return f"# {vendor_name} Security Assessment\n\nReport generation failed."
    
    def build_structured_data(self, facts: List[ExtractedFact]) -> Dict[str, Any]:
        """Build structured data dictionary from facts."""
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
                    'confidence': fact.confidence,
                    'snippet': fact.source_snippet
                }
        
        return structured


# =============================================================================
# MAIN RESEARCH AGENT
# =============================================================================

class ResearchAgentV35:
    """
    Research Agent v3.5 - Tool-calling architecture.
    
    Uses Claude's tool-use API with probe_url and fetch_content functions,
    matching Gemini's proven pattern for accurate web content extraction.
    """
    
    def __init__(
        self,
        anthropic_client: anthropic.Anthropic,
        db_session,
        max_urls_per_vendor: int = 10
    ):
        self.anthropic_client = anthropic_client
        self.db = db_session
        self.max_urls = max_urls_per_vendor
        
        self.discovery = URLDiscovery()
        self.extractor = AgenticExtractor(anthropic_client)
        self.synthesizer = ReportSynthesizer(anthropic_client)
    
    async def research(
        self,
        vendor_name: str,
        product_name: str = None,
        mode: ResearchMode = ResearchMode.FULL,
        domain: str = None
    ) -> ResearchResult:
        """Execute vendor research with tool-calling approach."""
        start_time = datetime.utcnow()
        product = product_name or vendor_name
        
        # Lookup vendor
        vendor_entry = lookup_vendor(self.db, vendor_name, product)
        
        # ========================================
        # BUILD vendor_urls FOR CLASSIFICATION
        # (Gold pattern from v3 - enables proper source_type during extraction)
        # ========================================
        if vendor_entry:
            vendor_urls = vendor_entry.get_all_urls()
            print(f"[V3.5] Known vendor '{vendor_name}' - {len(vendor_urls)} registry URLs")
        else:
            # NOVEL VENDOR: Discover domain FIRST, build vendor_urls BEFORE extraction
            # This is the key fix - without this, all sources become "third_party"
            if not domain:
                print(f"[V3.5] Novel vendor '{vendor_name}' - discovering domain...")
                domain = await self._discover_domain(vendor_name)
            
            if domain:
                print(f"[V3.5] Building vendor_urls from domain: {domain}")
                # Normalize domain
                domain = domain.lower().strip()
                if domain.startswith("www."):
                    domain = domain[4:]
                
                # Build vendor_urls from discovered domain
                # This enables proper classification DURING extraction, not after
                vendor_urls = [
                    {"type": "main_domain", "url": f"https://{domain}"},
                    {"type": "www_domain", "url": f"https://www.{domain}"},
                ]
                # Also add common subdomains
                for subdomain in ["trust", "security", "docs"]:
                    vendor_urls.append({"type": f"{subdomain}_subdomain", "url": f"https://{subdomain}.{domain}"})
                print(f"[V3.5] Built {len(vendor_urls)} effective vendor URLs for classification")
            else:
                print(f"[V3.5] Could not discover domain for '{vendor_name}' - classification will be limited")
                vendor_urls = []
        
        # Phase 1: URL Discovery
        print(f"\n[V3.5] Starting research for {vendor_name}")
        print(f"[V3.5] Phase 1: URL Discovery...")
        
        discovered_urls = await self.discovery.discover(vendor_name, vendor_entry, domain)
        
        if not discovered_urls:
            print(f"[V3.5] No URLs found")
            return ResearchResult(
                vendor_name=vendor_name,
                product_name=product,
                facts=[],
                synthesized_report=f"# {vendor_name}\n\nNo security pages found.",
                structured_data={},
                urls_discovered=0
            )
        
        # Phase 2: Rank URLs
        print(f"[V3.5] Phase 2: Ranking {len(discovered_urls)} URLs...")
        ranked_urls = self.discovery.rank_urls(discovered_urls)
        
        # Phase 3: Agentic Extraction
        print(f"[V3.5] Phase 3: Agentic extraction (max {self.max_urls} URLs)...")
        
        facts = self.extractor.extract_from_urls(
            ranked_urls,
            vendor_name,
            vendor_urls,
            max_urls=self.max_urls
        )
        
        # Deduplicate
        unique_facts = self._deduplicate_facts(facts)
        print(f"[V3.5] Extracted {len(unique_facts)} unique facts")
        
        # Phase 4: Synthesize
        print(f"[V3.5] Phase 4: Synthesizing report...")
        report = self.synthesizer.synthesize(vendor_name, product, unique_facts)
        structured_data = self.synthesizer.build_structured_data(unique_facts)
        
        # Save to DB
        if unique_facts:
            await self._save_facts(unique_facts, vendor_name, product)
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        print(f"[V3.5] Complete in {duration:.1f}s")
        print(f"[V3.5] Tool calls: {self.extractor.tool_call_counts}")
        
        return ResearchResult(
            vendor_name=vendor_name,
            product_name=product,
            facts=unique_facts,
            synthesized_report=report,
            structured_data=structured_data,
            urls_discovered=len(discovered_urls),
            urls_processed=self.max_urls,
            facts_extracted=len(unique_facts),
            tool_calls=self.extractor.tool_call_counts.copy(),
            duration_seconds=duration
        )
    
    async def _discover_domain(self, vendor_name: str) -> Optional[str]:
        """Quick search to find vendor's domain."""
        try:
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=256,
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
                messages=[{
                    "role": "user",
                    "content": f"What is the official website domain for {vendor_name}? Return only the domain like 'company.com'."
                }]
            )
            
            for block in response.content:
                if hasattr(block, 'text') and block.text:
                    text = block.text.strip().lower()
                    text = text.replace("https://", "").replace("http://", "").replace("www.", "")
                    text = text.split("/")[0].split()[0]
                    if "." in text:
                        return text
        except:
            pass
        return None
    
    def _deduplicate_facts(self, facts: List[ExtractedFact]) -> List[ExtractedFact]:
        """Keep highest confidence fact per key."""
        best = {}
        for fact in facts:
            key = f"{fact.category}:{fact.key}"
            existing = best.get(key)
            if existing is None:
                best[key] = fact
            elif fact.source_type == "vendor" and existing.source_type != "vendor":
                best[key] = fact
            elif fact.confidence > existing.confidence:
                best[key] = fact
        return list(best.values())
    
    async def _save_facts(self, facts: List[ExtractedFact], vendor_name: str, product_name: str):
        """Save facts to database."""
        for fact in facts:
            existing = self.db.query(VendorFact).filter(
                VendorFact.vendor_name == vendor_name,
                VendorFact.product_name == product_name,
                VendorFact.fact_category == fact.category,
                VendorFact.fact_key == fact.key
            ).first()
            
            if existing:
                if fact.confidence > existing.confidence_score:
                    existing.fact_value = fact.value
                    existing.source_url = fact.source_url
                    existing.source_snippet = fact.source_snippet
                    existing.source_type = fact.source_type
                    existing.confidence_score = fact.confidence
            else:
                new_fact = VendorFact(
                    vendor_name=vendor_name,
                    product_name=product_name,
                    fact_category=fact.category,
                    fact_key=fact.key,
                    fact_value=fact.value,
                    source_url=fact.source_url,
                    source_snippet=fact.source_snippet,
                    source_type=fact.source_type,
                    confidence_score=fact.confidence,
                    ttl_days=get_ttl_for_field(fact.category, fact.key),
                    recheck_priority=get_priority_for_field(fact.category, fact.key),
                )
                self.db.add(new_fact)
        
        self.db.commit()


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

async def research_vendor_v35(
    client: anthropic.Anthropic,
    db_session,
    vendor_name: str,
    product_name: str = None,
    domain: str = None,
    max_urls: int = 10
) -> ResearchResult:
    """Convenience function to run v3.5 research."""
    agent = ResearchAgentV35(
        anthropic_client=client,
        db_session=db_session,
        max_urls_per_vendor=max_urls
    )
    return await agent.research(vendor_name, product_name, domain=domain)


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    import sys
    
    async def test():
        client = anthropic.Anthropic()
        
        class MockDB:
            def query(self, *args): return self
            def filter(self, *args): return self
            def first(self): return None
            def add(self, *args): pass
            def commit(self): pass
        
        vendor = sys.argv[1] if len(sys.argv) > 1 else "Alivia Analytics"
        domain = sys.argv[2] if len(sys.argv) > 2 else "aliviaanalytics.com"
        
        agent = ResearchAgentV35(
            anthropic_client=client,
            db_session=MockDB(),
            max_urls_per_vendor=5
        )
        
        result = await agent.research(
            vendor_name=vendor,
            product_name=vendor,
            domain=domain
        )
        
        print("\n" + "="*60)
        print("FACTS EXTRACTED:")
        print("="*60)
        for f in result.facts:
            print(f"\n[{f.category}] {f.key}: {f.value}")
            print(f"  Source: {f.source_url}")
            if f.source_snippet:
                print(f"  Evidence: \"{f.source_snippet[:150]}...\"")
        
        print("\n" + "="*60)
        print("REPORT:")
        print("="*60)
        print(result.synthesized_report)
        
        print("\n" + "="*60)
        print(f"Stats: {result.urls_discovered} discovered, {result.facts_extracted} facts")
        print(f"Tool calls: {result.tool_calls}")
        print(f"Duration: {result.duration_seconds:.1f}s")
    
    asyncio.run(test())
