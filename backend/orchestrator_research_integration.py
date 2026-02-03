"""
Orchestrator Integration for Research Agents
Add these methods to AIOrchestrator class in orchestrator.py

This provides the research_vendor() method that:
1. Instantiates ResearchAgent (Claude) to gather and synthesize
2. Instantiates AuditAgent (Gemini) to cross-check
3. Combines results into audited ResearchLog
4. Saves to database with full audit trail
"""

# Add these imports to orchestrator.py:
# from research_agent import ResearchAgent, ResearchOutput
# from audit_agent import AuditAgent, AuditResult
# from research_log import ResearchLog, ResearchFact, FactStatus  # The original module


# Add this method to AIOrchestrator class:

async def research_vendor(
    self,
    vendor_name: str,
    product_name: str = None,
    assessment_id: int = None,
    save_to_db: bool = True,
    db_path: str = None
) -> dict:
    """
    Execute comprehensive vendor research with cross-AI verification.
    
    Flow:
    1. ResearchAgent (Claude) → web search, extract facts, synthesize report
    2. AuditAgent (Gemini) → cross-check facts vs report, find drops/hallucinations
    3. Combine into final ResearchLog with full audit trail
    
    Args:
        vendor_name: Name of the vendor to research
        product_name: Specific product (defaults to vendor_name)
        assessment_id: Optional link to an assessment
        save_to_db: Whether to persist to database
        db_path: Path to SQLite database
    
    Returns:
        dict with:
        - success: bool
        - research_output: The synthesized report and facts
        - audit_result: Cross-check findings (drops, hallucinations)
        - confidence_score: 0.0-1.0
        - confidence_level: low/medium/high
        - research_log_id: DB ID if saved
    """
    from research_agent import ResearchAgent
    from audit_agent import AuditAgent
    
    product = product_name or vendor_name
    
    try:
        # Phase 1: Research (Claude with web_search)
        research_agent = ResearchAgent(self.anthropic_client)
        research_output = await research_agent.research(vendor_name, product)
        
        # Phase 2: Audit (OpenAI/Codex cross-checks)
        audit_agent = AuditAgent(openai_client=self.openai_client)
        audit_result = await audit_agent.audit(research_output)
        
        # Phase 3: Build combined result
        result = {
            "success": True,
            "vendor_name": vendor_name,
            "product_name": product,
            "research_timestamp": research_output.research_timestamp,
            
            # From ResearchAgent
            "synthesized_report": research_output.synthesized_report,
            "structured_data": research_output.structured_data,
            "total_facts_found": len(research_output.all_facts_found),
            "queries_executed": len(research_output.queries),
            
            # From AuditAgent
            "facts_in_report": audit_result.facts_in_report,
            "dropped_facts": [
                {
                    "category": df.fact.category,
                    "key": df.fact.key,
                    "value": df.fact.value,
                    "source_url": df.fact.source_url,
                    "drop_reason": df.drop_reason,
                    "severity": df.severity
                }
                for df in audit_result.dropped_facts
            ],
            "unsupported_claims": [
                {
                    "claim": uc.claim_text,
                    "location": uc.location_in_report,
                    "severity": uc.severity
                }
                for uc in audit_result.unsupported_claims
            ],
            
            # Confidence
            "confidence_score": audit_result.confidence_score,
            "confidence_level": audit_result.confidence_level,
            "audit_notes": audit_result.audit_notes,
            
            # Models used
            "research_model": research_output.model_used,
            "audit_model": audit_result.auditor_model
        }
        
        # Phase 4: Save to database if requested
        if save_to_db and db_path:
            result["research_log_id"] = await self._save_research_log(
                research_output, audit_result, assessment_id, db_path
            )
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "vendor_name": vendor_name,
            "product_name": product
        }


async def _save_research_log(
    self,
    research_output,
    audit_result,
    assessment_id: int,
    db_path: str
) -> int:
    """Save research results to database with full audit trail"""
    import sqlite3
    import json
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Insert main log
        cursor.execute("""
            INSERT INTO research_logs (
                assessment_id, vendor_name, product_name, research_timestamp,
                confidence_score, confidence_level, sources_consulted, sources_cited,
                facts_extracted, facts_dropped, gaps_identified, synthesis_model,
                synthesis_notes, synthesized_report, structured_data, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            assessment_id,
            research_output.vendor_name,
            research_output.product_name,
            research_output.research_timestamp,
            audit_result.confidence_score,
            audit_result.confidence_level,
            len(research_output.queries) * 10,  # Approximate sources
            audit_result.facts_in_report,
            audit_result.total_facts_found,
            len(audit_result.dropped_facts),
            json.dumps([]),  # gaps_identified
            research_output.model_used,
            audit_result.audit_notes,
            research_output.synthesized_report,
            json.dumps(research_output.structured_data),
            "completed"
        ))
        
        research_log_id = cursor.lastrowid
        
        # Insert queries
        for seq, query in enumerate(research_output.queries):
            cursor.execute("""
                INSERT INTO research_queries (
                    research_log_id, query_sequence, query_type, query_text,
                    query_purpose, results_count, results_raw
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                research_log_id,
                seq + 1,
                "web_search",
                query.query_text,
                query.purpose,
                len(query.results),
                json.dumps(query.results)
            ))
        
        # Insert all facts (extracted)
        for fact in research_output.all_facts_found:
            cursor.execute("""
                INSERT INTO research_facts (
                    research_log_id, fact_category, fact_key, fact_value,
                    source_url, source_title, source_snippet, status,
                    fact_confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                research_log_id,
                fact.category,
                fact.key,
                fact.value,
                fact.source_url,
                fact.source_title,
                fact.source_snippet,
                "extracted",
                fact.confidence
            ))
        
        # Insert dropped facts (from audit)
        for dropped in audit_result.dropped_facts:
            cursor.execute("""
                INSERT INTO research_facts (
                    research_log_id, fact_category, fact_key, fact_value,
                    source_url, source_title, source_snippet, status,
                    drop_reason, fact_confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                research_log_id,
                dropped.fact.category,
                dropped.fact.key,
                dropped.fact.value,
                dropped.fact.source_url,
                dropped.fact.source_title,
                dropped.fact.source_snippet,
                "dropped",
                dropped.drop_reason,
                dropped.fact.confidence
            ))
        
        conn.commit()
        return research_log_id
        
    finally:
        conn.close()


# Add to routing map in route_task():
# "research": AIProvider.CLAUDE,  # But actually uses both via research_vendor()
