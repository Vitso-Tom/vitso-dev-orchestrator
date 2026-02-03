def apply_research_overrides(risk_analysis, user_data, research):
    """Three-tier: unqualified_go, conditional_no_go, disqualified_no_go"""
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
    report = research.get("synthesized_report", "").lower()

    overrides_applied = []
    conditions = []
    disqualifiers = []

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

    breach_info = security.get("breach_history", {})
    breach_value = breach_info.get("value", "").lower() if isinstance(breach_info, dict) else str(breach_info).lower()
    if "cve-" in report or "cve-" in breach_value:
        risk_analysis["overall_score"] = min(100, risk_analysis.get("overall_score", 0) + 15)
        overrides_applied.append("CVE_FOUND")
        conditions.append({"issue": "CVEs Found", "detail": "Security vulnerabilities disclosed", "resolution": "Review and confirm remediation"})
        if "ai_model_risk" in risk_analysis.get("category_scores", {}):
            risk_analysis["category_scores"]["ai_model_risk"] = min(100, risk_analysis["category_scores"]["ai_model_risk"] + 10)

    if "supply chain" in report or "malicious npm" in report or "malicious package" in report:
        risk_analysis["overall_score"] = min(100, risk_analysis.get("overall_score", 0) + 10)
        overrides_applied.append("SUPPLY_CHAIN_RISK")
        conditions.append({"issue": "Supply Chain Incident", "detail": "Historical incident found", "resolution": "Review and confirm remediation"})

    score = risk_analysis.get("overall_score", 0)

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
        risk_analysis["recommendation"] = "conditional_no_go"
        risk_analysis["overall_risk"] = "high"
        risk_analysis["rationale"] = f"CONDITIONAL NO-GO: Risk score {score:.0f} needs review"
        risk_analysis["conditions"] = [{"issue": "Elevated Risk", "detail": f"Score {score:.0f}", "resolution": "Security review required"}]
        risk_analysis["disqualifiers"] = []
    else:
        risk_analysis["recommendation"] = "unqualified_go"
        risk_analysis["overall_risk"] = "moderate" if score >= 40 else "low"
        risk_analysis["rationale"] = "No blocking issues - approved"
        risk_analysis["conditions"] = []
        risk_analysis["disqualifiers"] = []

    risk_analysis["research_overrides"] = overrides_applied
    return risk_analysis
