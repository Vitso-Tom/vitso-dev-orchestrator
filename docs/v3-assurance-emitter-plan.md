# Block 2: VDO Assurance Emitter Implementation Plan

**Version**: 3.0-final  
**Date**: January 3, 2026  
**Status**: Implementation Plan (Block 2)  
**Author**: Tom Smolinsky / VITSO Consulting  
**Prerequisite**: Block 1 (v3-vdo-assurance-contract.md)

---

## 1. Purpose

This document defines how VDO will populate `assurance_findings[]` and `blocked_access[]` from existing `structured_data`. It is **additive only** — no changes to crawling, extraction, or synthesis logic.

---

## 2. Input: Current `structured_data` Shape

Based on the Tabnine payload, certification-relevant data lives in two sections:

### 2.1 `structured_data.certification`

Contains keys like:
- `soc2_status`, `soc2_type_ii_status`, `soc2_type_ii_detailed`
- `iso27001_status`, `iso_27001_status`, `iso_27001_third_party_claim`
- `iso9001_status`, `iso_9001_compliance`
- `gdpr_status`, `gdpr_compliance`
- `hipaa_baa`, `hipaa_alignment`, `hipaa_compliance`
- `itar_alignment`
- `infrastructure_compliance` (inherited — must be filtered)
- `certification_publishing_status`, `public_certifications_evidence`

### 2.2 `structured_data.compliance`

Contains keys like:
- `iso_9001`, `iso_27001`, `soc2_status`, `hipaa_baa`

### 2.3 Fact Structure

Each fact has:
```
{
  "value": "SOC 2 Type 2 compliant",
  "source": "https://...",
  "confidence": 0.85,
  "source_type": "vendor" | "third_party"
}
```

### 2.4 `source_type` Reliability

**Important**: The `source_type` field in `structured_data` is **advisory only**. VDO currently does not reliably distinguish auditor sources from third-party sources. The emitter must not rely on `source_type` to gate verification status. Instead, verification is determined by evidence characteristics (see Step 6).

---

## 3. Module: `assurance_emitter.py`

A new module that post-processes `structured_data` and emits the v3 contract arrays.

### 3.1 Entry Point

```
def emit_assurance(structured_data: dict, programs_index: dict) -> dict:
    """
    Returns:
      {
        "assurance_findings": [...],
        "blocked_access": [...]
      }
    """
```

Called after synthesis, before API response serialization. Does not modify `structured_data`.

---

## 4. Step-by-Step Processing

### Step 1: Load Normalization Index

**Input**: `assurance_programs.json`

**Action**: Build lookup structures:
- `alias_to_program_id`: maps lowercase aliases → program `id`
- `program_meta`: maps program `id` → `canonical_name`, `levels[]`, `assurance_type`

**Example**:
```
"soc 2" → "SOC_2"
"soc2 type ii" → "SOC_2" (with level hint "Type II")
"iso 27001" → "ISO_IEC_27001"
```

### Step 2: Extract Candidate Facts

**Input**: `structured_data.certification`, `structured_data.compliance`

**Action**: Iterate all keys in both sections. For each fact:
1. Extract `value`, `source`, `confidence`, `source_type`
2. Skip if `value` is empty or null
3. Skip if source is empty (no attribution possible)

**Output**: List of candidate facts with their original keys.

### Step 3: Filter Inherited Compliance

**Rule**: Discard any fact where:
- Key contains `infrastructure` or `cloud_provider`
- Value contains "inherited", "AWS compliance", "GCP compliance", "Azure compliance"

**Rationale**: Hosting provider certifications do not apply to the vendor.

**Example filtered out**:
```
"infrastructure_compliance": {
  "value": "AWS and GCP compliance certifications (inherited)",
  ...
}
```

### Step 4: Normalize to Program ID

**Input**: Each candidate fact's key and value text

