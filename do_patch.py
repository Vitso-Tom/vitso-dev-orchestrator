#!/usr/bin/env python3
import re

# Read current app
with open('/mnt/demo-output/job-53/app.py', 'r') as f:
    content = f.read()

# Read new functions
with open('/tmp/new_apply_func.py', 'r') as f:
    new_apply = f.read()

with open('/tmp/new_recon_func.py', 'r') as f:
    new_recon = f.read()

# Replace apply_research_overrides
pattern1 = r'def apply_research_overrides\(risk_analysis, user_data, research\):.*?(?=\ndef [a-z])'
content = re.sub(pattern1, new_apply + '\n', content, flags=re.DOTALL)

# Replace build_reconciliation  
pattern2 = r'def build_reconciliation\(user_data, research\):.*?(?=\ndef [a-z]|\Z)'
content = re.sub(pattern2, new_recon + '\n', content, flags=re.DOTALL)

with open('/mnt/demo-output/job-53/app.py', 'w') as f:
    f.write(content)

print("Patched app.py")
