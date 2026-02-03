"""
Research API Endpoints for AI Governance Platform
Exposes vendor research capabilities via REST API (FastAPI + SQLAlchemy)
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from database import get_db
from research_models import ResearchLog, ResearchQuery, ResearchFact
from assurance_emitter import build_assurance_section, post_process_narrative


# =============================================================================
# BLOCK 3.5: ASSURANCE PERSISTENCE HELPER
# =============================================================================

def persist_assurance_to_structured_data(
    db: Session,
    research_log_id: int,
    assurance_findings: list,
    blocked_access: list
) -> bool:
    """
    Block 3.5: Persist assurance_emitter output into research_logs.structured_data.
    
    This is ADDITIVE - it updates the existing structured_data JSONB to include
    assurance_findings and blocked_access keys without overwriting other data.
    
    Args:
        db: SQLAlchemy session
        research_log_id: ID of the research_log row to update
        assurance_findings: List of findings from assurance_emitter
        blocked_access: List of blocked access entries from assurance_emitter
    
    Returns:
        True if update succeeded, False otherwise
    """
    if not research_log_id:
        return False
    
    # Only persist if we have data to persist
    if not assurance_findings and not blocked_access:
        return False
    
    try:
        log = db.query(ResearchLog).filter(ResearchLog.id == research_log_id).first()
        if not log:
            return False
        
        # Get existing structured_data (defensive)
        existing_data = log.structured_data or {}
        
        # Make a shallow copy to avoid mutating the original
        updated_data = dict(existing_data)
        
        # Add assurance keys
        if assurance_findings:
            updated_data['assurance_findings'] = assurance_findings
        if blocked_access:
            updated_data['blocked_access'] = blocked_access
        
        # Update the record
        log.structured_data = updated_data
        db.commit()
        
        return True
        
    except Exception as e:
        # Don't let persistence failure break the response
        db.rollback()
        # Optionally log: print(f"Block 3.5: Assurance persistence failed: {e}")
        return False


def build_structured_data_from_facts(db: Session, research_log_id: int) -> Dict[str, Any]:
    """
    Build structured_data dictionary from research_facts table.
    
    This provides a fallback when structured_data wasn't saved properly,
    allowing existing research to be used without re-running.
    
    Groups facts by category, using highest-confidence value for each key.
    """
    facts = db.query(ResearchFact).filter(
        ResearchFact.research_log_id == research_log_id,
        ResearchFact.status == 'extracted'
    ).all()
    
    if not facts:
        return {}
    
    structured = {}
    
    for fact in facts:
        category = fact.fact_category
        key = fact.fact_key
        
        if category not in structured:
            structured[category] = {}
        
        # Check if we already have this key - keep higher confidence one
        existing = structured[category].get(key)
        fact_confidence = fact.fact_confidence or 0.5
        
        if existing is None or fact_confidence > existing.get('confidence', 0):
            structured[category][key] = {
                'value': fact.fact_value,
                'source': fact.source_url,
                'confidence': fact_confidence
            }
    
    return structured


# Create router
research_router = APIRouter(prefix="/api", tags=["research"])


# Pydantic models
class VendorResearchRequest(BaseModel):
    vendor_name: str
    product_name: Optional[str] = None
    assessment_id: Optional[int] = None
    save_to_db: bool = True
    use_v2: bool = True  # Use V2 agent by default
    use_pipeline: bool = True  # NEW: Use cost-optimized pipeline (V3)
    force_refresh: bool = False  # Skip cache, do full research
    use_cache: bool = True  # Use cached facts
    cost_mode: str = "balanced"  # economy, balanced, quality


class DroppedFactResponse(BaseModel):
    fact_category: Optional[str]
    fact_key: Optional[str]
    fact_value: Optional[str]
    source_url: Optional[str]
    drop_reason: Optional[str]
    severity: Optional[str]


class ResearchLogResponse(BaseModel):
    success: bool
    vendor_name: str
    product_name: Optional[str] = None
    research_timestamp: Optional[str] = None
    synthesized_report: Optional[str] = None
    confidence_score: Optional[float] = None
    confidence_level: Optional[str] = None
    total_facts_found: Optional[int] = None
    facts_in_report: Optional[int] = None
    dropped_facts: Optional[List[Dict[str, Any]]] = None
    unsupported_claims: Optional[List[Dict[str, Any]]] = None
    research_log_id: Optional[int] = None
    error: Optional[str] = None
    structured_data: Optional[Dict[str, Any]] = None
    
    # V2 specific fields
    facts_from_cache: Optional[int] = None
    facts_from_recheck: Optional[int] = None
    facts_from_direct_fetch: Optional[int] = None
    facts_from_web_search: Optional[int] = None
    cache_hit_rate: Optional[float] = None
    research_mode: Optional[str] = None
    duration_seconds: Optional[float] = None
    agent_version: Optional[str] = None
    
    # V3 Assurance fields (additive)
    assurance_findings: Optional[List[Dict[str, Any]]] = None
    blocked_access: Optional[List[Dict[str, Any]]] = None
    
    class Config:
        from_attributes = True


class ReviewRequest(BaseModel):
    reviewer: str
    notes: Optional[str] = ""


def get_orchestrator():
    """Get or create the AI orchestrator instance"""
    from orchestrator import AIOrchestrator
    return AIOrchestrator()


@research_router.post("/research-vendor", response_model=ResearchLogResponse)
async def research_vendor(request: VendorResearchRequest, db: Session = Depends(get_db)):
    """
    Initiate AI-powered vendor research with cross-AI verification.
    
    V3 (pipeline, default): Index-first, cost-optimized approach
    V2 (fallback): Three-phase flow with caching, source recheck, and direct fetch
    V1 (legacy): Original web search only
    
    Flow for V3 Pipeline:
    1. Sitemap discovery (~$0)
    2. Pattern filtering (~$0)
    3. HEAD validation (~$0)
    4. Snippet extraction (no LLM)
    5. Single LLM call for fact extraction
    6. Single LLM call for report synthesis
    """
    try:
        # V3.5 PIPELINE (cost-optimized, default)
        if request.use_pipeline:
            print(f"[RESEARCH] Using V3.5 pipeline for {request.vendor_name}")
            result = await run_pipeline_and_synthesize(
                vendor_name=request.vendor_name,
                product_name=request.product_name,
                db=db,
                save_to_db=request.save_to_db
            )
            
            # V3 Assurance Emission (same as V2)
            try:
                assurance_output = build_assurance_section(
                    vendor_name=request.vendor_name,
                    product_name=request.product_name or request.vendor_name,
                    structured_data=result.get('structured_data', {}),
                    synthesized_report=result.get('synthesized_report'),
                )
                result['assurance_findings'] = assurance_output.get('assurance_findings', [])
                result['blocked_access'] = assurance_output.get('blocked_access', [])
                
                if result.get('synthesized_report'):
                    result['synthesized_report'] = post_process_narrative(
                        result['synthesized_report'],
                        result['assurance_findings']
                    )
            except Exception as e:
                result['assurance_findings'] = []
                result['blocked_access'] = []
            
            return ResearchLogResponse(**result)
        
        # V2/V1 FALLBACK
        orchestrator = get_orchestrator()
        
        if request.use_v2:
            # Use V2 agent with caching and verification
            result = await orchestrator.research_vendor_v2(
                vendor_name=request.vendor_name,
                product_name=request.product_name,
                assessment_id=request.assessment_id,
                save_to_db=request.save_to_db,
                db=db if request.save_to_db else None,
                force_refresh=request.force_refresh,
                use_cache=request.use_cache,
                cost_mode=request.cost_mode
            )
        else:
            # Use V1 agent (original)
            result = await orchestrator.research_vendor(
                vendor_name=request.vendor_name,
                product_name=request.product_name,
                assessment_id=request.assessment_id,
                save_to_db=request.save_to_db,
                db=db if request.save_to_db else None
            )
        
        # If structured_data is empty but we have a research_log_id, rebuild from facts
        if (not result.get('structured_data') or result.get('structured_data') == {}) and result.get('research_log_id'):
            rebuilt = build_structured_data_from_facts(db, result['research_log_id'])
            if rebuilt:
                result['structured_data'] = rebuilt
        
        # V3 Assurance Emission (ADDITIVE - does not modify existing fields)
        try:
            assurance_output = build_assurance_section(
                vendor_name=request.vendor_name,
                product_name=request.product_name or request.vendor_name,
                structured_data=result.get('structured_data', {}),
                synthesized_report=result.get('synthesized_report'),
            )
            result['assurance_findings'] = assurance_output.get('assurance_findings', [])
            result['blocked_access'] = assurance_output.get('blocked_access', [])
            
            # Block 3.4: Post-process narrative to enforce certification gating
            if result.get('synthesized_report'):
                result['synthesized_report'] = post_process_narrative(
                    result['synthesized_report'],
                    result['assurance_findings']
                )
            
            # Block 3.5: Persist assurance output into structured_data JSONB
            # This ensures AITGP can read assurance_findings from DB instead of
            # falling back to synthesized_report (which may contain hallucinations)
            if request.save_to_db and result.get('research_log_id'):
                persist_assurance_to_structured_data(
                    db=db,
                    research_log_id=result.get('research_log_id'),
                    assurance_findings=result.get('assurance_findings', []),
                    blocked_access=result.get('blocked_access', [])
                )
        except Exception as e:
            # Assurance emission failure must not break existing behavior
            result['assurance_findings'] = []
            result['blocked_access'] = []
            # Optionally log: print(f"Assurance emission failed: {e}")
        
        return ResearchLogResponse(**result)
        
    except Exception as e:
        return ResearchLogResponse(
            success=False,
            vendor_name=request.vendor_name,
            product_name=request.product_name,
            error=str(e)
        )


@research_router.get("/research-logs")
async def get_research_logs(
    vendor: Optional[str] = None,
    assessment_id: Optional[int] = None,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get research logs, optionally filtered."""
    try:
        query = db.query(ResearchLog)
        
        if vendor:
            query = query.filter(ResearchLog.vendor_name.ilike(f"%{vendor}%"))
        
        if assessment_id:
            query = query.filter(ResearchLog.assessment_id == assessment_id)
        
        logs = query.order_by(ResearchLog.research_timestamp.desc()).limit(limit).all()
        
        return {
            "logs": [
                {
                    "id": log.id,
                    "vendor_name": log.vendor_name,
                    "product_name": log.product_name,
                    "confidence_score": log.confidence_score,
                    "confidence_level": log.confidence_level,
                    "facts_extracted": log.facts_extracted,
                    "facts_dropped": log.facts_dropped,
                    "status": log.status,
                    "research_timestamp": log.research_timestamp.isoformat() if log.research_timestamp else None
                }
                for log in logs
            ],
            "total": len(logs),
            "filters": {"vendor": vendor, "assessment_id": assessment_id, "limit": limit}
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@research_router.get("/research-logs/{log_id}")
async def get_research_log(log_id: int, db: Session = Depends(get_db)):
    """Get detailed research log with full audit trail."""
    try:
        log = db.query(ResearchLog).filter(ResearchLog.id == log_id).first()
        
        if not log:
            raise HTTPException(status_code=404, detail="Research log not found")
        
        queries = db.query(ResearchQuery).filter(
            ResearchQuery.research_log_id == log_id
        ).order_by(ResearchQuery.query_sequence).all()
        
        facts = db.query(ResearchFact).filter(
            ResearchFact.research_log_id == log_id
        ).all()
        
        return {
            "log": {
                "id": log.id,
                "vendor_name": log.vendor_name,
                "product_name": log.product_name,
                "confidence_score": log.confidence_score,
                "confidence_level": log.confidence_level,
                "sources_consulted": log.sources_consulted,
                "sources_cited": log.sources_cited,
                "facts_extracted": log.facts_extracted,
                "facts_dropped": log.facts_dropped,
                "synthesis_model": log.synthesis_model,
                "synthesized_report": log.synthesized_report,
                "structured_data": log.structured_data,
                "status": log.status,
                "reviewed_by": log.reviewed_by,
                "reviewed_at": log.reviewed_at.isoformat() if log.reviewed_at else None,
                "research_timestamp": log.research_timestamp.isoformat() if log.research_timestamp else None
            },
            "queries": [
                {
                    "id": q.id,
                    "query_sequence": q.query_sequence,
                    "query_type": q.query_type,
                    "query_text": q.query_text,
                    "query_purpose": q.query_purpose,
                    "results_count": q.results_count
                }
                for q in queries
            ],
            "facts": [
                {
                    "id": f.id,
                    "fact_category": f.fact_category,
                    "fact_key": f.fact_key,
                    "fact_value": f.fact_value,
                    "source_url": f.source_url,
                    "status": f.status,
                    "drop_reason": f.drop_reason,
                    "fact_confidence": f.fact_confidence
                }
                for f in facts
            ],
            "extracted_count": len([f for f in facts if f.status == 'extracted']),
            "dropped_count": len([f for f in facts if f.status == 'dropped'])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@research_router.get("/research-logs/{log_id}/dropped")
async def get_dropped_facts(log_id: int, db: Session = Depends(get_db)):
    """
    Get only dropped facts for review (the a16z problem).
    Shows what was found but not included in synthesis.
    """
    try:
        dropped = db.query(ResearchFact).filter(
            ResearchFact.research_log_id == log_id,
            ResearchFact.status == 'dropped'
        ).all()
        
        return {
            "dropped_facts": [
                {
                    "id": f.id,
                    "fact_category": f.fact_category,
                    "fact_key": f.fact_key,
                    "fact_value": f.fact_value,
                    "source_url": f.source_url,
                    "source_snippet": f.source_snippet,
                    "drop_reason": f.drop_reason,
                    "fact_confidence": f.fact_confidence
                }
                for f in dropped
            ],
            "count": len(dropped),
            "log_id": log_id,
            "message": "These facts were found during research but not included in the final report."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@research_router.get("/research-logs/{log_id}/confidence")
async def get_confidence_breakdown(log_id: int, db: Session = Depends(get_db)):
    """Get confidence score breakdown for a research log."""
    try:
        log = db.query(ResearchLog).filter(ResearchLog.id == log_id).first()
        
        if not log:
            raise HTTPException(status_code=404, detail="Research log not found")
        
        # Calculate rates
        citation_rate = None
        if log.sources_consulted and log.sources_consulted > 0:
            citation_rate = round((log.sources_cited / log.sources_consulted) * 100, 1)
        
        total_facts = (log.facts_extracted or 0) + (log.facts_dropped or 0)
        drop_rate = None
        if total_facts > 0:
            drop_rate = round((log.facts_dropped / total_facts) * 100, 1)
        
        return {
            "id": log.id,
            "vendor_name": log.vendor_name,
            "product_name": log.product_name,
            "confidence_score": log.confidence_score,
            "confidence_level": log.confidence_level,
            "sources_consulted": log.sources_consulted,
            "sources_cited": log.sources_cited,
            "facts_extracted": log.facts_extracted,
            "facts_dropped": log.facts_dropped,
            "citation_rate": citation_rate,
            "drop_rate": drop_rate,
            "gaps_identified": log.gaps_identified,
            "research_timestamp": log.research_timestamp.isoformat() if log.research_timestamp else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@research_router.post("/research-logs/{log_id}/review")
async def review_research_log(log_id: int, request: ReviewRequest, db: Session = Depends(get_db)):
    """Mark research log as reviewed by human."""
    try:
        log = db.query(ResearchLog).filter(ResearchLog.id == log_id).first()
        
        if not log:
            raise HTTPException(status_code=404, detail="Research log not found")
        
        log.status = "reviewed"
        log.reviewed_by = request.reviewer
        log.reviewed_at = datetime.utcnow()
        log.reviewer_notes = request.notes
        log.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "status": "reviewed",
            "log_id": log_id,
            "reviewed_by": request.reviewer,
            "reviewed_at": log.reviewed_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# PIPELINE V3: Index-First Research (Cost-Optimized)
# =============================================================================

class PipelineRequest(BaseModel):
    domain: str
    vendor_name: Optional[str] = None
    max_pages: int = 15
    use_pipeline: bool = True  # Flag to enable pipeline


async def discover_vendor_domain(vendor_name: str, product_name: Optional[str], anthropic_client) -> Optional[str]:
    """
    Use a cheap search to discover the vendor's actual domain.
    Searches for vendor + product together to find the correct company.
    Called when simple domain inference fails (zero facts found).
    """
    import asyncio
    import re
    
    # Search for vendor + product together - this disambiguates
    search_term = f"{vendor_name} {product_name}" if product_name else vendor_name
    
    prompt = f"""Search for "{search_term}" and find their official company website.

Return ONLY the domain (e.g., "example.com"), nothing else. No explanation."""
    
    try:
        response = await asyncio.to_thread(
            anthropic_client.messages.create,
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        
        for block in response.content:
            if hasattr(block, 'text') and block.text:
                text = block.text.strip().lower()
                
                # If response is short and looks like a domain, use it directly
                if len(text) < 50 and "." in text and " " not in text:
                    domain = text.replace("https://", "").replace("http://", "")
                    domain = domain.replace("www.", "").rstrip("/")
                    if domain:
                        print(f"[DOMAIN DISCOVERY] Found domain for {vendor_name}: {domain}")
                        return domain
                
                # Otherwise, try to extract domains from the text
                # Look for patterns like "example.com" or "www.example.com"
                domain_pattern = r'\b([a-z0-9][-a-z0-9]*\.)+[a-z]{2,}\b'
                matches = re.findall(domain_pattern, text)
                
                # Also look for explicit URLs
                url_pattern = r'https?://(?:www\.)?([a-z0-9][-a-z0-9]*(?:\.[a-z0-9][-a-z0-9]*)+)'
                url_matches = re.findall(url_pattern, text)
                
                # Combine and filter
                all_domains = []
                for m in matches:
                    # matches returns the last group, reconstruct
                    pass
                
                # Better: find full domain patterns
                full_domain_pattern = r'([a-z0-9][-a-z0-9]*(?:\.[a-z0-9][-a-z0-9]*)+\.[a-z]{2,})'
                full_matches = re.findall(full_domain_pattern, text)
                
                # Filter to likely vendor domains (not common sites)
                skip_domains = ['google.com', 'linkedin.com', 'facebook.com', 'twitter.com', 'crunchbase.com']
                for domain in full_matches:
                    domain = domain.replace("www.", "")
                    if domain not in skip_domains and vendor_name.lower().split()[0] in domain:
                        print(f"[DOMAIN DISCOVERY] Extracted domain for {vendor_name}: {domain}")
                        return domain
                
                # Fallback: return first non-common domain
                for domain in full_matches:
                    domain = domain.replace("www.", "")
                    if domain not in skip_domains:
                        print(f"[DOMAIN DISCOVERY] Fallback domain for {vendor_name}: {domain}")
                        return domain
                        
    except Exception as e:
        print(f"[DOMAIN DISCOVERY] Error: {e}")
    
    return None


async def run_pipeline_and_synthesize(
    vendor_name: str,
    product_name: Optional[str],
    db: Session,
    save_to_db: bool = True
) -> Dict[str, Any]:
    """
    Run the v3.5 tool-calling research pipeline.
    
    V3.5 Architecture:
    1. URL Discovery (free) - sitemaps, path probing
    2. URL Ranking (free) - prioritize trust/security pages
    3. Agentic Extraction (Claude tool-calling) - probe then fetch
    4. Report Synthesis (Claude) - structured report generation
    
    Domain Resolution Strategy (from v3):
    1. Multi-word vendor names -> direct inference works
    2. Single-word vendor names -> use search to disambiguate
    3. If initial attempt finds 0 URLs -> retry with discovered domain
    
    Returns dict compatible with ResearchLogResponse.
    """
    import anthropic
    from research_agent_v3_5 import ResearchAgentV35, ResearchMode
    from research_models_v2 import VendorFact, get_ttl_for_field, get_priority_for_field
    
    # Initialize Claude client
    anthropic_client = anthropic.Anthropic()
    
    # Domain resolution strategy (from v3)
    vendor_words = vendor_name.strip().split()
    
    if len(vendor_words) >= 2:
        # Multi-word: direct inference
        vendor_slug = vendor_name.lower().replace(" ", "").replace("-", "").replace("_", "")
        domain = f"{vendor_slug}.com"
        print(f"[V3.5 PIPELINE] Multi-word vendor, inferred domain: {domain}")
    else:
        # Single-word: ambiguous, search with product for disambiguation
        print(f"[V3.5 PIPELINE] Single-word vendor '{vendor_name}', using search to find domain...")
        domain = await discover_vendor_domain(vendor_name, product_name, anthropic_client)
        
        if not domain:
            # Fallback to simple inference
            vendor_slug = vendor_name.lower().replace(" ", "").replace("-", "").replace("_", "")
            domain = f"{vendor_slug}.com"
            print(f"[V3.5 PIPELINE] Discovery failed, falling back to: {domain}")
        else:
            print(f"[V3.5 PIPELINE] Discovered domain: {domain}")
    
    print(f"[V3.5 PIPELINE] Starting research for {vendor_name} (domain: {domain})")
    
    # Create v3.5 agent
    agent = ResearchAgentV35(
        anthropic_client=anthropic_client,
        db_session=db,
        max_urls_per_vendor=10
    )
    
    # Run research
    result = await agent.research(
        vendor_name=vendor_name,
        product_name=product_name or vendor_name,
        domain=domain
    )
    
    # If no facts found and we haven't tried discovery yet, try it now
    if not result.facts and len(vendor_words) >= 2:
        print(f"[V3.5 PIPELINE] No facts from {domain}, attempting domain discovery...")
        discovered_domain = await discover_vendor_domain(vendor_name, product_name, anthropic_client)
        
        if discovered_domain and discovered_domain != domain:
            print(f"[V3.5 PIPELINE] Retrying with discovered domain: {discovered_domain}")
            domain = discovered_domain
            result = await agent.research(
                vendor_name=vendor_name,
                product_name=product_name or vendor_name,
                domain=domain
            )
    
    # Convert v3.5 facts to structured_data format expected by AITGP
    structured_data = {}
    for fact in result.facts:
        category = fact.category
        key = fact.key
        
        if category not in structured_data:
            structured_data[category] = {}
        
        # Keep highest confidence per key
        existing = structured_data[category].get(key)
        if existing is None or fact.confidence > existing.get('confidence', 0):
            structured_data[category][key] = {
                'value': fact.value,
                'source': fact.source_url,
                'source_type': fact.source_type,
                'confidence': fact.confidence,
                'snippet': fact.source_snippet
            }
    
    # Calculate confidence score
    if result.facts:
        avg_confidence = sum(f.confidence for f in result.facts) / len(result.facts)
        vendor_facts = sum(1 for f in result.facts if f.source_type == "vendor")
        vendor_boost = min(0.1, vendor_facts * 0.02)
        confidence_score = min(0.95, avg_confidence + vendor_boost)
    else:
        confidence_score = 0.3
    
    # Determine confidence level
    if confidence_score >= 0.8:
        confidence_level = "high"
    elif confidence_score >= 0.6:
        confidence_level = "moderate"
    else:
        confidence_level = "low"
    
    # Persist to database
    research_log_id = None
    if save_to_db and db and result.facts:
        try:
            # Create ResearchLog entry
            research_log = ResearchLog(
                vendor_name=vendor_name,
                product_name=product_name or vendor_name,
                confidence_score=confidence_score,
                confidence_level=confidence_level,
                sources_consulted=result.urls_discovered,
                sources_cited=len(set(f.source_url for f in result.facts)),
                facts_extracted=len(result.facts),
                facts_dropped=0,
                synthesis_model="claude-sonnet-4-20250514",
                synthesized_report=result.synthesized_report,
                structured_data=structured_data,
                status="completed",
            )
            db.add(research_log)
            db.flush()
            research_log_id = research_log.id
            
            # Persist facts to VendorFact table
            unique_facts = {}
            for fact in result.facts:
                key = (fact.category, fact.key)
                if key not in unique_facts or fact.confidence > unique_facts[key].confidence:
                    unique_facts[key] = fact
            
            for (cat, key), fact in unique_facts.items():
                ttl = get_ttl_for_field(fact.category, fact.key)
                priority = get_priority_for_field(fact.category, fact.key)
                
                existing = db.query(VendorFact).filter(
                    VendorFact.vendor_name == vendor_name,
                    VendorFact.product_name == (product_name or vendor_name),
                    VendorFact.fact_category == fact.category,
                    VendorFact.fact_key == fact.key
                ).first()
                
                if existing:
                    existing.fact_value = fact.value
                    existing.source_url = fact.source_url
                    existing.source_snippet = fact.source_snippet
                    existing.source_type = fact.source_type
                    existing.confidence_score = fact.confidence
                    existing.verification_status = "verified"
                    existing.verified_by = "v3.5_tool_calling"
                    existing.verified_at = datetime.utcnow()
                    existing.expires_at = datetime.utcnow() + timedelta(days=ttl)
                    existing.last_updated_by_research_log_id = research_log_id
                else:
                    vendor_fact = VendorFact(
                        vendor_name=vendor_name,
                        product_name=product_name or vendor_name,
                        fact_category=fact.category,
                        fact_key=fact.key,
                        fact_value=fact.value,
                        source_url=fact.source_url,
                        source_snippet=fact.source_snippet,
                        source_type=fact.source_type,
                        confidence_score=fact.confidence,
                        verification_status="verified",
                        verified_by="v3.5_tool_calling",
                        verified_at=datetime.utcnow(),
                        ttl_days=ttl,
                        expires_at=datetime.utcnow() + timedelta(days=ttl),
                        recheck_priority=priority,
                        first_found_by_research_log_id=research_log_id,
                        last_updated_by_research_log_id=research_log_id,
                    )
                    db.add(vendor_fact)
            
            db.commit()
            print(f"[V3.5 PIPELINE] Persisted {len(unique_facts)} facts (research_log_id={research_log_id})")
            
        except Exception as e:
            db.rollback()
            print(f"[V3.5 PIPELINE] DB persistence failed: {e}")
    
    # Build blocked_access from tool calls that failed
    blocked_access = []
    
    return {
        "success": True,
        "vendor_name": vendor_name,
        "product_name": product_name or vendor_name,
        "synthesized_report": result.synthesized_report,
        "structured_data": structured_data,
        "confidence_score": confidence_score,
        "confidence_level": confidence_level,
        "total_facts_found": result.facts_extracted,
        "facts_in_report": result.facts_extracted,
        "research_log_id": research_log_id,
        "research_mode": "v3.5_tool_calling",
        "agent_version": "v3.5",
        "duration_seconds": result.duration_seconds,
        "blocked_access": blocked_access,
        # Fields expected by AITGP
        "facts_from_cache": 0,
        "facts_from_recheck": 0,
        "facts_from_direct_fetch": result.urls_processed,
        "facts_from_web_search": 0,
        "cache_hit_rate": 0.0,
        "pipeline_stats": {
            "urls_discovered": result.urls_discovered,
            "urls_processed": result.urls_processed,
            "tool_calls": result.tool_calls,
        }
    }


@research_router.post("/pipeline-research")
async def run_pipeline_research(request: PipelineRequest, db: Session = Depends(get_db)):
    """
    Run the new index-first research pipeline.
    
    This is the cost-optimized architecture:
    1. Sitemap discovery (~$0)
    2. Pattern filtering (~$0)
    3. HEAD validation (~$0)
    4. Authority ranking (~$0)
    5. Snippet extraction (no LLM)
    6. Fact extraction (single LLM call)
    
    Returns facts and pipeline statistics for cost analysis.
    """
    import anthropic
    from openai import OpenAI
    from research_agent_v2 import VendorAssessmentPipeline
    
    try:
        # Initialize clients
        anthropic_client = anthropic.Anthropic()
        openai_client = OpenAI()
        
        # Run pipeline
        pipeline = VendorAssessmentPipeline(
            anthropic_client=anthropic_client,
            openai_client=openai_client,
            cost_mode="economy"
        )
        
        facts, stats = await pipeline.run(
            domain=request.domain,
            vendor_name=request.vendor_name,
            max_pages=request.max_pages
        )
        
        # Convert facts to serializable format
        facts_serialized = [
            {
                "category": f.category,
                "key": f.key,
                "value": f.value,
                "snippet": f.snippet,
                "source_url": f.source_url,
                "confidence": f.confidence,
                "authority_tier": f.authority_tier
            }
            for f in facts
        ]
        
        return {
            "success": True,
            "facts": facts_serialized,
            "stats": stats,
            "message": f"Pipeline extracted {len(facts)} facts from {stats.get('pages_fetched', 0)} pages"
        }
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


# To register in main.py:
# from research_routes import research_router
# app.include_router(research_router)
