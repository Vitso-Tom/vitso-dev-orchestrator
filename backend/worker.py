from rq import Queue, Worker
from redis import Redis
import os
import sys
import tempfile
import shutil
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from models import Job, Task, Log, JobStatus, AIProvider, GeneratedFile
from orchestrator import AIOrchestrator
from database import SessionLocal
import docker
import json
from datetime import datetime
from file_extractor import extract_files_from_response

# Add vdo_github to path
sys.path.insert(0, '/')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from vdo_github import create_project_repo, is_configured as github_is_configured
    GITHUB_AVAILABLE = True
except ImportError as e:
    print(f"vdo_github import failed: {e}")
    GITHUB_AVAILABLE = False
    github_is_configured = lambda: False

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
    """Processes jobs through the complete pipeline"""
    
    def __init__(self):
        self.orchestrator = AIOrchestrator()
    
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
        broadcast_update("log_update", job_id)
    
    def _extract_and_store_code(self, db: Session, job: Job, task: Task, content: str) -> Dict[str, str]:
        """
        Extract code blocks from AI response and store as files.
        Returns dict of {filename: content} for use as context in subsequent tasks.
        """
        files = extract_files_from_response(content, job.id, task.id)
        
        files_saved = 0
        extracted_files = {}
        
        for f in files:
            filename = f['filename']
            filepath = f"job_{job.id}/{filename}"
            
            generated_file = GeneratedFile(
                job_id=job.id,
                task_id=task.id,
                filename=filename,
                filepath=filepath,
                content=f['content'],
                language=f['language'],
                file_size=len(f['content'])
            )
            db.add(generated_file)
            files_saved += 1
            extracted_files[filename] = f['content']
            print(f"[Job {job.id}] Extracted: {filename}")
        
        if files_saved > 0:
            db.commit()
            print(f"[Job {job.id}] Saved {files_saved} files from task {task.id}")
        else:
            print(f"[Job {job.id}] WARNING: No code extracted from task {task.id} (content length: {len(content)})")
        
        return extracted_files
    
    def _get_previous_files(self, db: Session, job_id: int) -> Dict[str, str]:
        """Get all files generated so far for this job"""
        files = db.query(GeneratedFile).filter(GeneratedFile.job_id == job_id).all()
        return {f.filename: f.content for f in files}
    
    async def process_job(self, job_id: int):
        """Main job processing pipeline"""
        db = SessionLocal()
        
        total_tokens = 0
        
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                print(f"Job {job_id} not found")
                return
            
            # ============================================================
            # GUARD: Prevent rebuilding adopted projects
            # ============================================================
            if job.is_adopted:
                self.log_message(
                    db, job_id,
                    f"⛔ BLOCKED: Cannot rebuild adopted project. Code is managed externally at {job.adopted_path}",
                    "ERROR"
                )
                job.status = JobStatus.FAILED
                job.error_message = "Cannot rebuild adopted project - code is managed externally"
                job.completed_at = datetime.utcnow()
                db.commit()
                broadcast_update("job_update", job_id, status="failed")
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
            
            # Phase 1: Planning (now includes file manifest)
            planning_tokens = await self.planning_phase(db, job)
            total_tokens += planning_tokens
            
            # Phase 2: Building (with file manifest and context passing)
            building_tokens = await self.building_phase(db, job)
            total_tokens += building_tokens
            
            # Phase 3: Testing
            testing_tokens = await self.testing_phase(db, job)
            total_tokens += testing_tokens
            
            # Phase 4: Sandboxing
            await self.sandboxing_phase(db, job)
            
            # Phase 5: GitHub Push
            await self.github_push_phase(db, job)
            
            # Calculate metrics
            end_time = datetime.utcnow()
            execution_seconds = int((end_time - start_time).total_seconds())
            estimated_cost = (total_tokens / 1000) * 0.01
            
            job.status = JobStatus.COMPLETED
            job.completed_at = end_time
            job.total_tokens = total_tokens
            job.execution_time_seconds = execution_seconds
            job.estimated_cost = f"${estimated_cost:.4f}"
            db.commit()
            broadcast_update("job_update", job_id, status="completed")
            
            self.log_message(db, job_id, f"Job completed. Tokens: {total_tokens}, Time: {execution_seconds}s, Cost: ${estimated_cost:.4f}", "success")
            
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
            self.log_message(db, job.id, f"Scanning failed: {e}", "warning")
            job.project_index = None
            db.commit()

    async def planning_phase(self, db: Session, job: Job) -> int:
        """Phase 1: Create execution plan with file manifest."""
        self.log_message(db, job.id, "Creating execution plan with file manifest...")
        
        result = await self.orchestrator.plan_job(job.description, project_index=job.project_index)
        tokens_used = result.get("tokens_used", 0)
        
        if result["success"]:
            plan = result["plan"]
            job.plan = plan
            
            # Log the file manifest
            file_manifest = plan.get("file_manifest", {})
            if file_manifest:
                files_list = ", ".join(file_manifest.keys())
                self.log_message(db, job.id, f"File manifest: {files_list}")
            
            # Create tasks from plan
            order = 0
            for phase in plan["phases"]:
                for task_spec in phase["tasks"]:
                    task = Task(
                        job_id=job.id,
                        phase=phase["name"],
                        description=task_spec["description"],
                        ai_provider=self.orchestrator.route_task(phase["name"], job.ai_provider),
                        order=order
                    )
                    # Store which files this task should create (if specified)
                    if "files" in task_spec:
                        task.output = {"target_files": task_spec["files"]}
                    db.add(task)
                    order += 1
            
            db.commit()
            self.log_message(db, job.id, f"Plan created with {order} tasks ({tokens_used} tokens)")
            return tokens_used
        else:
            raise Exception(f"Planning failed: {result.get('error', 'Unknown error')}")
    
    async def building_phase(self, db: Session, job: Job) -> int:
        """Phase 2: Execute building tasks with context passing."""
        job.status = JobStatus.BUILDING
        db.commit()
        broadcast_update("job_update", job.id, status="building")
        
        phase_tokens = 0
        
        # Get file manifest from plan
        file_manifest = job.plan.get("file_manifest", {}) if job.plan else {}
        
        building_tasks = db.query(Task).filter(
        Task.job_id == job.id,
        ~Task.phase.in_(['Planning', 'Testing', 'Sandboxing'])
        ).order_by(Task.order).all()
        
        for task in building_tasks:
            self.log_message(db, job.id, f"Building: {task.description}", task_id=task.id)
            task.status = JobStatus.BUILDING
            task.started_at = datetime.utcnow()
            db.commit()
            
            # Get files this task should create
            task_files = []
            if task.output and isinstance(task.output, dict):
                task_files = task.output.get("target_files", [])
            
            # Get previously generated files for context
            previous_files = self._get_previous_files(db, job.id)
            
            # Create enhanced prompt with file manifest and context
            prompt = self.orchestrator.create_building_task_prompt(
                task_description=task.description,
                job_title=job.title,
                job_description=job.description,
                file_manifest=file_manifest,
                task_files=task_files,
                previous_files=previous_files if previous_files else None
            )
            
            # Execute the building task
            result = await self.orchestrator.execute_task(
                task.ai_provider,
                prompt,
                context={"job": job.description}
            )
            
            task_tokens = result.get("tokens_used", 0)
            phase_tokens += task_tokens
            
            if result["success"]:
                # Extract and store files, get back the extracted content
                extracted = self._extract_and_store_code(db, job, task, result["content"])
                
                task.output = {
                    "content": result["content"],
                    "tokens": task_tokens,
                    "files_created": list(extracted.keys())
                }
                task.status = JobStatus.COMPLETED
                task.completed_at = datetime.utcnow()
                
                files_list = ", ".join(extracted.keys()) if extracted else "none"
                self.log_message(db, job.id, f"Task completed: {files_list} ({task_tokens} tokens)", task_id=task.id)
            else:
                task.status = JobStatus.FAILED
                task.error_message = result.get("error", "Unknown error")
                task.completed_at = datetime.utcnow()
                self.log_message(db, job.id, f"Task failed: {task.error_message}", "ERROR", task_id=task.id)
            
            db.commit()
        
        return phase_tokens
    
    async def testing_phase(self, db: Session, job: Job) -> int:
        """Phase 3: Actual syntax validation and linting."""
        import subprocess
        import tempfile
        import os as os_module
        
        job.status = JobStatus.TESTING
        db.commit()
        broadcast_update("job_update", job.id, status="testing")
        
        self.log_message(db, job.id, "Running syntax validation...")
        
        # Get all generated files
        files = self._get_previous_files(db, job.id)
        
        errors = []
        warnings = []
        
        for filename, content in files.items():
            # Python syntax check
            if filename.endswith('.py'):
                try:
                    compile(content, filename, 'exec')
                    self.log_message(db, job.id, f"✓ {filename}: Python syntax OK")
                except SyntaxError as e:
                    error_msg = f"{filename}: Line {e.lineno}: {e.msg}"
                    errors.append(error_msg)
                    self.log_message(db, job.id, f"✗ {error_msg}", "ERROR")
            
            # HTML basic validation (check for unclosed tags is complex, just check it parses)
            elif filename.endswith('.html'):
                # Basic checks
                if '<html' in content and '</html>' in content:
                    self.log_message(db, job.id, f"✓ {filename}: HTML structure OK")
                else:
                    warnings.append(f"{filename}: Missing <html> or </html> tags")
            
            # JavaScript basic check (look for obvious issues)
            elif filename.endswith('.js'):
                # Check for common issues
                issues = []
                if content.count('{') != content.count('}'):
                    issues.append("Mismatched braces")
                if content.count('(') != content.count(')'):
                    issues.append("Mismatched parentheses")
                
                if issues:
                    warnings.append(f"{filename}: {', '.join(issues)}")
                    self.log_message(db, job.id, f"⚠ {filename}: {', '.join(issues)}", "WARNING")
                else:
                    self.log_message(db, job.id, f"✓ {filename}: JavaScript structure OK")
            
            # CSS basic check
            elif filename.endswith('.css'):
                if content.count('{') != content.count('}'):
                    warnings.append(f"{filename}: Mismatched braces")
                    self.log_message(db, job.id, f"⚠ {filename}: Mismatched braces", "WARNING")
                else:
                    self.log_message(db, job.id, f"✓ {filename}: CSS structure OK")
        
        # Summary
        if errors:
            self.log_message(db, job.id, f"❌ Validation found {len(errors)} errors", "ERROR")
        elif warnings:
            self.log_message(db, job.id, f"⚠️ Validation passed with {len(warnings)} warnings", "WARNING")
        else:
            self.log_message(db, job.id, f"✅ All {len(files)} files passed validation", "SUCCESS")
        
        # Mark testing tasks as complete (we did real validation, not AI review)
        testing_tasks = db.query(Task).filter(
            Task.job_id == job.id,
            Task.phase == "Testing"
        ).all()
        
        for task in testing_tasks:
            task.status = JobStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            task.output = {
                "validation": "syntax_check",
                "errors": errors,
                "warnings": warnings
            }
            db.commit()
        
        return 0  # No tokens used - we did real validation, not AI calls
    
    async def sandboxing_phase(self, db: Session, job: Job):
        """Phase 4: Deploy to sandbox"""
        job.status = JobStatus.SANDBOXING
        db.commit()
        broadcast_update("job_update", job.id, status="sandboxing")
        self.log_message(db, job.id, "Sandbox phase complete (use Deploy button for local deployment)")

    async def github_push_phase(self, db: Session, job: Job) -> bool:
        """Phase 5: Push generated files to GitHub."""
        auto_push = os.getenv("GITHUB_AUTO_PUSH", "false").lower() == "true"
        
        if not auto_push:
            self.log_message(db, job.id, "GitHub auto-push disabled")
            return False
            
        if not GITHUB_AVAILABLE or not github_is_configured():
            self.log_message(db, job.id, "GitHub not configured", "warning")
            return False
        
        files = db.query(GeneratedFile).filter(GeneratedFile.job_id == job.id).all()
        if not files:
            self.log_message(db, job.id, "No generated files to push")
            return False
        
        temp_dir = None
        try:
            temp_dir = tempfile.mkdtemp(prefix=f"vdo_job_{job.id}_")
            
            for f in files:
                file_path = os.path.join(temp_dir, f.filename)
                os.makedirs(os.path.dirname(file_path) if os.path.dirname(file_path) else temp_dir, exist_ok=True)
                with open(file_path, 'w', encoding='utf-8') as fp:
                    fp.write(f.content)
            
            self.log_message(db, job.id, f"Wrote {len(files)} files to temp directory")
            
            repo_name = job.title.lower().replace(' ', '-')
            repo_name = ''.join(c for c in repo_name if c.isalnum() or c in '-_')[:50]
            repo_name = f"vdo-{repo_name}-{job.id}"
            
            self.log_message(db, job.id, f"Creating GitHub repository: {repo_name}")
            
            result = create_project_repo(
                project_name=repo_name,
                project_path=temp_dir,
                description=f"Generated by VDO - {job.title}"
            )
            
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
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)


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
