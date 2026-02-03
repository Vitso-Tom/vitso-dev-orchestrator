#!/usr/bin/env python3
"""Fix the synthesis prompt to use dynamic date"""

with open('/home/temlock/vitso-dev-orchestrator/backend/research_agent_v2.py', 'r') as f:
    content = f.read()

# Find and replace the synthesis prompt
old_prompt = '''Create a vendor security research report for {vendor_name} ({product_name}).

Facts gathered (includes source type - "vendor" is authoritative, "third_party" is discovered):
{facts_json}

Create a professional markdown report with:'''

new_prompt = '''Create a vendor security research report for {vendor_name} ({product_name}).

Report Date: Use today's date which is {report_date}

Facts gathered (includes source type - "vendor" is authoritative, "third_party" is discovered):
{facts_json}

Create a professional markdown report with:'''

content = content.replace(old_prompt, new_prompt)

# Also need to add the date variable to the f-string
old_fstring = 'f"""Create a vendor security research report for {vendor_name} ({product_name}).'
new_fstring = 'f"""Create a vendor security research report for {vendor_name} ({product_name}).'

# Add import for date if not present
if 'from datetime import datetime, timedelta' not in content:
    content = content.replace('from datetime import datetime', 'from datetime import datetime, timedelta')

# Update the method to include date
old_synthesis_start = '''async def _synthesize_report(
        self, vendor_name: str, product_name: str, facts: List[FactResult]
    ) -> str:
        """
        Create synthesized markdown report from all facts.
        """
        facts_json = json.dumps'''

new_synthesis_start = '''async def _synthesize_report(
        self, vendor_name: str, product_name: str, facts: List[FactResult]
    ) -> str:
        """
        Create synthesized markdown report from all facts.
        """
        report_date = datetime.utcnow().strftime("%B %d, %Y")
        facts_json = json.dumps'''

content = content.replace(old_synthesis_start, new_synthesis_start)

# Update the prompt to use report_date
old_content_line = 'content": f"""Create a vendor security research report for {vendor_name} ({product_name}).'
new_content_line = 'content": f"""Create a vendor security research report for {vendor_name} ({product_name}).\n\nReport Date: {report_date}'

content = content.replace(old_content_line, new_content_line)

with open('/home/temlock/vitso-dev-orchestrator/backend/research_agent_v2.py', 'w') as f:
    f.write(content)

print("Fixed synthesis prompt with dynamic date")
