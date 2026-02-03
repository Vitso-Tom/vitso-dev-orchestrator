# VDO Spec: Iterative Development Mode

**Status:** Proposed  
**Priority:** High  
**Prerequisite:** Phase B1 (Codebase Awareness)  
**Author:** Tom Smolinsky / Claude Session  
**Date:** December 20, 2025

---

## Problem Statement

VDO currently treats each job as a standalone greenfield project. This works for simple, self-contained builds but fails for realistic software development where:

1. **Projects evolve incrementally** - Features are added over multiple sessions
2. **Modules need to integrate** - Components must work together
3. **Context matters** - New code must understand existing architecture
4. **Iteration is normal** - Fix bugs, extend features, refactor

### Example Failure Case

**Goal:** Build an AI Governance Platform with 5 modules:
- Risk Assessment Engine
- SIG Questionnaire Generator  
- Precedent Database
- Scenario Modeler
- Retrospective Analyzer

**What happened:**
- Job 1 produced a working Risk Assessment module
- Job 2 (SIG Generator) had no knowledge of Job 1's code
- Result: Two incompatible standalone apps, not an integrated platform
- Manual Frankenstein assembly required

**What should happen:**
- Job 1 produces Risk Assessment + platform shell
- Job 2 extends Job 1, adding SIG Generator that integrates with existing code
- Jobs 3-5 continue extending, each aware of all previous work
- Final result: Unified platform, no manual assembly

---

## Proposed Solution: Job Extension Mode

### New Job Creation Flow

```
┌─────────────────────────────────────────────────────────────┐
│  Create New Job                                             │
├─────────────────────────────────────────────────────────────┤
│  Project Type:                                              │
│  ○ New Project (current behavior)                           │
│  ● Extend Existing Job                                      │
│                                                             │
│  Parent Job: [Dropdown: Recent Jobs]                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ #50 - AI Governance Platform (12/20, 6 files)       │   │
│  │ #49 - Password Generator (12/19, 3 files)           │   │
│  │ #48 - Risk Assessment Tool (12/18, 8 files)         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Title: [Add SIG Generator Module                    ]      │
│                                                             │
│  Description:                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Add a SIG questionnaire generator that reads        │   │
│  │ assessments from the risk engine and maps them      │   │
│  │ to SIG Lite format. Create as a Flask Blueprint     │   │
│  │ that integrates with the existing app.py...         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [Create Job]                                               │
└─────────────────────────────────────────────────────────────┘
```

### Database Schema Changes

```sql
-- Add to jobs table
ALTER TABLE jobs ADD COLUMN extends_job_id INTEGER REFERENCES jobs(id);
ALTER TABLE jobs ADD COLUMN is_extension BOOLEAN DEFAULT FALSE;

-- Add index for lineage queries
CREATE INDEX idx_jobs_extends ON jobs(extends_job_id);

-- View for job lineage
CREATE VIEW job_lineage AS
WITH RECURSIVE lineage AS (
  SELECT id, title, extends_job_id, 1 as depth
  FROM jobs WHERE extends_job_id IS NULL
  UNION ALL
  SELECT j.id, j.title, j.extends_job_id, l.depth + 1
  FROM jobs j
  JOIN lineage l ON j.extends_job_id = l.id
)
SELECT * FROM lineage;
```

```python
# models.py addition
class Job(Base):
    # ... existing fields ...
    
    # Extension support
    extends_job_id = Column(Integer, ForeignKey('jobs.id'), nullable=True)
    is_extension = Column(Boolean, default=False)
    
    # Relationship
    parent_job = relationship("Job", remote_side=[id], backref="child_jobs")
```

### Worker Pipeline Changes

#### Phase 1: Context Loading (New)

When a job has `extends_job_id`, load the parent project's files before planning:

