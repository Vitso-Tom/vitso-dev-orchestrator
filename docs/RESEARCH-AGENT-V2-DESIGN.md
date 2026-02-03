# Research Agent V2 - Design Document

## Problem Statement

The current research agent has fundamental reliability issues:
- Web search results are non-deterministic (same query, different results)
- Critical compliance facts (HIPAA BAA, SOC 2) found inconsistently
- No persistence of verified findings across assessments
- Each assessment starts from scratch, wasting time and API costs
- 133 facts on one run, 59 on the next - unacceptable variability

## Solution Architecture

### Three-Phase Research Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    ASSESSMENT REQUEST                            │
│                  (vendor: Cursor, product: Cursor IDE)           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 PHASE 1: DATABASE LOOKUP                         │
│                                                                  │
│  • Check vendor_facts for existing verified facts                │
│  • Partition into: fresh/verified, stale, missing                │
│  • Fresh + verified → use directly                               │
│  • Stale → queue for recheck                                     │
│  • Missing → queue for research                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 PHASE 2: SOURCE RECHECK                          │
│                                                                  │
│  For each stale fact with source_url:                           │
│  • Fetch original source URL                                     │
│  • Ask Claude: "Does this still say [fact]?"                     │
│  • If confirmed → refresh verified_at                            │
│  • If changed → mark disputed, queue for research                │
│  • If 404/blocked → queue for research                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 PHASE 3: NEW RESEARCH                            │
│                                                                  │
│  3A. DIRECT FETCH (deterministic)                                │
│      • Lookup vendor in vendor_registry                          │
│      • Fetch known trust center URLs                             │
│      • Extract facts from authoritative sources                  │
│      • Tag as source_type: 'vendor'                              │
│                                                                  │
│  3B. WEB SEARCH (discovery)                                      │
│      • Run targeted searches for missing fields                  │
│      • Discover third-party analysis, incidents, news            │
│      • Tag as source_type: 'third_party'                         │
│                                                                  │
│  3C. AUDIT & VERIFY                                              │
│      • AuditAgent cross-checks all new facts                     │
│      • Conflicts flagged for human review                        │
│      • Verified facts stored with confidence scores              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 PHASE 4: SYNTHESIS                               │
│                                                                  │
│  • Merge: cached + rechecked + new facts                         │
│  • Generate report from combined dataset                         │
│  • Confidence based on source diversity & verification           │
│  • Return assessment with full audit trail                       │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow Summary

| Scenario | Phase 1 | Phase 2 | Phase 3 | Time |
|----------|---------|---------|---------|------|
| First assessment | Miss | Skip | Full research | ~2 min |
| Same day repeat | Hit (fresh) | Skip | Skip | ~2 sec |
| 31 days later | Hit (stale) | Recheck URLs | Partial research | ~30 sec |
| Low confidence | Hit | Recheck | Targeted research | ~45 sec |

## Database Schema

### New Tables

#### vendor_registry
Known vendors and their authoritative URLs for direct fetching.

```sql
CREATE TABLE vendor_registry (
    id SERIAL PRIMARY KEY,
    vendor_name VARCHAR(255) NOT NULL,
    vendor_aliases TEXT[], -- ['Anysphere', 'Cursor AI']
    trust_center_url VARCHAR(500),
    security_page_url VARCHAR(500),
    privacy_page_url VARCHAR(500),
    pricing_page_url VARCHAR(500),
    status_page_url VARCHAR(500),
    docs_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(vendor_name)
);
```

#### vendor_facts
The core fact store - persistent, verified vendor intelligence.

