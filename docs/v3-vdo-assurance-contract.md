# v3 VDO Assurance Evidence Output Contract

**Version**: 3.0-draft  
**Date**: January 3, 2026  
**Status**: Specification (Block 1)  
**Author**: Tom Smolinsky / VITSO Consulting

---

## 1. Purpose

This document defines the **additive** JSON structure that VDO will return to provide structured assurance evidence to AITGP. The schema is designed to:

- Separate **status** (what we know) from **confidence** (how sure we are)
- Surface **blocked access events** transparently
- Attribute sources per finding
- Remain minimal and forward-compatible

This contract is **additive** to the existing VDO response. Existing fields (`structured_data`, `synthesized_report`, `success`, etc.) remain unchanged.

---

## 2. Schema Overview

Two new top-level arrays are added to the VDO API response:

```json
{
  "assurance_findings": [ ... ],
  "blocked_access": [ ... ]
}
```

Both arrays are always present (may be empty). This ensures consistent parsing.

---

## 3. Field Definitions

### 3.1 `assurance_findings[]`

An array of assurance evidence records. **Only populated when evidence exists.** One record per distinct assurance program finding.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `program_id` | string | Yes | Normalized identifier from `assurance_programs.json` (e.g., `SOC_2`, `ISO_IEC_27001`). Used for matching, not discovery. |
| `program_name` | string | Yes | Human-readable name (e.g., "SOC 2", "ISO/IEC 27001"). |
| `level` | string | No | Level or type when evidenced (e.g., "Type II", "Moderate"). Must match `levels[].name` in `assurance_programs.json`. Omit if not evidenced. |
| `status` | enum | Yes | Evidence status. See §4.1. |
| `confidence` | enum | Yes | Confidence level. See §4.2. |
| `sources` | array | Yes | Array of source attribution objects. See §3.2. Minimum 1 required. |
| `notes` | string | No | Brief context (e.g., why evidence is gated). Max 200 chars. |

### 3.2 `sources[]` (within each finding)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string | Yes | Source URL. |
| `source_type` | enum | Yes | Source category. See §4.3. |
| `evidence_kind` | enum | Yes | Type of evidence found at source. See §4.5. |
| `retrieved_at` | string | Yes | ISO 8601 timestamp of retrieval attempt. |
| `excerpt` | string | No | Relevant verbatim snippet. Max 300 chars. Omit if blocked or unavailable. |

### 3.3 `blocked_access[]`

An array of access-blocked events encountered during research. **Only populated when blocking occurred.**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string | Yes | The URL that was blocked. |
| `blocker_type` | enum | Yes | What caused the block. See §4.4. |
| `context` | string | Yes | What VDO was attempting to retrieve (e.g., "vendor trust portal"). |
| `detected_at` | string | Yes | ISO 8601 timestamp. |

---

## 4. Enumerated Values

### 4.1 `status` (Assurance Status)

| Value | Meaning |
|-------|---------|
| `verified` | Supported by directly attributable evidence (auditor report, registry listing, accessible vendor trust page). |
| `claimed` | Vendor asserts but direct verification artifacts not accessible or evidence is indirect. |
| `evidence_gated` | Trust documentation known to exist but blocked (SafeBase, auth wall, etc.). |
| `conflicting` | Credible sources provide materially contradictory information. |
| `denied` | Vendor explicitly states this assurance is not offered. |

**Prohibited values**: `unknown`, `pending`, `n/a`, null, empty string.

### 4.2 `confidence` (Confidence Level)

| Value | Meaning |
|-------|---------|
| `high` | Multiple independent credible sources corroborate, even if direct artifacts gated. |
| `medium` | Some corroboration but sources limited or lack diversity. |
| `low` | Evidence sparse, indirect, or from low-reliability sources. |

### 4.3 `source_type` (Source Attribution)

| Value | Meaning |
|-------|---------|
| `vendor` | Published directly by the vendor (including gated trust portals). |
| `auditor` | Independent certification body, registry, or official marketplace. |
| `third_party` | Reputable external source (not vendor or auditor). |
| `aggregator` | Compiled security profile with inconsistent attribution. Requires corroboration. |

**Clarification on `auditor`**: In v3, `auditor` encompasses both auditor-issued artifacts (e.g., attestation letters, audit reports) and official registry listings (e.g., FedRAMP Marketplace, CSA STAR Registry). Future versions may split these into distinct values (`auditor`, `registry`), but v3 treats them as a single category. Consumers should not assume `auditor` implies a specific artifact type without checking `evidence_kind`.

### 4.4 `blocker_type` (Access Blocker)

| Value | Meaning |
|-------|---------|
| `safebase` | SafeBase trust portal blocking bots or requiring auth. |
| `cloudflare` | Cloudflare bot protection or challenge. |
| `auth_wall` | Login or NDA required. |
| `robots_block` | robots.txt disallowed crawling. |
| `rate_limit` | Request blocked due to rate limiting. |
| `other` | Other mechanism (explain in `context`). |

### 4.5 `evidence_kind` (Evidence Type)

Classifies the type of evidence found at a given source. This field enables deterministic confidence calculation without requiring prose inference from excerpts.

| Value | Meaning |
|-------|---------|
| `explicit_cert_statement` | Source explicitly states the vendor holds a specific certification (e.g., "XYZ Corp is ISO 27001 certified"). |
| `attestation_statement` | Source references an attestation report or audit completion (e.g., "SOC 2 Type II report available"). |
| `registry_listing` | Source is an official registry or marketplace entry (e.g., FedRAMP Marketplace, CSA STAR Registry). |
| `policy_statement` | Source describes policies or practices aligned with a framework but does not claim certification (e.g., "We follow NIST CSF guidelines"). |
| `marketing_claim` | Source uses promotional language without specific certification evidence (e.g., "enterprise-grade security"). |