```python
# worker.py

async def process_job(self, job_id: int):
    # ... existing setup ...
    
    # NEW: Load parent project context
    parent_context = None
    if job.extends_job_id:
        parent_context = await self.load_parent_context(db, job.extends_job_id)
        self.log_message(db, job_id, 
            f"Extending job #{job.extends_job_id} ({len(parent_context['files'])} files)")
    
    # Phase 1: Planning (now with parent context)
    planning_tokens = await self.planning_phase(db, job, parent_context)
    # ... rest of pipeline ...

async def load_parent_context(self, db: Session, parent_job_id: int) -> Dict:
    """Load all files and metadata from parent job for context."""
    
    # Get parent job
    parent_job = db.query(Job).filter(Job.id == parent_job_id).first()
    if not parent_job:
        raise Exception(f"Parent job {parent_job_id} not found")
    
    # Get all files from parent (and its ancestors)
    all_files = {}
    current_job_id = parent_job_id
    
    while current_job_id:
        files = db.query(GeneratedFile).filter(
            GeneratedFile.job_id == current_job_id
        ).all()
        
        for f in files:
            # Earlier files don't overwrite later ones (child takes precedence)
            if f.filename not in all_files:
                all_files[f.filename] = f.content
        
        # Walk up the lineage
        current_job = db.query(Job).filter(Job.id == current_job_id).first()
        current_job_id = current_job.extends_job_id if current_job else None
    
    return {
        'files': all_files,
        'parent_job': {
            'id': parent_job.id,
            'title': parent_job.title,
            'description': parent_job.description
        },
        'file_manifest': list(all_files.keys())
    }
```

#### Phase 2: Planning (Enhanced)

Modify the planning prompt to include parent context:

```python
# orchestrator.py

async def plan_job(self, job_description: str, parent_context: Dict = None) -> Dict:
    
    # Build context section for extension jobs
    extension_context = ""
    if parent_context:
        extension_context = f"""
## EXTENDING EXISTING PROJECT

You are ADDING to an existing codebase, not creating from scratch.

### Parent Project
- Job: #{parent_context['parent_job']['id']} - {parent_context['parent_job']['title']}
- Description: {parent_context['parent_job']['description']}

### Existing Files (DO NOT RECREATE - extend or modify only)
{chr(10).join(f'- {f}' for f in parent_context['file_manifest'])}

### Existing Code Reference
{self._format_existing_code(parent_context['files'])}

## CRITICAL RULES FOR EXTENSION JOBS

1. **DO NOT recreate existing files from scratch** - modify them if needed
2. **REUSE existing patterns** - follow the same code style, naming conventions
3. **INTEGRATE with existing code** - import from existing modules, use shared models
4. **EXTEND app.py** - add new blueprint registrations, don't rewrite the whole file
5. **EXTEND templates/base.html** - add nav links, don't recreate the layout

When you need to MODIFY an existing file, output the COMPLETE updated file.
When you need to ADD a new file, create it fresh.

Your task is: {job_description}
"""
    
    planning_prompt = f"""{extension_context}

You are a software development planning expert. Create an execution plan.

{job_description}

... rest of planning prompt ...
"""
```

#### Phase 3: Building (Enhanced)

Track which files are new vs modified:

```python
# worker.py

async def building_phase(self, db: Session, job: Job, parent_context: Dict = None) -> int:
    # ... existing setup ...
    
    parent_files = parent_context['files'] if parent_context else {}
    
    for task in building_tasks:
        # ... existing task execution ...
        
        if result["success"]:
            extracted = self._extract_and_store_code(db, job, task, result["content"])
            
            # Track file operation type
            for filename, content in extracted.items():
                if filename in parent_files:
                    if content != parent_files[filename]:
                        operation = "MODIFIED"
                    else:
                        operation = "UNCHANGED"
                else:
                    operation = "CREATED"
                
                self.log_message(db, job.id, 
                    f"[{operation}] {filename}", task_id=task.id)
```

#### Phase 4: File Merging

After building completes, merge new files with parent files:

