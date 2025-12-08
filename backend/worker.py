from rq import Queue, Worker
from redis import Redis
import os
import sys
import tempfile
import shutil
from typing import Dict, Any
from sqlalchemy.orm import Session
from models import Job, Task, Log, JobStatus, AIProvider, GeneratedFile
from orchestrator import AIOrchestrator
from database import SessionLocal
import docker
import json
from datetime import datetime

# Add vdo_github to path (mounted at /vdo_github in Docker, or ../vdo_github locally)
sys.path.insert(0, '/')  # For Docker: /vdo_github
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))  # For local dev

try:
    from vdo_github import create_project_repo, is_configured as github_is_configured
    GITHUB_AVAILABLE = True
except ImportError as e:
    print(f"vdo_github import failed: {e}")
    GITHUB_AVAILABLE = False
    github_is_configured = lambda: False

# Import scanner for codebase awareness
try:
    from scanner import scan_project
    SCANNER_AVAILABLE = True
except ImportError as e:
    print(f"scanner import failed: {e}")
    SCANNER_AVAILABLE = False
    scan_project = None

# Redis connection
redis_conn = Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0
)

# Create queue
job_queue = Queue("vitso-jobs", connection=redis_conn)

def broadcast_update(event_type: str, job_id: int, **kwargs):
    """Publish job update to Redis channel for WebSocket broadcast"""
    message = json.dumps({
        "type": event_type,
        "job_id": job_id,
        **kwargs
    })
    redis_conn.publish("vdo:job_updates", message)

class JobProcessor:
    """
    Processes jobs through the complete pipeline
    """
    
    def __init__(self):
        self.orchestrator = AIOrchestrator()
