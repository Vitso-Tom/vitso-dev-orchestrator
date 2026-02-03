from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import os
from dotenv import load_dotenv

load_dotenv()

# Database URL from environment variable (PostgreSQL required)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set in environment - check .env file")

# Create engine (PostgreSQL)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Create session maker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """
    Dependency for getting database sessions
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    Initialize database tables and seed vendor registry if empty.
    
    This function is idempotent:
    - Tables are created only if they don't exist (create_all behavior)
    - Vendor registry is seeded only if the table is empty
    """
    from models import Base
    # Import research_models so its tables are registered with Base
    import research_models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    
    # Seed vendor registry if empty (idempotent)
    _seed_vendor_registry_if_empty()


def _seed_vendor_registry_if_empty():
    """
    Seed the VendorRegistry table if it's empty.
    
    This is idempotent - it only seeds if the table has zero rows.
    Called automatically by init_db() at startup.
    """
    from research_models_v2 import VendorRegistry
    from vendor_registry_seed import seed_vendor_registry
    
    session = SessionLocal()
    try:
        # Check if registry is empty
        count = session.query(VendorRegistry).count()
        if count == 0:
            result = seed_vendor_registry(session)
            print(f"✓ Vendor registry seeded: {result['added']} vendors added")
        # If rows exist, do nothing (idempotent)
    finally:
        session.close()
