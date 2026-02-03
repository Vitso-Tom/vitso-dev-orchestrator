import os
from typing import Dict, Any, Optional, List
from anthropic import Anthropic
import openai
import google.generativeai as genai
from models import AIProvider, JobStatus
import asyncio
import json
from sqlalchemy.orm import Session

# Research agents for vendor intelligence
from research_agent import ResearchAgent, ResearchOutput
from audit_agent import AuditAgent, AuditResult
from research_models import ResearchLog, ResearchQuery, ResearchFact

# V2 research agent with caching and verification
try:
    from research_agent_v2 import ResearchAgentV2, ResearchResult, ResearchMode, CostMode
    from research_models_v2 import VendorFact, FactVerificationLog
    V2_AVAILABLE = True
except ImportError:
    V2_AVAILABLE = False
    CostMode = None  # Placeholder


class AIOrchestrator:
    """
    Orchestrates AI interactions across multiple providers
    """
    
    def __init__(self):
        # Initialize API clients
        self.anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY", ""))
    
    def route_task(self, task_type: str, provider: AIProvider = AIProvider.AUTO) -> AIProvider:
        """
        Intelligently route tasks to the best AI provider
        """
        if provider != AIProvider.AUTO:
            return provider
        
        # Smart routing based on task type
        routing_map = {
            "planning": AIProvider.CLAUDE,
            "building": AIProvider.CLAUDE,
            "testing": AIProvider.OPENAI,
            "reviewing": AIProvider.GEMINI,
        }
        
        return routing_map.get(task_type, AIProvider.CLAUDE)

    async def plan_job(self, job_description: str, project_index: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a structured execution plan with explicit file manifest.
        The file manifest ensures all tasks know exactly what files to create.
        """
        
        project_context = ""
        if project_index:
            project_context = self._format_project_context(project_index)
        
        planning_prompt = f"""You are a software development planning expert. Create a detailed execution plan for this project:

{job_description}
{project_context}

IMPORTANT: You must create a FILE MANIFEST that specifies EXACT filenames for all code that will be generated.
This ensures consistency - if app.py references 'templates/index.html', that exact file must exist.

For Flask/Python web apps, use this standard structure:
- app.py (main application)
- templates/index.html (main HTML template)
- static/css/style.css (stylesheets)
- static/js/app.js (JavaScript)
- requirements.txt (dependencies)

Respond in this EXACT JSON format (no markdown, no extra text):
{{
  "file_manifest": {{
    "app.py": "Main Flask application with routes and API endpoints",
    "templates/index.html": "Main HTML template with Jinja2",
    "static/css/style.css": "CSS styles for the application",
    "static/js/app.js": "JavaScript for interactivity",
    "requirements.txt": "Python dependencies (flask, etc.)"
  }},
  "phases": [
    {{
      "name": "Planning",
      "tasks": [
        {{"description": "Design application architecture and data flow"}}
      ]
    }},
    {{
      "name": "Building",
      "tasks": [
        {{"description": "Create app.py with Flask routes and API endpoints", "files": ["app.py", "requirements.txt"]}},
        {{"description": "Create templates/index.html with the UI", "files": ["templates/index.html"]}},
        {{"description": "Create static/css/style.css and static/js/app.js", "files": ["static/css/style.css", "static/js/app.js"]}}
      ]
    }},
    {{
      "name": "Testing",
      "tasks": [
        {{"description": "Write unit tests for API endpoints"}}
      ]
    }},
    {{
      "name": "Sandboxing",
      "tasks": [
        {{"description": "Deploy and validate the application"}}
      ]
    }}
  ]
}}

CRITICAL RULES:
1. file_manifest must list EVERY file that will be created
2. Each Building task must specify which files it creates in the "files" array
3. Use EXACT paths - "templates/index.html" not just "index.html"
4. Template references in Python code MUST match file_manifest entries
5. For Flask apps: templates go in templates/, static files in static/css/ and static/js/

Return ONLY the JSON, nothing else."""

        try:
            result = await self._execute_claude(planning_prompt, context=None)
            if not result["success"]:
                return {"success": False, "error": result.get("error", "Planning request failed")}
            
            content = result["content"].strip()
            
            # Clean up markdown code fences if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            if content.endswith("```"):
                content = content[:-3]
            
            plan = json.loads(content.strip())
            
            # Validate file_manifest exists
            if "file_manifest" not in plan:
                plan["file_manifest"] = self._infer_file_manifest(plan)
            
            return {"success": True, "plan": plan, "tokens_used": result.get("tokens_used", 0)}
            
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Failed to parse plan JSON: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Planning failed: {str(e)}"}

    def _infer_file_manifest(self, plan: Dict) -> Dict[str, str]:
        """Fallback: infer file manifest from task descriptions if not provided"""
        manifest = {
            "app.py": "Main application",
            "templates/index.html": "Main HTML template",
            "static/css/style.css": "Stylesheet",
            "static/js/app.js": "JavaScript",
            "requirements.txt": "Dependencies"
        }
        return manifest

    def _extract_html_ids(self, html_content: str) -> List[str]:
        """Extract all element IDs from HTML content"""
        import re
        ids = re.findall(r'id=["\']([^"\']+)["\']', html_content)
        return ids
    
    def _extract_css_classes(self, html_content: str) -> List[str]:
        """Extract all CSS classes from HTML content"""
        import re
        classes = re.findall(r'class=["\']([^"\']+)["\']', html_content)
        # Flatten space-separated classes
        all_classes = []
        for c in classes:
            all_classes.extend(c.split())
        return list(set(all_classes))

    def create_building_task_prompt(
        self,
        task_description: str,
        job_title: str,
        job_description: str,
        file_manifest: Dict[str, str],
        task_files: List[str],
        previous_files: Dict[str, str] = None
    ) -> str:
        """
        Create a detailed prompt for a building task with explicit file requirements.
        Includes cross-file consistency information (HTML IDs for JS tasks, etc.)
        """
        import re
        
        # Format file manifest
        manifest_str = "\n".join([f"  - {f}: {desc}" for f, desc in file_manifest.items()])
        
        # Format task files
        task_files_str = ", ".join(task_files) if task_files else "as needed"
        
        # Extract cross-file dependencies
        html_ids = []
        css_classes = []
        api_endpoints = []
        
        if previous_files:
            for fname, content in previous_files.items():
                if fname.endswith('.html'):
                    html_ids.extend(self._extract_html_ids(content))
                    css_classes.extend(self._extract_css_classes(content))
                if fname.endswith('.py'):
                    # Extract Flask routes
                    routes = re.findall(r"@app\.route\(['\"]([^'\"]+)['\"]\)", content)
                    api_endpoints.extend(routes)
        
        # Build cross-file consistency section
        consistency_section = ""
        
        # If this task creates JS and we have HTML IDs
        is_js_task = any(f.endswith('.js') for f in task_files)
        if is_js_task and html_ids:
            consistency_section += f"\n## CRITICAL: HTML Element IDs (use these EXACTLY)\n"
            consistency_section += "The HTML file uses these element IDs. Your JavaScript MUST use these exact IDs:\n"
            for id in sorted(set(html_ids)):
                consistency_section += f"  - document.getElementById('{id}')\n"
            consistency_section += "\nDO NOT use different naming conventions (e.g., if HTML has 'cpuChart', do NOT use 'cpu-chart')\n"
        
        # If this task creates CSS and we have HTML classes
        is_css_task = any(f.endswith('.css') for f in task_files)
        if is_css_task and css_classes:
            consistency_section += f"\n## CSS Classes Used in HTML\n"
            consistency_section += "Style these classes: " + ", ".join(sorted(set(css_classes))[:30]) + "\n"
        
        # If this task creates HTML/JS and we have API endpoints
        if api_endpoints and (is_js_task or any(f.endswith('.html') for f in task_files)):
            consistency_section += f"\n## API Endpoints Available\n"
            for endpoint in api_endpoints:
                consistency_section += f"  - {endpoint}\n"
        
        # Format previous files for context
        prev_context = ""
        if previous_files:
            prev_context = "\n\n## FILES ALREADY CREATED (reference these for consistency):\n"
            for fname, content in previous_files.items():
                # Include first 60 lines max to stay under token limits
                lines = content.split('\n')[:60]
                truncated = '\n'.join(lines)
                if len(lines) == 60:
                    truncated += "\n... (truncated)"
                prev_context += f"\n--- {fname} ---\n{truncated}\n"
        
        return f"""## Project: {job_title}

{job_description}

## Your Task
{task_description}

## Files You Must Create
{task_files_str}

## Complete Project File Structure
{manifest_str}

## CRITICAL REQUIREMENTS

1. **Use EXACT filenames** - Your code blocks MUST specify the filename like this:
   
   ```python:app.py
   # Your Python code here
   ```
   
   ```html:templates/index.html
   <!-- Your HTML here -->
   ```
   
   ```css:static/css/style.css
   /* Your CSS here */
   ```
   
   ```javascript:static/js/app.js
   // Your JavaScript here
   ```

2. **File references must match** - If your Python code does:
   `render_template('index.html')` 
   Then templates/index.html MUST exist in the file manifest.

3. **Use standard Flask structure**:
   - Templates: templates/filename.html
   - CSS: static/css/filename.css
   - JS: static/js/filename.js
   - render_template() uses just the filename, not the path

4. **For Flask apps**:
   - Use `app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))`
   - This allows the port to be set via environment variable

5. **Static file references in HTML**:
   - Use: `href="{{{{ url_for('static', filename='css/style.css') }}}}"`
   - Use: `src="{{{{ url_for('static', filename='js/app.js') }}}}"`

6. **UI/UX Requirements**:
   - The current year is 2025 - use this for any copyright notices
   - Layout MUST fit on a single screen at 100% zoom (no scrolling for main content)
   - Use compact padding/margins - avoid excessive whitespace
   - Cards/panels should be appropriately sized, not oversized
   - For dashboards: use a grid layout that maximizes screen real estate
{consistency_section}
{prev_context}

Now create the files specified above. Remember to use the ```language:filename format for EVERY code block."""

    async def execute_task(
        self,
        provider: AIProvider,
        prompt: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a task with the specified AI provider
        """
        try:
            if provider == AIProvider.CLAUDE:
                return await self._execute_claude(prompt, context)
            elif provider == AIProvider.OPENAI:
                return await self._execute_openai(prompt, context)
            elif provider == AIProvider.GEMINI:
                return await self._execute_gemini(prompt, context)
            else:
                raise ValueError(f"Unknown provider: {provider}")
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "provider": provider.value
            }
    
    async def _execute_claude(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute task with Claude"""
        try:
            messages = [{"role": "user", "content": prompt}]
            
            if context and context.get("conversation_history"):
                messages = context["conversation_history"] + messages
            
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8192,  # Increased for full file generation
                messages=messages
            )
            
            return {
                "success": True,
                "content": response.content[0].text,
                "provider": "claude",
                "tokens_used": response.usage.input_tokens + response.usage.output_tokens
            }
        except Exception as e:
            return {"success": False, "error": str(e), "provider": "claude"}
    
    async def _execute_openai(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute task with OpenAI"""
        try:
            messages = [{"role": "user", "content": prompt}]
            
            if context and context.get("conversation_history"):
                messages = context["conversation_history"] + messages
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=8192
            )
            
            return {
                "success": True,
                "content": response.choices[0].message.content,
                "provider": "openai",
                "tokens_used": response.usage.total_tokens
            }
        except Exception as e:
            return {"success": False, "error": str(e), "provider": "openai"}
    
    async def _execute_gemini(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute task with Gemini"""
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(prompt)
            
            return {
                "success": True,
                "content": response.text,
                "provider": "gemini",
                "tokens_used": 0
            }
        except Exception as e:
            return {"success": False, "error": str(e), "provider": "gemini"}

    # =========================================================================
    # VENDOR RESEARCH METHODS
    # =========================================================================
    
    async def research_vendor(
        self,
        vendor_name: str,
        product_name: str = None,
        assessment_id: int = None,
        save_to_db: bool = True,
        db: Session = None
    ) -> dict:
        """
        Execute comprehensive vendor research with cross-AI verification.
        
        Flow:
        1. ResearchAgent (Claude) → web search, extract facts, synthesize report
        2. AuditAgent (OpenAI/Codex) → cross-check facts vs report, find drops/hallucinations
        3. Combine into final result with full audit trail
        
        Args:
            vendor_name: Name of the vendor to research
            product_name: Specific product (defaults to vendor_name)
            assessment_id: Optional link to an assessment
            save_to_db: Whether to persist to database
            db: SQLAlchemy Session for database operations
        
        Returns:
            dict with:
            - success: bool
            - synthesized_report: The report
            - dropped_facts: Facts found but not in report (the a16z fix)
            - unsupported_claims: Potential hallucinations
            - confidence_score: 0.0-1.0
            - confidence_level: low/medium/high
            - research_log_id: DB ID if saved
        """
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
            if save_to_db and db:
                result["research_log_id"] = self._save_research_log(
                    db, research_output, audit_result, assessment_id
                )
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "vendor_name": vendor_name,
                "product_name": product
            }

    async def research_vendor_v2(
        self,
        vendor_name: str,
        product_name: str = None,
        assessment_id: int = None,
        save_to_db: bool = True,
        db: Session = None,
        force_refresh: bool = False,
        use_cache: bool = True,
        cost_mode: str = "balanced"  # economy, balanced, quality
    ) -> dict:
        """
        Execute vendor research using V2 agent with caching and verification.
        
        V2 Features:
        - Database-first lookup (instant for repeat assessments)
        - Source URL recheck (verify stale facts without full re-search)
        - Direct vendor trust center fetch (deterministic for critical fields)
        - Falls back to web search for discovery
        
        Args:
            vendor_name: Name of the vendor to research
            product_name: Specific product (defaults to vendor_name)
            assessment_id: Optional link to an assessment
            save_to_db: Whether to persist to database
            db: SQLAlchemy Session for database operations
            force_refresh: Skip cache, do full research
            use_cache: Whether to use cached facts (default True)
        
        Returns:
            dict with:
            - success: bool
            - synthesized_report: The report
            - facts_from_cache: Count of cached facts used
            - facts_from_recheck: Count of facts verified via URL recheck
            - facts_from_direct_fetch: Count from vendor trust center
            - facts_from_web_search: Count from web search discovery
            - cache_hit_rate: Percentage of facts from cache
            - confidence_score: 0.0-1.0
            - research_log_id: DB ID if saved
        """
        if not V2_AVAILABLE:
            # Fall back to V1 if V2 not available
            return await self.research_vendor(
                vendor_name, product_name, assessment_id, save_to_db, db
            )
        
        product = product_name or vendor_name
        
        try:
            # Determine research mode
            if force_refresh:
                mode = ResearchMode.FULL
            elif use_cache:
                mode = ResearchMode.CACHED
            else:
                mode = ResearchMode.FULL
            
            # Map cost_mode string to CostMode enum
            cost_mode_enum = {
                "economy": CostMode.ECONOMY,
                "balanced": CostMode.BALANCED,
                "quality": CostMode.QUALITY
            }.get(cost_mode, CostMode.BALANCED)
            
            # Execute V2 research with cost mode
            research_agent = ResearchAgentV2(
                anthropic_client=self.anthropic_client,
                db_session=db,
                openai_client=self.openai_client,
                cost_mode=cost_mode_enum
            )
            research_result = await research_agent.research(
                vendor_name=vendor_name,
                product_name=product,
                mode=mode,
                research_log_id=assessment_id
            )
            
            # Skip audit for cache_hit - facts already verified
            if research_result.research_mode == "cache_hit":
                result = {
                    "success": True,
                    "vendor_name": vendor_name,
                    "product_name": product,
                    "research_timestamp": research_result.research_timestamp,
                    "synthesized_report": research_result.synthesized_report,
                    "structured_data": research_result.structured_data,
                    "total_facts_found": len(research_result.facts),
                    "facts_from_cache": research_result.facts_from_cache,
                    "facts_from_recheck": research_result.facts_from_recheck,
                    "facts_from_direct_fetch": research_result.facts_from_direct_fetch,
                    "facts_from_web_search": research_result.facts_from_web_search,
                    "cache_hit_rate": research_result.cache_hit_rate,
                    "research_mode": research_result.research_mode,
                    "duration_seconds": research_result.duration_seconds,
                    "facts_in_report": research_result.facts_from_cache,
                    "dropped_facts": [],
                    "unsupported_claims": [],
                    "confidence_score": 0.85,  # High confidence for verified cache
                    "confidence_level": "high",
                    "audit_notes": "Cache hit - facts previously verified",
                    "research_model": research_result.model_used,
                    "audit_model": "skipped",
                    "agent_version": "v2"
                }
                return result
            
            # V2 still uses AuditAgent for cross-checking NEW facts
            audit_agent = AuditAgent(openai_client=self.openai_client)
            
            # Convert V2 result to format audit expects
            research_output_for_audit = ResearchOutput(
                vendor_name=research_result.vendor_name,
                product_name=research_result.product_name,
                queries=[],  # V2 doesn't track queries same way
                all_facts_found=[
                    type('Fact', (), {
                        'category': f.category,
                        'key': f.key,
                        'value': f.value,
                        'source_url': f.source_url,
                        'source_title': f.source_title,
                        'source_snippet': f.source_snippet,
                        'confidence': f.confidence
                    })() for f in research_result.facts if not f.from_cache
                ],
                synthesized_report=research_result.synthesized_report,
                structured_data=research_result.structured_data or {},
                model_used=research_result.model_used
            )
            
            audit_result = await audit_agent.audit(research_output_for_audit)
            
            # Build combined result
            result = {
                "success": True,
                "vendor_name": vendor_name,
                "product_name": product,
                "research_timestamp": research_result.research_timestamp,
                
                # Report
                "synthesized_report": research_result.synthesized_report,
                "structured_data": research_result.structured_data,  # From V2 facts
                
                # V2 specific metrics
                "total_facts_found": len(research_result.facts),
                "facts_from_cache": research_result.facts_from_cache,
                "facts_from_recheck": research_result.facts_from_recheck,
                "facts_from_direct_fetch": research_result.facts_from_direct_fetch,
                "facts_from_web_search": research_result.facts_from_web_search,
                "cache_hit_rate": research_result.cache_hit_rate,
                "research_mode": research_result.research_mode,
                "duration_seconds": research_result.duration_seconds,
                
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
                
                # Models
                "research_model": research_result.model_used,
                "audit_model": audit_result.auditor_model,
                "agent_version": "v2",
                "cost_mode": cost_mode
            }
            
            # Save to V1 tables for backward compatibility
            if save_to_db and db:
                result["research_log_id"] = self._save_research_log_v2(
                    db, research_result, audit_result, assessment_id
                )
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "vendor_name": vendor_name,
                "product_name": product,
                "agent_version": "v2"
            }

    def _save_research_log_v2(
        self,
        db: Session,
        research_result: 'ResearchResult',
        audit_result: AuditResult,
        assessment_id: int = None
    ) -> int:
        """Save V2 research results to database."""
        from datetime import datetime
        
        # Create main research log (V1 table for compatibility)
        research_log = ResearchLog(
            assessment_id=assessment_id,
            vendor_name=research_result.vendor_name,
            product_name=research_result.product_name,
            research_timestamp=datetime.fromisoformat(research_result.research_timestamp),
            confidence_score=audit_result.confidence_score,
            confidence_level=audit_result.confidence_level,
            sources_consulted=research_result.facts_from_web_search + research_result.facts_from_direct_fetch,
            sources_cited=audit_result.facts_in_report,
            facts_extracted=len(research_result.facts),
            facts_dropped=len(audit_result.dropped_facts),
            gaps_identified=[],
            synthesis_model=research_result.model_used,
            synthesis_notes=f"V2 agent. Cache: {research_result.facts_from_cache}, Recheck: {research_result.facts_from_recheck}, Direct: {research_result.facts_from_direct_fetch}, Search: {research_result.facts_from_web_search}",
            synthesized_report=research_result.synthesized_report,
            structured_data=research_result.structured_data or {},
            status="completed"
        )
        db.add(research_log)
        db.flush()
        
        # Insert facts
        for fact in research_result.facts:
            research_fact = ResearchFact(
                research_log_id=research_log.id,
                fact_category=fact.category,
                fact_key=fact.key,
                fact_value=fact.value,
                source_url=fact.source_url,
                source_title=fact.source_title,
                source_snippet=fact.source_snippet,
                status="extracted",
                fact_confidence=fact.confidence
            )
            db.add(research_fact)
        
        db.commit()
        return research_log.id

    def _save_research_log(
        self,
        db: Session,
        research_output: ResearchOutput,
        audit_result: AuditResult,
        assessment_id: int = None
    ) -> int:
        """Save research results to database with full audit trail using SQLAlchemy"""
        from datetime import datetime
        
        # Create main research log
        research_log = ResearchLog(
            assessment_id=assessment_id,
            vendor_name=research_output.vendor_name,
            product_name=research_output.product_name,
            research_timestamp=datetime.fromisoformat(research_output.research_timestamp),
            confidence_score=audit_result.confidence_score,
            confidence_level=audit_result.confidence_level,
            sources_consulted=len(research_output.queries) * 10,  # Approximate
            sources_cited=audit_result.facts_in_report,
            facts_extracted=audit_result.total_facts_found,
            facts_dropped=len(audit_result.dropped_facts),
            gaps_identified=[],
            synthesis_model=research_output.model_used,
            synthesis_notes=audit_result.audit_notes,
            synthesized_report=research_output.synthesized_report,
            structured_data=research_output.structured_data,
            status="completed"
        )
        db.add(research_log)
        db.flush()  # Get the ID
        
        # Insert queries
        for seq, query in enumerate(research_output.queries):
            research_query = ResearchQuery(
                research_log_id=research_log.id,
                query_sequence=seq + 1,
                query_type="web_search",
                query_text=query.query_text,
                query_purpose=query.purpose,
                results_count=len(query.results),
                results_raw=query.results
            )
            db.add(research_query)
        
        # Insert all extracted facts
        for fact in research_output.all_facts_found:
            research_fact = ResearchFact(
                research_log_id=research_log.id,
                fact_category=fact.category,
                fact_key=fact.key,
                fact_value=fact.value,
                source_url=fact.source_url,
                source_title=fact.source_title,
                source_snippet=fact.source_snippet,
                status="extracted",
                fact_confidence=fact.confidence
            )
            db.add(research_fact)
        
        # Insert dropped facts (from audit - the a16z fix)
        for dropped in audit_result.dropped_facts:
            research_fact = ResearchFact(
                research_log_id=research_log.id,
                fact_category=dropped.fact.category,
                fact_key=dropped.fact.key,
                fact_value=dropped.fact.value,
                source_url=dropped.fact.source_url,
                source_title=dropped.fact.source_title,
                source_snippet=dropped.fact.source_snippet,
                status="dropped",
                drop_reason=dropped.drop_reason,
                fact_confidence=dropped.fact.confidence
            )
            db.add(research_fact)
        
        db.commit()
        return research_log.id

    def _format_project_context(self, project_index: Dict[str, Any]) -> str:
        """Format project index for inclusion in planning prompt."""
        if not project_index:
            return ""
        
        sections = ["\n--- EXISTING PROJECT CONTEXT ---"]
        
        if project_index.get('root'):
            sections.append(f"Project Root: {project_index['root']}")
        
        patterns = project_index.get('patterns', {})
        if patterns.get('tech_stack'):
            sections.append(f"Tech Stack: {', '.join(patterns['tech_stack'])}")
        if patterns.get('frameworks'):
            sections.append(f"Frameworks: {', '.join(patterns['frameworks'])}")
        
        structure = project_index.get('structure', [])
        if structure:
            sections.append("\nDirectory Structure:")
            for dir_path in structure[:15]:
                sections.append(f"  {dir_path}")
        
        key_files = project_index.get('key_files', {})
        if key_files:
            sections.append("\nKey Files:")
            for filepath, info in list(key_files.items())[:12]:
                sections.append(f"  {filepath}")
        
        sections.append("--- END PROJECT CONTEXT ---\n")
        
        return "\n".join(sections)
