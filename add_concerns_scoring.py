#!/usr/bin/env python3
"""Add specific_concerns impact on operational risk scoring"""

with open('/mnt/demo-output/job-53/app.py', 'r') as f:
    content = f.read()

# Find the operational risk section in apply_research_overrides and add concern-based adjustment
# We'll add it after the data exposure adjustments section

old_section = '''    # Apply data exposure adjustments
    if "data_exposure" in cat_scores:
        cat_scores["data_exposure"] = max(5, cat_scores["data_exposure"] + data_adjustments)
    
    # =====================================================
    # RECALCULATE OVERALL SCORE from adjusted categories'''

new_section = '''    # Apply data exposure adjustments
    if "data_exposure" in cat_scores:
        cat_scores["data_exposure"] = max(5, cat_scores["data_exposure"] + data_adjustments)
    
    # =====================================================
    # OPERATIONAL RISK ADJUSTMENTS (based on user context)
    # =====================================================
    operational_adjustments = 0
    
    specific_concerns = user_data.get("specific_concerns", "").lower()
    if specific_concerns:
        # Enforcement/detection gaps mentioned
        if any(p in specific_concerns for p in ["no way of blocking", "no way to block", "cannot enforce", 
               "can't enforce", "no enforcement", "cannot detect", "can't detect", "no detection",
               "no control", "unable to prevent", "unable to block"]):
            operational_adjustments += 15
            overrides_applied.append("ENFORCEMENT_GAP_ACKNOWLEDGED")
        
        # PHI exposure risk mentioned
        if any(p in specific_concerns for p in ["phi may", "phi could", "patient data", "production support",
               "log harvesting", "local files"]):
            operational_adjustments += 10
            overrides_applied.append("PHI_EXPOSURE_RISK_NOTED")
        
        # Policy-only controls (no technical enforcement)
        if any(p in specific_concerns for p in ["instructed not to", "told not to", "policy", 
               "training only", "awareness only"]):
            operational_adjustments += 5
            overrides_applied.append("POLICY_ONLY_CONTROL")
    
    # Apply operational risk adjustments
    if "operational_risk" in cat_scores and operational_adjustments > 0:
        cat_scores["operational_risk"] = min(100, cat_scores["operational_risk"] + operational_adjustments)
    
    # =====================================================
    # RECALCULATE OVERALL SCORE from adjusted categories'''

content = content.replace(old_section, new_section)

with open('/mnt/demo-output/job-53/app.py', 'w') as f:
    f.write(content)

print("Added specific_concerns impact on operational risk")
