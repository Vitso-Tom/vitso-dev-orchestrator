#!/usr/bin/env python3
"""Fix remaining reconciliation issues"""

with open('/mnt/demo-output/job-53/app.py', 'r') as f:
    content = f.read()

# Fix SCIM display
old_scim = 'comparisons.append({"field": "SCIM Provisioning", "user_input": "Yes" if user_scim else "No"'
new_scim = 'comparisons.append({"field": "SCIM Provisioning", "user_input": display_input(user_scim)'
content = content.replace(old_scim, new_scim)

with open('/mnt/demo-output/job-53/app.py', 'w') as f:
    f.write(content)

print("Fixed SCIM display")