**Why this field exists**: Confidence scoring must be deterministic and auditable. Rather than inferring evidence strength from excerpt text, `evidence_kind` provides an explicit classification that VDO assigns during research. This removes ambiguity and enables consistent AITGP behavior across runs.

---

## 5. Example Payload

**Scenario**: Research on Tabnine.
- Trust portal at `trust.tabnine.com` blocked by SafeBase
- SOC 2 Type II corroborated by third-party sources
- ISO 27001 mentioned on vendor page but no third-party corroboration

```json
{
  "assurance_findings": [
    {
      "program_id": "SOC_2",
      "program_name": "SOC 2",
      "level": "Type II",
      "status": "claimed",
      "confidence": "high",
      "sources": [
        {
          "url": "https://trust.tabnine.com/",
          "source_type": "vendor",
          "evidence_kind": "explicit_cert_statement",
          "retrieved_at": "2026-01-03T14:30:00Z",
          "excerpt": null
        },
        {
          "url": "https://www.g2.com/products/tabnine/security",
          "source_type": "third_party",
          "evidence_kind": "explicit_cert_statement",
          "retrieved_at": "2026-01-03T14:30:12Z",
          "excerpt": "Tabnine has completed SOC 2 Type II certification."
        },
        {
          "url": "https://securityscorecard.com/company/tabnine",
          "source_type": "aggregator",
          "evidence_kind": "explicit_cert_statement",
          "retrieved_at": "2026-01-03T14:30:18Z",
          "excerpt": "SOC 2 Type II: Yes"
        }
      ],
      "notes": "Vendor trust portal gated; status based on third-party corroboration."
    },
    {
      "program_id": "ISO_IEC_27001",
      "program_name": "ISO/IEC 27001",
      "level": null,
      "status": "claimed",
      "confidence": "medium",
      "sources": [
        {
          "url": "https://www.tabnine.com/security",
          "source_type": "vendor",
          "evidence_kind": "explicit_cert_statement",
          "retrieved_at": "2026-01-03T14:30:05Z",
          "excerpt": "We maintain ISO 27001 certification for our security management system."
        }
      ],
      "notes": "Single vendor source; no third-party corroboration found."
    }
  ],
  "blocked_access": [
    {
      "url": "https://trust.tabnine.com/",
      "blocker_type": "safebase",
      "context": "vendor trust portal",
      "detected_at": "2026-01-03T14:30:00Z"
    }
  ]
}
```

### Interpretation

| Finding | Status | Confidence | Rationale |
|---------|--------|------------|-----------|
| SOC 2 Type II | `claimed` | `high` | Vendor asserts via trust portal (gated). Two additional sources corroborate. However, `source_type` values are `third_party` and `aggregator`—neither qualifies as `auditor` (auditor-issued artifact or official registry). Without an `auditor` source, the finding cannot reach `verified` status regardless of confidence level. |
| ISO/IEC 27001 | `claimed` | `medium` | Vendor asserts on public security page. No third-party corroboration found. Single source limits confidence. |

**Key distinction**: `verified` requires at least one source with `source_type: auditor` (auditor artifact or registry listing). Third-party review sites and aggregators report *about* certifications but are not authoritative issuers. High confidence from corroboration does not substitute for authoritative sourcing.

The `blocked_access` entry enables AITGP to disclose that direct verification was attempted but blocked—transparency without unfair confidence penalty.

---

## 6. Emission Rules

### 6.1 What to Emit

1. **Only evidenced findings.** A finding requires at least one source.
2. **Only blocked access events that actually occurred.** Do not speculatively list URLs.
3. **Normalized `program_id`** must exist in `assurance_programs.json`. If evidence references an unrecognized program, use `program_id: "UNMAPPED"` and populate `program_name` with the as-found name.

### 6.2 What NOT to Emit

| Condition | Rule |
|-----------|------|
| No evidence found for a program | Do not emit. Absence = not in array. |
| Program exists in `assurance_programs.json` but no evidence | Do not emit. The file is for normalization, not discovery. |
| Hosting provider certifications (AWS, GCP, Azure) | Do not emit. Vendor must hold the assurance directly. |
| Marketing language without evidence | Do not emit. "Enterprise-grade security" is not evidence. |
| Inferred certifications | Do not emit. "HIPAA compliant" does not imply SOC 2. |
| Speculative levels | Omit `level` unless explicitly evidenced. "SOC 2" without type specification → `level: null`. |
| Any form of "unknown" | Never emit. If status cannot be determined, do not include the finding. |

### 6.3 Array Presence

Both arrays are **always returned**, even if empty:

```json
{
  "assurance_findings": [],
  "blocked_access": []
}
```

This ensures consistent parsing in AITGP without null checks.

---

## 7. Relationship to Existing Fields

This schema is **additive**. Existing VDO response fields remain unchanged:

| Existing Field | Disposition |
|----------------|-------------|
| `structured_data.certifications` | Retained for backward compatibility. AITGP v3 prefers `assurance_findings` when present. |
| `synthesized_report` | Unchanged. |
| `success`, `status`, `confidence_score` | Unchanged. Top-level research status. |
| `source_type` (top-level) | Unchanged. Known limitation: always returns `third_party`. Does not affect per-finding attribution. |

---

## 8. Forward Compatibility

- New `status` or `confidence` values may be added; consumers should use `.get()` with defaults.
- New fields may be added to finding objects; consumers should ignore unrecognized fields.
- `program_id: "UNMAPPED"` provides escape hatch for programs not yet in normalization file.
- `notes` field allows context without schema changes.

---

## End of Specification

**Next**: Block 2 – VDO implementation plan for populating this contract.
