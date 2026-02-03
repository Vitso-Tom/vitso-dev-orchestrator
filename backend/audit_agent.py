"""
Audit Agent - OpenAI/Codex-powered cross-checker for research verification
Part of VDO AI Governance Platform (Job 53)

This agent:
1. Receives ResearchOutput from ResearchAgent
2. Compares all_facts_found vs synthesized_report
3. Identifies facts that were found but NOT in final report (drops)
4. Flags potential hallucinations (claims not supported by facts)
5. Calculates confidence score with full audit trail

Uses OpenAI/Codex for:
- Independent verification (different AI than Claude)
- Strong analytical capabilities
- Precise comparison tasks
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import openai

# Import from research agent
from research_agent import ResearchOutput, RawFact, FactStatus


@dataclass
class DroppedFact:
    """A fact that was found but not included in synthesis"""
    fact: RawFact
    drop_reason: str
    severity: str  # "low", "medium", "high" - how important was this omission


@dataclass
class UnsupportedClaim:
    """A claim in the report not supported by gathered facts"""
    claim_text: str
    location_in_report: str
    severity: str  # Potential hallucination severity


@dataclass
class AuditResult:
    """Complete audit output"""
    research_id: str
    vendor_name: str
    product_name: str
    
    # What we checked
    total_facts_found: int
    facts_in_report: int
    
    # Issues found
    dropped_facts: List[DroppedFact]
    unsupported_claims: List[UnsupportedClaim]
    
    # Scoring
    confidence_score: float  # 0.0 - 1.0
    confidence_level: str  # "low", "medium", "high"
    
    # Audit metadata
    audit_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    auditor_model: str = "gpt-4o"
    audit_notes: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "research_id": self.research_id,
            "vendor_name": self.vendor_name,
            "product_name": self.product_name,
            "total_facts_found": self.total_facts_found,
            "facts_in_report": self.facts_in_report,
            "dropped_facts": [
                {
                    "category": df.fact.category,
                    "key": df.fact.key,
                    "value": df.fact.value,
                    "source_url": df.fact.source_url,
                    "drop_reason": df.drop_reason,
                    "severity": df.severity
                }
                for df in self.dropped_facts
            ],
            "unsupported_claims": [
                {
                    "claim": uc.claim_text,
                    "location": uc.location_in_report,
                    "severity": uc.severity
                }
                for uc in self.unsupported_claims
            ],
            "confidence_score": self.confidence_score,
            "confidence_level": self.confidence_level,
            "audit_timestamp": self.audit_timestamp,
            "auditor_model": self.auditor_model,
            "audit_notes": self.audit_notes
        }


class AuditAgent:
    """
    OpenAI/Codex-powered audit agent that cross-checks research output.
    
    Uses a different AI (OpenAI) than the research (Claude) for:
    - Independent verification
    - Catching blind spots
    - Strong analytical/comparison capabilities
    """
    
    def __init__(self, openai_client: openai.OpenAI = None, api_key: str = None):
        if openai_client:
            self.client = openai_client
        elif api_key:
            self.client = openai.OpenAI(api_key=api_key)
        else:
            # Will use OPENAI_API_KEY env var
            self.client = openai.OpenAI()
        
        self.model = "gpt-4o"  # Strong reasoning for audit tasks
    
    async def audit(self, research_output: ResearchOutput) -> AuditResult:
        """
        Audit the research output for completeness and accuracy.
        
        Checks:
        1. Are all found facts represented in the report?
        2. Are there claims in the report not supported by facts?
        3. What is the overall confidence level?
        """
        
        # Prepare data for comparison
        facts_json = json.dumps([{
            "category": f.category,
            "key": f.key,
            "value": f.value,
            "source_url": f.source_url,
            "source_snippet": f.source_snippet
        } for f in research_output.all_facts_found], indent=2)
        
        report = research_output.synthesized_report
        
        # Ask OpenAI to cross-check
        prompt = f"""You are an AI audit agent. Your job is to compare research facts against a synthesized report to find:

1. DROPPED FACTS: Facts that were found in research but NOT included in the report
2. UNSUPPORTED CLAIMS: Claims in the report that are NOT supported by any fact

## FACTS FOUND DURING RESEARCH:
{facts_json}

## SYNTHESIZED REPORT:
{report}

## YOUR TASK:
Compare the facts to the report carefully. Return a JSON object with:

{{
    "dropped_facts": [
        {{
            "fact_key": "the key of the dropped fact",
            "fact_value": "the value that was dropped",
            "drop_reason": "why you think it was omitted",
            "severity": "low|medium|high based on importance"
        }}
    ],
    "unsupported_claims": [
        {{
            "claim_text": "the exact claim from the report",
            "location": "which section it's in",
            "severity": "low|medium|high based on risk"
        }}
    ],
    "facts_in_report": <number of facts that ARE in the report>,
    "audit_notes": "any general observations about completeness"
}}

