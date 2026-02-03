# AITGP Integration with VDO v3.5 - Migration Guide

> **Document Version**: 1.0
> **Last Updated**: 2025-01-07
> **Status**: Action items for AITGP alignment with v3.5 gold standard
> **Location**: Copy this file to ~/aitgp-app/job-53/AITGP_V35_MIGRATION.md

---

## Executive Summary

VDO v3.5 is now the gold standard for vendor research. AITGP needs to:
1. ✅ Receive correctly classified source_type (fixed in VDO)
2. 🔄 Verify integration path uses v3.5
3. 🔄 Reconcile certification key names
4. 🔄 Validate filtering logic works with v3.5 output

---

## Current State Analysis

### What's Working

1. **VDO v3.5 extraction** - Accurate, with evidence quotes
2. **Source classification** - Fixed with novel vendor pattern
3. **structured_data format** - Compatible with AITGP expectations

### What Needs Verification

1. **Integration endpoint** - Is AITGP calling v3.5 or older version?
2. **Key name matching** - Do v3.5 keys match assurance_programs.json?
3. **Confidence values** - Are they passing AITGP thresholds?

---

## Issue #1: Integration Endpoint

### Current AITGP Code (app.py)

```python
# Need to verify which research function is called
async def run_assessment(vendor_name, product_name):
    # Is this using v3.5?
    research_result = await research_vendor(...)  # Which version?
```

### Required Change

Ensure AITGP calls the v3.5 research function:

```python
from research_agent_v3_5 import research_vendor_v35

async def run_assessment(vendor_name, product_name, domain=None):
    research_result = await research_vendor_v35(
        client=anthropic_client,
        db_session=db,
        vendor_name=vendor_name,
        product_name=product_name,
        domain=domain,  # Optional, helps novel vendor classification
        max_urls=10
    )
    
    # Use research_result.structured_data for certification extraction
    structured_data = research_result.structured_data
```

### Verification Steps

```bash
# Check what's imported in app.py
grep -n "research_agent\|research_vendor" ~/aitgp-app/job-53/app.py

# Check if v3.5 is available
ls -la ~/vitso-dev-orchestrator/backend/research_agent_v3_5.py
```

---

## Issue #2: Certification Key Name Reconciliation

### The Problem

v3.5 generates natural key names based on what Claude extracts:
```json
{
  "certification": {
    "hitrust_r2": {"value": "Certified", ...},
    "soc_2_type_ii": {"value": "Certified", ...}
  }
}
```

assurance_programs.json may expect different keys:
```json
{
  "programs": [
    {
      "canonical_name": "HITRUST CSF",
      "aliases": ["hitrust", "hitrust csf", "hitrust r2"],
      "key": "hitrust_csf"  // Different from "hitrust_r2"
    }
  ]
}
```

### Solution Options

#### Option A: Flexible Matching in AITGP (Recommended)

```python
def match_certification_to_program(cert_key, cert_value):
    """
    Match a v3.5 certification key to assurance_programs.json entry.
    Uses fuzzy matching on canonical_name, aliases, and key.
    """
    cert_key_lower = cert_key.lower().replace("_", " ").replace("-", " ")
    
    for program in ASSURANCE_PROGRAMS:
        # Check exact key match
        if program.get("key", "").lower() == cert_key.lower():
            return program
        
        # Check canonical name match
        canonical = program.get("canonical_name", "").lower()
        if cert_key_lower in canonical or canonical in cert_key_lower:
            return program
        
        # Check aliases
        for alias in program.get("aliases", []):
            alias_lower = alias.lower()
            if cert_key_lower in alias_lower or alias_lower in cert_key_lower:
                return program
    
    return None  # No match found
```

#### Option B: Standardize Keys in v3.5 Prompt

Add key standardization to v3.5 extraction prompt:
```
Use these EXACT keys for certifications:
- hitrust_csf (not hitrust_r2)
- soc2_type_ii (not soc_2_type_ii)
- iso_27001 (not iso27001)
```

