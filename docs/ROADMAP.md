# VDO Development Roadmap
**Last Updated:** December 8, 2025

## Overview

Two parallel tracks:
- **Track A: Feature Development** — Expanding VDO's capabilities
- **Track B: Quality & Autonomy** — Making VDO self-sufficient

---

## Track A: Feature Development

### ✅ Completed

| Feature | Status | Notes |
|---------|--------|-------|
| Core Pipeline | ✅ Done | Plan → Build → Test → Sandbox |
| Multi-AI Orchestration | ✅ Done | Claude, OpenAI, Gemini routing |
| Real-time Dashboard | ✅ Done | WebSocket updates, log streaming |
| Job Rating System | ✅ Done | 1-5 stars, reference jobs |
| GitHub Integration Phase 1 | ✅ Done | Create repo, push code |
| Auto GitHub Push | ✅ Done | Optional push on job completion |

### 🔄 In Progress

| Feature | Status | Next Step |
|---------|--------|-----------|
| Gemini Integration | 🔄 Fixed | Updated to gemini-2.5-flash |

### 📋 Planned: Phase 2 GitHub

**Goal:** Full git workflow support

| Feature | Priority | Effort |
|---------|----------|--------|
| List user repositories | High | 2 hrs |
| Clone existing repo | High | 3 hrs |
| Branch management (create/switch/merge) | Medium | 4 hrs |
| Pull/fetch updates | Medium | 2 hrs |
| Delete repositories | Low | 1 hr |

**Spec:** `/mnt/user-data/outputs/vdo-spec-github-integration.md`

### 📋 Planned: Training Analytics Backend

**Goal:** Anonymous analytics for PHI/PII training app

| Component | Description |
|-----------|-------------|
| Django REST API | Track completions, scores, time spent |
| PostgreSQL | Store anonymous session data (UUID-based) |
| Docker deployment | Portable, Fly.io ready |
| Privacy-first | No PII, no tracking |

**Spec:** `/mnt/user-data/outputs/vdo-spec-training-analytics.md`

### 📋 Planned: AI Provider Dashboard

**Goal:** Visibility into which AIs did what

| Feature | Description |
|---------|-------------|
| Provider breakdown per job | Show Claude/OpenAI/Gemini usage |
| Token tracking per provider | Cost attribution |
| Provider health status | API availability, latency |
| Failover configuration | Set backup providers |

### 📋 Future: Advanced Features

| Feature | Description | Priority |
|---------|-------------|----------|
| Job templates | Pre-built prompts for common tasks | Medium |
| Workspace projects | Group related jobs | Medium |
| Code deployment | Push to actual environments | Low |
| External agent integration | Connect AI-workspace agents | Low |

### 💡 Aspirational: AI Spend Tracking

**Goal:** Fuel gauge for AI provider credits

| Feature | Description |
|---------|-------------|
| Cumulative spend tracking | Sum costs from job history per provider |
| Budget configuration | User sets monthly limits per provider |
| Visual gauge | Progress bar showing spend vs budget |
| Burn rate indicator | "At current pace, $X by month end" |
| Alerts | Warn when approaching budget limits |

**Challenge:** Most AI APIs don't expose balance endpoints. Solution is local tracking + user-configured budgets.

```
┌─────────────────────────────────┐
│ Claude    ████████░░  $42/$50   │
│ OpenAI    ██░░░░░░░░  $8/$50    │
│ Gemini    ░░░░░░░░░░  $0.12/$50 │
└─────────────────────────────────┘
```

---

## Track B: Quality & Autonomy

**Goal:** VDO produces usable output without manual remediation

### Current Pain Points

| Problem | Impact | Frequency |
|---------|--------|-----------|
| Hallucinated plans | Complete miss on intent | ~30% of jobs |
| No codebase context | Generic/unusable output | ~50% of jobs |
| Files don't integrate | Manual wiring required | ~80% of jobs |
| No verification | Syntax errors, broken code | ~40% of jobs |

### Phase B1: Codebase Awareness ⬅️ START HERE
**Timeline:** 1-2 weeks

| Task | Description | Effort |
|------|-------------|--------|
| Project scanner | Index files on job start | 4 hrs |
| Context injection | Feed relevant files to planner | 3 hrs |
| File-targeted tasks | Tasks specify exact file paths | 2 hrs |
| Architecture summary | Auto-generate project overview | 3 hrs |

**Success Metric:** Planning phase produces tasks referencing actual files

### Phase B2: Edit Mode
**Timeline:** 2-3 weeks

| Task | Description | Effort |
|------|-------------|--------|
| Diff-based output | AI generates patches not files | 4 hrs |
| Edit application | Apply changes to real codebase | 6 hrs |
| Git branch per job | Isolate changes safely | 3 hrs |
| Rollback support | One-click revert | 2 hrs |

**Success Metric:** VDO edits existing files correctly

### Phase B3: Verification Loop
**Timeline:** 2-3 weeks

| Task | Description | Effort |
|------|-------------|--------|
| Syntax validation | Lint/compile generated code | 3 hrs |
| Test execution | Actually run generated tests | 4 hrs |
| Error feedback loop | Retry on failure with error context | 4 hrs |
| Self-critique step | AI reviews own output | 3 hrs |

**Success Metric:** Generated code passes basic validation

### Phase B4: Learning Loop
**Timeline:** 3-4 weeks

| Task | Description | Effort |
|------|-------------|--------|
| Correction capture | Store manual fixes as training data | 4 hrs |
| Reference job injection | Feed good examples to planner | 3 hrs |
| Prompt evolution | Auto-improve prompts from patterns | 6 hrs |
| Success metrics | Track improvement over time | 3 hrs |

**Success Metric:** Remediation rate decreases over time

---

## Recommended Execution Order

```
Week 1-2:   [A] Phase 2 GitHub (list, clone)
            [B] Phase B1: Codebase scanner + context injection

Week 3-4:   [A] Phase 2 GitHub (branches, pull)
            [B] Phase B1: Complete + test

Week 5-6:   [A] Training Analytics backend
            [B] Phase B2: Edit mode (diff-based)

Week 7-8:   [A] AI Provider Dashboard
            [B] Phase B2: Complete + git integration

Week 9-10:  [A] Job templates
            [B] Phase B3: Verification loop

Week 11+:   [A] Advanced features
            [B] Phase B4: Learning loop
```

---

## Quick Reference: Next Actions

### If continuing Feature Development:
1. Write Phase 2 GitHub spec (branch management)
2. Have VDO build list repos + clone features
3. Test with real GitHub workflow

### If starting Quality Track:
1. Spec out codebase scanner
2. Build project indexer into worker.py
3. Modify planning prompt to include context
4. Test with "improve VDO" meta-job

### If testing current state:
1. Create new job with `GITHUB_AUTO_PUSH=true`
2. Verify repo appears on GitHub
3. Check job record has `github_repo_url`

---

## Files Reference

| File | Purpose |
|------|---------|
| `backend/worker.py` | Job processing pipeline |
| `backend/orchestrator.py` | AI routing and execution |
| `backend/models.py` | Database models |
| `vdo_github/` | GitHub integration module |
| `frontend/src/App.jsx` | Dashboard UI |
| `docs/ROADMAP.md` | This file |