```python
# worker.py

async def merge_with_parent(self, db: Session, job: Job, parent_context: Dict):
    """Ensure child job has complete file set (parent + new/modified)."""
    
    parent_files = parent_context['files']
    child_files = {f.filename: f for f in db.query(GeneratedFile).filter(
        GeneratedFile.job_id == job.id
    ).all()}
    
    # Copy parent files that weren't touched by this job
    for filename, content in parent_files.items():
        if filename not in child_files:
            # Inherit from parent
            inherited_file = GeneratedFile(
                job_id=job.id,
                task_id=None,  # No task - inherited
                filename=filename,
                content=content,
                language=self._detect_language(filename),
                inherited_from_job_id=parent_context['parent_job']['id']
            )
            db.add(inherited_file)
            self.log_message(db, job.id, f"[INHERITED] {filename}")
    
    db.commit()
```

### Deployment Changes

Extended jobs deploy the **complete merged codebase**, not just new files:

```python
# deployment.py

async def deploy(self, job_id: int) -> bool:
    # ... existing setup ...
    
    # Get ALL files (including inherited)
    all_files = db.query(GeneratedFile).filter(
        GeneratedFile.job_id == job_id
    ).all()
    
    # Write complete project
    for f in all_files:
        file_path = os.path.join(output_dir, f.filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as fp:
            fp.write(f.content)
        
        # Log source
        source = f"inherited from job #{f.inherited_from_job_id}" if f.inherited_from_job_id else "generated"
        print(f"[Deploy] {f.filename} ({source})")
```

---

## UI Changes

### Job List View

Show job lineage visually:

```
┌────────────────────────────────────────────────────────────┐
│ Jobs                                              [+ New]  │
├────────────────────────────────────────────────────────────┤
│ #52 AI Governance - Scenarios      ✓ Completed    12/20   │
│   └─ extends #51                                           │
│ #51 AI Governance - Precedents     ✓ Completed    12/20   │
│   └─ extends #50                                           │
│ #50 AI Governance - Risk Engine    ✓ Completed    12/20   │
│ #49 Password Generator             ✓ Completed    12/19   │
└────────────────────────────────────────────────────────────┘
```

### Job Detail View

Show file sources:

```
┌────────────────────────────────────────────────────────────┐
│ Job #51: AI Governance - Precedents                        │
│ Extends: Job #50 (AI Governance - Risk Engine)            │
├────────────────────────────────────────────────────────────┤
│ Files (8 total)                                            │
│                                                            │
│ Created in this job:                                       │
│   modules/precedent.py                                     │
│   templates/precedents/list.html                           │
│   templates/precedents/compare.html                        │
│                                                            │
│ Modified from parent:                                      │
│   app.py (added blueprint registration)                    │
│   templates/base.html (added nav link)                     │
│                                                            │
│ Inherited unchanged:                                       │
│   modules/risk_engine.py                                   │
│   templates/risk/form.html                                 │
│   static/css/style.css                                     │
└────────────────────────────────────────────────────────────┘
```

### Project View (New)

Group related jobs as a "project":

```
┌────────────────────────────────────────────────────────────┐
│ Project: AI Governance Platform                            │
│ Root: Job #50 | Latest: Job #54 | 5 iterations            │
├────────────────────────────────────────────────────────────┤
│                                                            │
│ #50 ──► #51 ──► #52 ──► #53 ──► #54                       │
│ Risk    Prec   Scen    SIG     Retro                      │
│                                                            │
│ Combined: 14 files | Deploy Latest | View Lineage         │
└────────────────────────────────────────────────────────────┘
```

---

## API Changes

### Create Job (Extended)

```
POST /api/jobs
{
  "title": "Add SIG Generator Module",
  "description": "...",
  "extends_job_id": 50  // NEW: optional
}
```

### Get Job (Extended Response)

```
GET /api/jobs/51
{
  "id": 51,
  "title": "Add Precedent Module",
  "extends_job_id": 50,
  "parent_job": {
    "id": 50,
    "title": "AI Governance - Risk Engine"
  },
  "child_jobs": [
    {"id": 52, "title": "Add Scenario Modeler"}
  ],
  "files": [
    {"filename": "app.py", "source": "modified", "from_job": null},
    {"filename": "modules/precedent.py", "source": "created", "from_job": null},
    {"filename": "modules/risk_engine.py", "source": "inherited", "from_job": 50}
  ]
}
```

