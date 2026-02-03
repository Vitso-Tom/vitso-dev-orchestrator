"""
Research Agent - Claude-powered vendor research with web search
Part of VDO AI Governance Platform (Job 53)

This agent:
1. Executes web searches for vendor intelligence
2. Extracts structured facts from results
3. Synthesizes a coherent report
4. Tracks ALL facts found (for audit by AuditAgent)
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import anthropic
import asyncio


class FactStatus(Enum):
    EXTRACTED = "extracted"
    DROPPED = "dropped"
    CONFLICTING = "conflicting"
    UNVERIFIED = "unverified"


@dataclass
class RawFact:
    """A fact found in search results (before synthesis)"""
    category: str
    key: str
    value: str
    source_url: str
    source_title: str
    source_snippet: str
    confidence: float = 0.8
    query_that_found_it: str = ""


@dataclass
class SearchQuery:
    """A search query and its raw results"""
    query_text: str
    purpose: str
    results: List[Dict] = field(default_factory=list)
    facts_found: List[RawFact] = field(default_factory=list)
    executed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass 
class ResearchOutput:
    """Complete output from ResearchAgent - passed to AuditAgent"""
    vendor_name: str
    product_name: str
    queries: List[SearchQuery]
    all_facts_found: List[RawFact]  # Everything we found
    synthesized_report: str  # The final report
    structured_data: Dict  # Extracted structured fields
    research_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    model_used: str = "claude-sonnet-4-20250514"


# Categories of facts we look for in vendor research
RESEARCH_CATEGORIES = {
    "company": ["founded", "headquarters", "employees", "customers", "leadership"],
    "funding": ["valuation", "funding_total", "funding_round", "investors", "revenue"],
    "certification": ["soc2", "iso27001", "hitrust", "fedramp", "hipaa_baa", "pci_dss"],
    "security": ["trust_center", "breach_history", "bug_bounty", "pentest", "security_team"],
    "data_handling": ["training_policy", "data_retention", "encryption", "data_residency"],
    "integration": ["sso", "scim", "api", "audit_logs", "rbac"],
}

# Search queries to execute for comprehensive vendor research
RESEARCH_QUERIES = [
    {"query": "{vendor} {product} security trust center SOC 2 ISO 27001", "purpose": "Security certifications"},
    {"query": "{vendor} {product} HIPAA BAA business associate agreement", "purpose": "Healthcare compliance"},
    {"query": "{vendor} funding valuation investors revenue", "purpose": "Company stability/funding"},
    {"query": "{vendor} {product} data breach security incident", "purpose": "Security incident history"},
    {"query": "{vendor} {product} enterprise SSO SCIM audit logs", "purpose": "Enterprise integrations"},
    {"query": "{vendor} {product} AI training data policy privacy", "purpose": "AI data handling"},
]


class ResearchAgent:
    """
    Claude-powered research agent with web search capability.
    
    Responsibilities:
    - Execute structured web searches
    - Extract ALL facts from results (nothing dropped here)
    - Synthesize coherent report
    - Pass everything to AuditAgent for cross-checking
    """
    
    def __init__(self, anthropic_client: anthropic.Anthropic):
        self.client = anthropic_client
        self.model = "claude-sonnet-4-20250514"
    
    async def research(self, vendor_name: str, product_name: str = None) -> ResearchOutput:
        """
        Execute comprehensive vendor research.
        
        Returns ResearchOutput containing:
        - All queries executed
        - ALL facts found (for audit)
        - Synthesized report
        - Structured data
        """
        product = product_name or vendor_name
        queries_executed: List[SearchQuery] = []
        all_facts: List[RawFact] = []
        
        # Phase 1: Execute searches in parallel
        search_tasks = [
            self._execute_search(
                query_template["query"].format(vendor=vendor_name, product=product),
                query_template["purpose"]
            )
            for query_template in RESEARCH_QUERIES
        ]
        queries_executed = await asyncio.gather(*search_tasks)
        
        # Collect all facts from results
        for search_query in queries_executed:
            all_facts.extend(search_query.facts_found)
        
        # Phase 2: Extract structured data from all facts
        structured_data = self._structure_facts(all_facts)
        
        # Phase 3: Synthesize report (some facts may not make it in)
        synthesized_report = await self._synthesize_report(
            vendor_name, product, all_facts, structured_data
        )
        
        return ResearchOutput(
            vendor_name=vendor_name,
            product_name=product,
            queries=queries_executed,
            all_facts_found=all_facts,
            synthesized_report=synthesized_report,
            structured_data=structured_data,
            model_used=self.model
        )
    
    async def _execute_search(self, query_text: str, purpose: str) -> SearchQuery:
        """Execute a single search query using Claude's web_search tool"""
        
        search_query = SearchQuery(query_text=query_text, purpose=purpose)
        
        try:
            # Call Claude with web_search tool
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=4096,
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
                messages=[{
                    "role": "user",
                    "content": f"""Search for: {query_text}

Purpose: {purpose}

After searching, extract ALL factual claims from the results. For each fact, provide:
- category: one of {list(RESEARCH_CATEGORIES.keys())}
- key: specific attribute (e.g., "soc2_status", "valuation", "employee_count")
- value: the factual value found
- source_url: where you found it
- source_title: title of the source
- source_snippet: exact text supporting this fact
- confidence: 0.0-1.0 how confident this fact is accurate

Return as JSON array of facts. Include EVERYTHING you find, even if it seems minor.
Do not filter or summarize - the audit agent will review."""
                }]
            )
            
            # Parse response to extract search results and facts
            search_query.results = self._extract_search_results(response)
            search_query.facts_found = self._extract_facts(response, query_text)
            
        except Exception as e:
            # Log error but continue - don't fail entire research
            search_query.results = [{"error": str(e)}]
        
        return search_query
    
    def _extract_search_results(self, response) -> List[Dict]:
        """Extract raw search results from Claude response"""
        results = []
        for block in response.content:
            if hasattr(block, 'type'):
                if block.type == 'tool_use' and block.name == 'web_search':
                    # Capture the search input
                    results.append({"search_query": block.input.get("query", "")})
                elif block.type == 'web_search_tool_result':
                    # Capture search results if available
                    if hasattr(block, 'content'):
                        for item in block.content:
                            if hasattr(item, 'url'):
                                results.append({
                                    "url": item.url,
                                    "title": getattr(item, 'title', ''),
                                    "snippet": getattr(item, 'snippet', '')
                                })
        return results
    
    def _extract_facts(self, response, query_text: str) -> List[RawFact]:
        """Extract facts from Claude's response"""
        facts = []
        all_text = []
        
        for block in response.content:
            if hasattr(block, 'text') and block.text:
                text = block.text
                all_text.append(text)
                
                # Try to parse JSON facts from text response
                try:
                    start = text.find('[')
                    end = text.rfind(']') + 1
                    if start != -1 and end > start:
                        json_str = text[start:end]
                        parsed = json.loads(json_str)
                        for item in parsed:
                            facts.append(RawFact(
                                category=item.get('category', 'unknown'),
                                key=item.get('key', ''),
                                value=item.get('value', ''),
                                source_url=item.get('source_url', ''),
                                source_title=item.get('source_title', ''),
                                source_snippet=item.get('source_snippet', ''),
                                confidence=float(item.get('confidence', 0.8)),
                                query_that_found_it=query_text
                            ))
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass
        
        # Fallback: if no structured facts, capture prose as raw content
        if not facts and all_text:
            combined = ' '.join(all_text)
            facts.append(RawFact(
                category='raw_research',
                key='search_findings',
                value=combined[:2000],  # Limit length
                source_url='',
                source_title='Web Search Results',
                source_snippet=combined[:500],
                confidence=0.7,
                query_that_found_it=query_text
            ))
        
        return facts
    
    def _structure_facts(self, facts: List[RawFact]) -> Dict:
        """Organize facts into structured categories"""
        structured = {category: {} for category in RESEARCH_CATEGORIES}
        
        for fact in facts:
            if fact.category in structured:
                # Take highest confidence value if duplicate keys
                if fact.key not in structured[fact.category]:
                    structured[fact.category][fact.key] = {
                        "value": fact.value,
                        "confidence": fact.confidence,
                        "source": fact.source_url
                    }
                elif fact.confidence > structured[fact.category][fact.key]["confidence"]:
                    structured[fact.category][fact.key] = {
                        "value": fact.value,
                        "confidence": fact.confidence,
                        "source": fact.source_url
                    }
        
        return structured
    
    async def _synthesize_report(
        self, 
        vendor_name: str, 
        product_name: str,
        facts: List[RawFact], 
        structured: Dict
    ) -> str:
        """
        Create synthesized markdown report from facts.
        Note: Some facts may not make it into the report - AuditAgent will catch this.
        """
        
        facts_summary = json.dumps([{
            "category": f.category,
            "key": f.key,
            "value": f.value,
            "source": f.source_url
        } for f in facts], indent=2)
        
        response = await asyncio.to_thread(
            self.client.messages.create,
            model=self.model,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": f"""Create a vendor security research report for {vendor_name} ({product_name}).

Here are all the facts gathered from research:

{facts_summary}

Create a professional markdown report with these sections:
1. Company Overview (founded, HQ, employees, customers)
2. Funding & Stability (valuation, investors, revenue)
3. Security Certifications (SOC 2, ISO, HIPAA, etc.)
4. Data Handling & Privacy (training policy, retention, encryption)
5. Security Incidents (any breaches or issues found)
6. Enterprise Integration (SSO, SCIM, audit logs)
7. Risk Summary for Healthcare Use

Include a confidence score (0-100%) based on data completeness.
Cite sources inline where possible.
Flag any gaps where information was not found."""
            }]
        )
        
        # Extract text from response
        for block in response.content:
            if hasattr(block, 'text'):
                return block.text
        
        return "Error: Could not generate report"


# Convenience function for one-off research
async def research_vendor(
    client: anthropic.Anthropic, 
    vendor_name: str, 
    product_name: str = None
) -> ResearchOutput:
    """Convenience function to run vendor research"""
    agent = ResearchAgent(client)
    return await agent.research(vendor_name, product_name)
