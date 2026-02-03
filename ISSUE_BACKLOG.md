# AITGP/VDO Issue Backlog

## Active Issues (Priority Order)

### Fix 15a: Source URL Classification Bug
**Status:** Code ready, needs apply
**Issue:** `_execute_web_search_with_source_classification` hardcodes `source_type="third_party"` instead of checking URL
**Impact:** `tabnine.com/blog/...` marked as "Third Party" instead of "Vendor Source"
**Fix:** Check `source_url` against `vendor_domains` list before assigning type

### Fix 15b: FedRAMP/CSTAR Hallucinations  
**Status:** Backlog
**Issue:** Research agent claims certifications that don't exist
**Root Cause:** LLM inventing facts not present in sources
**Options:**
1. Stronger prompt: "Only claim certifications explicitly stated with exact quote"
2. Audit Agent catch (already runs but results not surfaced)
3. Verification step cross-checking against trust center
4. Require source snippet for certification claims

### Fix 15c: Generalize Cert Verification Status
**Status:** Backlog
**Issue:** Only ISO 27001 shows "(Unverified)" - others don't have this distinction
**Impact:** SOC 2, HIPAA BAA, FedRAMP all show without verification status

### Fix 15d: BAA Language Clarity
**Status:** Backlog
**Issue:** "NOT AVAILABLE - No evidence found" conflates two different states
**Correct Model:**
- "Unconfirmed" = No evidence either way, needs investigation
- "Not Available" = Vendor explicitly confirmed no BAA
- "Available" = Confirmed available (with tier/conditions if applicable)

---

## Architecture: Multi-Backend Research Agent

### Rationale
Current implementation uses Claude Sonnet for ALL research tasks. At ~10 API calls per assessment, costs add up quickly. Many tasks don't require Claude's capabilities.

### Proposed Task Routing

| Task | Current | Proposed | Est. Savings |
|------|---------|----------|--------------|
| Discovery searches (2x) | Claude Sonnet | Gemini Flash | 90% |
| Fact extraction (8x) | Claude Sonnet | GPT-4o-mini | 80% |
| Page parsing | Claude Sonnet | Gemini Pro | 70% |
| Fact verification | Claude Sonnet | Gemini Flash | 90% |
| Report synthesis | Claude Sonnet | Claude Sonnet | 0% |
| Audit check | GPT-4o | GPT-4o | 0% |

### Implementation Approach

```python
# research_agent_v2.py

class AIBackend(Enum):
    CLAUDE_SONNET = "claude-sonnet-4-20250514"
    CLAUDE_HAIKU = "claude-haiku"  # Cheaper Claude option
    GPT4O = "gpt-4o"
    GPT4O_MINI = "gpt-4o-mini"
    GEMINI_PRO = "gemini-pro"
    GEMINI_FLASH = "gemini-flash"

# Task-to-backend mapping (configurable)
TASK_BACKENDS = {
    "discovery_search": AIBackend.GEMINI_FLASH,
    "fact_extraction": AIBackend.GPT4O_MINI,
    "page_parsing": AIBackend.GEMINI_PRO,
    "fact_verification": AIBackend.GEMINI_FLASH,
    "report_synthesis": AIBackend.CLAUDE_SONNET,
    "audit_check": AIBackend.GPT4O,
}

class MultiBackendClient:
    """Unified client for multiple AI backends"""
    
    def __init__(self, anthropic_key, openai_key, google_key):
        self.anthropic = anthropic.Anthropic(api_key=anthropic_key)
        self.openai = OpenAI(api_key=openai_key)
        self.google = genai.Client(api_key=google_key)
    
    async def complete(self, task_type: str, prompt: str, **kwargs):
        backend = TASK_BACKENDS.get(task_type, AIBackend.CLAUDE_SONNET)
        
        if backend.value.startswith("claude"):
            return await self._claude_complete(backend, prompt, **kwargs)
        elif backend.value.startswith("gpt"):
            return await self._openai_complete(backend, prompt, **kwargs)
        elif backend.value.startswith("gemini"):
            return await self._gemini_complete(backend, prompt, **kwargs)
```

### Environment Variables Needed

```bash
# .env additions
OPENAI_API_KEY=sk-...
GOOGLE_AI_API_KEY=AIza...

# Optional: Override task routing
RESEARCH_DISCOVERY_BACKEND=gemini-flash
RESEARCH_EXTRACTION_BACKEND=gpt-4o-mini
RESEARCH_SYNTHESIS_BACKEND=claude-sonnet
```

### Dependencies to Add

```bash
pip install openai google-generativeai
```

### Migration Path

1. **Phase 1:** Add OpenAI client (already have for Audit Agent)
2. **Phase 2:** Add Gemini client
3. **Phase 3:** Create `MultiBackendClient` abstraction
4. **Phase 4:** Refactor `ResearchAgentV2` to use task routing
5. **Phase 5:** Add config for backend selection per task

---

## Completed Fixes

| Fix | Issue | Status |
|-----|-------|--------|
| 13 | BAA negation pattern bug | ✅ Deployed |
| 14 | Source discovery and hierarchy | ✅ Deployed |

---

## Session Notes

**2025-12-31:** User identified that multi-backend support is critical for cost management. Claude-only research is too expensive for production use. Gemini Flash and GPT-4o-mini can handle bulk search/extraction tasks at fraction of cost.
