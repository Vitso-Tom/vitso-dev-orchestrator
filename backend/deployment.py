"""
VDO Local Deployment Module

Handles automatic deployment of generated code for demos and testing.
Features:
- Writes files to local filesystem
- Installs dependencies (Python/Node)
- Starts applications on available ports
- Health checks
- Process management
- Clean teardown
"""

import os
import signal
import shutil
import subprocess
import asyncio
import socket
from typing import Optional, Dict, List
from datetime import datetime
from sqlalchemy.orm import Session

from models import Job, GeneratedFile, Log
from database import SessionLocal


class DeploymentManager:
    """Manages local deployment of generated code"""
    
    def __init__(self, output_base_dir: str = "/mnt/demo-output"):
        self.output_base_dir = output_base_dir
        os.makedirs(output_base_dir, exist_ok=True)
    
    def log_message(self, db: Session, job_id: int, message: str, level: str = "INFO"):
        """Add a log entry for deployment"""
        log = Log(
            job_id=job_id,
            level=level,
            message=f"[DEPLOY] {message}"
        )
        db.add(log)
        db.commit()
        print(f"[Deploy {job_id}] {message}")
    
    async def deploy(self, job_id: int) -> bool:
        """
        Main deployment entry point.
        Returns True if deployment successful, False otherwise.
        
        For adopted projects:
        - Uses adopted_path as output_dir (no file copying)
        - Uses startup_command if provided
        """
        db = SessionLocal()
        
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                print(f"Job {job_id} not found")
                return False
            
            self.log_message(db, job_id, "Starting local deployment...")
            
            # ============================================================
            # ADOPTED PROJECT HANDLING
            # ============================================================
            if job.is_adopted:
                if not job.adopted_path or not os.path.exists(job.adopted_path):
                    raise Exception(f"Adopted path not found: {job.adopted_path}")
                
                output_dir = job.adopted_path
                job.deployment_output_dir = output_dir
                db.commit()
                
                self.log_message(db, job_id, f"📦 Adopted project: using existing codebase at {output_dir}")
                
                # Skip to dependency installation (step 3)
            else:
                # ============================================================
                # STANDARD VDO-BUILT PROJECT
                # ============================================================
                # 1. Create output directory
                output_dir = os.path.join(self.output_base_dir, f"job-{job_id}")
                if os.path.exists(output_dir):
                    shutil.rmtree(output_dir)
                os.makedirs(output_dir)
                
                job.deployment_output_dir = output_dir
                db.commit()
                
                self.log_message(db, job_id, f"Created directory: {output_dir}")
                
                # 2. Write all generated files (deduplicate - keep latest version of each)
                all_files = db.query(GeneratedFile).filter(
                    GeneratedFile.job_id == job_id
                ).order_by(GeneratedFile.id.asc()).all()
                
                if not all_files:
                    raise Exception("No files to deploy")
                
                # Deduplicate: later files overwrite earlier ones
                files_map = {}
                for f in all_files:
                    files_map[f.filename] = f
                
                files = list(files_map.values())
                
                for f in files:
                    file_path = os.path.join(output_dir, f.filename)
                    # Create subdirectories if needed (templates/, static/css/, etc.)
                    file_dir = os.path.dirname(file_path)
                    if file_dir and file_dir != output_dir:
                        os.makedirs(file_dir, exist_ok=True)
                    with open(file_path, 'w', encoding='utf-8') as fp:
                        fp.write(f.content)
                    print(f"[Deploy {job_id}] Wrote: {f.filename}")
                
                # List unique files written
                file_list = ', '.join(sorted([f.filename for f in files]))
                self.log_message(db, job_id, f"✅ Wrote {len(files)} files: {file_list}")
            
            # 3. Install dependencies
            await self._install_dependencies(db, job, output_dir)
            
            # 4. Assign port
            # For adopted projects, use the pre-configured port if set
            if job.is_adopted and job.deployment_port:
                port = job.deployment_port
                # Verify port is available
                import socket
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.bind(('', port))
                except OSError:
                    raise Exception(f"Configured port {port} is already in use")
                self.log_message(db, job_id, f"Using configured port: {port}")
            else:
                port = self._find_available_port()
                job.deployment_port = port
                db.commit()
                self.log_message(db, job_id, f"Assigned port: {port}")
            
            # 5. Detect entry point (or use startup_command for adopted projects)
            if job.is_adopted and job.startup_command:
                entry_point = job.startup_command  # Will be handled specially in _start_application
                self.log_message(db, job_id, f"Using custom startup command: {entry_point}")
            else:
                entry_point = self._detect_entry_point(output_dir)
                if not entry_point:
                    raise Exception("No entry point detected (app.py, server.py, main.py, index.html)")
                self.log_message(db, job_id, f"Detected entry point: {entry_point}")
            
            # 6. Start application
            proc_info = await self._start_application(db, job, output_dir, entry_point, port)
            
            job.deployment_pid = proc_info['pid']
            job.deployment_url = proc_info['url']
            job.deployment_type = proc_info['type']
            job.deployment_error = None
            db.commit()
            
            # 7. Health check
            self.log_message(db, job_id, "Running health check...")
            if await self._wait_for_health(job.deployment_url):
                self.log_message(
                    db, job_id,
                    f"🎉 Application ready at {job.deployment_url}",
                    "SUCCESS"
                )
                return True
            else:
                self.log_message(
                    db, job_id,
                    f"⚠️ Health check timeout. Application may still be starting: {job.deployment_url}",
                    "WARNING"
                )
                return True  # Consider success even if health check times out
        
        except Exception as e:
            if 'job' in locals() and job:
                job.deployment_error = str(e)
                db.commit()
            
            self.log_message(db, job_id, f"❌ Deployment failed: {e}", "ERROR")
            return False
        
        finally:
            db.close()
    
    async def _install_dependencies(self, db: Session, job: Job, output_dir: str):
        """Install Python or Node dependencies"""
        
        # Detect what frameworks are used by scanning Python files
        detected_packages = set()
        for root, dirs, files in os.walk(output_dir):
            for file in files:
                if file.endswith('.py'):
                    try:
                        with open(os.path.join(root, file), 'r') as f:
                            content = f.read()
                            if 'from flask import' in content or 'import flask' in content:
                                detected_packages.add('flask')
                            if 'from fastapi import' in content or 'import fastapi' in content:
                                detected_packages.add('fastapi')
                                detected_packages.add('uvicorn')
                            if 'import requests' in content or 'from requests' in content:
                                detected_packages.add('requests')
                    except:
                        pass
        
        # Python dependencies - try requirements.txt first
        req_file = os.path.join(output_dir, "requirements.txt")
        
        # FALLBACK: If no requirements.txt, look for any .txt file with deps
        if not os.path.exists(req_file):
            for file in os.listdir(output_dir):
                if file.endswith('.txt'):
                    file_path = os.path.join(output_dir, file)
                    try:
                        with open(file_path, 'r') as f:
                            content = f.read().lower()
                            if any(pkg in content for pkg in ['flask', 'fastapi', 'django', 'requests', '==']):
                                req_file = file_path
                                self.log_message(db, job.id, f"Found requirements in {file}")
                                break
                    except:
                        pass
        
        if os.path.exists(req_file):
            self.log_message(db, job.id, "📦 Installing Python dependencies from requirements.txt...")
            
            try:
                result = subprocess.run(
                    ["pip", "install", "-r", req_file, "--break-system-packages", "--quiet"],
                    cwd=output_dir,
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                
                if result.returncode == 0:
                    self.log_message(db, job.id, "✅ Python dependencies installed")
                else:
                    self.log_message(
                        db, job.id,
                        f"⚠️ pip warnings (non-fatal): {result.stderr[:200]}",
                        "WARNING"
                    )
            except subprocess.TimeoutExpired:
                self.log_message(db, job.id, "⚠️ pip install timeout - continuing anyway", "WARNING")
            except Exception as e:
                self.log_message(db, job.id, f"⚠️ pip install error: {e}", "WARNING")
        
        # Auto-install detected packages not in requirements.txt
        if detected_packages:
            packages_str = ' '.join(detected_packages)
            self.log_message(db, job.id, f"📦 Auto-installing detected packages: {packages_str}")
            
            try:
                result = subprocess.run(
                    ["pip", "install"] + list(detected_packages) + ["--break-system-packages", "--quiet"],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                if result.returncode == 0:
                    self.log_message(db, job.id, f"✅ Installed: {packages_str}")
            except Exception as e:
                self.log_message(db, job.id, f"⚠️ Auto-install warning: {e}", "WARNING")
        
        # Node dependencies
        package_json = os.path.join(output_dir, "package.json")
        if os.path.exists(package_json):
            self.log_message(db, job.id, "📦 Installing Node dependencies...")
            
            try:
                result = subprocess.run(
                    ["npm", "install", "--silent"],
                    cwd=output_dir,
                    capture_output=True,
                    text=True,
                    timeout=180  # 3 minute timeout
                )
                
                if result.returncode == 0:
                    self.log_message(db, job.id, "✅ Node dependencies installed")
                else:
                    raise Exception(f"npm install failed: {result.stderr}")
            except subprocess.TimeoutExpired:
                raise Exception("npm install timeout")
            except Exception as e:
                raise Exception(f"npm install error: {e}")
    
    def _detect_entry_point(self, output_dir: str) -> Optional[str]:
        """Detect application entry point"""
        
        # Python web apps (order matters - app.py is most common)
        for entry in ["app.py", "main.py", "server.py", "run.py"]:
            if os.path.exists(os.path.join(output_dir, entry)):
                return entry
        
        # Static HTML
        if os.path.exists(os.path.join(output_dir, "index.html")):
            return "index.html"
        
        # Node apps
        package_json_path = os.path.join(output_dir, "package.json")
        if os.path.exists(package_json_path):
            return "package.json"
        
        # FALLBACK: Try any .py file (for VDO's generic filenames)
        for file in os.listdir(output_dir):
            if file.endswith('.py'):
                return file
        
        return None
    
    async def _start_application(
        self,
        db: Session,
        job: Job,
        output_dir: str,
        entry_point: str,
        port: int
    ) -> Dict:
        """Start the application based on entry point type"""
        
        # ============================================================
        # ADOPTED PROJECT WITH CUSTOM STARTUP COMMAND
        # ============================================================
        if job.is_adopted and job.startup_command:
            # Parse startup command (e.g., "python arma_app.py" or "flask run")
            cmd_parts = job.startup_command.split()
            
            env = os.environ.copy()
            env['PORT'] = str(port)
            env['FLASK_APP'] = cmd_parts[-1] if cmd_parts[-1].endswith('.py') else 'app.py'
            env['FLASK_ENV'] = 'development'
            
            # If command includes flask, add host/port args
            if 'flask' in job.startup_command.lower():
                if '--host' not in job.startup_command:
                    cmd_parts.extend(['--host=0.0.0.0'])
                if '--port' not in job.startup_command:
                    cmd_parts.extend([f'--port={port}'])
            
            self.log_message(db, job.id, f"Starting with custom command: {' '.join(cmd_parts)}")
            
            proc = subprocess.Popen(
                cmd_parts,
                cwd=output_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            await asyncio.sleep(3)  # Give adopted apps more startup time
            
            if proc.poll() is not None:
                stderr = proc.stderr.read()
                raise Exception(f"Process died immediately: {stderr}")
            
            return {
                'pid': proc.pid,
                'url': f"http://localhost:{port}",
                'type': job.deployment_type or 'python'
            }
        
        # ============================================================
        # STANDARD ENTRY POINT DETECTION
        # ============================================================
        if entry_point.endswith('.py'):
            # Python web app (Flask/FastAPI)
            # Detect if it's a Flask app
            file_path = os.path.join(output_dir, entry_point)
            with open(file_path, 'r') as f:
                content = f.read()
            
            env = os.environ.copy()
            env['PORT'] = str(port)
            env['FLASK_APP'] = entry_point
            env['FLASK_ENV'] = 'development'
            
            # Use flask run for Flask apps, python3 for everything else
            if 'from flask import' in content or 'import flask' in content:
                cmd = ['flask', 'run', '--host=0.0.0.0', f'--port={port}']
            else:
                # Try to inject port - look for common patterns
                self._inject_port_to_python(output_dir, entry_point, port)
                cmd = ['python3', entry_point]
            
            proc = subprocess.Popen(
                cmd,
                cwd=output_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Give it a moment to start
            await asyncio.sleep(2)
            
            # Check if process died immediately
            if proc.poll() is not None:
                stderr = proc.stderr.read()
                raise Exception(f"Process died immediately: {stderr}")
            
            return {
                'pid': proc.pid,
                'url': f"http://localhost:{port}",
                'type': 'python'
            }
        
        elif entry_point == 'index.html':
            # Static HTML - use simple HTTP server
            proc = subprocess.Popen(
                ["python3", "-m", "http.server", str(port)],
                cwd=output_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            await asyncio.sleep(1)
            
            return {
                'pid': proc.pid,
                'url': f"http://localhost:{port}",
                'type': 'static'
            }
        
        elif entry_point == 'package.json':
            # Node app
            proc = subprocess.Popen(
                ["npm", "start"],
                cwd=output_dir,
                env={**os.environ, 'PORT': str(port)},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            await asyncio.sleep(3)  # Node apps need more time
            
            return {
                'pid': proc.pid,
                'url': f"http://localhost:{port}",
                'type': 'node'
            }
        
        raise Exception(f"Unknown entry point type: {entry_point}")
    
    def _inject_port_to_python(self, output_dir: str, entry_point: str, port: int):
        """Try to inject port number into Python app code"""
        import re
        
        file_path = os.path.join(output_dir, entry_point)
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            original_content = content
            
            # Pattern 1: app.run() with various arguments
            # Matches: app.run(), app.run(debug=True), app.run(host='0.0.0.0'), etc.
            app_run_pattern = r'(app\.run\s*\()([^)]*)(\))'
            
            def replace_app_run(match):
                prefix = match.group(1)
                args = match.group(2)
                suffix = match.group(3)
                
                # Parse existing arguments
                has_host = 'host=' in args or 'host =' in args
                has_port = 'port=' in args or 'port =' in args
                
                new_args = []
                
                # Add host if not present
                if not has_host:
                    new_args.append('host="0.0.0.0"')
                
                # Keep existing args but replace port
                if args.strip():
                    # Remove existing port argument
                    args_cleaned = re.sub(r',?\s*port\s*=\s*\d+', '', args)
                    args_cleaned = re.sub(r'port\s*=\s*\d+\s*,?', '', args_cleaned)
                    if args_cleaned.strip():
                        new_args.append(args_cleaned.strip())
                
                # Add our port
                new_args.append(f'port={port}')
                
                return f"{prefix}{', '.join(new_args)}{suffix}"
            
            content = re.sub(app_run_pattern, replace_app_run, content)
            
            # Pattern 2: Hardcoded port variables
            # Matches: port = 5000, PORT = 8000, etc.
            port_var_pattern = r'((?:port|PORT)\s*=\s*)\d+'
            content = re.sub(port_var_pattern, f'\\g<1>{port}', content)
            
            # Pattern 3: __main__ block with hardcoded port
            # Matches: if __name__ == '__main__': app.run(port=5000)
            main_port_pattern = r"(if\s+__name__\s*==\s*['\"]__main__['\"]\s*:.*?port\s*=\s*)\d+"
            content = re.sub(main_port_pattern, f'\\g<1>{port}', content, flags=re.DOTALL)
            
            if content != original_content:
                with open(file_path, 'w') as f:
                    f.write(content)
                print(f"[Deploy] Injected port {port} into {entry_point}")
            else:
                print(f"[Deploy] No port patterns found in {entry_point} - using env PORT")
        
        except Exception as e:
            # Non-fatal - port injection is best-effort
            print(f"[Deploy] Port injection failed (non-fatal): {e}")
    
    def _find_available_port(self, start_port: int = 5050, max_attempts: int = 50) -> int:
        """Find an available port starting from start_port"""
        for port in range(start_port, start_port + max_attempts):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('', port))
                    return port
            except OSError:
                continue
        
        raise Exception(f"No available ports found in range {start_port}-{start_port + max_attempts}")
    
    async def _wait_for_health(self, url: str, timeout: int = 30) -> bool:
        """Wait for application to become healthy"""
        import httpx
        
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    response = await client.get(url)
                    # Accept any response that's not a 5xx error
                    if response.status_code < 500:
                        return True
            except:
                pass
            
            await asyncio.sleep(1)
        
        return False
    
    async def stop(self, job_id: int) -> bool:
        """Stop deployment and cleanup files (preserves files for adopted projects)"""
        db = SessionLocal()
        
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return False
            
            self.log_message(db, job_id, "Stopping deployment...")
            
            # Kill process
            if job.deployment_pid:
                try:
                    os.kill(job.deployment_pid, signal.SIGTERM)
                    await asyncio.sleep(2)  # Wait for graceful shutdown
                    
                    # Force kill if still running
                    try:
                        os.kill(job.deployment_pid, 0)  # Check if still alive
                        os.kill(job.deployment_pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass  # Already dead
                    
                    self.log_message(db, job_id, f"Stopped process {job.deployment_pid}")
                
                except ProcessLookupError:
                    self.log_message(db, job_id, "Process already stopped")
                except Exception as e:
                    self.log_message(db, job_id, f"Error stopping process: {e}", "WARNING")
            
            # Remove files ONLY for VDO-built projects (not adopted)
            if job.is_adopted:
                self.log_message(db, job_id, f"📦 Adopted project: preserving files at {job.deployment_output_dir}")
            elif job.deployment_output_dir and os.path.exists(job.deployment_output_dir):
                shutil.rmtree(job.deployment_output_dir)
                self.log_message(db, job_id, f"Removed {job.deployment_output_dir}")
            
            # Clear deployment fields (but preserve adopted_path and port for adopted projects)
            job.deployment_pid = None
            job.deployment_url = None
            job.deployment_error = None
            
            if not job.is_adopted:
                # Only clear these for VDO-built projects
                job.deployment_port = None
                job.deployment_output_dir = None
                job.deployment_type = None
            
            db.commit()
            
            self.log_message(db, job_id, "✅ Deployment cleaned up", "SUCCESS")
            return True
        
        except Exception as e:
            self.log_message(db, job_id, f"Cleanup error: {e}", "ERROR")
            return False
        
        finally:
            db.close()
    
    def is_running(self, job_id: int) -> bool:
        """Check if deployment is currently running"""
        db = SessionLocal()
        
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job or not job.deployment_pid:
                return False
            
            try:
                os.kill(job.deployment_pid, 0)  # Signal 0 just checks if process exists
                return True
            except ProcessLookupError:
                return False
        
        finally:
            db.close()


# Global deployment manager instance
deployment_manager = DeploymentManager()
