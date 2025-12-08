import os
content = open('/home/temlock/vitso-dev-orchestrator/backend/orchestrator.py').read()
if 'async def plan_job' not in content:
    lines = content.split('\n')
    insert_pos = 0
    for i, line in enumerate(lines):
        if 'return routing_map.get(task_type, AIProvider.CLAUDE)' in line:
            insert_pos = i + 1
            break
    
    new_method = '''
    async def plan_job(self, job_description: str) -> Dict[str, Any]:
        """Create a structured execution plan for a job using Claude"""
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
    {{"name": "Planning", "tasks": [{{"description": "Analyze requirements and define system architecture"}}, {{"description": "Create data models and API specifications"}}]}},
    {{"name": "Building", "tasks": [{{"description": "Implement core backend logic"}}, {{"description": "Build frontend components"}}, {{"description": "Integrate APIs and services"}}]}},
    {{"name": "Testing", "tasks": [{{"description": "Write unit tests for critical functions"}}, {{"description": "Perform integration testing"}}]}},
    {{"name": "Sandboxing", "tasks": [{{"description": "Deploy to test environment"}}, {{"description": "Run smoke tests and validate deployment"}}]}}
  ]
}}

Return ONLY the JSON, nothing else."""

        try:
            result = await self._execute_claude(planning_prompt, context=None)
            if not result["success"]:
                return {"success": False, "error": result.get("error", "Planning request failed")}
            import json
            content = result["content"].strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            plan = json.loads(content)
            return {"success": True, "plan": plan, "tokens_used": result.get("tokens_used", 0)}
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Failed to parse plan JSON: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Planning failed: {str(e)}"}
'''
    
    lines.insert(insert_pos, new_method)
    with open('/home/temlock/vitso-dev-orchestrator/backend/orchestrator.py', 'w') as f:
        f.write('\n'.join(lines))
    print("✓ Fixed!")
else:
    print("✓ Already has plan_job method")
EOF