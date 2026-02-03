from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json
import os
import subprocess
import base64
import httpx
import asyncio
from redis import Redis

from database import get_db, init_db
from research_routes import research_router
from models import Job, Task, Log, JobStatus, AIProvider, GeneratedFile, AgentAnalysis, AnalysisStatus
from worker import enqueue_job
from startup_cleanup import cleanup_stale_deployments
from pydantic import BaseModel

# Initialize FastAPI app
app = FastAPI(title="Vitso Dev Orchestrator", version="1.0.0")
app.include_router(research_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup event - cleanup stale deployments
@app.on_event("startup")
async def startup_event():
    cleanup_stale_deployments()

# Pydantic models for API
class JobCreate(BaseModel):
    title: str
    description: str
    ai_provider: AIProvider = AIProvider.AUTO
    project_path: Optional[str] = None  # Path to scan for codebase context

class JobResponse(BaseModel):
    id: int
    title: str
    description: str
    status: JobStatus
    ai_provider: AIProvider
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    # Token & Time Tracking
    input_tokens: Optional[int] = 0
    output_tokens: Optional[int] = 0
    total_tokens: Optional[int] = 0
    estimated_cost: Optional[str]
    execution_time_seconds: Optional[int]
    # Rating fields
    rating: Optional[int]
    is_reference: Optional[bool]
    rating_notes: Optional[str]
    # GitHub fields
    github_repo_url: Optional[str]
    github_repo_name: Optional[str]
    github_pushed_at: Optional[datetime]
    # Scanner fields
    project_path: Optional[str]
    # Adopted project fields
    is_adopted: Optional[bool] = False
    adopted_path: Optional[str] = None
    startup_command: Optional[str] = None
    
    class Config:
        from_attributes = True

class TaskResponse(BaseModel):
    id: int
    job_id: int
    phase: str
    description: str
    status: JobStatus
    ai_provider: AIProvider
    created_at: datetime
    order: int
    
    class Config:
        from_attributes = True

class LogResponse(BaseModel):
    id: int
    job_id: int
    task_id: Optional[int]
    timestamp: datetime
    level: str
    message: str
    
    class Config:
        from_attributes = True

# NEW: Rating request model
class RatingRequest(BaseModel):
    rating: int  # 1-5
    is_reference: bool = False
    notes: Optional[str] = None

# NEW: GitHub push request model
class GitHubPushRequest(BaseModel):
    repo_name: str
    description: Optional[str] = None
    private: bool = True

# NEW: Agent analysis request model
class AnalysisRequest(BaseModel):
    agents: List[str] = ["security", "code_review"]  # Which agents to run

# NEW: Adopt project request model
class AdoptProjectRequest(BaseModel):
    title: str
    description: str
    project_path: str  # Path to external codebase
    deployment_type: str = "python"  # python, node, static
    deployment_port: int
    startup_command: Optional[str] = None  # e.g., "python arma_app.py"

# NEW: Agent analysis response model
class AgentAnalysisResponse(BaseModel):
    id: int
    job_id: int
    agent_name: str
    agent_type: Optional[str]
    status: AnalysisStatus
    findings: Optional[dict]
    recommendations: Optional[dict]
    severity_summary: Optional[dict]
    created_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]
    
    class Config:
        from_attributes = True

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

# Redis connection for pub/sub
redis_conn = Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0
)

async def redis_subscriber():
    """Subscribe to Redis channel and broadcast to WebSocket clients"""
    pubsub = redis_conn.pubsub()
    pubsub.subscribe("vdo:job_updates")
    
    print("✓ Redis subscriber started")
    
    while True:
        try:
            message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                data = json.loads(message["data"])
                await manager.broadcast(data)
        except Exception as e:
            print(f"Redis subscriber error: {e}")
        await asyncio.sleep(0.1)  # Prevent busy loop

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_db()
    print("✓ Database initialized")
    
    # Start Redis subscriber as background task
    asyncio.create_task(redis_subscriber())
    
    print("✓ Vitso Dev Orchestrator is running!")

# API Routes
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "name": "Vitso Dev Orchestrator",
        "version": "1.0.0",
        "status": "running"
    }

