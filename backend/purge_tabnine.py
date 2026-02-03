#!/usr/bin/env python3
"""Purge Tabnine facts from database for fresh research run."""

import sys
sys.path.insert(0, '.')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from research_models_v2 import VendorFact, FactVerificationLog
import os

# Use same database as the app
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./vitso_dev_orchestrator.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
Session = sessionmaker(bind=engine)
db = Session()

print("=" * 50)
print("PURGING TABNINE FROM DATABASE")
print("=" * 50)

# Count before
tabnine_facts = db.query(VendorFact).filter(VendorFact.vendor_name.ilike('%tabnine%')).all()
print(f"\nTabnine facts found: {len(tabnine_facts)}")

if tabnine_facts:
    # Get fact IDs for log cleanup
    fact_ids = [f.id for f in tabnine_facts]
    
    # Delete verification logs first (foreign key constraint)
    logs_deleted = db.query(FactVerificationLog).filter(
        FactVerificationLog.vendor_fact_id.in_(fact_ids)
    ).delete(synchronize_session=False)
    print(f"Verification logs deleted: {logs_deleted}")
    
    # Delete facts
    facts_deleted = db.query(VendorFact).filter(VendorFact.vendor_name.ilike('%tabnine%')).delete(synchronize_session=False)
    print(f"Facts deleted: {facts_deleted}")
    
    db.commit()
    print("\n✅ Tabnine purged successfully!")
else:
    print("\n⚠️  No Tabnine facts found in database")

db.close()
print("\nReady for fresh research run.")
