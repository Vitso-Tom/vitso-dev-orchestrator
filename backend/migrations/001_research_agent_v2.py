"""
Migration: Create Research Agent V2 Tables
Run this to add the new vendor_registry, vendor_facts, and fact_verification_log tables
"""

import sys
sys.path.insert(0, '/app')

from database import engine, SessionLocal
from sqlalchemy import text

# SQL statements - split properly
CREATE_STATEMENTS = [
    # Vendor Registry
    """CREATE TABLE IF NOT EXISTS vendor_registry (
        id SERIAL PRIMARY KEY,
        vendor_name VARCHAR(255) NOT NULL UNIQUE,
        vendor_aliases TEXT[],
        trust_center_url VARCHAR(500),
        security_page_url VARCHAR(500),
        privacy_page_url VARCHAR(500),
        pricing_page_url VARCHAR(500),
        status_page_url VARCHAR(500),
        docs_url VARCHAR(500),
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
    
    # Vendor Facts
    """CREATE TABLE IF NOT EXISTS vendor_facts (
        id SERIAL PRIMARY KEY,
        vendor_name VARCHAR(255) NOT NULL,
        product_name VARCHAR(255),
        vendor_registry_id INT REFERENCES vendor_registry(id),
        fact_category VARCHAR(50) NOT NULL,
        fact_key VARCHAR(100) NOT NULL,
        fact_value TEXT NOT NULL,
        fact_context TEXT,
        source_url VARCHAR(500),
        source_title VARCHAR(500),
        source_snippet TEXT,
        source_type VARCHAR(20) DEFAULT 'third_party',
        verification_status VARCHAR(20) DEFAULT 'pending',
        verified_by VARCHAR(50),
        verified_at TIMESTAMP,
        confidence_score FLOAT DEFAULT 0.5,
        ttl_days INT DEFAULT 30,
        expires_at TIMESTAMP,
        source_last_checked_at TIMESTAMP,
        source_last_status VARCHAR(20),
        recheck_count INT DEFAULT 0,
        next_recheck_at TIMESTAMP,
        recheck_priority INT DEFAULT 0,
        first_found_at TIMESTAMP DEFAULT NOW(),
        first_found_by_research_log_id INT,
        last_updated_at TIMESTAMP DEFAULT NOW(),
        last_updated_by_research_log_id INT,
        superseded_by_id INT REFERENCES vendor_facts(id),
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(vendor_name, product_name, fact_category, fact_key)
    )""",
    
    # Indexes for vendor_facts
    "CREATE INDEX IF NOT EXISTS idx_vendor_facts_vendor ON vendor_facts(vendor_name)",
    "CREATE INDEX IF NOT EXISTS idx_vendor_facts_expires ON vendor_facts(expires_at)",
    "CREATE INDEX IF NOT EXISTS idx_vendor_facts_verification ON vendor_facts(verification_status)",
    "CREATE INDEX IF NOT EXISTS idx_vendor_facts_category ON vendor_facts(fact_category, fact_key)",
    
    # Fact Verification Log
    """CREATE TABLE IF NOT EXISTS fact_verification_log (
        id SERIAL PRIMARY KEY,
        vendor_fact_id INT REFERENCES vendor_facts(id),
        action VARCHAR(50),
        previous_value TEXT,
        new_value TEXT,
        previous_status VARCHAR(20),
        new_status VARCHAR(20),
        method VARCHAR(50),
        source_url VARCHAR(500),
        source_response_status INT,
        performed_by VARCHAR(100),
        research_log_id INT,
        confidence_delta FLOAT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    )""",
    
    "CREATE INDEX IF NOT EXISTS idx_fact_verification_fact ON fact_verification_log(vendor_fact_id)",
]

# ALTER statements for research_logs - run separately with error handling
ALTER_STATEMENTS = [
    "ALTER TABLE research_logs ADD COLUMN IF NOT EXISTS facts_from_cache INT DEFAULT 0",
    "ALTER TABLE research_logs ADD COLUMN IF NOT EXISTS facts_from_recheck INT DEFAULT 0",
    "ALTER TABLE research_logs ADD COLUMN IF NOT EXISTS facts_from_research INT DEFAULT 0",
    "ALTER TABLE research_logs ADD COLUMN IF NOT EXISTS cache_hit_rate FLOAT",
    "ALTER TABLE research_logs ADD COLUMN IF NOT EXISTS research_mode VARCHAR(20) DEFAULT 'full'",
]


def run_migration():
    """Execute the migration"""
    print("Running Research Agent V2 migration...")
    
    with engine.connect() as conn:
        # Execute CREATE statements
        for statement in CREATE_STATEMENTS:
            try:
                conn.execute(text(statement))
                conn.commit()
                print(f"  ✓ Executed: {statement[:60]}...")
            except Exception as e:
                print(f"  Warning: {str(e)[:100]}")
                conn.rollback()
        
        # Execute ALTER statements (these may fail if columns exist)
        for statement in ALTER_STATEMENTS:
            try:
                conn.execute(text(statement))
                conn.commit()
                print(f"  ✓ Executed: {statement[:60]}...")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    print(f"  - Skipped (exists): {statement[:50]}...")
                else:
                    print(f"  Warning: {str(e)[:80]}")
                conn.rollback()
    
    print("Migration complete. Seeding vendor registry...")
    
    # Seed vendor registry
    from vendor_registry_seed import seed_vendor_registry
    session = SessionLocal()
    try:
        result = seed_vendor_registry(session)
        print(f"Vendor registry seeded: {result['added']} added, {result['updated']} updated")
    finally:
        session.close()
    
    print("Research Agent V2 setup complete!")


def verify_migration():
    """Verify the migration ran successfully"""
    with engine.connect() as conn:
        # Check tables exist
        tables = ['vendor_registry', 'vendor_facts', 'fact_verification_log']
        for table in tables:
            result = conn.execute(text(
                f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table}')"
            ))
            exists = result.scalar()
            print(f"  {table}: {'✓' if exists else '✗'}")
        
        # Check vendor registry has data
        result = conn.execute(text("SELECT COUNT(*) FROM vendor_registry"))
        count = result.scalar()
        print(f"  vendor_registry entries: {count}")


if __name__ == "__main__":
    run_migration()
    print("\nVerifying migration:")
    verify_migration()
