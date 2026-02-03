# VDO Session Handoff - December 8, 2025

## Project Overview

**VDO (Vitso Dev Orchestrator)** is an AI-powered development platform that orchestrates multiple AI providers (Claude, OpenAI, Gemini) to automatically plan, build, test, and deploy code projects.

**Repository:** https://github.com/Vitso-Tom/vitso-dev-orchestrator
**Current Commit:** `fbf32fd` - "Phase B1: Codebase scanner for context-aware task generation"
**Location:** `~/vitso-dev-orchestrator` (WSL Ubuntu)

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│   Backend   │────▶│   Worker    │
│  React/Vite │     │   FastAPI   │     │   RQ/Redis  │
│  port 3000  │     │  port 8000  │     │             │
└─────────────┘     └─────────────┘     └─────────────┘
                           │                   │
                           ▼                   ▼
                    ┌─────────────┐     ┌─────────────┐
                    │  PostgreSQL │     │  AI APIs    │
                    │   port 5432 │     │ Claude/GPT/ │
                    └─────────────┘     │   Gemini    │
                                        └─────────────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │   GitHub    │
                                        │  Auto-push  │
                                        └─────────────┘
```

## Key Files

| File | Purpose |
|------|---------|
| `backend/worker.py` | Job processing pipeline (5 phases: scan → plan → build → test → sandbox → github) |
| `backend/orchestrator.py` | AI routing, prompt construction, context injection |
| `backend/scanner.py` | **NEW** Codebase indexer using AST analysis |
| `backend/models.py` | SQLAlchemy models (Job, Task, Log, GeneratedFile, AgentAnalysis) |
| `backend/main.py` | FastAPI routes, WebSocket manager |
| `frontend/src/App.jsx` | React dashboard with real-time updates |
| `vdo_github/` | GitHub integration module (create repo, push files) |
| `docker-compose.yml` | Full stack: postgres, redis, backend, worker, frontend |

## What Was Completed This Session

### Phase B1: Codebase Scanner ✅
- **scanner.py** - Scans project directories, extracts classes/functions via Python AST
- **Worker integration** - `scanning_phase()` runs before planning if `project_path` set
- **Orchestrator update** - `_format_project_context()` injects file structure into planning prompt
- **API update** - `/api/jobs` accepts `project_path` parameter
- **UI update** - Checkbox "Scan VDO codebase for context" in New Job form
- **Database** - Added `project_path` and `project_index` columns to jobs table

### Validation Results
Side-by-side comparison of same job with/without scanner:

| Metric | No Scanner | With Scanner |
|--------|-----------|--------------|
| Tasks | 16 generic | 14 file-specific |
| Task example | "Implement token tracking middleware" | "Modify AIOrchestrator class in orchestrator.py" |
| Tokens | 33,986 | 29,157 (14% less) |
| Cost | $0.34 | $0.29 |
| Time | 366s | 322s |

### Other Completions
- GitHub auto-push integration (GITHUB_AUTO_PUSH=true)
- Removed docker-compose version warning
- First git commit and push to GitHub

## Environment Setup

**.env file (root):**
```
GITHUB_TOKEN=ghp_xxxxx
GITHUB_USERNAME=Vitso-Tom
GITHUB_AUTO_PUSH=true
```

**backend/.env:**
```
ANTHROPIC_API_KEY=sk-ant-xxxxx
OPENAI_API_KEY=sk-xxxxx
GOOGLE_API_KEY=AIzaxxxxx
DATABASE_URL=postgresql://vitso:vitso_password@postgres:5432/vitso_dev_orchestrator
REDIS_HOST=redis
```

## Common Commands

```bash
# Start stack
cd ~/vitso-dev-orchestrator
docker compose up -d

# View logs
docker compose logs worker -f --tail=50
docker compose logs backend -f --tail=50

# Restart after code changes
docker compose restart backend worker

# Test scanner
docker compose exec backend python3 -c "from scanner import scan_project; print(scan_project('/app'))"

# Check job status
docker compose exec backend python3 -c "
from database import SessionLocal
from models import Job
db = SessionLocal()
job = db.query(Job).order_by(Job.id.desc()).first()
print(f'Job {job.id}: {job.status}, Scanner: {job.project_index is not None}')
"
```

## Roadmap - What's Next

### Track B: Quality & Autonomy (recommended next)

**Phase B2: Edit Mode** (not started)
- Output diffs instead of full files
- Apply changes to actual codebase
- Git branch per job
- Rollback support

**Phase B3: Verification Loop**
- Syntax validation
- Test execution
- Error feedback loop

### Track A: Features

**Phase 2 GitHub**
- List user repositories
- Clone existing repos
- Branch management

**Aspirational: AI Spend Tracking**
- Fuel gauge for API credits
- Budget configuration
- Burn rate indicator

## Known Issues / Notes

1. **Sandboxing phase skipped** - Needs Docker-in-Docker config
2. **Gemini model** - Using `gemini-2.5-flash` (updated from deprecated model)
3. **Scanner path** - Currently hardcoded to `/app` for self-scanning; checkbox sets this
4. **VDO-generated code** - Produces correct standalone code but may need manual integration

## Documentation

| Doc | Purpose |
|-----|---------|
| `docs/ROADMAP.md` | Full development roadmap |
| `docs/ARCHITECTURE.md` | System architecture details |
| `docs/SPEC-B1-CODEBASE-SCANNER.md` | Scanner specification (completed) |
| `docs/GAMMA-PROMPT.md` | Presentation outline for Gamma |

## Session Start Checklist

1. Verify stack is running: `docker compose ps`
2. Check UI: http://localhost:3000
3. Check API: http://localhost:8000/docs
4. Review recent jobs in UI to confirm state
5. Pull latest if needed: `git pull origin main`