#       self.docker_client = docker.from_env()
    
    def log_message(self, db: Session, job_id: int, message: str, level: str = "INFO", task_id: int = None):
        """Add a log entry"""
        log = Log(
            job_id=job_id,
            task_id=task_id,
            level=level,
            message=message
        )
        db.add(log)
        db.commit()
        # Broadcast log update
        broadcast_update("log_update", job_id)
        
    def _extract_and_store_code(self, db: Session, job: Job, task: Task, content: str):
        """Extract code blocks from AI response and store as files"""
        import re
        
        code_pattern = r'```(\w+)?\n(.*?)```'
        matches = re.findall(code_pattern, content, re.DOTALL)
        
        if not matches:
            return
        
        for idx, (language, code) in enumerate(matches):
            language = language.lower() if language else "txt"
            extensions = {"python": "py", "javascript": "js", "typescript": "ts", "bash": "sh", "json": "json"}
            ext = extensions.get(language, language or "txt")
            
            filename = f"generated_{task.id}_{idx}.{ext}"
            filepath = f"job_{job.id}/{filename}"
            
            generated_file = GeneratedFile(
                job_id=job.id, task_id=task.id, filename=filename,
                filepath=filepath, content=code.strip(),
                language=language, file_size=len(code)
            )
            db.add(generated_file)
        db.commit()
        # Also print to console for worker logs
    
    async def process_job(self, job_id: int):
        """
        Main job processing pipeline
        """
        db = SessionLocal()
        
        # Token tracking
        total_input_tokens = 0
        total_output_tokens = 0
        total_tokens = 0
        
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                print(f"Job {job_id} not found")
                return
            
            self.log_message(db, job_id, "Starting job processing")
            job.status = JobStatus.PLANNING
            job.started_at = datetime.utcnow()
            db.commit()
            broadcast_update("job_update", job_id, status="planning")
            
            start_time = datetime.utcnow()
            
            # Phase 0: Scan codebase (if project_path provided)
            if job.project_path and SCANNER_AVAILABLE:
                await self.scanning_phase(db, job)
            
            # Phase 1: Planning
            planning_tokens = await self.planning_phase(db, job)
            total_tokens += planning_tokens
            
            # Phase 2: Building
            building_tokens = await self.building_phase(db, job)
            total_tokens += building_tokens
            
            # Phase 3: Testing
            testing_tokens = await self.testing_phase(db, job)
            total_tokens += testing_tokens
            
            # Phase 4: Sandboxing
            await self.sandboxing_phase(db, job)
            
            # Phase 5: GitHub Push (optional)
            await self.github_push_phase(db, job)
            
            # Calculate execution time
            end_time = datetime.utcnow()
            execution_seconds = int((end_time - start_time).total_seconds())
            
            # Calculate estimated cost (rough estimates per 1K tokens)
            # Claude: ~$0.003/1K input, $0.015/1K output (using blended ~$0.01/1K)
            # OpenAI: ~$0.01/1K
            # Gemini: ~$0.001/1K
            estimated_cost = (total_tokens / 1000) * 0.01  # Default estimate
            
            # Mark complete and save token data
            job.status = JobStatus.COMPLETED
            job.completed_at = end_time
            job.total_tokens = total_tokens
            job.execution_time_seconds = execution_seconds
            job.estimated_cost = f"${estimated_cost:.4f}"
            db.commit()
            broadcast_update("job_update", job_id, status="completed")
            
            self.log_message(db, job_id, f"Job completed successfully. Tokens: {total_tokens}, Time: {execution_seconds}s, Cost: ${estimated_cost:.4f}", "success")
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()
            broadcast_update("job_update", job_id, status="failed")
            self.log_message(db, job_id, f"Job failed: {str(e)}", "error")
        finally:
            db.close()
    
    async def scanning_phase(self, db: Session, job: Job):
        """Phase 0: Scan codebase for context."""
        self.log_message(db, job.id, f"Scanning project: {job.project_path}")
        
        try:
            project_index = scan_project(job.project_path)
            job.project_index = project_index
            db.commit()
            
            file_count = project_index.get('indexed_files', 0)
            patterns = project_index.get('patterns', {})
            tech_stack = patterns.get('tech_stack', [])
            
            self.log_message(
                db, job.id, 
                f"Indexed {file_count} files. Tech stack: {', '.join(tech_stack) if tech_stack else 'unknown'}"
            )
        except Exception as e:
            self.log_message(db, job.id, f"Scanning failed (continuing without context): {e}", "warning")
            job.project_index = None
            db.commit()

    async def planning_phase(self, db: Session, job: Job) -> int:
        """Phase 1: Create execution plan. Returns tokens used."""
        self.log_message(db, job.id, "Creating execution plan...")
        
        result = await self.orchestrator.plan_job(job.description, project_index=job.project_index)
        tokens_used = result.get("tokens_used", 0)
        
        if result["success"]:
            job.plan = result["plan"]
            
            # Create tasks from plan
            order = 0
            for phase in result["plan"]["phases"]:
                for task_spec in phase["tasks"]:
                    task = Task(
                        job_id=job.id,
                        phase=phase["name"],
                        description=task_spec["description"],
                        ai_provider=self.orchestrator.route_task(phase["name"], job.ai_provider),
                        order=order
                    )
                    db.add(task)
                    order += 1
            
            db.commit()
            self.log_message(db, job.id, f"Plan created with {order} tasks ({tokens_used} tokens)")
            return tokens_used
        else:
            raise Exception(f"Planning failed: {result.get('error', 'Unknown error')}")
    
    async def building_phase(self, db: Session, job: Job) -> int:
        """Phase 2: Execute building tasks. Returns tokens used."""
        job.status = JobStatus.BUILDING
        db.commit()
        broadcast_update("job_update", job.id, status="building")
        
        phase_tokens = 0
        
        building_tasks = db.query(Task).filter(
            Task.job_id == job.id,
            Task.phase == "Building"
        ).order_by(Task.order).all()
        
        for task in building_tasks:
            self.log_message(db, job.id, f"Building: {task.description}", task_id=task.id)
            task.status = JobStatus.BUILDING
            task.started_at = datetime.utcnow()
            db.commit()
            
            # Execute the building task
            result = await self.orchestrator.execute_task(
                task.ai_provider,
                self._create_task_prompt(task, job),
                context={"job": job.description}
            )
            
            task_tokens = result.get("tokens_used", 0)
            phase_tokens += task_tokens
            
            if result["success"]:
                task.output = {"content": result["content"], "tokens": task_tokens}
                task.status = JobStatus.COMPLETED
                task.completed_at = datetime.utcnow()
                self.log_message(db, job.id, f"Task completed ({task_tokens} tokens)", task_id=task.id)
                # Extract and store generated code
                self._extract_and_store_code(db, job, task, result["content"])
            else:
                task.status = JobStatus.FAILED
                task.error_message = result.get("error", "Unknown error")
                task.completed_at = datetime.utcnow()
                self.log_message(db, job.id, f"Task failed: {task.error_message}", "ERROR", task_id=task.id)
            
            db.commit()
        
        return phase_tokens
    
    async def testing_phase(self, db: Session, job: Job) -> int:
        """Phase 3: Run tests. Returns tokens used."""
        job.status = JobStatus.TESTING
        db.commit()
        broadcast_update("job_update", job.id, status="testing")
        
        phase_tokens = 0
        
        self.log_message(db, job.id, "Running automated tests...")
        
        testing_tasks = db.query(Task).filter(
            Task.job_id == job.id,
            Task.phase == "Testing"
        ).all()
        
        for task in testing_tasks:
            self.log_message(db, job.id, f"Testing: {task.description}", task_id=task.id)
            task.status = JobStatus.TESTING
            task.started_at = datetime.utcnow()
            db.commit()
            
            # Execute testing
            result = await self.orchestrator.execute_task(
                task.ai_provider,
                self._create_task_prompt(task, job),
                context={"job": job.description, "build_output": self._get_build_outputs(db, job.id)}
            )
            
            task_tokens = result.get("tokens_used", 0)
            phase_tokens += task_tokens
            
            task.output = result
            task.status = JobStatus.COMPLETED if result["success"] else JobStatus.FAILED
            task.completed_at = datetime.utcnow()
            db.commit()
        
        return phase_tokens
    
    async def sandboxing_phase(self, db: Session, job: Job):
        """Phase 4: Deploy to sandbox"""
        job.status = JobStatus.SANDBOXING
        db.commit()
        broadcast_update("job_update", job.id, status="sandboxing")

        self.log_message(db, job.id, "Sandbox phase skipped (Docker-in-Docker config needed)")

    async def github_push_phase(self, db: Session, job: Job) -> bool:
        """
        Phase 5 (optional): Push generated files to GitHub.
        Only runs if GITHUB_AUTO_PUSH=true and GitHub is configured.
        Returns True if push succeeded, False otherwise.
        """
        # Check if auto-push is enabled
        auto_push = os.getenv("GITHUB_AUTO_PUSH", "false").lower() == "true"
        
        if not auto_push:
            self.log_message(db, job.id, "GitHub auto-push disabled (set GITHUB_AUTO_PUSH=true to enable)")
            return False
            
        if not GITHUB_AVAILABLE:
            self.log_message(db, job.id, "GitHub module not available", "warning")
            return False
            
        if not github_is_configured():
            self.log_message(db, job.id, "GitHub not configured (missing GITHUB_TOKEN or GITHUB_USERNAME)", "warning")
            return False
        
        # Get generated files for this job
        files = db.query(GeneratedFile).filter(GeneratedFile.job_id == job.id).all()
        if not files:
            self.log_message(db, job.id, "No generated files to push to GitHub")
            return False
        
        temp_dir = None
        try:
            # Create temp directory
            temp_dir = tempfile.mkdtemp(prefix=f"vdo_job_{job.id}_")
            self.log_message(db, job.id, f"Created temp directory for GitHub push")
            
            # Write generated files to temp directory
            for f in files:
                file_path = os.path.join(temp_dir, f.filename)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, 'w', encoding='utf-8') as fp:
                    fp.write(f.content)
            
            self.log_message(db, job.id, f"Wrote {len(files)} files to temp directory")
            
            # Generate repo name from job title
            repo_name = job.title.lower().replace(' ', '-')
            repo_name = ''.join(c for c in repo_name if c.isalnum() or c in '-_')[:50]
            repo_name = f"vdo-{repo_name}-{job.id}"
            
            # Create GitHub repo and push
            self.log_message(db, job.id, f"Creating GitHub repository: {repo_name}")
            
            result = create_project_repo(
                project_name=repo_name,
                project_path=temp_dir,
                description=f"Generated by VDO - {job.title}"
            )
            
            # Update job record
            job.github_repo_url = result['github_url']
            job.github_repo_name = result['name']
            job.github_pushed_at = datetime.utcnow()
            db.commit()
            
            self.log_message(db, job.id, f"Pushed to GitHub: {result['github_url']}", "success")
            broadcast_update("job_update", job.id, github_url=result['github_url'])
            
            return True
            
        except Exception as e:
            self.log_message(db, job.id, f"GitHub push failed: {str(e)}", "error")
            return False
            
        finally:
            # Cleanup temp directory
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _create_task_prompt(self, task: Task, job: Job) -> str:
        """Create a detailed prompt for the task"""
        return f"""Job: {job.title}
Description: {job.description}

Task Phase: {task.phase}
Task Description: {task.description}

Please complete this task and provide detailed output.
"""
    
    def _get_build_outputs(self, db: Session, job_id: int) -> Dict[str, Any]:
        """Get outputs from all completed building tasks"""
        tasks = db.query(Task).filter(
            Task.job_id == job_id,
            Task.phase == "Building",
            Task.status == JobStatus.COMPLETED
        ).all()
        
        return {
            "tasks": [
                {"description": t.description, "output": t.output}
                for t in tasks
            ]
        }

def enqueue_job(job_id: int):
    """Enqueue a job for processing"""
    return job_queue.enqueue(
        'worker.process_job_sync',
        job_id,
        job_timeout='1h'
    )

def process_job_sync(job_id: int):
    """Synchronous wrapper for async job processing"""
    import asyncio
    processor = JobProcessor()
    asyncio.run(processor.process_job(job_id))
