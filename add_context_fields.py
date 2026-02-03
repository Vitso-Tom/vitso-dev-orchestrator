#!/usr/bin/env python3
"""Add context fields to assessment_data"""

with open('/mnt/demo-output/job-53/app.py', 'r') as f:
    content = f.read()

old_assessment = """        assessment_data = {
            'id': assessment_id,
            'tool_name': data['tool_name'],
            'vendor': data['vendor'],
            'timestamp': datetime.utcnow(),
            'inputs': data,
            'risk_analysis': risk_analysis,"""

new_assessment = """        assessment_data = {
            'id': assessment_id,
            'tool_name': data['tool_name'],
            'vendor': data['vendor'],
            'timestamp': datetime.utcnow(),
            'inputs': data,
            'business_sponsor': data.get('business_sponsor', ''),
            'requestor': data.get('requestor', ''),
            'use_cases': data.get('use_cases', ''),
            'specific_concerns': data.get('specific_concerns', ''),
            'risk_analysis': risk_analysis,"""

content = content.replace(old_assessment, new_assessment)

with open('/mnt/demo-output/job-53/app.py', 'w') as f:
    f.write(content)

print("Added context fields to assessment_data")
