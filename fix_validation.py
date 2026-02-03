#!/usr/bin/env python3
"""Fix validation in helpers.py for slim form"""

with open('/mnt/demo-output/job-53/utils/helpers.py', 'r') as f:
    content = f.read()

# 1. Remove data_sensitivity from required fields
old_required = "required_fields = ['tool_name', 'vendor', 'data_sensitivity']"
new_required = "required_fields = ['tool_name', 'vendor']"
content = content.replace(old_required, new_required)

# 2. Add 'multiple' to model_provider enum and make data_sensitivity optional
old_enum = "'model_provider': ['openai', 'anthropic', 'google', 'aws', 'azure', 'self_hosted', 'other', 'unknown'],"
new_enum = "'model_provider': ['openai', 'anthropic', 'google', 'aws', 'azure', 'self_hosted', 'multiple', 'other', 'unknown'],"
content = content.replace(old_enum, new_enum)

# 3. Make data_sensitivity validation optional (allow empty)
old_sensitivity = "'data_sensitivity': ['phi', 'pii', 'confidential', 'internal', 'public', 'unknown'],"
new_sensitivity = "'data_sensitivity': ['phi', 'pii', 'confidential', 'internal', 'public', 'unknown', ''],"
content = content.replace(old_sensitivity, new_sensitivity)

with open('/mnt/demo-output/job-53/utils/helpers.py', 'w') as f:
    f.write(content)

print("Fixed validation: removed data_sensitivity from required, added 'multiple' to model_provider")