### Get Job Lineage

```
GET /api/jobs/54/lineage
{
  "root_job_id": 50,
  "chain": [
    {"id": 50, "title": "Risk Engine", "files_created": 6},
    {"id": 51, "title": "Precedents", "files_created": 3, "files_modified": 2},
    {"id": 52, "title": "Scenarios", "files_created": 2, "files_modified": 1},
    {"id": 53, "title": "SIG Generator", "files_created": 2, "files_modified": 1},
    {"id": 54, "title": "Retrospective", "files_created": 3, "files_modified": 2}
  ],
  "total_files": 14
}
```

### Deploy Latest

```
POST /api/jobs/54/deploy
{
  "include_lineage": true  // Deploy complete merged codebase
}
```

---

## Implementation Phases

### Phase 1: Core Extension Support (MVP)
**Effort:** 8-12 hours

- [ ] Add `extends_job_id` to Job model
- [ ] Load parent files in worker pipeline
- [ ] Modify planning prompt with parent context
- [ ] Basic file inheritance (copy unmodified parent files)
- [ ] UI: Add "Extend Job" option to create form
- [ ] UI: Show parent job in job detail

### Phase 2: Smart Merging
**Effort:** 6-8 hours

- [ ] Track file operation types (created/modified/inherited)
- [ ] Conflict detection (file modified in both parent and child)
- [ ] Merge parent files into child job record
- [ ] UI: Show file sources in job detail

### Phase 3: Project View
**Effort:** 4-6 hours

- [ ] Job lineage query/view
- [ ] Project grouping (jobs with same root)
- [ ] Deploy from any point in lineage
- [ ] UI: Project timeline visualization

### Phase 4: Advanced Features
**Effort:** 8-10 hours

- [ ] Branch-like parallel extensions (Job A and Job B both extend Job 50)
- [ ] Merge parallel branches
- [ ] Diff view between jobs
- [ ] Rollback to previous job in lineage

---

## Success Criteria

1. **Can build multi-module platform in sequential jobs** without manual file assembly
2. **Child job has full context** of parent code when planning
3. **Deployed child job** includes all files (inherited + new + modified)
4. **UI clearly shows** job relationships and file provenance
5. **No regression** in standalone job functionality

---

## Test Cases

### Test 1: Basic Extension
1. Create Job A: "Build Flask hello world"
2. Create Job B extending A: "Add /goodbye route"
3. Verify: Job B's app.py has both routes
4. Deploy Job B: Both routes work

### Test 2: Multi-Level Extension
1. Job A: Flask shell
2. Job B extends A: Add module 1
3. Job C extends B: Add module 2
4. Deploy Job C: All modules present and integrated

### Test 3: File Modification
1. Job A: Flask app with basic nav
2. Job B extends A: Add new page + nav link
3. Verify: Job B's base.html has updated nav
4. Verify: Job B's file shows as "modified"

### Test 4: Parallel Extensions (Phase 4)
1. Job A: Flask shell
2. Job B extends A: Add feature X
3. Job C extends A: Add feature Y
4. Job D merges B and C: Has both X and Y

---

## Open Questions

1. **Token limits:** Large parent codebases may exceed context window. Solution: Smart truncation? File summaries? Selective loading?

2. **Conflict resolution:** What if AI generates a file that conflicts with parent? Auto-merge? Fail? User prompt?

3. **Orphaned children:** What happens to child jobs if parent is deleted? Prevent deletion? Copy files to child?

4. **GitHub integration:** Should extended jobs push to same repo? New branch? New repo with full history?

---

## Appendix: Alternative Approaches Considered

### A. Session-Based Development
Keep conversation context across multiple "turns" within a single job. 
**Rejected:** Doesn't fit VDO's job-based model; complex state management.

### B. Workspace/Project First-Class Object
Create a "Project" that contains multiple related jobs.
**Deferred:** Good idea but adds complexity. Extension chains achieve similar result.

### C. Git-Based Approach
Each job is a git commit; extensions are commits on top.
**Partial:** Good for Phase 4 but overkill for MVP. Keep as future enhancement.
