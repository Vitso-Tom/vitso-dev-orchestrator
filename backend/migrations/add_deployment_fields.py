"""
Database migration: Add local deployment fields to Job model

Run this migration to add deployment tracking fields:
    cd backend
    python migrations/add_deployment_fields.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine, text
from database import engine, SessionLocal

def migrate():
    """Add deployment fields to jobs table"""
    print("🔄 Adding deployment fields to jobs table...")
    
    db = SessionLocal()
    
    try:
        # Add columns using raw SQL (SQLite/PostgreSQL compatible)
        with engine.connect() as conn:
            try:
                # Try to add each column (will fail silently if exists)
                conn.execute(text("ALTER TABLE jobs ADD COLUMN deploy_local BOOLEAN DEFAULT FALSE"))
                conn.commit()
                print("   ✅ Added deploy_local")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e).lower():
                    print("   ℹ️  deploy_local already exists")
                else:
                    raise
            
            try:
                conn.execute(text("ALTER TABLE jobs ADD COLUMN deployment_pid INTEGER"))
                conn.commit()
                print("   ✅ Added deployment_pid")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e).lower():
                    print("   ℹ️  deployment_pid already exists")
                else:
                    raise
            
            try:
                conn.execute(text("ALTER TABLE jobs ADD COLUMN deployment_port INTEGER"))
                conn.commit()
                print("   ✅ Added deployment_port")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e).lower():
                    print("   ℹ️  deployment_port already exists")
                else:
                    raise
            
            try:
                conn.execute(text("ALTER TABLE jobs ADD COLUMN deployment_url VARCHAR(200)"))
                conn.commit()
                print("   ✅ Added deployment_url")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e).lower():
                    print("   ℹ️  deployment_url already exists")
                else:
                    raise
            
            try:
                conn.execute(text("ALTER TABLE jobs ADD COLUMN deployment_output_dir VARCHAR(500)"))
                conn.commit()
                print("   ✅ Added deployment_output_dir")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e).lower():
                    print("   ℹ️  deployment_output_dir already exists")
                else:
                    raise
            
            try:
                conn.execute(text("ALTER TABLE jobs ADD COLUMN deployment_type VARCHAR(50)"))
                conn.commit()
                print("   ✅ Added deployment_type")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e).lower():
                    print("   ℹ️  deployment_type already exists")
                else:
                    raise
            
            try:
                conn.execute(text("ALTER TABLE jobs ADD COLUMN deployment_error TEXT"))
                conn.commit()
                print("   ✅ Added deployment_error")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e).lower():
                    print("   ℹ️  deployment_error already exists")
                else:
                    raise
        
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("VDO Database Migration: Add Deployment Fields")
    print("=" * 60)
    migrate()
    print("=" * 60)