**Downside**: Constrains Claude's natural extraction, may reduce accuracy.

#### Option C: Post-Processing in VDO

Add key normalization before returning structured_data:
```python
KEY_NORMALIZATION = {
    "hitrust_r2": "hitrust_csf",
    "hitrust r2": "hitrust_csf",
    "soc_2_type_ii": "soc2_type_ii",
    "soc 2 type ii": "soc2_type_ii",
}

def normalize_keys(structured_data):
    cert_data = structured_data.get("certification", {})
    normalized = {}
    for key, value in cert_data.items():
        normalized_key = KEY_NORMALIZATION.get(key.lower(), key)
        normalized[normalized_key] = value
    structured_data["certification"] = normalized
    return structured_data
```

### Recommendation

**Option A** - Flexible matching in AITGP is most robust because:
1. Doesn't constrain v3.5's accurate extraction
2. Handles future certification naming variations
3. Centralizes matching logic in one place

---

## Issue #3: Certification Filtering Logic

### Current AITGP Logic (Confirmed Working)

```python
def extract_certifications_from_research(structured_data, vendor_name):
    """Extract certifications from research data."""
    certifications = []
    
    cert_data = structured_data.get("certification", {})
    for key, data in cert_data.items():
        program = match_certification_to_program(key, data.get("value", ""))
        
        if program:
            risk_level = program.get("risk_level", "MEDIUM_RISK")
            source_type = data.get("source_type", "third_party")
            confidence = data.get("confidence", 0.5)
            
            # HIGH_RISK filtering - this is correct
            if risk_level == "HIGH_RISK":
                if source_type != "vendor":
                    print(f"[FILTER] Skipping {key}: HIGH_RISK but source_type={source_type}")
                    continue
                if confidence < 0.8:
                    print(f"[FILTER] Skipping {key}: HIGH_RISK but confidence={confidence}")
                    continue
            
            certifications.append({
                "canonical_name": program["canonical_name"],
                "value": data["value"],
                "source": data.get("source"),
                "source_type": source_type,
                "confidence": confidence,
                "risk_level": risk_level
            })
    
    return certifications
```

### v3.5 Output (After Fix)

```json
{
  "certification": {
    "hitrust_r2": {
      "value": "Certified",
      "source": "https://aliviaanalytics.com/about/compliance-and-security",
      "source_type": "vendor",  // ← NOW CORRECT (was "third_party")
      "confidence": 0.95,       // ← Exceeds 0.8 threshold
      "snippet": "...HITRUST r2 Certified status..."
    }
  }
}
```

### Expected Result

With the v3.5 fix:
1. `source_type` = "vendor" ✅
2. `confidence` = 0.95 > 0.8 ✅
3. HITRUST passes HIGH_RISK filter ✅
4. Appears in final report ✅

---

## Issue #4: assurance_programs.json Completeness

### Current Coverage Check

```bash
# List all programs in assurance_programs.json
cat ~/aitgp-app/job-53/config/assurance_programs.json | jq '.programs[].canonical_name'
```

### Required Programs for Healthcare

| Program | risk_level | Required |
|---------|------------|----------|
| HITRUST CSF | HIGH_RISK | ✅ Critical |
| SOC 2 Type II | HIGH_RISK | ✅ Critical |
| ISO 27001 | MEDIUM_RISK | ✅ Important |
| HIPAA | HIGH_RISK | ✅ Critical |
| HIPAA BAA | HIGH_RISK | ✅ Critical |
| NIST CSF | MEDIUM_RISK | Recommended |
| NIST 800-53 | HIGH_RISK | For FedRAMP |
| SOC 1 | MEDIUM_RISK | Financial |
| PCI DSS | HIGH_RISK | If payment |

### Add Missing Programs

If any are missing from assurance_programs.json:

```json
{
  "canonical_name": "HITRUST CSF",
  "aliases": ["hitrust", "hitrust csf", "hitrust r2", "hitrust certified"],
  "key": "hitrust_csf",
  "risk_level": "HIGH_RISK",
  "category": "certification",
  "verification_url_patterns": ["/trust", "/security", "/compliance"],
  "evidence_keywords": ["hitrust", "certified", "r2", "csf"]
}
```

---

## Migration Checklist

### Phase 1: Verification (Do First)

- [ ] Confirm which research function AITGP currently calls
- [ ] Run test assessment with debug logging
- [ ] Verify structured_data format from v3.5

### Phase 2: Integration Updates

- [ ] Update AITGP to import `research_vendor_v35`
- [ ] Add flexible key matching function
- [ ] Update extraction to use flexible matching

### Phase 3: Testing

- [ ] Test with Alivia Analytics (novel vendor, HITRUST)
- [ ] Test with Tabnine (known vendor, multiple certs)
- [ ] Test with vendor missing certifications (should report "Not found")

### Phase 4: Production

- [ ] Deploy updated AITGP
- [ ] Monitor certification extraction accuracy
- [ ] Document any new edge cases

---

## Debug Logging Recommendations

Add these logs to AITGP for troubleshooting:

```python
def extract_certifications_from_research(structured_data, vendor_name):
    print(f"[CERT_EXTRACT] Processing vendor: {vendor_name}")
    print(f"[CERT_EXTRACT] structured_data keys: {structured_data.keys()}")
    
    cert_data = structured_data.get("certification", {})
    print(f"[CERT_EXTRACT] Found {len(cert_data)} certification entries")
    
    for key, data in cert_data.items():
        print(f"[CERT_EXTRACT] Processing: {key}")
        print(f"  value: {data.get('value')}")
        print(f"  source_type: {data.get('source_type')}")
        print(f"  confidence: {data.get('confidence')}")
        
        program = match_certification_to_program(key, data.get("value", ""))
        if program:
            print(f"  matched_to: {program.get('canonical_name')}")
            print(f"  risk_level: {program.get('risk_level')}")
        else:
            print(f"  NO MATCH FOUND in assurance_programs.json")
```

---

## Quick Reference: v3.5 → AITGP Data Flow

```
VDO v3.5 Research
    │
    ├─→ URL Discovery (free)
    ├─→ Tool-calling extraction (Claude decides)
    ├─→ classify_source() with vendor_urls ← KEY FIX
    │
    └─→ ResearchResult
          ├── facts: List[ExtractedFact]
          ├── structured_data: Dict  ← AITGP uses this
          │     └── certification:
          │           └── hitrust_r2:
          │                 ├── value: "Certified"
          │                 ├── source: "https://..."
          │                 ├── source_type: "vendor"  ← NOW CORRECT
          │                 └── confidence: 0.95
          └── synthesized_report: str

AITGP Processing
    │
    ├─→ extract_certifications_from_research()
    │     ├─→ match_certification_to_program()
    │     ├─→ HIGH_RISK filter (source_type + confidence)
    │     └─→ Build certification list
    │
    ├─→ Calculate assurance scores
    │
    └─→ Generate report with certifications
```

---

## Files to Modify

| File | Change | Priority |
|------|--------|----------|
| `aitgp-app/job-53/app.py` | Import and use v3.5 | High |
| `aitgp-app/job-53/app.py` | Add flexible key matching | High |
| `aitgp-app/job-53/config/assurance_programs.json` | Verify all programs | Medium |
| `aitgp-app/job-53/app.py` | Add debug logging | Medium |

---

## Support

For questions about:
- **VDO v3.5 internals**: See `V3_5_DOCUMENTATION.md`
- **Gold patterns**: See `GOLD_PATTERNS.md`
- **Source classification**: See `source_classifier.py`

---

*This migration guide should be followed sequentially. Each phase builds on the previous. Test thoroughly before production deployment.*
