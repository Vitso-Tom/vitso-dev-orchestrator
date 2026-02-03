# Fix 14: Source Discovery and Hierarchy

**Date:** 2025-12-31
**Issue:** Research agent treats all sources equally, doesn't prioritize vendor trust centers
**Root Cause:** Static vendor registry is useless for new vendors; agent doesn't discover trust centers

## Problem Identified by User

1. `trust.tabnine.com` (vendor authoritative source) should be PRIMARY
2. `nudgesecurity.com` (third-party aggregator) should be SECONDARY
3. FedRAMP was hallucinated - not in Nudge screenshot, not on Tabnine trust center
4. Static vendor registry defeats purpose of a research agent

## Solution Implemented

### Changes to `research_agent_v2.py`

#### 1. Priority-Based Search Queries
```python
WEB_SEARCH_QUERIES = [
    # PHASE 1: Discover vendor's authoritative sources FIRST
    {"query": "{vendor} trust center security", "purpose": "Vendor trust center discovery", "priority": 1, "find_vendor_source": True},
    {"query": "{vendor} security page compliance", "purpose": "Vendor security page discovery", "priority": 1, "find_vendor_source": True},
    # PHASE 2: Specific compliance searches (after trust center found)
    {"query": "{vendor} {product} SOC 2 Type II certification", "purpose": "SOC 2 certification status", "priority": 2},
    # ... etc
    # PHASE 3: Supplementary info
    {"query": "{vendor} funding valuation investors", "purpose": "Company stability/funding", "priority": 3},
    # ... etc
]
```

#### 2. New Three-Phase Web Search Flow
```
_web_search_research():
  PHASE 1: Discovery searches → find vendor trust center URLs
  PHASE 2: Direct-fetch discovered vendor URLs (authoritative, 0.85 confidence)
  PHASE 3: Supplementary searches for context (third-party, 0.7 confidence)
```

#### 3. New Methods Added
- `_execute_discovery_search()` - Finds vendor trust center URLs from search results
- `_execute_web_search_with_source_classification()` - Tags sources as vendor vs third-party

#### 4. Confidence Scoring
- Vendor source (trust center, security page): **0.85** confidence
- Third-party source (Nudge, G2, etc.): **0.70** confidence
- Synthesis prompt now requires distinguishing vendor vs third-party in citations

## Files Modified

- `backend/research_agent_v2.py` - Complete web search rewrite
- `backend/vendor_registry_seed.py` - Added Tabnine (but registry is now less important)

## What This Fixes

1. **New vendor discovery** - Agent now searches for trust center FIRST, doesn't need registry
2. **Source hierarchy** - Vendor sources weighted higher than third-party
3. **Hallucination prevention** - Facts from vendor sources get higher confidence
4. **Audit trail** - Facts tagged with source_type for transparency

## Still Outstanding

1. **Audit Agent results not surfaced** - `unsupported_claims` (hallucinations) not shown in AITGP UI
2. **FedRAMP hallucination** - Audit Agent should catch this but results aren't displayed
3. **Fix 13 not tested** - BAA negation pattern fix needs verification

## To Apply Changes

```bash
# Restart VDO backend
cd ~/vitso-dev-orchestrator
docker compose restart backend worker

# Restart AITGP Flask (if not already on 5001)
pkill -f "flask run"
cd ~/aitgp-app/job-53
python3 -m flask run --host=0.0.0.0 --port=5001 &
```

## To Test

1. Clear Tabnine from PostgreSQL cache:
   ```bash
   psql -d vdo -c "DELETE FROM vendor_facts WHERE vendor_name = 'Tabnine';"
   ```

2. Run fresh Tabnine assessment with PHI selected

3. Verify:
   - [ ] `trust.tabnine.com` appears as primary source
   - [ ] Sources appendix shows "Vendor Source" vs "Third Party"
   - [ ] No FedRAMP claim (or if present, from third-party with lower confidence)
   - [ ] Recommendation is CONDITIONAL NO-GO (BAA unconfirmed)
