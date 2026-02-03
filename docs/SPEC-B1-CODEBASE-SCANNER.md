# VDO Phase B1: Codebase Scanner

## Problem Statement

VDO generates correct code but lacks context about the existing codebase. This results in:
- Standalone files that require manual integration
- Generic task descriptions ("implement backend logic") vs. specific ("edit worker.py line 150")
- No awareness of existing patterns, imports, or architecture

## Goal

Give VDO visibility into the project it's working on so it can:
1. Generate tasks that reference actual files
2. Produce code that follows existing patterns
3. Specify where new code should be integrated

## Scope

### In Scope
- Scan project directory structure on job start
- Extract key file summaries (first 50 lines, exports, classes)
- Inject context into planning prompt
- Store project index in job record for building phase

### Out of Scope (Phase B2+)
- Actually editing existing files (diff-based)
- Git operations during build
- Running generated code

---

## Technical Design

### 1. Project Scanner Module

**Location:** `backend/scanner.py`

**Functions:**

```python
def scan_project(project_path: str) -> dict:
    """
    Scan a project directory and return structured index.
    
    Returns:
        {
            "root": "/path/to/project",
            "structure": ["backend/", "frontend/", ...],
            "key_files": {
                "backend/worker.py": {
                    "type": "python",
                    "lines": 350,
                    "classes": ["JobProcessor"],
                    "functions": ["enqueue_job", "process_job_sync"],
                    "imports": ["redis", "sqlalchemy", ...],
                    "summary": "First 30 lines..."
                },
                ...
            },
            "patterns": {
                "database": "SQLAlchemy",
                "api": "FastAPI",
                "queue": "Redis + RQ"
            }
        }
    """

def get_file_summary(file_path: str) -> dict:
    """Extract metadata and summary from a single file."""

def identify_key_files(project_path: str) -> list:
    """
    Identify important files to index.
    Priority: models, routes, workers, configs, main entry points.
    Skip: node_modules, __pycache__, .git, assets, etc.
    """

def detect_patterns(project_index: dict) -> dict:
    """Infer tech stack and patterns from file contents."""
```

### 2. Database Changes

**Add to Job model (`models.py`):**

```python
# Project context for AI phases
project_index = Column(JSON, nullable=True)  # Scanner output
project_path = Column(String(500), nullable=True)  # Root path scanned
```

### 3. Worker Integration

**Modify `worker.py`:**

```python
async def process_job(self, job_id: int):
    # ... existing setup ...
    
    # NEW: Scan project if path provided
    if job.project_path:
        self.log_message(db, job_id, f"Scanning project: {job.project_path}")
        project_index = scan_project(job.project_path)
        job.project_index = project_index
        db.commit()
        self.log_message(db, job_id, f"Indexed {len(project_index['key_files'])} key files")
    
    # Phase 1: Planning (now with context)
    planning_tokens = await self.planning_phase(db, job)
    # ...
```

### 4. Enhanced Planning Prompt

**Modify `orchestrator.py` planning prompt:**

```python
def build_planning_prompt(job_description: str, project_index: dict = None) -> str:
    prompt = f"""You are a software development planning expert.

Project Request:
{job_description}
"""
    
    if project_index:
        prompt += f"""
Existing Project Context:
- Root: {project_index['root']}
- Tech Stack: {project_index['patterns']}
- Structure:
{chr(10).join('  ' + d for d in project_index['structure'][:20])}

Key Files:
"""
        for filepath, info in list(project_index['key_files'].items())[:10]:
            prompt += f"""
### {filepath}
- Type: {info['type']}
- Classes: {', '.join(info.get('classes', []))}
- Functions: {', '.join(info.get('functions', [])[:5])}
"""
        
        prompt += """
IMPORTANT: Reference actual files in your tasks. Instead of "implement backend logic", 
write "Add function X to backend/worker.py after line Y" or "Create new file backend/foo.py".
"""
    
    prompt += """
Create a structured plan with 4 phases: Planning, Building, Testing, Sandboxing.
For each task, specify the target file path when applicable.
...
"""
    return prompt
```

### 5. Job Creation API Update

**Modify `main.py` JobCreate model:**

```python
class JobCreate(BaseModel):
    title: str
    description: str
    ai_provider: AIProvider = AIProvider.AUTO
    project_path: Optional[str] = None  # NEW: Path to scan
```

### 6. Frontend Update (Optional)

Add optional "Project Path" field to new job form:
- Text input for local path
- Or dropdown of recent/saved project paths
- Default: VDO's own codebase for dogfooding

---

## File Identification Heuristics

**High Priority (always index):**
- `**/models.py`, `**/schemas.py` — Data structures
- `**/main.py`, `**/app.py`, `**/__init__.py` — Entry points
- `**/worker*.py`, `**/tasks.py` — Background jobs
- `**/routes/*.py`, `**/api/*.py` — API endpoints
- `**/*.config.*`, `**/settings.py` — Configuration
- `**/docker-compose.yml`, `**/Dockerfile` — Infrastructure
- `**/requirements.txt`, `**/package.json` — Dependencies

**Medium Priority (index if < 20 key files):**
- `**/utils/*.py`, `**/helpers/*.py`
- `**/components/*.jsx`, `**/pages/*.jsx`
- `**/*_test.py`, `**/test_*.py`

**Always Skip:**
- `node_modules/`, `__pycache__/`, `.git/`
- `*.pyc`, `*.min.js`, `*.map`
- `dist/`, `build/`, `.next/`
- Binary files, images, fonts

---

## Success Criteria

1. **Scanner produces useful index** — Run on VDO codebase, verify output captures key files
2. **Planning uses context** — Tasks reference actual file paths
3. **Building has access** — Task prompts include relevant file content
4. **Measurable improvement** — Compare task specificity before/after

---

## Test Plan

### Test 1: Scanner Unit Tests
```python
def test_scan_vdo_project():
    index = scan_project("/app")
    assert "backend/worker.py" in index["key_files"]
    assert "JobProcessor" in index["key_files"]["backend/worker.py"]["classes"]

def test_skip_pycache():
    index = scan_project("/app")
    assert not any("__pycache__" in f for f in index["key_files"])
```

### Test 2: Integration Test
1. Create job with `project_path="/app"` (VDO itself)
2. Verify `project_index` populated in job record
3. Check planning output references actual files

### Test 3: Dogfood Test
Create job: "Add a /health endpoint to the API that returns uptime and version"
- Without scanner: Generic tasks
- With scanner: Tasks should reference `backend/main.py`, existing route patterns

---

## Estimated Effort

| Task | Hours |
|------|-------|
| scanner.py module | 4 |
| Database migration | 1 |
| Worker integration | 2 |
| Planning prompt update | 2 |
| API update | 1 |
| Frontend field (optional) | 2 |
| Testing | 3 |
| **Total** | **15** |

---

## Notes

- For dogfooding, default `project_path` to VDO's own directory
- Consider caching project index for repeated jobs on same codebase
- Token budget: Keep total context injection under 4K tokens
