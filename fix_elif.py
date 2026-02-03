#!/usr/bin/env python3
"""Fix the incomplete elif block"""

with open('/mnt/demo-output/job-53/app.py', 'r') as f:
    content = f.read()

old_block = '''    elif score >= 70:
    else:'''

new_block = '''    elif score >= 70:
        risk_analysis["recommendation"] = "conditional_no_go"
        risk_analysis["overall_risk"] = "high"
        risk_analysis["rationale"] = f"CONDITIONAL NO-GO: Risk score {score:.0f} requires review"
        risk_analysis["conditions"] = [{"issue": "Elevated Risk", "detail": f"Score {score:.0f}", "resolution": "Security review required"}]
        risk_analysis["disqualifiers"] = []
    elif score >= 50:
        risk_analysis["recommendation"] = "conditional_no_go"
        risk_analysis["overall_risk"] = "moderate"
        risk_analysis["rationale"] = f"CONDITIONAL NO-GO: Moderate risk ({score:.0f}) requires review"
        risk_analysis["conditions"] = [{"issue": "Moderate Risk", "detail": f"Score {score:.0f}", "resolution": "Review recommended"}]
        risk_analysis["disqualifiers"] = []
    else:'''

content = content.replace(old_block, new_block)

# Also remove duplicate research_overrides line if present
content = content.replace('    risk_analysis["research_overrides"] = overrides_applied\n    risk_analysis["research_overrides"] = overrides_applied', '    risk_analysis["research_overrides"] = overrides_applied')

with open('/mnt/demo-output/job-53/app.py', 'w') as f:
    f.write(content)

print("Fixed incomplete elif block")
