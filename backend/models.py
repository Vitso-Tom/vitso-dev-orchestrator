from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    PLANNING = "planning"
    BUILDING = "building"
    TESTING = "testing"
    SANDBOXING = "sandboxing"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"

class AIProvider(str, enum.Enum):
    CLAUDE = "claude"
    OPENAI = "openai"
    GEMINI = "gemini"
    AUTO = "auto"

class AnalysisStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(Enum(JobStatus), default=JobStatus.QUEUED)
    ai_provider = Column(Enum(AIProvider), default=AIProvider.AUTO)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # === Token & Time Tracking ===
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    estimated_cost = Column(String(20), nullable=True)  # e.g., "$0.0234"
    execution_time_seconds = Column(Integer, nullable=True)
    
    # === NEW: Rating System ===
    rating = Column(Integer, nullable=True)  # 1-5 stars
    is_reference = Column(Boolean, default=False)  # Mark as reference job
    rating_notes = Column(Text, nullable=True)  # Optional feedback
    
    # === NEW: GitHub Integration ===
    github_repo_url = Column(String(500), nullable=True)
    github_repo_name = Column(String(200), nullable=True)
    github_pushed_at = Column(DateTime, nullable=True)
    
    # === NEW: Codebase Scanner (Phase B1) ===
    project_path = Column(String(500), nullable=True)  # Path to scan
    project_index = Column(JSON, nullable=True)  # Scanner output
    
    # Relationships
    tasks = relationship("Task", back_populates="job", cascade="all, delete-orphan")
    logs = relationship("Log", back_populates="job", cascade="all, delete-orphan")
    generated_files = relationship("GeneratedFile", back_populates="job")
    agent_analyses = relationship("AgentAnalysis", back_populates="job", cascade="all, delete-orphan")
    
    # Store plan as JSON
    plan = Column(JSON, nullable=True)
    
    # Store results
    output_path = Column(String(500), nullable=True)
    sandbox_id = Column(String(100), nullable=True)

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    phase = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(Enum(JobStatus), default=JobStatus.QUEUED)
    ai_provider = Column(Enum(AIProvider), default=AIProvider.AUTO)
    order = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Relationships
    job = relationship("Job", back_populates="tasks")
    logs = relationship("Log", back_populates="task", cascade="all, delete-orphan")
    
    # Store task output
    output = Column(JSON, nullable=True)

class Log(Base):
    __tablename__ = "logs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    level = Column(String(20), default="INFO")
    message = Column(Text, nullable=False)
    log_metadata = Column(JSON, nullable=True)
    
    # Relationships
    job = relationship("Job", back_populates="logs")
    task = relationship("Task", back_populates="logs")

class GeneratedFile(Base):
    __tablename__ = "generated_files"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    
    filename = Column(String(500), nullable=False)
    filepath = Column(String(1000), nullable=False)
    content = Column(Text, nullable=False)
    language = Column(String(50), nullable=True)
    file_size = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    job = relationship("Job", back_populates="generated_files")


# === NEW: Agent Analysis Model ===
class AgentAnalysis(Base):
    __tablename__ = "agent_analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    
    agent_name = Column(String(100), nullable=False)  # security, code_review, optimization, documentation
    agent_type = Column(String(50), nullable=True)  # ai-workspace, internal, custom
    status = Column(Enum(AnalysisStatus), default=AnalysisStatus.PENDING)
    
    # Results
    findings = Column(JSON, nullable=True)  # List of findings
    recommendations = Column(JSON, nullable=True)  # List of recommendations
    severity_summary = Column(JSON, nullable=True)  # {critical: 0, high: 1, medium: 2, low: 3}
    
    # Timing
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    error_message = Column(Text, nullable=True)
    
    # Relationship
    job = relationship("Job", back_populates="agent_analyses")
