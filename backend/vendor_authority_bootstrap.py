"""
Vendor Authority Bootstrap - Promotion and persistence for candidate URLs

This module handles:
1. Storing candidate vendor URLs pending review
2. Promoting confirmed candidates to VendorRegistry
3. Tracking the bootstrap workflow state

WORKFLOW:
1. Research discovers URL → candidate_authority.analyze_candidate()
2. If is_candidate=True → create PendingVendorAuthority record
3. Admin reviews and confirms/rejects
4. If confirmed → promote_candidate() creates VendorRegistry entry
5. Future classifications return source_type="vendor"

DESIGN PRINCIPLES:
1. Candidates NEVER affect source_type until promoted
2. All promotions require explicit confirmation
3. Audit trail maintained for all state changes
4. Testable without database (using stubs)
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import Column, Integer, String, Float, DateTime, Enum as SQLEnum
from sqlalchemy.sql import func

# Import from existing modules
try:
    from models import Base
    from research_models_v2 import VendorRegistry
    HAS_SQLALCHEMY = True
except ImportError:
    # For offline testing without full SQLAlchemy setup
    HAS_SQLALCHEMY = False
    Base = object

from candidate_authority import CandidateType, CandidateStatus, CandidateResult, get_registry_field_for_candidate_type


# =============================================================================
# DATA MODEL: PendingVendorAuthority
# =============================================================================

if HAS_SQLALCHEMY:
    class PendingVendorAuthority(Base):
        """
        Tracks candidate vendor URLs pending review and promotion.
        
        This is the persistence layer for the bootstrap workflow.
        URLs stored here are candidates, NOT authoritative sources.
        source_type classification ignores this table entirely.
        """
        __tablename__ = 'pending_vendor_authority'
        
        id = Column(Integer, primary_key=True)
        
        # Vendor identification
        vendor_name = Column(String(255), nullable=False, index=True)
        product_name = Column(String(255))
        
        # Candidate URL details
        candidate_url = Column(String(500), nullable=False)
        candidate_type = Column(String(50), nullable=False)  # trust_center, security_page, etc.
        normalized_domain = Column(String(255))
        
        # Detection metadata
        confidence = Column(Float, default=0.0)
        match_reason = Column(String(100))
        discovered_at = Column(DateTime, default=func.now())
        discovered_by = Column(String(100))  # research_agent, manual, etc.
        
        # Review workflow
        status = Column(String(20), default='pending', index=True)  # pending, confirmed, rejected, promoted
        reviewed_at = Column(DateTime)
        reviewed_by = Column(String(100))
        review_notes = Column(String(500))
        
        # Promotion tracking
        promoted_at = Column(DateTime)
        vendor_registry_id = Column(Integer)  # FK to vendor_registry after promotion
        
        created_at = Column(DateTime, default=func.now())
        updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
        
        def to_dict(self) -> dict:
            return {
                'id': self.id,
                'vendor_name': self.vendor_name,
                'product_name': self.product_name,
                'candidate_url': self.candidate_url,
                'candidate_type': self.candidate_type,
                'normalized_domain': self.normalized_domain,
                'confidence': self.confidence,
                'match_reason': self.match_reason,
                'status': self.status,
                'discovered_at': self.discovered_at.isoformat() if self.discovered_at else None,
                'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
                'promoted_at': self.promoted_at.isoformat() if self.promoted_at else None,
            }
else:
    # Stub for testing without SQLAlchemy
    class PendingVendorAuthority:
        """Stub for testing without database"""
        pass


# =============================================================================
# PROMOTION RESULT
# =============================================================================

@dataclass
class PromotionResult:
    """
    Result of attempting to promote a candidate to VendorRegistry.
    
    Attributes:
        success: Whether promotion succeeded
        vendor_registry_id: ID of created/updated VendorRegistry entry
        field_updated: Which URL field was set (e.g., "trust_center_url")
        error: Error message if failed
        was_new_vendor: True if new VendorRegistry entry was created
    """
    success: bool
    vendor_registry_id: Optional[int] = None
    field_updated: Optional[str] = None
    error: Optional[str] = None
    was_new_vendor: bool = False


# =============================================================================
# BOOTSTRAP HELPER FUNCTIONS (Database-aware)
# =============================================================================

def create_pending_candidate(
    db_session,
    vendor_name: str,
    candidate_result: CandidateResult,
    candidate_url: str,
    product_name: str = None,
    discovered_by: str = "research_agent"
) -> Optional[Any]:
    """
    Create a PendingVendorAuthority record for a candidate URL.
    
    This stores the candidate for later review. It does NOT affect
    source_type classification in any way.
    
    Args:
        db_session: SQLAlchemy session
        vendor_name: Name of the vendor being researched
        candidate_result: Result from analyze_candidate()
        candidate_url: The URL identified as a candidate
        product_name: Optional product name
        discovered_by: What discovered this candidate
        
    Returns:
        PendingVendorAuthority instance if created, None if not a candidate
    """
    if not candidate_result.is_candidate:
        return None
    
    if not HAS_SQLALCHEMY:
        return None
    
    # Check for duplicate
    existing = db_session.query(PendingVendorAuthority).filter(
        PendingVendorAuthority.vendor_name == vendor_name,
        PendingVendorAuthority.candidate_url == candidate_url
    ).first()
    
    if existing:
        # Update confidence if higher
        if candidate_result.confidence > existing.confidence:
            existing.confidence = candidate_result.confidence
            existing.match_reason = candidate_result.match_reason
            db_session.commit()
        return existing
    
    # Create new
    pending = PendingVendorAuthority(
        vendor_name=vendor_name,
        product_name=product_name,
        candidate_url=candidate_url,
        candidate_type=candidate_result.candidate_type.value,
        normalized_domain=candidate_result.normalized_domain,
        confidence=candidate_result.confidence,
        match_reason=candidate_result.match_reason,
        discovered_by=discovered_by,
        status=CandidateStatus.PENDING.value,
    )
    
    db_session.add(pending)
    db_session.commit()
    
    return pending


def promote_candidate(
    db_session,
    pending_id: int,
    reviewed_by: str,
    review_notes: str = None
) -> PromotionResult:
    """
    Promote a confirmed candidate to VendorRegistry.
    
    This creates or updates a VendorRegistry entry with the candidate URL,
    making future source_type classifications return "vendor" for this URL.
    
    Args:
        db_session: SQLAlchemy session
        pending_id: ID of PendingVendorAuthority to promote
        reviewed_by: Who is performing the promotion
        review_notes: Optional notes about the review
        
    Returns:
        PromotionResult with success status and details
    """
    if not HAS_SQLALCHEMY:
        return PromotionResult(success=False, error="SQLAlchemy not available")
    
    # Get pending record
    pending = db_session.query(PendingVendorAuthority).filter(
        PendingVendorAuthority.id == pending_id
    ).first()
    
    if not pending:
        return PromotionResult(success=False, error="Pending candidate not found")
    
    if pending.status == CandidateStatus.PROMOTED.value:
        return PromotionResult(
            success=False, 
            error="Already promoted",
            vendor_registry_id=pending.vendor_registry_id
        )
    
    # Determine which field to update
    try:
        candidate_type = CandidateType(pending.candidate_type)
    except ValueError:
        return PromotionResult(success=False, error=f"Invalid candidate_type: {pending.candidate_type}")
    
    field_name = get_registry_field_for_candidate_type(candidate_type)
    if not field_name:
        return PromotionResult(success=False, error=f"No registry field for type: {candidate_type.value}")
    
    # Find or create VendorRegistry entry
    vendor_entry = db_session.query(VendorRegistry).filter(
        VendorRegistry.vendor_name == pending.vendor_name
    ).first()
    
    was_new_vendor = False
    if not vendor_entry:
        # Create new vendor entry
        vendor_entry = VendorRegistry(
            vendor_name=pending.vendor_name,
            vendor_aliases=[],
        )
        db_session.add(vendor_entry)
        db_session.flush()  # Get the ID
        was_new_vendor = True
    
    # Set the URL field
    setattr(vendor_entry, field_name, pending.candidate_url)
    
    # Update pending record
    pending.status = CandidateStatus.PROMOTED.value
    pending.reviewed_at = datetime.utcnow()
    pending.reviewed_by = reviewed_by
    pending.review_notes = review_notes
    pending.promoted_at = datetime.utcnow()
    pending.vendor_registry_id = vendor_entry.id
    
    db_session.commit()
    
    return PromotionResult(
        success=True,
        vendor_registry_id=vendor_entry.id,
        field_updated=field_name,
        was_new_vendor=was_new_vendor
    )


def reject_candidate(
    db_session,
    pending_id: int,
    reviewed_by: str,
    review_notes: str = None
) -> bool:
    """
    Reject a candidate URL (mark as not authoritative).
    
    Args:
        db_session: SQLAlchemy session
        pending_id: ID of PendingVendorAuthority to reject
        reviewed_by: Who is performing the rejection
        review_notes: Optional notes about why rejected
        
    Returns:
        True if rejected, False if not found
    """
    if not HAS_SQLALCHEMY:
        return False
    
    pending = db_session.query(PendingVendorAuthority).filter(
        PendingVendorAuthority.id == pending_id
    ).first()
    
    if not pending:
        return False
    
    pending.status = CandidateStatus.REJECTED.value
    pending.reviewed_at = datetime.utcnow()
    pending.reviewed_by = reviewed_by
    pending.review_notes = review_notes
    
    db_session.commit()
    return True


def get_pending_candidates(
    db_session,
    vendor_name: str = None,
    status: str = None
) -> List[Any]:
    """
    Get pending candidate URLs for review.
    
    Args:
        db_session: SQLAlchemy session
        vendor_name: Optional filter by vendor
        status: Optional filter by status (pending, confirmed, rejected, promoted)
        
    Returns:
        List of PendingVendorAuthority records
    """
    if not HAS_SQLALCHEMY:
        return []
    
    query = db_session.query(PendingVendorAuthority)
    
    if vendor_name:
        query = query.filter(PendingVendorAuthority.vendor_name == vendor_name)
    
    if status:
        query = query.filter(PendingVendorAuthority.status == status)
    else:
        # Default to pending
        query = query.filter(PendingVendorAuthority.status == CandidateStatus.PENDING.value)
    
    return query.order_by(PendingVendorAuthority.confidence.desc()).all()


# =============================================================================
# OFFLINE HELPER FUNCTIONS (No database required)
# =============================================================================

@dataclass
class CandidateVendorUrl:
    """
    Lightweight data structure for tracking candidate URLs without database.
    
    Used for:
    - In-memory tracking during research
    - Offline testing
    - API response structures
    """
    vendor_name: str
    candidate_url: str
    candidate_type: CandidateType
    confidence: float
    match_reason: str
    normalized_domain: Optional[str] = None
    status: CandidateStatus = CandidateStatus.PENDING
    discovered_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        return {
            'vendor_name': self.vendor_name,
            'candidate_url': self.candidate_url,
            'candidate_type': self.candidate_type.value,
            'confidence': self.confidence,
            'match_reason': self.match_reason,
            'normalized_domain': self.normalized_domain,
            'status': self.status.value,
            'discovered_at': self.discovered_at.isoformat(),
        }


def collect_candidates_from_urls(
    vendor_name: str,
    urls: List[str]
) -> List[CandidateVendorUrl]:
    """
    Analyze a list of URLs and collect candidates.
    
    This is a pure function that can be used for offline testing
    or in-memory tracking during research.
    
    Args:
        vendor_name: Name of vendor being researched
        urls: List of URLs discovered during research
        
    Returns:
        List of CandidateVendorUrl for URLs that match candidate patterns
    """
    from candidate_authority import analyze_candidate
    
    candidates = []
    
    for url in urls:
        result = analyze_candidate(url)
        if result.is_candidate:
            candidates.append(CandidateVendorUrl(
                vendor_name=vendor_name,
                candidate_url=url,
                candidate_type=result.candidate_type,
                confidence=result.confidence,
                match_reason=result.match_reason,
                normalized_domain=result.normalized_domain,
            ))
    
    return candidates


def build_registry_entry_from_candidates(
    vendor_name: str,
    candidates: List[CandidateVendorUrl]
) -> Dict[str, str]:
    """
    Build a VendorRegistry-compatible dict from confirmed candidates.
    
    This is a pure function for preparing registry data.
    Actual promotion to database requires promote_candidate().
    
    Args:
        vendor_name: Vendor name
        candidates: List of confirmed CandidateVendorUrl
        
    Returns:
        Dict with vendor_name and URL fields ready for VendorRegistry
    """
    entry = {"vendor_name": vendor_name}
    
    # Group by candidate_type, take highest confidence for each
    by_type: Dict[CandidateType, CandidateVendorUrl] = {}
    
    for candidate in candidates:
        if candidate.status != CandidateStatus.CONFIRMED:
            continue
        
        existing = by_type.get(candidate.candidate_type)
        if not existing or candidate.confidence > existing.confidence:
            by_type[candidate.candidate_type] = candidate
    
    # Build entry
    for candidate_type, candidate in by_type.items():
        field_name = get_registry_field_for_candidate_type(candidate_type)
        if field_name:
            entry[field_name] = candidate.candidate_url
    
    return entry
