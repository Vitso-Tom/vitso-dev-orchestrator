"""
Research Agent V2 - Database Models
Persistent vendor facts with verification and caching
"""

from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime, 
    ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, timedelta
from models import Base  # Import Base from models, not database


class VendorRegistry(Base):
    """Known vendors with their authoritative URLs for direct fetching"""
    __tablename__ = 'vendor_registry'
    
    id = Column(Integer, primary_key=True)
    vendor_name = Column(String(255), nullable=False, unique=True)
    vendor_aliases = Column(ARRAY(String), default=[])  # ['Anysphere', 'Cursor AI']
    
    # Authoritative URLs
    trust_center_url = Column(String(500))
    security_page_url = Column(String(500))
    privacy_page_url = Column(String(500))
    pricing_page_url = Column(String(500))
    status_page_url = Column(String(500))
    docs_url = Column(String(500))
    
    # Metadata
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    facts = relationship("VendorFact", back_populates="vendor_registry_entry")
    
    # Authoritative URL attributes in canonical order for source classification.
    # This order MUST match source_classifier.py expectations.
    # Do NOT add status_page_url or other URLs without updating source_classifier tests.
    _URL_ATTRS = [
        ('trust_center_url', 'trust_center'),
        ('security_page_url', 'security_page'),
        ('privacy_page_url', 'privacy_page'),
        ('pricing_page_url', 'pricing_page'),
        ('docs_url', 'docs'),
    ]
    
    def get_all_urls(self) -> list:
        """
        Return all non-empty authoritative URLs for this vendor.
        
        Used by source_classifier.classify_source() to determine if a URL
        is from this vendor (source_type='vendor') or third-party.
        
        Returns:
            List of dicts with 'type' and 'url' keys, in canonical order:
            - trust_center
            - security_page
            - privacy_page
            - pricing_page
            - docs
            
        Example:
            [
                {"type": "trust_center", "url": "https://trust.vendor.com"},
                {"type": "security_page", "url": "https://vendor.com/security"},
            ]
        """
        urls = []
        for attr, url_type in self._URL_ATTRS:
            url = getattr(self, attr, None)
            if url:  # Skip None and empty strings
                urls.append({'type': url_type, 'url': url})
        return urls


class VendorFact(Base):
    """Persistent, verified vendor intelligence"""
    __tablename__ = 'vendor_facts'
    
    id = Column(Integer, primary_key=True)
    
    # Vendor identification
    vendor_name = Column(String(255), nullable=False, index=True)
    product_name = Column(String(255))
    vendor_registry_id = Column(Integer, ForeignKey('vendor_registry.id'))
    
    # Fact data
    fact_category = Column(String(50), nullable=False)  # certification, funding, security, etc.
    fact_key = Column(String(100), nullable=False)       # hipaa_baa, soc2_status, etc.
    fact_value = Column(Text, nullable=False)
    fact_context = Column(Text)                          # additional context/notes
    
    # Source tracking
    source_url = Column(String(500))
    source_title = Column(String(500))
    source_snippet = Column(Text)
    source_type = Column(String(20), default='third_party')  # vendor, third_party, both
    
    # Verification status
    verification_status = Column(String(20), default='pending', index=True)  
    # pending, verified, disputed, stale, superseded
    verified_by = Column(String(50))  # audit_agent, source_recheck, manual
    verified_at = Column(DateTime)
    
    # Confidence & freshness
    confidence_score = Column(Float, default=0.5)
    ttl_days = Column(Integer, default=30)
    expires_at = Column(DateTime, index=True)
    
    # Recheck tracking
    source_last_checked_at = Column(DateTime)
    source_last_status = Column(String(20))  # accessible, changed, 404, blocked, timeout
    recheck_count = Column(Integer, default=0)
    next_recheck_at = Column(DateTime)
    recheck_priority = Column(Integer, default=0)  # higher = recheck sooner
    
    # Audit trail
    first_found_at = Column(DateTime, default=func.now())
    first_found_by_research_log_id = Column(Integer)
    last_updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_updated_by_research_log_id = Column(Integer)
    superseded_by_id = Column(Integer, ForeignKey('vendor_facts.id'))
    
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    vendor_registry_entry = relationship("VendorRegistry", back_populates="facts")
    verification_logs = relationship("FactVerificationLog", back_populates="fact")
    superseded_by = relationship("VendorFact", remote_side=[id])
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('vendor_name', 'product_name', 'fact_category', 'fact_key', 
                        name='uq_vendor_fact'),
        Index('idx_vendor_facts_category', 'fact_category', 'fact_key'),
    )
    
    def is_fresh(self) -> bool:
        """Check if fact is still within TTL"""
        if not self.verified_at:
            return False
        if self.expires_at:
            return datetime.utcnow() < self.expires_at
        return (datetime.utcnow() - self.verified_at).days < self.ttl_days
    
    def is_verified(self) -> bool:
        """Check if fact has been verified"""
        return self.verification_status == 'verified'
    
    def needs_recheck(self) -> bool:
        """Check if fact should be rechecked"""
        if self.verification_status in ['disputed', 'stale']:
            return True
        if not self.is_fresh():
            return True
        if self.next_recheck_at and datetime.utcnow() > self.next_recheck_at:
            return True
        return False
    
    def set_verified(self, verified_by: str, research_log_id: int = None):
        """Mark fact as verified and update timestamps"""
        self.verification_status = 'verified'
        self.verified_by = verified_by
        self.verified_at = datetime.utcnow()
        self.expires_at = datetime.utcnow() + timedelta(days=self.ttl_days)
        if research_log_id:
            self.last_updated_by_research_log_id = research_log_id
    
    def set_stale(self):
        """Mark fact as stale, needs recheck"""
        self.verification_status = 'stale'
    
    def set_disputed(self, new_value: str = None):
        """Mark fact as disputed (conflicting information found)"""
        self.verification_status = 'disputed'
        if new_value:
            self.fact_context = f"Disputed. New value found: {new_value}"
    
    def record_recheck(self, status: str):
        """Record a source URL recheck attempt"""
        self.source_last_checked_at = datetime.utcnow()
        self.source_last_status = status
        self.recheck_count += 1
    
    def calculate_confidence(self) -> float:
        """Calculate confidence score based on multiple factors"""
        score = 0.5  # base
        
        # Source type bonus
        if self.source_type == 'vendor':
            score += 0.2  # authoritative
        elif self.source_type == 'both':
            score += 0.3  # corroborated
        
        # Verification bonus
        if self.verification_status == 'verified':
            score += 0.2
        elif self.verification_status == 'disputed':
            score -= 0.3
        elif self.verification_status == 'stale':
            score -= 0.1
        
        # Freshness penalty
        if self.verified_at:
            age_days = (datetime.utcnow() - self.verified_at).days
            if age_days > self.ttl_days:
                score -= 0.2 * min(2.0, age_days / self.ttl_days)
        
        # Recheck success bonus
        if self.recheck_count > 0 and self.source_last_status == 'accessible':
            score += 0.1
        
        return max(0.0, min(1.0, score))
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'vendor_name': self.vendor_name,
            'product_name': self.product_name,
            'fact_category': self.fact_category,
            'fact_key': self.fact_key,
            'fact_value': self.fact_value,
            'fact_context': self.fact_context,
            'source_url': self.source_url,
            'source_type': self.source_type,
            'verification_status': self.verification_status,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'confidence_score': self.confidence_score,
            'is_fresh': self.is_fresh(),
            'needs_recheck': self.needs_recheck(),
        }