@app.post("/api/jobs", response_model=JobResponse)
async def create_job(job: JobCreate, db: Session = Depends(get_db)):
    """Create a new job"""
    new_job = Job(
        title=job.title,
        description=job.description,
        ai_provider=job.ai_provider,
        project_path=job.project_path,
        status=JobStatus.QUEUED
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    
    # Enqueue the job for processing
    enqueue_job(new_job.id)
    
    # Broadcast to WebSocket clients
    await manager.broadcast({
        "type": "job_created",
        "job_id": new_job.id,
        "title": new_job.title
    })
    
    return new_job

@app.get("/api/jobs", response_model=List[JobResponse])
async def list_jobs(
    status: Optional[JobStatus] = None,
    reference_only: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """List all jobs"""
    query = db.query(Job)
    
    if status:
        query = query.filter(Job.status == status)
    
    if reference_only:
        query = query.filter(Job.is_reference == True)
    
    jobs = query.order_by(Job.created_at.desc()).limit(limit).all()
    return jobs

@app.get("/api/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: Session = Depends(get_db)):
    """Get a specific job"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/api/jobs/{job_id}/tasks", response_model=List[TaskResponse])
async def get_job_tasks(job_id: int, db: Session = Depends(get_db)):
    """Get all tasks for a job"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    tasks = db.query(Task).filter(Task.job_id == job_id).order_by(Task.order).all()
    return tasks

@app.get("/api/jobs/{job_id}/logs", response_model=List[LogResponse])
async def get_job_logs(
    job_id: int,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get logs for a job"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    logs = db.query(Log).filter(
        Log.job_id == job_id
    ).order_by(Log.timestamp.desc()).limit(limit).all()
    
    return logs

@app.delete("/api/jobs/{job_id}")
async def cancel_job(job_id: int, db: Session = Depends(get_db)):
    """Cancel a job"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
        raise HTTPException(status_code=400, detail="Job already finished")
    
    job.status = JobStatus.FAILED
    job.error_message = "Cancelled by user"
    job.completed_at = datetime.utcnow()
    db.commit()
    
    await manager.broadcast({
        "type": "job_cancelled",
        "job_id": job_id
    })
    
    return {"message": "Job cancelled successfully"}

@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get system statistics"""
    total_jobs = db.query(Job).count()
    queued_jobs = db.query(Job).filter(Job.status == JobStatus.QUEUED).count()
    running_jobs = db.query(Job).filter(
        Job.status.in_([JobStatus.PLANNING, JobStatus.BUILDING, JobStatus.TESTING, JobStatus.SANDBOXING])
    ).count()
    completed_jobs = db.query(Job).filter(Job.status == JobStatus.COMPLETED).count()
    failed_jobs = db.query(Job).filter(Job.status == JobStatus.FAILED).count()
    reference_jobs = db.query(Job).filter(Job.is_reference == True).count()
    
    return {
        "total_jobs": total_jobs,
        "queued": queued_jobs,
        "running": running_jobs,
        "completed": completed_jobs,
        "failed": failed_jobs,
        "reference_jobs": reference_jobs
    }


# ============================================================
# NEW: Adopted Projects Endpoints
# ============================================================

@app.post("/api/jobs/adopt", response_model=JobResponse)
async def adopt_project(adopt_req: AdoptProjectRequest, db: Session = Depends(get_db)):
    """
    Register an externally-managed codebase with VDO.
    
    Adopted projects:
    - Can be deployed/stopped from VDO
    - Cannot be rebuilt (code lives outside VDO)
    - Deleting the job only removes it from VDO (code untouched)
    """
    import os
    
    # Validate path exists
    if not os.path.exists(adopt_req.project_path):
        raise HTTPException(
            status_code=400, 
            detail=f"Project path does not exist: {adopt_req.project_path}"
        )
    
    # Check for duplicate adoption
    existing = db.query(Job).filter(
        Job.is_adopted == True,
        Job.adopted_path == adopt_req.project_path
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Project already adopted as Job {existing.id}: {existing.title}"
        )
    
    # Check port not already in use by another job
    port_in_use = db.query(Job).filter(
        Job.deployment_port == adopt_req.deployment_port,
        Job.deploy_local == True
    ).first()
    if port_in_use:
        raise HTTPException(
            status_code=400,
            detail=f"Port {adopt_req.deployment_port} already in use by Job {port_in_use.id}"
        )
    
    # Create adopted job record
    new_job = Job(
        title=adopt_req.title,
        description=adopt_req.description,
        status=JobStatus.COMPLETED,  # Already "built" - ready to deploy
        ai_provider=AIProvider.AUTO,
        is_adopted=True,
        adopted_path=adopt_req.project_path,
        deployment_type=adopt_req.deployment_type,
        deployment_port=adopt_req.deployment_port,
        startup_command=adopt_req.startup_command,
        completed_at=datetime.utcnow()  # Mark as completed immediately
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    
    await manager.broadcast({
        "type": "job_adopted",
        "job_id": new_job.id,
        "title": new_job.title,
        "path": adopt_req.project_path
    })
    
    return new_job


@app.get("/api/jobs/adopted")
async def list_adopted_projects(db: Session = Depends(get_db)):
    """List all adopted projects"""
    jobs = db.query(Job).filter(Job.is_adopted == True).order_by(Job.created_at.desc()).all()
    return jobs


@app.delete("/api/jobs/{job_id}/unadopt")
async def unadopt_project(job_id: int, db: Session = Depends(get_db)):
    """
    Remove an adopted project from VDO.
    This only removes the job record - the actual codebase is untouched.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if not job.is_adopted:
        raise HTTPException(status_code=400, detail="Job is not an adopted project")
    
    # Stop deployment if running
    if job.deploy_local and job.deployment_pid:
        from deployment import deployment_manager
        await deployment_manager.stop(job_id)
    
    # Store path for response
    path = job.adopted_path
    
    # Delete the job record (code untouched)
    db.delete(job)
    db.commit()
    
    await manager.broadcast({
        "type": "job_unadopted",
        "job_id": job_id
    })
    
    return {
        "message": "Project removed from VDO (codebase untouched)",
        "job_id": job_id,
        "path": path
    }


# ============================================================
# NEW: Job Rating Endpoints
# ============================================================

@app.put("/api/jobs/{job_id}/rating")
async def rate_job(job_id: int, rating_req: RatingRequest, db: Session = Depends(get_db)):
    """Rate a job and optionally mark as reference"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if rating_req.rating < 1 or rating_req.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
    
    job.rating = rating_req.rating
    job.is_reference = rating_req.is_reference
    job.rating_notes = rating_req.notes
    db.commit()
    db.refresh(job)
    
    await manager.broadcast({
        "type": "job_rated",
        "job_id": job_id,
        "rating": rating_req.rating,
        "is_reference": rating_req.is_reference
    })
    
    return {
        "message": "Job rated successfully",
        "job_id": job_id,
        "rating": job.rating,
        "is_reference": job.is_reference
    }

@app.get("/api/jobs/references")
async def get_reference_jobs(db: Session = Depends(get_db)):
    """Get all reference jobs"""
    jobs = db.query(Job).filter(Job.is_reference == True).order_by(Job.rating.desc()).all()
    return jobs


# ============================================================
# NEW: GitHub Integration Endpoints
# ============================================================

@app.post("/api/jobs/{job_id}/github-push")
async def push_to_github(
    job_id: int, 
    push_req: GitHubPushRequest, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Push generated files to a new GitHub repository"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Can only push completed jobs to GitHub")
    
    # Check for GitHub token
    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        raise HTTPException(status_code=400, detail="GITHUB_TOKEN not configured")
    
    # Get generated files
    files = db.query(GeneratedFile).filter(GeneratedFile.job_id == job_id).all()
    if not files:
        raise HTTPException(status_code=400, detail="No generated files to push")
    
    # Create GitHub repo and push files (async background task)
    background_tasks.add_task(
        create_github_repo_and_push,
        job_id=job_id,
        repo_name=push_req.repo_name,
        description=push_req.description or job.description,
        private=push_req.private,
        files=[(f.filename, f.content) for f in files],
        github_token=github_token
    )
    
    return {
        "message": "GitHub push initiated",
        "job_id": job_id,
        "repo_name": push_req.repo_name,
        "status": "processing"
    }

async def create_github_repo_and_push(
    job_id: int,
    repo_name: str,
    description: str,
    private: bool,
    files: List[tuple],
    github_token: str
):
    """Background task to create GitHub repo and push files"""
    from database import SessionLocal
    db = SessionLocal()
    
    try:
        async with httpx.AsyncClient() as client:
            # Create repository
            create_repo_response = await client.post(
                "https://api.github.com/user/repos",
                headers={
                    "Authorization": f"token {github_token}",
                    "Accept": "application/vnd.github.v3+json"
                },
                json={
                    "name": repo_name,
                    "description": description[:200] if description else "",
                    "private": private,
                    "auto_init": True  # Creates README
                }
            )
            
            if create_repo_response.status_code not in [201, 422]:  # 422 = already exists
                raise Exception(f"Failed to create repo: {create_repo_response.text}")
            
            repo_data = create_repo_response.json()
            repo_url = repo_data.get("html_url", f"https://github.com/{repo_name}")
            owner = repo_data.get("owner", {}).get("login", "")
            
            # Push each file
            for filename, content in files:
                file_path = filename
                encoded_content = base64.b64encode(content.encode()).decode()
                
                await client.put(
                    f"https://api.github.com/repos/{owner}/{repo_name}/contents/{file_path}",
                    headers={
                        "Authorization": f"token {github_token}",
                        "Accept": "application/vnd.github.v3+json"
                    },
                    json={
                        "message": f"Add {filename} via VDO",
                        "content": encoded_content
                    }
                )
            
            # Update job with GitHub info
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.github_repo_url = repo_url
                job.github_repo_name = repo_name
                job.github_pushed_at = datetime.utcnow()
                db.commit()
                
    except Exception as e:
        print(f"GitHub push error for job {job_id}: {e}")
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            # Store error but don't fail the job
            pass
    finally:
        db.close()


# ============================================================
# NEW: Agent Analysis Endpoints
# ============================================================

@app.post("/api/jobs/{job_id}/analyze")
async def run_agent_analysis(
    job_id: int,
    analysis_req: AnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Run agent analysis on a completed job"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Can only analyze completed jobs")
    
    # Create analysis records
    analyses = []
    for agent_name in analysis_req.agents:
        analysis = AgentAnalysis(
            job_id=job_id,
            agent_name=agent_name,
            agent_type="internal",
            status=AnalysisStatus.PENDING
        )
        db.add(analysis)
        analyses.append(analysis)
    
    db.commit()
    
    # Refresh to get IDs
    for analysis in analyses:
        db.refresh(analysis)
    
    # Run analysis in background
    for analysis in analyses:
        background_tasks.add_task(
            run_single_agent_analysis,
            analysis_id=analysis.id,
            job_id=job_id,
            agent_name=analysis.agent_name
        )
    
    await manager.broadcast({
        "type": "analysis_started",
        "job_id": job_id,
        "agents": analysis_req.agents
    })
    
    return {
        "message": "Analysis started",
        "job_id": job_id,
        "analyses": [{"id": a.id, "agent": a.agent_name, "status": "pending"} for a in analyses]
    }

@app.get("/api/jobs/{job_id}/analyses", response_model=List[AgentAnalysisResponse])
async def get_job_analyses(job_id: int, db: Session = Depends(get_db)):
    """Get all analyses for a job"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    analyses = db.query(AgentAnalysis).filter(AgentAnalysis.job_id == job_id).all()
    return analyses

async def run_single_agent_analysis(analysis_id: int, job_id: int, agent_name: str):
    """Background task to run a single agent analysis"""
    from database import SessionLocal
    from orchestrator import AIOrchestrator
    
    db = SessionLocal()
    orchestrator = AIOrchestrator()
    
    try:
        analysis = db.query(AgentAnalysis).filter(AgentAnalysis.id == analysis_id).first()
        if not analysis:
            return
        
        analysis.status = AnalysisStatus.RUNNING
        analysis.started_at = datetime.utcnow()
        db.commit()
        
        # Get the generated files for this job
        files = db.query(GeneratedFile).filter(GeneratedFile.job_id == job_id).all()
        code_content = "\n\n".join([
            f"# File: {f.filename}\n{f.content}" for f in files
        ])
        
        # Build agent prompt based on type
        agent_prompts = {
            "security": """You are a security expert. Analyze this code for:
- OWASP Top 10 vulnerabilities
- Authentication/authorization issues
- Data exposure risks
- Input validation problems
- SQL injection, XSS, CSRF risks

Return JSON format:
{
    "findings": [{"severity": "critical|high|medium|low", "issue": "description", "location": "file/line", "recommendation": "fix"}],
    "summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
    "overall_risk": "low|medium|high|critical"
}""",
            
            "code_review": """You are a senior code reviewer. Analyze this code for:
- Code quality and readability
- Best practices violations
- Performance issues
- Error handling
- Code organization

Return JSON format:
{
    "findings": [{"category": "quality|performance|error_handling|organization", "issue": "description", "suggestion": "improvement"}],
    "quality_score": 1-10,
    "summary": "brief overall assessment"
}""",
            
            "optimization": """You are a performance optimization expert. Analyze this code for:
- Performance bottlenecks
- Memory usage issues
- Algorithmic complexity
- Caching opportunities
- Database query optimization

Return JSON format:
{
    "findings": [{"type": "performance|memory|complexity|caching|database", "issue": "description", "impact": "high|medium|low", "suggestion": "optimization"}],
    "optimization_score": 1-10
}""",
            
            "documentation": """You are a technical documentation expert. Analyze this code for:
- Missing docstrings
- Unclear function/variable names
- Missing type hints
- README completeness
- API documentation

Return JSON format:
{
    "findings": [{"type": "docstring|naming|types|readme|api", "issue": "description", "suggestion": "improvement"}],
    "documentation_score": 1-10
}"""
        }
        
        prompt = agent_prompts.get(agent_name, agent_prompts["code_review"])
        full_prompt = f"{prompt}\n\nCode to analyze:\n```\n{code_content}\n```"
        
        # Use orchestrator to run analysis
        result = await orchestrator.execute_task(full_prompt, "analysis")
        
        # Parse result
        try:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                parsed_result = json.loads(json_match.group())
                analysis.findings = parsed_result.get("findings", [])
                analysis.recommendations = parsed_result.get("recommendations", [])
                analysis.severity_summary = parsed_result.get("summary", {})
            else:
                analysis.findings = [{"raw_response": result}]
        except json.JSONDecodeError:
            analysis.findings = [{"raw_response": result}]
        
        analysis.status = AnalysisStatus.COMPLETED
        analysis.completed_at = datetime.utcnow()
        db.commit()
        
    except Exception as e:
        analysis = db.query(AgentAnalysis).filter(AgentAnalysis.id == analysis_id).first()
        if analysis:
            analysis.status = AnalysisStatus.FAILED
            analysis.error_message = str(e)
            analysis.completed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


# ============================================================
# Generated Files Endpoints
# ============================================================

@app.get("/api/jobs/{job_id}/generated-files")
async def get_job_generated_files(job_id: int, db: Session = Depends(get_db)):
    """Get all generated files for a job"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    files = db.query(GeneratedFile).filter(GeneratedFile.job_id == job_id).all()
    
    return {
        "job_id": job_id,
        "job_title": job.title,
        "total_files": len(files),
        "files": [
            {
                "id": f.id,
                "filename": f.filename,
                "filepath": f.filepath,
                "language": f.language,
                "file_size": f.file_size,
                "content": f.content,
                "created_at": f.created_at.isoformat()
            }
            for f in files
        ]
    }

@app.get("/api/generated-files/{file_id}")
async def get_generated_file(file_id: int, db: Session = Depends(get_db)):
    """Get a specific generated file"""
    file = db.query(GeneratedFile).filter(GeneratedFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    return {
        "id": file.id,
        "filename": file.filename,
        "filepath": file.filepath,
        "language": file.language,
        "file_size": file.file_size,
        "content": file.content,
        "created_at": file.created_at.isoformat(),
        "job_id": file.job_id
    }


# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time job updates"""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back for now, but could handle commands
            await websocket.send_json({"type": "pong", "data": data})
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ============================================================
# LOCAL DEPLOYMENT ENDPOINTS
# ============================================================

# ============================================================
# ADOPTED PROJECTS ENDPOINT
# ============================================================

@app.post("/api/jobs/adopt", response_model=JobResponse)
async def adopt_project(adopt_req: AdoptProjectRequest, db: Session = Depends(get_db)):
    """
    Register an externally-managed codebase with VDO.
    
    Adopted projects:
    - Can be deployed/stopped via VDO
    - Cannot be rebuilt (code lives outside VDO)
    - Files are not deleted on stop (VDO doesn't own them)
    """
    # Validate project path exists
    if not os.path.exists(adopt_req.project_path):
        raise HTTPException(
            status_code=400, 
            detail=f"Project path does not exist: {adopt_req.project_path}"
        )
    
    # Check for duplicate adoption
    existing = db.query(Job).filter(
        Job.is_adopted == True,
        Job.adopted_path == adopt_req.project_path
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Project already adopted as Job {existing.id}: {existing.title}"
        )
    
    # Create job record
    new_job = Job(
        title=adopt_req.title,
        description=adopt_req.description,
        status=JobStatus.COMPLETED,  # Already "built"
        is_adopted=True,
        adopted_path=adopt_req.project_path,
        deployment_type=adopt_req.deployment_type,
        deployment_port=adopt_req.deployment_port,
        startup_command=adopt_req.startup_command,
        project_path=adopt_req.project_path,  # Also set project_path for consistency
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    
    # Add adoption log
    log = Log(
        job_id=new_job.id,
        level="INFO",
        message=f"[ADOPT] Project adopted from {adopt_req.project_path}"
    )
    db.add(log)
    db.commit()
    
    await manager.broadcast({
        "type": "job_adopted",
        "job_id": new_job.id,
        "title": new_job.title,
        "adopted_path": adopt_req.project_path
    })
    
    return new_job


@app.post("/api/jobs/{job_id}/deploy")
async def deploy_job_locally(
    job_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Deploy generated code locally for demo/testing"""
    from deployment import deployment_manager
    
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job not completed yet")
    
    # If already deploying or deployed, clean up first
    if job.deployment_pid:
        from deployment import deployment_manager as dm
        if dm.is_running(job_id):
            raise HTTPException(status_code=400, detail="Already deployed. Stop existing deployment first.")
        else:
            # Process is dead but DB still has data - clean it up
            job.deployment_pid = None
            job.deployment_url = None
            job.deployment_port = None
            job.deployment_error = None
            job.deployment_output_dir = None
            job.deployment_type = None
    
    job.deploy_local = True
    db.commit()
    
    background_tasks.add_task(deployment_manager.deploy, job_id)
    
    await manager.broadcast({
        "type": "deployment_started",
        "job_id": job_id
    })
    
    return {
        "message": "Deployment started",
        "job_id": job_id,
        "status": "deploying"
    }

@app.get("/api/jobs/{job_id}/deployment")
async def get_deployment_status(job_id: int, db: Session = Depends(get_db)):
    """Get current deployment status"""
    from deployment import deployment_manager
    
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    is_running = deployment_manager.is_running(job_id)
    
    return {
        "job_id": job_id,
        "deployed": is_running,
        "url": job.deployment_url if is_running else None,
        "port": job.deployment_port,
        "pid": job.deployment_pid,
        "output_dir": job.deployment_output_dir,
        "type": job.deployment_type,
        "error": job.deployment_error,
        "deploy_requested": job.deploy_local
    }


@app.delete("/api/jobs/{job_id}/deployment")
async def stop_deployment(
    job_id: int,
    db: Session = Depends(get_db)
):
    """Stop deployment and cleanup files"""
    from deployment import deployment_manager
    
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Clear deploy_requested flag IMMEDIATELY so UI stops polling
    job.deploy_local = False
    db.commit()
    
    # Run cleanup synchronously (it's fast)
    await deployment_manager.stop(job_id)
    
    await manager.broadcast({
        "type": "deployment_stopped",
        "job_id": job_id
    })
    
    return {
        "message": "Deployment stopped and cleaned up",
        "job_id": job_id
    }


@app.get("/api/jobs/{job_id}/deployment/logs")
async def get_deployment_logs(
    job_id: int,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get deployment-related logs"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    logs = db.query(Log).filter(
        Log.job_id == job_id,
        Log.message.contains('[DEPLOY]')
    ).order_by(Log.timestamp.desc()).limit(limit).all()
    
    return [
        {
            "timestamp": log.timestamp.isoformat(),
            "message": log.message.replace('[DEPLOY] ', ''),
            "level": log.level
        }
        for log in logs
    ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
