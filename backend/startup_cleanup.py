"""Cleanup stale deployment state on startup"""
import os
from database import SessionLocal
from models import Job


def cleanup_stale_deployments():
    """Reset all deployment state - called on backend startup"""
    db = SessionLocal()
    try:
        # Kill any orphan processes
        os.system("pkill -f 'flask run' 2>/dev/null || true")
        os.system("pkill -f 'http.server' 2>/dev/null || true")
        
        # Clear deployment state from all jobs
        jobs_with_deployments = db.query(Job).filter(
            (Job.deployment_pid.isnot(None)) | (Job.deploy_local == True)
        ).all()
        
        for job in jobs_with_deployments:
            job.deployment_pid = None
            job.deployment_url = None
            job.deployment_port = None
            job.deployment_output_dir = None
            job.deployment_error = None
            job.deployment_type = None
            job.deploy_local = False
        
        db.commit()
        print(f"[Startup] Cleared {len(jobs_with_deployments)} stale deployments")
    except Exception as e:
        print(f"[Startup] Cleanup warning: {e}")
    finally:
        db.close()
