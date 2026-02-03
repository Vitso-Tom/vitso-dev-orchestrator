#!/usr/bin/env python3
"""Add missing context fields to helpers.py"""

with open('/mnt/demo-output/job-53/utils/helpers.py', 'r') as f:
    content = f.read()

old_fields = "'business_sponsor', 'timeline_pressure', 'executive_pressure',\n        'competing_priorities', 'budget_constraints', 'vendor_soc2_report_date'"

new_fields = "'business_sponsor', 'requestor', 'use_cases', 'specific_concerns',\n        'timeline_pressure', 'executive_pressure',\n        'competing_priorities', 'budget_constraints', 'vendor_soc2_report_date'"

content = content.replace(old_fields, new_fields)

with open('/mnt/demo-output/job-53/utils/helpers.py', 'w') as f:
    f.write(content)

print("Added requestor, use_cases, specific_concerns to string_fields")
