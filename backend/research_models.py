"""
Research Models for AI Governance Platform
SQLAlchemy models for research audit trail
"""

from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum

# Import Base from your models
from models import Base


class ResearchStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REVIEWED = "reviewed"


class FactStatus(str, Enum):
    EXTRACTED = "extracted"
    DROPPED = "dropped"
    CONFLICTING = "conflicting"
    UNVERIFIED = "unverified"


class ResearchLog(Base):
    """Main research log entry - one per vendor research session"""
    __tablename__ = "research_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, nullable=True)  # Links to assessment if used
    vendor_name = Column(String(255), nullable=False, index=True)
    product_name = Column(String(255), nullable=True)
    research_timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Confidence scoring
    confidence_score = Column(Float, nullable=True)  # 0.0 to 1.0
    confidence_level = Column(String(20), nullable=True)  # low/medium/high
    
    # Source metrics
    sources_consulted = Column(Integer, default=0)
    sources_cited = Column(Integer, default=0)
    facts_extracted = Column(Integer, default=0)
    facts_dropped = Column(Integer, default=0)
    gaps_identified = Column(JSONB, nullable=True)
    
    # Synthesis metadata
    synthesis_model = Column(String(100), nullable=True)
    synthesis_notes = Column(Text, nullable=True)
    
    # Final outputs
    synthesized_report = Column(Text, nullable=True)
    structured_data = Column(JSONB, nullable=True)
    
    # Status
    status = Column(String(20), default="completed")
    reviewed_by = Column(String(255), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewer_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    queries = relationship("ResearchQuery", back_populates="research_log", cascade="all, delete-orphan")
    facts = relationship("ResearchFact", back_populates="research_log", cascade="all, delete-orphan")


class ResearchQuery(Base):
    """Individual queries executed during research"""
    __tablename__ = "research_queries"
    
    id = Column(Integer, primary_key=True, index=True)
    research_log_id = Column(Integer, ForeignKey("research_logs.id", ondelete="CASCADE"), nullable=False)
    query_sequence = Column(Integer, nullable=True)
    
    # Query details
    query_type = Column(String(50), nullable=True)  # web_search, web_fetch, api_call
    query_text = Column(Text, nullable=False)
    query_purpose = Column(Text, nullable=True)
    
    # Results
    results_count = Column(Integer, default=0)
    results_raw = Column(JSONB, nullable=True)
    
    # Timing
    executed_at = Column(DateTime, default=datetime.utcnow)
    duration_ms = Column(Integer, nullable=True)
    
    # Relationship
    research_log = relationship("ResearchLog", back_populates="queries")
    facts = relationship("ResearchFact", back_populates="query")


class ResearchFact(Base):
    """Facts extracted from research - granular tracking"""
    __tablename__ = "research_facts"
    
    id = Column(Integer, primary_key=True, index=True)
    research_log_id = Column(Integer, ForeignKey("research_logs.id", ondelete="CASCADE"), nullable=False)
    research_query_id = Column(Integer, ForeignKey("research_queries.id", ondelete="SET NULL"), nullable=True)
    
    # Fact details
    fact_category = Column(String(100), nullable=True, index=True)
    fact_key = Column(String(255), nullable=True)
    fact_value = Column(Text, nullable=True)
    fact_context = Column(Text, nullable=True)
    
    # Source attribution
    source_url = Column(Text, nullable=True)
    source_title = Column(Text, nullable=True)
    source_date = Column(DateTime, nullable=True)
    source_snippet = Column(Text, nullable=True)
    
    # Status - key field for the a16z fix
    status = Column(String(20), default="extracted", index=True)  # extracted/dropped/conflicting
    drop_reason = Column(Text, nullable=True)  # Why it was dropped
    
    # Confidence
    fact_confidence = Column(Float, nullable=True)
    
    # Verification
    verified = Column(Boolean, default=False)
    verified_by = Column(String(255), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    research_log = relationship("ResearchLog", back_populates="facts")
    query = relationship("ResearchQuery", back_populates="facts")
