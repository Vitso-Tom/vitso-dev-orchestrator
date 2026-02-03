"""
Migration: Add Adopted Projects Support

Adds columns for adopted project management and marks Job-53 (AITGP) as adopted.

Run with: python migrations/add_adopted_projects.py
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database import engine, SessionLocal
from models import Job


def run_migration():
    """Add adopted project columns and protect Job-53"""
    
    print("=" * 60)
    print("Migration: Add Adopted Projects Support")
    print("=" * 60)
    
    with engine.connect() as conn:
        # Check if columns already exist
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'jobs' AND column_name = 'is_adopted'
        """))
        
        if result.fetchone():
            print("✓ Column 'is_adopted' already exists")
        else:
            print("Adding column 'is_adopted'...")
            conn.execute(text("ALTER TABLE jobs ADD COLUMN is_adopted BOOLEAN DEFAULT FALSE"))
            conn.commit()
            print("✓ Added 'is_adopted' column")
        
        # Check adopted_path
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'jobs' AND column_name = 'adopted_path'
        """))
        
        if result.fetchone():
            print("✓ Column 'adopted_path' already exists")
        else:
            print("Adding column 'adopted_path'...")
            conn.execute(text("ALTER TABLE jobs ADD COLUMN adopted_path VARCHAR(500)"))
            conn.commit()
            print("✓ Added 'adopted_path' column")
        
        # Check startup_command
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'jobs' AND column_name = 'startup_command'
        """))
        
        if result.fetchone():
            print("✓ Column 'startup_command' already exists")
        else:
            print("Adding column 'startup_command'...")
            conn.execute(text("ALTER TABLE jobs ADD COLUMN startup_command VARCHAR(500)"))
            conn.commit()
            print("✓ Added 'startup_command' column")
    
    # Mark Job-53 as adopted (AITGP)
    print("\n" + "-" * 60)
    print("Protecting Job-53 (AITGP)...")
    print("-" * 60)
    
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == 53).first()
        
        if not job:
            print("⚠ Job-53 not found - skipping AITGP protection")
        elif job.is_adopted:
            print("✓ Job-53 already marked as adopted")
        else:
            job.is_adopted = True
            job.adopted_path = "/home/temlock/aitgp-app/job-53"
            job.startup_command = "python app.py"
            job.deployment_type = "python"
            job.deployment_port = 5000
            db.commit()
            print("✓ Job-53 marked as adopted")
            print(f"  - adopted_path: {job.adopted_path}")
            print(f"  - startup_command: {job.startup_command}")
            print(f"  - deployment_port: {job.deployment_port}")
    finally:
        db.close()
    
    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60)
    print("\nAdopted projects:")
    print("  - Cannot be rebuilt by VDO (code is external)")
    print("  - Can be deployed/stopped via VDO UI")
    print("  - Files preserved on stop (VDO doesn't own them)")


if __name__ == "__main__":
    run_migration()
