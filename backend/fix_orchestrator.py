import os
from typing import Dict, Any, Optional
from anthropic import Anthropic
import openai
import google.generativeai as genai
from models import AIProvider, JobStatus
import asyncio

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
    
    async def plan_job(self, job_description: str) -> Dict[str, Any]:
        """
        Create a structured execution plan for a job using Claude
        """
        planning_prompt = f"""You are a software development planning expert. Create a detailed execution plan for this project:

{job_description}

Provide a structured plan with these 4 phases:
1. Planning - Break down requirements and create architecture
2. Building - Implement the solution with specific tasks  
3. Testing - Define test strategies and test cases
4. Sandboxing - Deployment and validation steps

For each phase, specify 2-4 concrete, actionable tasks.

Respond in this EXACT JSON format (no markdown, no extra text):
{{
  "phases": [
    {{
      "name": "Planning",
      "tasks": [
        {{"description": "Analyze requirements and define system architecture"}},
        {{"description": "Create data models and API specifications"}}
      ]
    }},
    {{
      "name": "Building",
      "tasks": [
        {{"description": "Implement core backend logic"}},
        {{"description": "Build frontend components"}},
        {{"description": "Integrate APIs and services"}}
      ]
    }},
    {{
      "name": "Testing",
      "tasks": [
        {{"description": "Write unit tests for critical functions"}},
        {{"description": "Perform integration testing"}}
      ]
    }},
    {{
      "name": "Sandboxing",
      "tasks": [
        {{"description": "Deploy to test environment"}},
        {{"description": "Run smoke tests and validate deployment"}}
      ]
    }}
  ]
}}

Return ONLY the JSON, nothing else."""

        try:
            result = await self._execute_claude(planning_prompt, context=None)
            
            if not result["success"]:
                return {
                    "success": False,
                    "error": result.get("error", "Planning request failed")
                }
            
            import json
            content = result["content"].strip()
            
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            
            plan = json.loads(content)
            
            return {
                "success": True,
                "plan": plan,
                "tokens_used": result.get("tokens_used", 0)
            }
            
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Failed to parse plan JSON: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Planning failed: {str(e)}"
            }
    
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
                max_tokens=4096,
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
                max_tokens=4096
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
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(prompt)
            
            return {
                "success": True,
                "content": response.text,
                "provider": "gemini",
                "tokens_used": 0
            }
        except Exception as e:
            return {"success": False, "error": str(e), "provider": "gemini"}
    
    def _create_task_prompt(self, task: dict, job_description: str) -> str:
        """Create a detailed prompt for a task"""
        return f"""
Job Description: {job_description}

Task: {task['description']}
Phase: {task['phase']}

Please provide a detailed, high-quality response for this task.
"""