```sql
CREATE TABLE vendor_facts (
    id SERIAL PRIMARY KEY,
    
    -- Vendor identification
    vendor_name VARCHAR(255) NOT NULL,
    product_name VARCHAR(255),
    
    -- Fact data
    fact_category VARCHAR(50) NOT NULL, -- certification, funding, security, etc.
    fact_key VARCHAR(100) NOT NULL,      -- hipaa_baa, soc2_status, etc.
    fact_value TEXT NOT NULL,
    fact_context TEXT,                   -- additional context/notes
    
    -- Source tracking
    source_url VARCHAR(500),
    source_title VARCHAR(500),
    source_snippet TEXT,
    source_type VARCHAR(20) DEFAULT 'third_party', -- vendor, third_party, both
    
    -- Verification status
    verification_status VARCHAR(20) DEFAULT 'pending', -- pending, verified, disputed, stale, superseded
    verified_by VARCHAR(50),             -- audit_agent, source_recheck, manual
    verified_at TIMESTAMP,
    
    -- Confidence & freshness
    confidence_score FLOAT DEFAULT 0.5,
    ttl_days INT DEFAULT 30,
    expires_at TIMESTAMP,
    
    -- Recheck tracking
    source_last_checked_at TIMESTAMP,
    source_last_status VARCHAR(20),      -- accessible, changed, 404, blocked, timeout
    recheck_count INT DEFAULT 0,
    next_recheck_at TIMESTAMP,
    
    -- Audit trail
    first_found_at TIMESTAMP DEFAULT NOW(),
    first_found_by_research_log_id INT,
    last_updated_at TIMESTAMP DEFAULT NOW(),
    last_updated_by_research_log_id INT,
    superseded_by_id INT REFERENCES vendor_facts(id),
    
    -- Indexing
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(vendor_name, product_name, fact_category, fact_key)
);

CREATE INDEX idx_vendor_facts_vendor ON vendor_facts(vendor_name);
CREATE INDEX idx_vendor_facts_expires ON vendor_facts(expires_at);
CREATE INDEX idx_vendor_facts_verification ON vendor_facts(verification_status);
CREATE INDEX idx_vendor_facts_category ON vendor_facts(fact_category, fact_key);
```

#### fact_verification_log
Audit trail of all verification attempts.

```sql
CREATE TABLE fact_verification_log (
    id SERIAL PRIMARY KEY,
    vendor_fact_id INT REFERENCES vendor_facts(id),
    
    -- What happened
    action VARCHAR(50), -- initial_extract, recheck, manual_verify, dispute, supersede
    previous_value TEXT,
    new_value TEXT,
    previous_status VARCHAR(20),
    new_status VARCHAR(20),
    
    -- How it happened
    method VARCHAR(50), -- web_search, direct_fetch, source_recheck, audit_agent, manual
    source_url VARCHAR(500),
    source_response_status INT, -- HTTP status code
    
    -- Who/what did it
    performed_by VARCHAR(100), -- research_agent, audit_agent, user:tom
    research_log_id INT,
    
    -- Result
    confidence_delta FLOAT,
    notes TEXT,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_fact_verification_fact ON fact_verification_log(vendor_fact_id);
```

### Modified Tables

#### research_logs (add columns)
```sql
ALTER TABLE research_logs ADD COLUMN IF NOT EXISTS
    facts_from_cache INT DEFAULT 0,
    facts_from_recheck INT DEFAULT 0,
    facts_from_research INT DEFAULT 0,
    cache_hit_rate FLOAT,
    research_mode VARCHAR(20) DEFAULT 'full'; -- full, partial, cache_only
```

## Critical Compliance Fields

These fields get special treatment - always verified, lower TTL, higher recheck priority.

```python
CRITICAL_FIELDS = {
    "certification": {
        "hipaa_baa": {"ttl_days": 14, "recheck_priority": 10},
        "soc2": {"ttl_days": 30, "recheck_priority": 8},
        "iso27001": {"ttl_days": 30, "recheck_priority": 8},
        "hitrust": {"ttl_days": 30, "recheck_priority": 8},
        "fedramp": {"ttl_days": 30, "recheck_priority": 8},
    },
    "data_handling": {
        "training_policy": {"ttl_days": 14, "recheck_priority": 9},
        "data_retention": {"ttl_days": 30, "recheck_priority": 7},
    },
    "security": {
        "breach_history": {"ttl_days": 7, "recheck_priority": 10},
    }
}
```

