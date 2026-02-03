#!/usr/bin/env python3
"""
Enhance apply_research_overrides to adjust category scores based on research findings.
Also fix CCPA extraction.
"""

with open('/mnt/demo-output/job-53/app.py', 'r') as f:
    content = f.read()

# Find and replace the apply_research_overrides function
old_func_start = 'def apply_research_overrides(risk_analysis, user_data, research):'
old_func_end = 'elif score >= 70:'

start_idx = content.find(old_func_start)
end_idx = content.find(old_func_end)

if start_idx == -1 or end_idx == -1:
    print(f"Could not find function boundaries: start={start_idx}, end={end_idx}")
    exit(1)

# Find the full end of the function (next elif after score >= 70)
remaining = content[end_idx:]
# Find where the function continues after "elif score >= 70:"
next_section = remaining.find('\n    elif score >= 50:')
if next_section == -1:
    next_section = remaining.find('\n    else:')

func_end_idx = end_idx + next_section if next_section != -1 else end_idx + 200

new_func = '''def apply_research_overrides(risk_analysis, user_data, research):
    """
    Three-tier recommendation with research-informed category score adjustments.
    
    Adjusts:
    - vendor_maturity: Based on SOC2, funding, employee count
    - ai_model_risk: Based on training policy, privacy mode
    - integration_risk: Based on SSO/SCIM availability
    - data_exposure: Based on encryption, retention policies
    """
    if not research or not research.get("success"):
        error_msg = research.get("error", "Unknown") if research else "Not performed"
        risk_analysis["recommendation"] = "conditional_no_go"
        risk_analysis["overall_risk"] = "high"
        risk_analysis["rationale"] = "CONDITIONAL NO-GO: Vendor research failed"
        risk_analysis["conditions"] = [{"issue": "Research Incomplete", "detail": str(error_msg)[:100], "resolution": "Retry or manually verify"}]
        risk_analysis["disqualifiers"] = []
        return risk_analysis

    structured = research.get("structured_data", {})
    cert = structured.get("certification", {})
    security = structured.get("security", {})
    data_handling = structured.get("data_handling", {})
    funding = structured.get("funding", {})
    company = structured.get("company", {}) or structured.get("company_info", {}) or structured.get("basic_info", {})
    integration = structured.get("integration", {})
    report = research.get("synthesized_report", "").lower()

    overrides_applied = []
    conditions = []
    disqualifiers = []
    
    # Initialize category_scores if not present
    if "category_scores" not in risk_analysis:
        risk_analysis["category_scores"] = {}
    cat_scores = risk_analysis["category_scores"]

    # =====================================================
    # VENDOR MATURITY ADJUSTMENTS (lower = better)
    # Default is typically 85 (high risk), reduce based on findings
    # =====================================================
    maturity_adjustments = 0
    
    # SOC 2 found -> reduce by 25
    if "soc 2" in report or "soc2" in report:
        maturity_adjustments -= 25
        overrides_applied.append("SOC2_FOUND")
    
    # Strong funding found -> reduce by 15
    funding_val = ""
    for key in funding:
        val = funding[key]
        if isinstance(val, dict):
            funding_val += " " + str(val.get("value", "")).lower()
        else:
            funding_val += " " + str(val).lower()
    if any(p in funding_val for p in ["billion", "series d", "series c", "growth", "public"]):
        maturity_adjustments -= 15
        overrides_applied.append("STRONG_FUNDING")
    elif any(p in funding_val for p in ["million", "series b", "series a"]):
        maturity_adjustments -= 10
        overrides_applied.append("MODERATE_FUNDING")
    
    # Employee count found -> reduce based on size
    employee_val = ""
    for key in company:
        if "employee" in key.lower():
            val = company[key]
            employee_val = str(val.get("value", "") if isinstance(val, dict) else val).lower()
            break
    if not employee_val:
        employee_val = report  # Fall back to report text
    
    if any(p in employee_val for p in ["1000+", "1,000", "thousands"]):
        maturity_adjustments -= 15
    elif any(p in employee_val for p in ["500", "200", "150", "100"]):
        maturity_adjustments -= 10
    elif any(p in employee_val for p in ["50", "51-"]):
        maturity_adjustments -= 5
    
    # ISO 27001 found -> reduce by 10
    if "iso 27001" in report or "iso27001" in report:
        maturity_adjustments -= 10
        overrides_applied.append("ISO27001_FOUND")
    
    # Apply maturity adjustments
    if "vendor_maturity" in cat_scores:
        cat_scores["vendor_maturity"] = max(10, cat_scores["vendor_maturity"] + maturity_adjustments)
    
    # =====================================================
    # AI MODEL RISK ADJUSTMENTS (lower = better)
    # =====================================================
    ai_adjustments = 0
    
    # No training on customer data -> reduce by 30
    if any(p in report for p in ["no training on customer", "does not train on", "never train", "opt-out", "opt out", "privacy mode"]):
        ai_adjustments -= 30
        overrides_applied.append("NO_TRAINING_FOUND")
    
    # Zero retention / privacy mode -> reduce by 15
    if any(p in report for p in ["zero retention", "no data stored", "never persisted", "data is never"]):
        ai_adjustments -= 15
        overrides_applied.append("ZERO_RETENTION")
    
    # Apply AI risk adjustments
    if "ai_model_risk" in cat_scores:
        cat_scores["ai_model_risk"] = max(10, cat_scores["ai_model_risk"] + ai_adjustments)
    
    # =====================================================
    # INTEGRATION RISK ADJUSTMENTS (lower = better)
    # =====================================================
    integration_adjustments = 0
    
    # SSO available -> reduce by 15
    if any(p in report for p in ["sso", "saml", "oidc", "single sign-on"]):
        integration_adjustments -= 15
        overrides_applied.append("SSO_FOUND")
    
    # SCIM available -> reduce by 10
    if "scim" in report:
        integration_adjustments -= 10
        overrides_applied.append("SCIM_FOUND")
    
    # Apply integration adjustments
    if "integration_risk" in cat_scores:
        cat_scores["integration_risk"] = max(5, cat_scores["integration_risk"] + integration_adjustments)
    
    # =====================================================
    # DATA EXPOSURE ADJUSTMENTS (lower = better)
    # =====================================================
    data_adjustments = 0
    
    # Strong encryption -> reduce by 10
    if any(p in report for p in ["aes-256", "aes 256", "tls 1.2", "tls 1.3"]):
        data_adjustments -= 10
        overrides_applied.append("STRONG_ENCRYPTION")
    
    # Apply data exposure adjustments
    if "data_exposure" in cat_scores:
        cat_scores["data_exposure"] = max(5, cat_scores["data_exposure"] + data_adjustments)
    
    # =====================================================
    # RECALCULATE OVERALL SCORE from adjusted categories
    # =====================================================
    weights = {
        "data_exposure": 0.20,
        "identity_surface": 0.15,
        "vendor_maturity": 0.20,
        "ai_model_risk": 0.20,
        "integration_risk": 0.10,
        "operational_risk": 0.15
    }
    
    if cat_scores:
        weighted_sum = 0
        total_weight = 0
        for cat, weight in weights.items():
            if cat in cat_scores:
                weighted_sum += cat_scores[cat] * weight
                total_weight += weight
        if total_weight > 0:
            risk_analysis["overall_score"] = weighted_sum / total_weight
    
    # =====================================================
    # PHI + BAA LOGIC (unchanged from original)
    # =====================================================
    data_types = user_data.get("data_types", [])
    has_phi = "phi" in data_types if isinstance(data_types, list) else data_types == "phi"

    hipaa_sources = [cert.get("hipaa_baa_status"), cert.get("hipaa_baa_availability"), cert.get("hipaa_baa"),
                     data_handling.get("hipaa_baa_availability"), data_handling.get("hipaa_baa")]
    hipaa_values = []
    for src in hipaa_sources:
        if src:
            val = src.get("value", "").lower() if isinstance(src, dict) else str(src).lower()
            if val: hipaa_values.append(val)
    hipaa_combined = " ".join(hipaa_values)

    baa_denied = any(p in hipaa_combined for p in ["not available", "no baa", "not sign", "does not sign", "unavailable", "not hipaa", "no hipaa", "not offered", "does not offer"])
    baa_confirmed = not baa_denied and any(p in hipaa_combined for p in ["available", "offers baa", "provides baa", "signs baa", "hipaa compliant", "hipaa ready"])

    if has_phi:
        if baa_denied:
            disqualifiers.append({"issue": "HIPAA BAA Unavailable", "detail": "Vendor confirms BAA NOT available", "resolution": "None - vendor prohibits BAA"})
            overrides_applied.append("PHI_BAA_DENIED")
        elif not baa_confirmed:
            conditions.append({"issue": "HIPAA BAA Unknown", "detail": "Could not confirm BAA availability", "resolution": "Contact vendor for BAA"})
            overrides_applied.append("PHI_BAA_UNKNOWN")

    # =====================================================
    # CVE / INCIDENT DETECTION
    # =====================================================
    if "cve-" in report:
        risk_analysis["overall_score"] = min(100, risk_analysis.get("overall_score", 0) + 15)
        overrides_applied.append("CVE_FOUND")
        conditions.append({"issue": "CVEs Found", "detail": "Security vulnerabilities disclosed", "resolution": "Review and confirm remediation"})
        if "ai_model_risk" in cat_scores:
            cat_scores["ai_model_risk"] = min(100, cat_scores["ai_model_risk"] + 10)

    if "supply chain" in report or "malicious npm" in report or "malicious package" in report:
        risk_analysis["overall_score"] = min(100, risk_analysis.get("overall_score", 0) + 10)
        overrides_applied.append("SUPPLY_CHAIN_RISK")
        conditions.append({"issue": "Supply Chain Incident", "detail": "Historical incident found", "resolution": "Review and confirm remediation"})

    # =====================================================
    # FINAL RECOMMENDATION LOGIC
    # =====================================================
    score = risk_analysis.get("overall_score", 0)
    risk_analysis["research_overrides"] = overrides_applied

    if disqualifiers:
        risk_analysis["recommendation"] = "disqualified_no_go"
        risk_analysis["overall_risk"] = "critical"
        risk_analysis["rationale"] = f"DISQUALIFIED: {disqualifiers[0]['issue']} - {disqualifiers[0]['detail']}"
        risk_analysis["disqualifiers"] = disqualifiers
        risk_analysis["conditions"] = []
    elif conditions:
        risk_analysis["recommendation"] = "conditional_no_go"
        risk_analysis["overall_risk"] = "high" if score >= 50 else "moderate"
        risk_analysis["rationale"] = f"CONDITIONAL NO-GO: {len(conditions)} issue(s) to resolve. Failure = No-Go."
        risk_analysis["conditions"] = conditions
        risk_analysis["disqualifiers"] = []
    elif score >= 85:
        risk_analysis["recommendation"] = "disqualified_no_go"
        risk_analysis["overall_risk"] = "critical"
        risk_analysis["rationale"] = f"DISQUALIFIED: Risk score {score:.0f} exceeds threshold"
        risk_analysis["disqualifiers"] = [{"issue": "Risk Score", "detail": f"Score {score:.0f} >= 85", "resolution": "None"}]
        risk_analysis["conditions"] = []
    elif score >= 70:
'''

# Replace the function
content = content[:start_idx] + new_func + content[func_end_idx:]

with open('/mnt/demo-output/job-53/app.py', 'w') as f:
    f.write(content)

print("Enhanced apply_research_overrides with category score adjustments")