class FactVerificationLog(Base):
    """Audit trail of all verification attempts"""
    __tablename__ = 'fact_verification_log'
    
    id = Column(Integer, primary_key=True)
    vendor_fact_id = Column(Integer, ForeignKey('vendor_facts.id'), index=True)
    
    # What happened
    action = Column(String(50))  # initial_extract, recheck, manual_verify, dispute, supersede
    previous_value = Column(Text)
    new_value = Column(Text)
    previous_status = Column(String(20))
    new_status = Column(String(20))
    
    # How it happened
    method = Column(String(50))  # web_search, direct_fetch, source_recheck, audit_agent, manual
    source_url = Column(String(500))
    source_response_status = Column(Integer)  # HTTP status code
    
    # Who/what did it
    performed_by = Column(String(100))  # research_agent, audit_agent, user:tom
    research_log_id = Column(Integer)
    
    # Result
    confidence_delta = Column(Float)
    notes = Column(Text)
    
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    fact = relationship("VendorFact", back_populates="verification_logs")
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'vendor_fact_id': self.vendor_fact_id,
            'action': self.action,
            'previous_value': self.previous_value,
            'new_value': self.new_value,
            'previous_status': self.previous_status,
            'new_status': self.new_status,
            'method': self.method,
            'performed_by': self.performed_by,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# Critical fields configuration - special handling for compliance
CRITICAL_FIELDS = {
    "certification": {
        "hipaa_baa": {"ttl_days": 14, "recheck_priority": 10},
        "soc2": {"ttl_days": 30, "recheck_priority": 8},
        "soc2_status": {"ttl_days": 30, "recheck_priority": 8},
        "iso27001": {"ttl_days": 30, "recheck_priority": 8},
        "hitrust": {"ttl_days": 30, "recheck_priority": 8},
        "fedramp": {"ttl_days": 30, "recheck_priority": 8},
        "pci_dss": {"ttl_days": 30, "recheck_priority": 8},
    },
    "data_handling": {
        "training_policy": {"ttl_days": 14, "recheck_priority": 9},
        "data_retention": {"ttl_days": 30, "recheck_priority": 7},
        "data_residency": {"ttl_days": 30, "recheck_priority": 6},
    },
    "security": {
        "breach_history": {"ttl_days": 7, "recheck_priority": 10},
        "security_incidents": {"ttl_days": 7, "recheck_priority": 10},
    }
}


def get_ttl_for_field(category: str, key: str) -> int:
    """Get TTL in days for a fact field"""
    if category in CRITICAL_FIELDS and key in CRITICAL_FIELDS[category]:
        return CRITICAL_FIELDS[category][key]["ttl_days"]
    return 30  # default


def get_priority_for_field(category: str, key: str) -> int:
    """Get recheck priority for a fact field"""
    if category in CRITICAL_FIELDS and key in CRITICAL_FIELDS[category]:
        return CRITICAL_FIELDS[category][key]["recheck_priority"]
    return 0  # default
