"""
Research Agent Module for AI Governance Platform
Handles automated vendor research with full audit trail
"""

import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum


class FactStatus(Enum):
    EXTRACTED = "extracted"
    DROPPED = "dropped"
    CONFLICTING = "conflicting"
    UNVERIFIED = "unverified"


class ConfidenceLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ResearchFact:
    """Individual fact extracted from research"""
    fact_category: str
    fact_key: str
    fact_value: str
    source_url: str
    source_title: str
    source_snippet: str
    status: FactStatus = FactStatus.EXTRACTED
    fact_confidence: float = 0.8
    drop_reason: Optional[str] = None
    fact_context: Optional[str] = None
    source_date: Optional[str] = None


@dataclass
class ResearchQuery:
    """Individual query executed during research"""
    query_type: str  # web_search, web_fetch, api_call
    query_text: str
    query_purpose: str
    results_count: int = 0
    results_raw: List[Dict] = None
    duration_ms: Optional[int] = None
    
    def __post_init__(self):
        if self.results_raw is None:
            self.results_raw = []


class ResearchLog:
    """
    Main research log manager - tracks all queries, facts, and synthesis
    for a single vendor research session.
    """
    
    def __init__(self, vendor_name: str, product_name: str = None, 
                 assessment_id: int = None, synthesis_model: str = "claude-sonnet-4"):
        self.vendor_name = vendor_name
        self.product_name = product_name
        self.assessment_id = assessment_id
        self.synthesis_model = synthesis_model
        self.research_timestamp = datetime.utcnow().isoformat()
        
        # Tracking
        self.queries: List[ResearchQuery] = []
        self.facts: List[ResearchFact] = []
        self.gaps_identified: List[str] = []
        self.synthesis_notes: str = ""
        self.synthesized_report: str = ""
        self.structured_data: Dict = {}
        
    def add_query(self, query: ResearchQuery) -> None:
        """Log a query that was executed"""
        self.queries.append(query)
        
    def add_fact(self, fact: ResearchFact) -> None:
        """Log a fact that was extracted"""
        self.facts.append(fact)
        
    def drop_fact(self, fact: ResearchFact, reason: str) -> None:
        """Mark a fact as dropped with reason (for audit trail)"""
        fact.status = FactStatus.DROPPED
        fact.drop_reason = reason
        self.facts.append(fact)
        
    def add_gap(self, gap: str) -> None:
        """Log a data gap that was identified"""
        self.gaps_identified.append(gap)
        
    @property
    def sources_consulted(self) -> int:
        """Total unique sources checked"""
        urls = set()
        for query in self.queries:
            for result in query.results_raw:
                if 'url' in result:
                    urls.add(result['url'])
        return len(urls)
    
    @property
    def sources_cited(self) -> int:
        """Sources that contributed to extracted facts"""
        return len(set(f.source_url for f in self.facts if f.status == FactStatus.EXTRACTED))
    
    @property
    def facts_extracted(self) -> int:
        return len([f for f in self.facts if f.status == FactStatus.EXTRACTED])
    
    @property
    def facts_dropped(self) -> int:
        return len([f for f in self.facts if f.status == FactStatus.DROPPED])
    
    @property
    def confidence_score(self) -> float:
        """
        Calculate overall confidence score based on:
        - Citation rate (sources cited / sources consulted)
        - Fact extraction rate
        - Number of gaps
        - Individual fact confidence scores
        """
        if not self.facts:
            return 0.0
            
        # Base: average of individual fact confidences
        extracted_facts = [f for f in self.facts if f.status == FactStatus.EXTRACTED]
        if not extracted_facts:
            return 0.0
            
        avg_fact_confidence = sum(f.fact_confidence for f in extracted_facts) / len(extracted_facts)
        
        # Penalty for gaps
        gap_penalty = min(len(self.gaps_identified) * 0.05, 0.2)
        
        # Penalty for high drop rate
        total_facts = self.facts_extracted + self.facts_dropped
        if total_facts > 0:
            drop_rate = self.facts_dropped / total_facts
            drop_penalty = drop_rate * 0.1
        else:
            drop_penalty = 0
            
        # Citation rate bonus
        if self.sources_consulted > 0:
            citation_bonus = (self.sources_cited / self.sources_consulted) * 0.1
        else:
            citation_bonus = 0
            
        score = avg_fact_confidence - gap_penalty - drop_penalty + citation_bonus
        return max(0.0, min(1.0, score))
    
    @property
    def confidence_level(self) -> ConfidenceLevel:
        score = self.confidence_score
        if score >= 0.8:
            return ConfidenceLevel.HIGH
        elif score >= 0.6:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW
    
    def to_dict(self) -> Dict:
        """Export full research log as dictionary"""
        return {
            "vendor_name": self.vendor_name,
            "product_name": self.product_name,
            "assessment_id": self.assessment_id,
            "research_timestamp": self.research_timestamp,
            "synthesis_model": self.synthesis_model,
            "confidence_score": round(self.confidence_score, 2),
            "confidence_level": self.confidence_level.value,
            "sources_consulted": self.sources_consulted,
            "sources_cited": self.sources_cited,
            "facts_extracted": self.facts_extracted,
            "facts_dropped": self.facts_dropped,
            "gaps_identified": self.gaps_identified,
            "synthesis_notes": self.synthesis_notes,
            "synthesized_report": self.synthesized_report,
            "structured_data": self.structured_data,
            "queries": [
                {
                    "query_type": q.query_type,
                    "query_text": q.query_text,
                    "query_purpose": q.query_purpose,
                    "results_count": q.results_count,
                    "results_raw": q.results_raw
                }
                for q in self.queries
            ],
            "facts": [
                {
                    "fact_category": f.fact_category,
                    "fact_key": f.fact_key,
                    "fact_value": f.fact_value,
                    "source_url": f.source_url,
                    "source_title": f.source_title,
                    "source_snippet": f.source_snippet,
                    "status": f.status.value,
                    "fact_confidence": f.fact_confidence,
                    "drop_reason": f.drop_reason
                }
                for f in self.facts
            ]
        }
    
    def save_to_db(self, db_path: str) -> int:
        """
        Save research log to SQLite database.
        Returns the research_log_id.
        """
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
                self.assessment_id,
                self.vendor_name,
                self.product_name,
                self.research_timestamp,
                self.confidence_score,
                self.confidence_level.value,
                self.sources_consulted,
                self.sources_cited,
                self.facts_extracted,
                self.facts_dropped,
                json.dumps(self.gaps_identified),
                self.synthesis_model,
                self.synthesis_notes,
                self.synthesized_report,
                json.dumps(self.structured_data),
                "completed"
            ))
            
            research_log_id = cursor.lastrowid
            
            # Insert queries
            for seq, query in enumerate(self.queries):
                cursor.execute("""
                    INSERT INTO research_queries (
                        research_log_id, query_sequence, query_type, query_text,
                        query_purpose, results_count, results_raw
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    research_log_id,
                    seq + 1,
                    query.query_type,
                    query.query_text,
                    query.query_purpose,
                    query.results_count,
                    json.dumps(query.results_raw)
                ))
                query_id = cursor.lastrowid
                
                # Insert facts linked to this query
                for fact in self.facts:
                    if fact.source_url in [r.get('url') for r in query.results_raw]:
                        cursor.execute("""
                            INSERT INTO research_facts (
                                research_log_id, research_query_id, fact_category,
                                fact_key, fact_value, fact_context, source_url,
                                source_title, source_snippet, status, drop_reason,
                                fact_confidence
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            research_log_id,
                            query_id,
                            fact.fact_category,
                            fact.fact_key,
                            fact.fact_value,
                            fact.fact_context,
                            fact.source_url,
                            fact.source_title,
                            fact.source_snippet,
                            fact.status.value,
                            fact.drop_reason,
                            fact.fact_confidence
                        ))
            
            conn.commit()
            return research_log_id
            
        finally:
            conn.close()


