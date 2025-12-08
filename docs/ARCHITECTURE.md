# VDO Architecture Clinic

## What Is VDO?

**Vitso Dev Orchestrator** — An AI-powered development pipeline that takes a project description and automatically plans, builds, tests, and delivers code.

**The pitch:** "Describe what you want, VDO builds it."

---

## The Big Picture

```
┌─────────────────────────────────────────────────────────────────┐
│                        YOU (Browser)                            │
│                     localhost:3000                              │
└─────────────────────┬───────────────────────────────────────────┘
                      │ HTTP + WebSocket
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FRONTEND (React)                             │
│  - Dashboard UI                                                 │
│  - Job creation form                                            │
│  - Real-time status updates                                     │
│  - Log viewer                                                   │
└─────────────────────┬───────────────────────────────────────────┘
                      │ REST API + WebSocket
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI)                            │
│  - API endpoints (/api/jobs, /api/logs, etc.)                   │
│  - WebSocket server (real-time updates)                         │
│  - Job queue management                                         │
│  Port: 8000                                                     │
└───────────┬─────────────────────────────────────────────────────┘
            │                                 │
            ▼                                 ▼
┌───────────────────────┐         ┌───────────────────────────────┐
│   POSTGRESQL          │         │   REDIS                       │
│   - Jobs table        │         │   - Job queue                 │
│   - Tasks table       │         │   - Pub/Sub for WebSocket     │
│   - Logs table        │         │                               │
│   - Generated files   │         │                               │
│   Port: 5432          │         │   Port: 6379                  │
└───────────────────────┘         └───────────┬───────────────────┘
                                              │
                                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    WORKER (RQ Worker)                           │
│  - Picks jobs from Redis queue                                  │
│  - Runs the 5-phase pipeline                                    │
│  - Calls AI providers                                           │
│  - Stores results in PostgreSQL                                 │
│  - Broadcasts updates via Redis pub/sub                         │
└───────────┬─────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                 AI ORCHESTRATOR                                 │
│  Routes tasks to best AI provider:                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   CLAUDE    │  │   OPENAI    │  │   GEMINI    │              │
│  │  (Planning) │  │  (Testing)  │  │  (Review)   │              │
│  │  (Building) │  │             │  │             │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    GITHUB INTEGRATION                           │
│  - Creates repository                                           │
│  - Pushes generated code                                        │
│  - Updates job with repo URL                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## The 5-Phase Pipeline

When you create a job, it flows through:

| Phase | What Happens | AI Used | Output |
|-------|--------------|---------|--------|
| **1. Planning** | AI breaks down your request into tasks | Claude | Task list (JSON) |
| **2. Building** | Each task executed, code generated | Claude | Generated files |
| **3. Testing** | AI writes tests for the code | OpenAI | Test files |
| **4. Sandboxing** | (Skipped) Would run code in Docker | — | — |
| **5. GitHub Push** | Pushes files to new repo | — | Repo URL |

---

## The Key Components

### 1. Frontend (`frontend/src/App.jsx`)
**Tech:** React + Vite + Tailwind CSS

**What it does:**
- Dashboard showing all jobs with status
- Create new job form
- Job details panel with pipeline progress
- Real-time log streaming
- GitHub repo link display

**Key feature:** WebSocket connection for live updates — no polling.

---

### 2. Backend API (`backend/main.py`)
**Tech:** FastAPI (Python)

**What it does:**
- REST endpoints for CRUD operations on jobs
- WebSocket endpoint for real-time updates
- Subscribes to Redis pub/sub, broadcasts to connected browsers

**Key endpoints:**
```
POST /api/jobs          → Create new job
GET  /api/jobs          → List all jobs
GET  /api/jobs/{id}     → Get job details
GET  /api/jobs/{id}/logs → Get job logs
WS   /ws                → Real-time updates
```

---

### 3. Worker (`backend/worker.py`)
**Tech:** RQ (Redis Queue) worker

**What it does:**
- Runs as separate process
- Pulls jobs from Redis queue
- Executes the 5-phase pipeline
- Updates database with progress
- Broadcasts status changes via Redis pub/sub

**The heart of VDO** — this is where the AI magic happens.

---

### 4. AI Orchestrator (`backend/orchestrator.py`)
**Tech:** Python + AI SDKs (Anthropic, OpenAI, Google)

**What it does:**
- Routes tasks to appropriate AI provider
- Manages prompts and context
- Handles retries and errors
- Tracks token usage

**Smart routing:**
```python
routing_map = {
    "planning": Claude,    # Best at breaking down problems
    "building": Claude,    # Best at code generation
    "testing": OpenAI,     # Good at test cases
    "reviewing": Gemini,   # Alternative perspective
}
```

---

### 5. GitHub Integration (`vdo_github/`)
**Tech:** PyGithub + GitPython

**What it does:**
- Creates private repos under your account
- Writes generated files to temp directory
- Initializes git, commits, pushes
- Updates job record with repo URL

---

### 6. Database Models (`backend/models.py`)
**Tech:** SQLAlchemy ORM

**Tables:**
```
Job
├── id, title, description
├── status (queued → planning → building → testing → sandboxing → completed)
├── ai_provider (auto, claude, openai, gemini)
├── tokens, cost, execution_time
├── github_repo_url, github_repo_name
└── rating, is_reference

