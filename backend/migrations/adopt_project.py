#!/usr/bin/env python3
"""
Utility script to adopt external projects into VDO.

Usage:
    python adopt_project.py --title "Project Name" --path /path/to/project --port 5010

Examples:
    # Adopt ARMA
    python adopt_project.py \
        --title "ARMA - Agent Runtime Maturity Assessment" \
        --description "Agent Runtime readiness assessment tool" \
        --path /home/temlock/agent-runtime-project/arma-app \
        --port 5010 \
        --startup "python arma_app.py"
    
    # Adopt AITGP
    python adopt_project.py \
        --title "AITGP - AI Third-Party Governance Platform" \
        --description "AI vendor security assessment platform" \
        --path /home/temlock/aitgp-app/job-53 \
        --port 5000 \
        --startup "python app.py"
"""

import argparse
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import Job, Log, JobStatus


def adopt_project(
    title: str,
    description: str,
    project_path: str,
    deployment_port: int,
    startup_command: str = None,
    deployment_type: str = "python"
):
    """Adopt an external project into VDO"""
    
    # Validate path exists
    if not os.path.exists(project_path):
        print(f"❌ Error: Path does not exist: {project_path}")
        sys.exit(1)
    
    db = SessionLocal()
    
    try:
        # Check for existing adoption
        existing = db.query(Job).filter(
            Job.is_adopted == True,
            Job.adopted_path == project_path
        ).first()
        
        if existing:
            print(f"⚠ Project already adopted as Job {existing.id}: {existing.title}")
            print(f"  Use the VDO UI to manage this deployment.")
            sys.exit(0)
        
        # Create job record
        job = Job(
            title=title,
            description=description,
            status=JobStatus.COMPLETED,
            is_adopted=True,
            adopted_path=project_path,
            project_path=project_path,
            deployment_type=deployment_type,
            deployment_port=deployment_port,
            startup_command=startup_command,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        
        # Add log
        log = Log(
            job_id=job.id,
            level="INFO",
            message=f"[ADOPT] Project adopted via CLI from {project_path}"
        )
        db.add(log)
        db.commit()
        
        print("=" * 60)
        print("✅ Project adopted successfully!")
        print("=" * 60)
        print(f"  Job ID:          {job.id}")
        print(f"  Title:           {job.title}")
        print(f"  Path:            {job.adopted_path}")
        print(f"  Port:            {job.deployment_port}")
        print(f"  Startup Command: {job.startup_command or '(auto-detect)'}")
        print("=" * 60)
        print("\nYou can now deploy this project from the VDO UI.")
        print(f"Or via API: POST http://localhost:8000/api/jobs/{job.id}/deploy")
        
        return job.id
        
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Adopt an external project into VDO",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument("--title", required=True, help="Project title")
    parser.add_argument("--description", default="", help="Project description")
    parser.add_argument("--path", required=True, help="Path to project directory")
    parser.add_argument("--port", type=int, required=True, help="Deployment port")
    parser.add_argument("--startup", help="Startup command (e.g., 'python app.py')")
    parser.add_argument("--type", default="python", help="Deployment type (python/node/static)")
    
    args = parser.parse_args()
    
    adopt_project(
        title=args.title,
        description=args.description,
        project_path=args.path,
        deployment_port=args.port,
        startup_command=args.startup,
        deployment_type=args.type
    )
