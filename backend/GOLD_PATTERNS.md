# VDO Research Agent - Gold Patterns

> **Last Updated**: 2025-01-07
> **Status**: Production-validated patterns - do not modify without testing

These patterns have been proven reliable through production testing and debugging sessions.
They represent hard-won solutions to subtle bugs that caused incorrect behavior.

---

## 1. Novel Vendor Source Classification

**Problem Solved**: Facts from vendor's own website were being marked as `source_type: "third_party"` because the classifier had no vendor URLs to match against.

**Root Cause**: For novel vendors (not in VendorRegistry), `vendor_urls` was empty when passed to `classify_source()`, so all URLs defaulted to "third_party".

**Gold Pattern** (from v3, applied to v3.5):

```python
# In research() method - BEFORE any extraction
if vendor_entry:
    vendor_urls = vendor_entry.get_all_urls()
    print(f"Known vendor - {len(vendor_urls)} registry URLs")
else:
    # NOVEL VENDOR: Discover domain FIRST, build vendor_urls BEFORE extraction
    if not domain:
        domain = await self._discover_domain(vendor_name)
    
    if domain:
        # Normalize
        domain = domain.lower().strip()
        if domain.startswith("www."):
            domain = domain[4:]
        
        # Build vendor_urls from discovered domain
        vendor_urls = [
            {"type": "main_domain", "url": f"https://{domain}"},
            {"type": "www_domain", "url": f"https://www.{domain}"},
        ]
        for subdomain in ["trust", "security", "docs"]:
            vendor_urls.append({"type": f"{subdomain}_subdomain", "url": f"https://{subdomain}.{domain}"})
    else:
        vendor_urls = []
```

**Why It Works**: By building `vendor_urls` from the domain BEFORE extraction begins, `classify_source()` can correctly identify vendor sources during the extraction phase.

**Files**: 
- `research_agent_v2.py` (v3 implementation)
- `research_agent_v3_5.py` (v3.5 implementation)

---

## 2. Deterministic Source Classification

**Problem Solved**: Source classification was inconsistent - sometimes based on LLM judgment, sometimes on substring matching.

**Gold Pattern** (source_classifier.py):

```python
def classify_source(url: str, vendor_urls: List[Dict[str, str]]) -> ClassificationResult:
    """
    Classify a URL as vendor or third_party.
    
    Rules:
    - EXACT domain matching only (no substring matching)
    - Pure function - no network, no LLM, no side effects
    - Single source of truth for classification
    """
    input_domain = normalize_domain(url)
    domain_index = _build_domain_index(vendor_urls)
    
    if input_domain in domain_index:
        return ClassificationResult(source_type="vendor", ...)
    return ClassificationResult(source_type="third_party", ...)
```

**Why It Works**: 
- Deterministic: same input always produces same output
- Auditable: can trace exactly why a URL was classified
- Single source of truth: classification happens in ONE place

**Files**: `source_classifier.py`

---

## 3. Tool-Calling Extraction Pattern

**Problem Solved**: Pre-filtering content with keywords caused missed extractions. Multi-stage pipelines had too many failure points.

**Gold Pattern** (v3.5):

```python
# Tools for Claude
TOOLS = [
    {
        "name": "probe_url",
        "description": "HEAD request - check if URL exists before fetching"
    },
    {
        "name": "fetch_content", 
        "description": "GET request - returns content AND security_links for navigation"
    }
]

# Agentic loop
while iteration < max_iterations:
    response = client.messages.create(model=..., tools=TOOLS, messages=messages)
    
    if response.stop_reason == "tool_use":
        # Execute tools, add results to conversation
        for block in response.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input)
                # Add tool result to messages
    else:
        # Claude is done - parse final response
        break
```

**Why It Works**:
- Claude sees full content (no pre-filtering = no missed data)
- Economical: probe first (cheap), fetch only if needed
- Self-navigating: follows security_links to discover more pages
- Simpler: one LLM call loop vs multi-stage pipeline

**Files**: `research_agent_v3_5.py`

---

## 4. Security Links Discovery

**Problem Solved**: Missing pages that weren't in sitemaps or at predictable paths.

**Gold Pattern** (in fetch_content tool):

```python
def fetch_content(url: str) -> str:
    # Extract links BEFORE stripping HTML
    raw_links = re.findall(r'href=["\']([^"\']+)["\']', html)
    
    # Filter for security-related links
    security_keywords = ['security', 'compliance', 'privacy', 'trust', 'soc', ...]
    relevant_links = [link for link in raw_links 
                      if any(kw in link.lower() for kw in security_keywords)]
    
    return json.dumps({
        "content": cleaned_text,
        "security_links": relevant_links[:20]  # For Claude to follow
    })
```

**Why It Works**: Pages link to related pages. By returning discovered links, Claude can navigate to pages that aren't predictable from sitemaps or path patterns.

**Files**: `research_agent_v3_5.py`

---

## 5. AITGP Certification Extraction

**Problem Solved**: HITRUST and other HIGH_RISK certifications were being filtered out despite accurate extraction.

**Root Cause**: AITGP's extraction logic filtered certifications based on `source_type`:
```python
if risk_level == "HIGH_RISK":
    if source_type != "vendor" or confidence < 0.8:
        return None  # Silently skip
```

**Solution**: Fix source classification at the source (VDO), not patch AITGP. Once v3.5 correctly classifies vendor sources, AITGP's filtering logic works as intended.

**Files**: 
- Fix applied to `research_agent_v3_5.py` (this document)
- AITGP extraction in `aitgp-app/job-53/app.py`

---

## Production Economics

| Version | Cost/Run | Accuracy | Architecture |
|---------|----------|----------|---------------|
| v1-v2 | $5-$8 | ~50% | LLM-heavy, no httpx |
| v3 | $0.05-$0.12 | ~70% | httpx-first, LLM-last |
| **v3.5** | **$0.12 avg, $0.18 max** | **~100%** | httpx + targeted fetch |

**Key Insight**: v3.5 achieves Gemini-level accuracy while maintaining v3-level economics by:
1. httpx handles ALL HTTP (free)
2. LLM only sees targeted, high-value content
3. Probe-first pattern avoids wasted fetches

---

## Testing Checklist

When modifying any of these patterns, verify:

1. **Novel Vendor Classification**
   ```bash
   # Test with vendor NOT in registry
   python research_agent_v3_5.py "Alivia Analytics" "aliviaanalytics.com"
   # Verify: facts from aliviaanalytics.com have source_type="vendor"
   ```

2. **Known Vendor Classification**
   ```bash
   # Test with vendor IN registry
   python research_agent_v3_5.py "Tabnine"
   # Verify: facts from tabnine.com have source_type="vendor"
   ```

3. **End-to-End AITGP**
   ```bash
   # Run assessment and check report
   # Verify: HITRUST certification appears if vendor has it
   ```

---

## Version History

| Date | Change | Validated |
|------|--------|-----------|
| 2025-01-07 | Added novel vendor classification to v3.5 | ✅ |
| 2025-01-06 | v3.5 tool-calling architecture | ✅ |
| 2025-01-05 | source_classifier.py single source of truth | ✅ |
| 2025-01-04 | v3 novel vendor pattern | ✅ |