Task
├── id, job_id, phase, description
├── status, ai_provider
└── output (JSON)

Log
├── id, job_id, task_id
├── timestamp, level, message

GeneratedFile
├── id, job_id, task_id
├── filename, content, language
```

---

## The Real-Time Update Flow

```
Worker completes task
       │
       ▼
Redis PUBLISH "vdo:job_updates" {type: "job_update", job_id: 42}
       │
       ▼
FastAPI subscriber receives message
       │
       ▼
WebSocket broadcast to all connected browsers
       │
       ▼
React receives, updates UI
       │
       ▼
You see status change instantly (no refresh)
```

---

## Docker Compose Stack

```yaml
services:
  postgres:    # Database - stores everything
  redis:       # Queue + pub/sub - coordinates everything
  backend:     # API server - serves requests
  worker:      # Job processor - does the work
  frontend:    # UI - you interact with this
```

All five containers talk to each other. One `docker-compose up -d` starts everything.

---

## What Makes It Interesting

1. **Multi-AI Orchestration** — Not locked into one provider. Routes tasks to the best AI for the job.

2. **Real-time Visibility** — Watch jobs progress live. See logs as they happen.

3. **Automatic GitHub Integration** — Code goes from idea → repo without manual steps.

4. **Self-improving Architecture** — We're using VDO to build VDO improvements (dogfooding).

5. **Token/Cost Tracking** — See exactly how much each job costs.

---

## Demo Script

1. **Show the dashboard** — "Here's the control center. Jobs on the left, details on the right."

2. **Create a simple job** — "Let's ask it to build a password generator."

3. **Watch it plan** — "See how it breaks this into tasks? That's Claude reasoning about the problem."

4. **Watch it build** — "Now it's generating code for each task. Notice the tokens counting up."

5. **Show the logs** — "Real-time logs. No refresh needed — WebSocket connection."

6. **Show GitHub link** — "Done. It created a repo and pushed the code. Click to see it on GitHub."

7. **View the code** — "This is what the AI wrote, tested, and delivered. From description to deployed code."

---

## Technology Summary

| Layer | Technology | Purpose |
|-------|------------|---------|
| Frontend | React, Vite, Tailwind | User interface |
| API | FastAPI | REST + WebSocket server |
| Database | PostgreSQL | Persistent storage |
| Queue | Redis + RQ | Job queue + pub/sub |
| AI | Claude, OpenAI, Gemini | Code generation |
| Version Control | PyGithub, GitPython | GitHub integration |
| Infrastructure | Docker Compose | Container orchestration |

---

## File Structure

```
vitso-dev-orchestrator/
├── backend/
│   ├── main.py           # FastAPI app, API routes, WebSocket
│   ├── worker.py         # RQ worker, job pipeline
│   ├── orchestrator.py   # AI routing and execution
│   ├── models.py         # SQLAlchemy database models
│   ├── database.py       # Database connection
│   ├── requirements.txt  # Python dependencies
│   ├── Dockerfile        # Backend container
│   └── .env              # API keys (not in git)
├── frontend/
│   ├── src/
│   │   ├── App.jsx       # Main React component
│   │   └── components/   # UI components
│   ├── package.json      # Node dependencies
│   └── Dockerfile        # Frontend container
├── vdo_github/
│   ├── __init__.py       # Module exports
│   ├── integration.py    # High-level functions
│   ├── github_client.py  # GitHub API wrapper
│   ├── git_operations.py # Git commands
│   └── config.py         # Credentials loading
├── docs/
│   ├── ROADMAP.md        # Development roadmap
│   ├── ARCHITECTURE.md   # This document
│   └── SPEC-*.md         # Feature specifications
├── docker-compose.yml    # Container orchestration
└── .env                  # Environment variables
```

---

## Getting Started (Quick Reference)

```bash
# Start everything
cd ~/vitso-dev-orchestrator
docker-compose up -d

# View logs
docker-compose logs -f worker

# Restart after code changes
docker-compose restart backend worker

# Full rebuild after dependency changes
docker-compose down
docker-compose build
docker-compose up -d

# Check container status
docker-compose ps
```

**Access points:**
- Dashboard: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
