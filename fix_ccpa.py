#!/usr/bin/env python3
"""Fix CCPA extraction - check for ccpa in cert data"""

with open('/mnt/demo-output/job-53/app.py', 'r') as f:
    content = f.read()

# The current CCPA logic checks security_data but the fact is stored as "ccpa_compliance" in cert
# Let me check what keys we have and fix the pattern matching

old_ccpa = '''    # CCPA
    ccpa_val = get_value(cert_data, ["ccpa"]) or get_value(security_data, ["ccpa"])
    if not ccpa_val:
        # Check compliance field for CCPA mention
        compliance_val = get_value(security_data, ["compliance"])
        if "ccpa" in compliance_val:
            certifications["privacy"].append({"name": "CCPA", "status": "Compliant", "icon": "☑️"})
    else:
        status = determine_status(ccpa_val)
        if status:
            certifications["privacy"].append({"name": "CCPA", **status})'''

new_ccpa = '''    # CCPA - check multiple possible key patterns
    ccpa_val = get_value(cert_data, ["ccpa"]) or get_value(security_data, ["ccpa"])
    if ccpa_val:
        status = determine_status(ccpa_val)
        if status:
            certifications["privacy"].append({"name": "CCPA", **status})
    else:
        # Check compliance field or report for CCPA mention
        compliance_val = get_value(security_data, ["compliance"])
        if "ccpa" in compliance_val:
            certifications["privacy"].append({"name": "CCPA", "status": "Compliant", "icon": "☑️"})
        elif "ccpa" in str(research.get("synthesized_report", "")).lower():
            # Found in report but not structured data
            certifications["privacy"].append({"name": "CCPA", "status": "Compliant", "icon": "☑️"})'''

content = content.replace(old_ccpa, new_ccpa)

with open('/mnt/demo-output/job-53/app.py', 'w') as f:
    f.write(content)

print("Fixed CCPA extraction to check report text as fallback")