**Action**:
1. Lowercase the key and value
2. Search for matches against `alias_to_program_id`
3. Check key first (e.g., `soc2_type_ii_status` → contains "soc2")
4. Then check value (e.g., "ISO/IEC 27001 certification available")
5. If no match found, skip fact (do not emit UNMAPPED for certification section keys that don't match — they may be metadata)

**Level extraction**:
- If value contains "Type II" or "Type 2" → level = "Type II"
- If value contains "Type I" or "Type 1" → level = "Type I"
- Otherwise → level = null

**Output**: `program_id`, `program_name`, `level` (or skip)

### Step 5: Assign `evidence_kind`

**Input**: Fact `value` text

**Rules** (applied in order, first match wins):

| Pattern in value | evidence_kind |
|------------------|---------------|
| "registry", "marketplace", "listed on", "appears in" | `registry_listing` |
| "report available", "attestation", "audited", "audit completed" | `attestation_statement` |
| "is certified", "has completed", "achieved certification", "holds certification", "certification available" | `explicit_cert_statement` |
| "alignment", "aligned", "follows", "adheres to", "compliant" (without "certified") | `policy_statement` |
| "enterprise-grade", "secure", "protected", "robust" (without cert name) | `marketing_claim` |

**Default**: If a recognized program name is present but no pattern matches, default to `policy_statement` — not `explicit_cert_statement`.

**Rationale**: Conservative default prevents marketing language from inflating evidence strength. Only explicit possession/completion language earns `explicit_cert_statement`.

### Step 6: Assign `status`

**Input**: All sources for a program, their `evidence_kind` values, source URLs, and value texts

**Verification is evidence-based, not `source_type`-based.** The `source_type` field is advisory only and must not gate verification in v3.

#### Known Auditor/Registry Domains

The following URL patterns indicate authoritative sources:

```
# Official registries
marketplace.fedramp.gov
cloudsecurityalliance.org/star/registry
hitrustalliance.net
# Certification body portals
schellman.com
coalfire.com
a-lign.com
kpmg.com/audit
deloitte.com/audit
ey.com/audit
pwc.com/audit
bsigroup.com
tuv*.com
dnv.com
```

A source is considered **authoritative** if:
- `evidence_kind` ∈ { `registry_listing`, `attestation_statement` }
- AND source URL domain matches a known auditor/registry domain

#### Status Resolution Rules

Status is determined by **rule-based resolution**, not priority weighting. Apply rules in this order:

1. **Denied**: If any source value contains explicit denial language:
   - "does not hold", "is not certified", "refused", "no longer certified", "certification lapsed"
   - → `status = denied`

2. **Conflicting**: If credible sources materially contradict:
   - One source asserts certification, another explicitly denies it
   - (Note: "certified" + "not publicly published" is NOT conflicting — see §7)
   - → `status = conflicting`

3. **Verified**: If verification criteria are met:
   - At least one source has `evidence_kind` ∈ { `registry_listing`, `attestation_statement` }
   - AND that source URL matches a known auditor/registry domain
   - → `status = verified`

4. **Evidence Gated**: If trust portal is blocked and only indirect evidence exists:
   - A `blocked_access` entry exists for this vendor's trust portal
   - AND no authoritative source was found
   - AND at least one source asserts the certification
   - → `status = evidence_gated`

5. **Claimed**: All other cases where evidence exists but verification criteria are not met:
   - → `status = claimed`

**Note**: `source_type` from `structured_data` is passed through to the output for transparency but does not affect status determination.

### Step 7: Assign `confidence`

**Input**: All facts for a given `program_id`

**Rules** (deterministic, no math):

| Condition | confidence |
|-----------|------------|
| 3+ sources with 2+ distinct source URLs (different domains) | `high` |
| 2 sources from different domains | `medium` |
| 1 source only | `low` |
| All sources are from aggregator domains (nudgesecurity, securityscorecard, etc.) | `low` |

**Override**: If all sources have `evidence_kind` = `marketing_claim`, cap at `low` regardless of count.

### Step 8: Aggregate by Program

**Action**: Group all facts by `program_id`. For each program:

1. Collect all sources
2. Collect all value texts
3. Apply **rule-based status resolution** (§Step 6) — not weighting
4. Determine `confidence` per §Step 7
5. Select `level` if consistently evidenced; if sources disagree on level, use `null`
6. Build `notes` if status requires explanation

**Status Resolution** (restated for clarity):

```
if any_source_denies(values):
    status = "denied"
elif sources_contradict(values):
    status = "conflicting"
elif has_authoritative_verification(sources):
    status = "verified"
elif trust_portal_blocked AND has_indirect_evidence(sources):
    status = "evidence_gated"
else:
    status = "claimed"
```

No numeric scoring. No priority weighting. Semantic resolution only.

**Output**: One `assurance_findings[]` entry per program.

### Step 9: Build `blocked_access[]`

**Current limitation**: VDO does not track blocked URLs in `structured_data`.

**Scope restriction**: Synthesized report parsing may **only** emit `blocked_access` disclosures. It must **never** create or modify `assurance_findings[]` entries. This prevents inference creep from narrative text.

**Interim approach**:
- Scan `synthesized_report` for blocked-access indicators only
- Look for phrases: "restricted", "gated", "SafeBase", "access blocked", "NDA required", "authentication required"
- If found with a recognizable trust portal URL pattern (`trust.*.com`, `security.*.com`):
   - Emit one `blocked_access` entry
   - `blocker_type`: infer from text (SafeBase → `safebase`, NDA → `auth_wall`) or default to `other`
   - `context`: "vendor trust portal"
- Do NOT use this parsing to create assurance_findings

**Future approach** (out of scope for Block 2):
- Crawler emits `blocked_urls[]` during research
- Emitter reads from that array directly

**For v3 initial release**: Return empty `blocked_access: []` unless explicit blocked URL data is added to structured_data in a future crawl enhancement.

---

## 5. Data Ignored

| Data | Reason |
|------|--------|
| `structured_data.company` | Not assurance-related |
| `structured_data.funding` | Not assurance-related |
| `structured_data.hosting` | Infrastructure only |
| `structured_data.security` (most keys) | Practices, not certifications |
| `structured_data.integration` | Feature inventory |
| `structured_data.data_handling` | Policy, not certification |
| Facts with `infrastructure_compliance` key | Inherited from cloud provider |
| Facts with empty `source` | No attribution possible |
| Values containing "inherited" | Cloud provider certification |
| `synthesized_report` (for findings) | May only inform `blocked_access`, never `assurance_findings` |

---

## 6. Blocked Access Handling

### Current State

The synthesized_report contains text like:
> "Trust center lists SOC 2 but attestation access appears restricted"
> "Procurement teams may require NDA attestations to access compliance documentation"

But `structured_data` has no `blocked_urls` field.

### Interim Behavior

1. Parse `synthesized_report` for blocked-access indicators **only**
2. If `trust.{vendor}.com` or `security.{vendor}.com` mentioned with "restricted", "gated", "SafeBase":
   - Emit one `blocked_access` entry
   - `blocker_type`: infer from text or default to `other`
   - `context`: "vendor trust portal"
3. This parsing must **never** create or modify `assurance_findings`
4. This is heuristic and low-confidence — acceptable for v3.0

### Future Enhancement (Not Block 2)

Add `blocked_urls[]` to VDO research output during crawl phase.

---

## 7. Conflicting Claims Handling

**Detection**: Multiple facts for same `program_id` with contradictory `value` text.

**Examples**:
- Fact A: `"SOC 2 Type 2 compliant"` (vendor)
- Fact B: `"Does not publish SOC 2 Type II certificates"` (third_party)

**Resolution**:

1. **Compatible statements** (NOT conflicting):
   - "certified/compliant" + "not published/not verified/evidence not available"
   - These are consistent: vendor claims it, but public proof isn't available
   - Status = `claimed`
   - Add `notes`: "Vendor claims certification; public evidence not available"

2. **Contradictory statements** (conflicting):
   - "certified" + "does not hold" or "is not certified" or "refused certification"
   - These cannot both be true
   - Status = `conflicting`
   - Add `notes`: "Sources disagree on certification status"

3. **Level disagreement**:
   - Sources cite different levels (Type I vs Type II)
   - Use `level: null`
   - Add `notes`: "Level disputed across sources"

---

## 8. Pseudocode: Main Loop

```
findings_by_program = {}

for section in ['certification', 'compliance']:
    for key, fact in structured_data.get(section, {}).items():
        if is_filtered(key, fact):
            continue
        
        program_id, level = normalize(key, fact['value'], programs_index)
        if not program_id:
            continue
        
        source_entry = {
            'url': fact['source'],
            'source_type': fact.get('source_type', 'third_party'),  # advisory only
            'evidence_kind': classify_evidence(fact['value']),
            'retrieved_at': research_timestamp,
            'excerpt': truncate(fact['value'], 300)
        }
        
        if program_id not in findings_by_program:
            findings_by_program[program_id] = {
                'program_id': program_id,
                'program_name': programs_index[program_id]['canonical_name'],
                'level': level,
                'sources': [],
                'values': []
            }
        
        findings_by_program[program_id]['sources'].append(source_entry)
        findings_by_program[program_id]['values'].append(fact['value'])

# Rule-based status resolution (not weighting)
assurance_findings = []
for prog_id, data in findings_by_program.items():
    status = resolve_status_by_rules(data['sources'], data['values'], blocked_access)
    confidence = determine_confidence(data['sources'])
    notes = build_notes(status, data['values'])
    
    assurance_findings.append({
        'program_id': prog_id,
        'program_name': data['program_name'],
        'level': resolve_level(data),
        'status': status,
        'confidence': confidence,
        'sources': data['sources'],
        'notes': notes
    })
```

---

## 9. Output Location

The emitter is called in `research_routes.py` (or equivalent API handler) after synthesis completes:

```
# After synthesis
assurance_output = emit_assurance(structured_data, load_programs_index())

# Merge into response
response['assurance_findings'] = assurance_output['assurance_findings']
response['blocked_access'] = assurance_output['blocked_access']
```

Existing fields (`structured_data`, `synthesized_report`, etc.) remain unchanged.

---

## 10. Testing Approach (Block 3)

1. Unit test `normalize()` against `assurance_programs.json` aliases
2. Unit test `classify_evidence()` with known value patterns — verify conservative defaults
3. Unit test `resolve_status_by_rules()` with rule-based scenarios (denied, conflicting, verified, evidence_gated, claimed)
4. Unit test authoritative domain matching
5. Integration test with Tabnine cached payload
6. Verify backward compatibility — existing AITGP must not break
7. Verify synthesized_report parsing does NOT create assurance_findings

---

## 11. What This Plan Does NOT Do

| Excluded | Reason |
|----------|--------|
| Modify crawling logic | Constraint: no crawling changes |
| Add new fields to `structured_data` | Constraint: no schema changes |
| Change UI | Constraint: no UI changes |
| Implement confidence scoring math | Constraint: no confidence math yet |
| Refactor existing extraction | Constraint: no refactors |
| Enumerate programs from JSON | Spec constraint: evidence-only |
| Rely on `source_type` for verification | VDO `source_type` is unreliable |
| Create findings from synthesized_report | Prevents inference creep |
| Use priority weighting for status | Rule-based resolution only |

---

## 12. Guardrails Summary

1. **`source_type` is advisory only** — verification is evidence-based
2. **Status resolution is rule-based** — no priority weighting
3. **Default `evidence_kind` is `policy_statement`** — not `explicit_cert_statement`
4. **Synthesized report may only inform `blocked_access`** — never `assurance_findings`
5. **No discovery from `assurance_programs.json`** — evidence-only emission
6. **No "unknown" as user-facing state** — omit finding if status cannot be determined

---

## End of Implementation Plan

**Next**: Block 3 – Incremental code implementation of `assurance_emitter.py`