Be thorough. Even minor omissions matter for audit purposes.
Focus especially on:
- Investor/funding information (specific dollar amounts, investor names like a16z)
- Certification dates and statuses
- Security incident details
- Any numerical data (employee counts, valuations, customer counts)
- Specific company names or partnerships

Return ONLY the JSON, no other text."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096,
                temperature=0.1  # Low temperature for precise analysis
            )
            
            response_text = response.choices[0].message.content
            audit_data = self._parse_audit_response(response_text)
            
        except Exception as e:
            # If OpenAI fails, return a basic audit with error
            audit_data = {
                "dropped_facts": [],
                "unsupported_claims": [],
                "facts_in_report": 0,
                "audit_notes": f"Audit error: {str(e)}"
            }
        
        # Build dropped facts list
        dropped_facts = []
        for df in audit_data.get("dropped_facts", []):
            # Find the original fact
            original = self._find_original_fact(
                df.get("fact_key", ""),
                df.get("fact_value", ""),
                research_output.all_facts_found
            )
            if original:
                dropped_facts.append(DroppedFact(
                    fact=original,
                    drop_reason=df.get("drop_reason", "Not included in synthesis"),
                    severity=df.get("severity", "medium")
                ))
        
        # Build unsupported claims list
        unsupported_claims = [
            UnsupportedClaim(
                claim_text=uc.get("claim_text", ""),
                location_in_report=uc.get("location", ""),
                severity=uc.get("severity", "medium")
            )
            for uc in audit_data.get("unsupported_claims", [])
        ]
        
        # Calculate confidence score
        total_facts = len(research_output.all_facts_found)
        facts_in_report = audit_data.get("facts_in_report", 0)
        dropped_count = len(dropped_facts)
        hallucination_count = len(unsupported_claims)
        
        confidence_score = self._calculate_confidence(
            total_facts, facts_in_report, dropped_count, hallucination_count
        )
        
        confidence_level = (
            "high" if confidence_score >= 0.8 else
            "medium" if confidence_score >= 0.6 else
            "low"
        )
        
        return AuditResult(
            research_id=f"{research_output.vendor_name}_{research_output.research_timestamp}",
            vendor_name=research_output.vendor_name,
            product_name=research_output.product_name,
            total_facts_found=total_facts,
            facts_in_report=facts_in_report,
            dropped_facts=dropped_facts,
            unsupported_claims=unsupported_claims,
            confidence_score=confidence_score,
            confidence_level=confidence_level,
            audit_notes=audit_data.get("audit_notes", "")
        )
    
    def _parse_audit_response(self, response_text: str) -> Dict:
        """Parse OpenAI's JSON response"""
        try:
            # Find JSON in response
            text = response_text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            
            return json.loads(text.strip())
        except json.JSONDecodeError:
            return {
                "dropped_facts": [],
                "unsupported_claims": [],
                "facts_in_report": 0,
                "audit_notes": "Could not parse audit response"
            }
    
    def _find_original_fact(
        self, 
        key: str, 
        value: str, 
        facts: List[RawFact]
    ) -> Optional[RawFact]:
        """Find the original RawFact that matches the dropped fact"""
        for fact in facts:
            if fact.key == key or fact.value == value:
                return fact
            # Fuzzy match on key
            if key.lower() in fact.key.lower() or fact.key.lower() in key.lower():
                return fact
            # Fuzzy match on value
            if value.lower() in fact.value.lower() or fact.value.lower() in value.lower():
                return fact
        return None
    
    def _calculate_confidence(
        self,
        total_facts: int,
        facts_in_report: int,
        dropped_count: int,
        hallucination_count: int
    ) -> float:
        """
        Calculate confidence score based on audit findings.
        
        Factors:
        - Inclusion rate (facts in report / total facts)
        - Drop penalty (high severity drops hurt more)
        - Hallucination penalty (unsupported claims are serious)
        """
        if total_facts == 0:
            return 0.0
        
        # Base score: what percentage of facts made it in
        inclusion_rate = facts_in_report / total_facts if total_facts > 0 else 0
        
        # Penalty for drops (scaled by count)
        drop_penalty = min(dropped_count * 0.05, 0.3)  # Max 30% penalty
        
        # Penalty for hallucinations (more severe)
        hallucination_penalty = min(hallucination_count * 0.1, 0.4)  # Max 40% penalty
        
        score = inclusion_rate - drop_penalty - hallucination_penalty
        
        return max(0.0, min(1.0, score))


# Convenience function
async def audit_research(
    research_output: ResearchOutput, 
    openai_client: openai.OpenAI = None
) -> AuditResult:
    """Convenience function to audit research output"""
    agent = AuditAgent(openai_client=openai_client)
    return await agent.audit(research_output)