## Confidence Score Calculation

```python
def calculate_confidence(fact: VendorFact) -> float:
    score = 0.5  # base
    
    # Source type bonus
    if fact.source_type == 'vendor':
        score += 0.2  # authoritative
    elif fact.source_type == 'both':
        score += 0.3  # corroborated
    
    # Verification bonus
    if fact.verification_status == 'verified':
        score += 0.2
    elif fact.verification_status == 'disputed':
        score -= 0.3
    
    # Freshness penalty
    age_days = (now() - fact.verified_at).days
    if age_days > fact.ttl_days:
        score -= 0.2 * (age_days / fact.ttl_days)
    
    # Recheck success bonus
    if fact.recheck_count > 0 and fact.source_last_status == 'accessible':
        score += 0.1
    
    return max(0.0, min(1.0, score))
```

## API Changes

### New Endpoints

```
GET  /api/vendors/{vendor}/facts
     Returns all cached facts for a vendor

GET  /api/vendors/{vendor}/facts/{category}
     Returns facts for a specific category

POST /api/vendors/{vendor}/facts/{fact_id}/verify
     Manual verification trigger

POST /api/vendors/{vendor}/recheck
     Force recheck of all stale facts

GET  /api/vendor-registry
     List all known vendors with trust center URLs

POST /api/vendor-registry
     Add/update vendor registry entry
```

### Modified Endpoints

```
POST /api/research-vendor
     New optional params:
     - use_cache: bool (default true)
     - force_refresh: bool (default false)
     - recheck_stale: bool (default true)
     
     Response adds:
     - cache_hit_rate: float
     - facts_from_cache: int
     - facts_from_recheck: int
     - facts_from_research: int
```

## Implementation Order

### Phase 1: Schema & Models (Day 1)
1. Create migration for new tables
2. Create SQLAlchemy models
3. Seed vendor_registry with known vendors (Cursor, Anthropic, OpenAI, etc.)

### Phase 2: Database-First Lookup (Day 1-2)
1. Add `lookup_cached_facts()` method
2. Add `partition_facts()` - fresh/stale/missing
3. Integrate into research flow before web search

### Phase 3: Source Recheck (Day 2)
1. Add `recheck_source_url()` method
2. Add `verify_fact_from_source()` Claude call
3. Update fact status based on recheck result

### Phase 4: Direct Fetch (Day 2-3)
1. Add `fetch_vendor_trust_center()` method
2. Add extraction prompt for trust center pages
3. Integrate before web search in flow

### Phase 5: Fact Persistence (Day 3)
1. Add `save_verified_fact()` method
2. Add `update_fact_verification()` method
3. Wire up audit logging

### Phase 6: Confidence & TTL (Day 3-4)
1. Implement confidence calculation
2. Add TTL expiration logic
3. Add recheck scheduling

### Phase 7: Testing & Tuning (Day 4-5)
1. Test with Cursor (known vendor)
2. Test with unknown vendor
3. Test recheck flow
4. Tune TTL and confidence thresholds

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Fact count variability | 59-133 (2x) | <10% variance |
| HIPAA BAA detection | ~50% | >95% |
| Repeat assessment time | ~2 min | <10 sec |
| Critical field coverage | Variable | 100% for known vendors |

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Source URL goes 404 | Fall back to web search, flag for registry update |
| Vendor changes trust center structure | Monitor extraction failures, alert for review |
| Cache serves stale wrong data | TTL + verification status prevents serving unverified |
| Database grows large | Supersede old facts, archive after 1 year |

## Open Questions

1. Should we expose fact verification to end users? (manual override)
2. Should disputed facts block NO-GO decisions or just flag?
3. What's the right TTL for different fact types?
4. Should we pre-populate registry or build it organically?