# Fact categories for vendor research
FACT_CATEGORIES = {
    "certification": ["soc2", "iso27001", "hitrust", "fedramp", "hipaa", "pci"],
    "funding": ["valuation", "funding_round", "investors", "revenue"],
    "company": ["employees", "founded", "headquarters", "customers"],
    "security": ["breach_history", "cve_history", "pentest", "bug_bounty", "trust_center"],
    "data_handling": ["training_policy", "retention", "encryption", "data_residency"],
    "compliance": ["baa_available", "dpa", "gdpr", "ccpa"],
    "integration": ["sso", "scim", "api", "audit_logs"]
}


def create_research_log_from_session(
    vendor_name: str,
    product_name: str,
    search_results: List[Dict],
    extracted_report: str,
    structured_findings: Dict,
    dropped_facts: List[Dict] = None
) -> ResearchLog:
    """
    Factory function to create a ResearchLog from a completed research session.
    
    Args:
        vendor_name: Name of the vendor researched
        product_name: Name of the product
        search_results: List of search queries and their results
        extracted_report: The synthesized markdown report
        structured_findings: Dict of structured data extracted
        dropped_facts: List of facts that were found but not included
    """
    log = ResearchLog(vendor_name, product_name)
    log.synthesized_report = extracted_report
    log.structured_data = structured_findings
    
    # Process search results into queries
    for sr in search_results:
        query = ResearchQuery(
            query_type=sr.get('type', 'web_search'),
            query_text=sr.get('query', ''),
            query_purpose=sr.get('purpose', ''),
            results_count=len(sr.get('results', [])),
            results_raw=sr.get('results', [])
        )
        log.add_query(query)
        
        # Extract facts from results
        for result in sr.get('results', []):
            if result.get('cited', False):
                fact = ResearchFact(
                    fact_category=result.get('category', 'unknown'),
                    fact_key=result.get('fact_key', ''),
                    fact_value=result.get('fact_value', ''),
                    source_url=result.get('url', ''),
                    source_title=result.get('title', ''),
                    source_snippet=result.get('snippet', ''),
                    fact_confidence=result.get('confidence', 0.8)
                )
                log.add_fact(fact)
    
    # Add dropped facts
    if dropped_facts:
        for df in dropped_facts:
            fact = ResearchFact(
                fact_category=df.get('category', 'unknown'),
                fact_key=df.get('fact_key', ''),
                fact_value=df.get('fact_value', ''),
                source_url=df.get('url', ''),
                source_title=df.get('title', ''),
                source_snippet=df.get('snippet', ''),
                status=FactStatus.DROPPED,
                drop_reason=df.get('drop_reason', 'Not included in synthesis')
            )
            log.facts.append(fact)
    
    return log
