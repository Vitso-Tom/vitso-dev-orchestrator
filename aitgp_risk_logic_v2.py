"""
AITGP Risk Analysis Logic V2
Three-tier recommendation system:
- unqualified_go (Green): No issues, approve
- conditional_no_go (Amber): Resolvable blockers, must resolve OR no-go  
- disqualified_no_go (Red): Definitive blockers, no path to approval
"""

def apply_research_overrides(risk_analysis, user_data, research):
    """
    Apply hard rules based on research findings.
    Uses structured_data for reliable boolean checks.
    
    Three-tier outcomes:
    - unqualified_go: No blocking issues found
    - conditional_no_go: Issues that MUST be resolved before approval
    - disqualified_no_go: Definitive blockers with no resolution path
    """
    if not research or not research.get("success"):
        return risk_analysis

    structured = research.get("structured_data", {})
    cert = structured.get("certification", {})
    security = structured.get("security", {})
    data_handling = structured.get("data_handling", {})

    overrides_applied = []
    conditions_to_resolve = []  # For conditional_no_go
    disqualifiers = []  # For disqualified_no_go

    # === ANALYZE PHI + HIPAA BAA STATUS ===
    data_types = user_data.get("data_types", [])
    has_phi = "phi" in data_types if isinstance(data_types, list) else data_types == "phi"

    # Check ALL possible locations for HIPAA BAA info
    hipaa_sources = [
        cert.get("hipaa_baa_status"),
        cert.get("hipaa_baa_availability"),
        cert.get("hipaa_baa"),
        data_handling.get("hipaa_baa_availability"),
        data_handling.get("hipaa_baa"),
        data_handling.get("baa_status"),
    ]
    
    # Combine all HIPAA BAA values found
    hipaa_baa_values = []
    for source in hipaa_sources:
        if source:
            val = source.get("value", "").lower() if isinstance(source, dict) else str(source).lower()
            if val:
                hipaa_baa_values.append(val)
    
    hipaa_baa_combined = " ".join(hipaa_baa_values)
    
    # Determine BAA status with three states
    # DENIED: Explicit statements that BAA is not available
    baa_denied_phrases = [
        "not available", "no baa", "not sign", "does not sign",
        "unavailable", "not hipaa", "no hipaa", "not offered", 
        "does not offer", "does not provide", "confirmed not",
        "explicitly not", "cannot provide", "will not sign"
    ]
    baa_denied = any(phrase in hipaa_baa_combined for phrase in baa_denied_phrases)
    
    # CONFIRMED: Explicit statements that BAA IS available
    baa_confirmed_phrases = [
        "available", "offers baa", "provides baa", "signs baa",
        "baa offered", "hipaa compliant", "hipaa ready",
        "will sign", "can provide baa"
    ]
    # Only check confirmed if not denied (denied takes precedence)
    baa_confirmed = not baa_denied and any(phrase in hipaa_baa_combined for phrase in baa_confirmed_phrases)
    
    # UNKNOWN: No definitive information either way
    baa_unknown = not baa_denied and not baa_confirmed

    # === APPLY PHI + BAA RULES ===
    if has_phi:
        if baa_denied:
            # DISQUALIFIED: Vendor explicitly refuses BAA - no resolution path
            disqualifiers.append({
                "issue": "HIPAA BAA Unavailable",
                "detail": "Vendor explicitly confirms BAA is NOT available",
                "resolution": "None - vendor policy prohibits BAA"
            })
            overrides_applied.append("PHI_BAA_DENIED")
            
        elif baa_unknown:
            # CONDITIONAL: BAA status unknown - must verify before approval
            conditions_to_resolve.append({
                "issue": "HIPAA BAA Status Unknown",
                "detail": "Research could not confirm BAA availability",
                "resolution": "Contact vendor to confirm BAA availability and obtain signed BAA"
            })
            overrides_applied.append("PHI_BAA_UNKNOWN")
            
        # If baa_confirmed and has_phi, no override needed - proceed normally

    # === HARD RULE 2: Active CVEs increase risk ===
    breach_info = security.get("breach_history", {})
    breach_value = breach_info.get("value", "").lower() if isinstance(breach_info, dict) else str(breach_info).lower()
    report = research.get("synthesized_report", "").lower()
    
    if "cve-" in report or "cve-" in breach_value:
        cve_bump = 15
        risk_analysis["overall_score"] = min(100, risk_analysis.get("overall_score", 0) + cve_bump)
        overrides_applied.append("CVE_FOUND")
        
        # Add as condition to review (not disqualifier)
        conditions_to_resolve.append({
            "issue": "Active CVEs Found",
            "detail": "Security vulnerabilities disclosed - review for applicability",
            "resolution": "Review CVE details and confirm vendor remediation status"
        })
        
        if "ai_model_risk" in risk_analysis.get("category_scores", {}):
            risk_analysis["category_scores"]["ai_model_risk"] = min(100,
                risk_analysis["category_scores"]["ai_model_risk"] + 10)

    # === HARD RULE 3: Supply chain incidents ===
    if "supply chain" in report or "malicious npm" in report or "malicious package" in report:
        risk_analysis["overall_score"] = min(100, risk_analysis.get("overall_score", 0) + 10)
        overrides_applied.append("SUPPLY_CHAIN_RISK")
        
        conditions_to_resolve.append({
            "issue": "Supply Chain Incident",
            "detail": "Historical supply chain security incident identified",
            "resolution": "Review incident details and confirm vendor remediation"
        })

    # === DETERMINE FINAL RECOMMENDATION ===
    score = risk_analysis.get("overall_score", 0)
    
    if disqualifiers:
        # RED: Disqualified - definitive blockers
        risk_analysis["recommendation"] = "disqualified_no_go"
        risk_analysis["recommendation_display"] = "DISQUALIFIED"
        risk_analysis["recommendation_color"] = "red"
        risk_analysis["overall_risk"] = "critical"
        risk_analysis["rationale"] = f"DISQUALIFIED: {disqualifiers[0]['issue']} - {disqualifiers[0]['detail']}"
        risk_analysis["disqualifiers"] = disqualifiers
        risk_analysis["conditions"] = []  # No conditions matter if disqualified
        
    elif conditions_to_resolve:
        # AMBER: Conditional No-Go - must resolve before approval
        risk_analysis["recommendation"] = "conditional_no_go"
        risk_analysis["recommendation_display"] = "CONDITIONAL NO-GO"
        risk_analysis["recommendation_color"] = "amber"
        risk_analysis["overall_risk"] = "high" if score >= 50 else "moderate"
        risk_analysis["rationale"] = f"CONDITIONAL NO-GO: {len(conditions_to_resolve)} issue(s) must be resolved before approval"
        risk_analysis["conditions"] = conditions_to_resolve
        risk_analysis["disqualifiers"] = []
        
    elif score >= 85:
        # RED: Score-based disqualification
        risk_analysis["recommendation"] = "disqualified_no_go"
        risk_analysis["recommendation_display"] = "DISQUALIFIED"
        risk_analysis["recommendation_color"] = "red"
        risk_analysis["overall_risk"] = "critical"
        risk_analysis["rationale"] = f"Risk score {score:.0f} exceeds maximum threshold"
        risk_analysis["disqualifiers"] = [{"issue": "Risk Score", "detail": f"Score {score:.0f} >= 85", "resolution": "None"}]
        risk_analysis["conditions"] = []
        
    elif score >= 70:
        # AMBER: High score warrants conditions
        risk_analysis["recommendation"] = "conditional_no_go"
        risk_analysis["recommendation_display"] = "CONDITIONAL NO-GO"
        risk_analysis["recommendation_color"] = "amber"
        risk_analysis["overall_risk"] = "high"
        risk_analysis["rationale"] = f"Risk score {score:.0f} requires additional review"
        risk_analysis["conditions"] = [{
            "issue": "Elevated Risk Score",
            "detail": f"Overall risk score of {score:.0f} indicates significant concerns",
            "resolution": "Conduct detailed security review and obtain risk acceptance"
        }]
        risk_analysis["disqualifiers"] = []
        
    else:
        # GREEN: Unqualified Go
        risk_analysis["recommendation"] = "unqualified_go"
        risk_analysis["recommendation_display"] = "GO"
        risk_analysis["recommendation_color"] = "green"
        if score >= 40:
            risk_analysis["overall_risk"] = "moderate"
        else:
            risk_analysis["overall_risk"] = "low"
        risk_analysis["rationale"] = "No blocking issues identified"
        risk_analysis["conditions"] = []
        risk_analysis["disqualifiers"] = []

    # Track what we did
    risk_analysis["research_overrides"] = overrides_applied

    return risk_analysis


def build_reconciliation(user_data, research):
    """
    Compare user inputs against research findings.
    Returns list of comparison items with status.
    
    Status values:
    - confirmed: User input matches research finding
    - conflict: User input contradicts research finding
    - unverified: User claimed something research couldn't verify
    - unknown: Research couldn't determine status
    - new_info: Research found info user didn't provide
    """
    if not research or not research.get("success"):
        return []
    
    structured = research.get("structured_data", {})
    cert = structured.get("certification", {})
    data_handling = structured.get("data_handling", {})
    security = structured.get("security", {})
    integration = structured.get("integration", {})
    
    report = research.get("synthesized_report", "").lower()
    comparisons = []

    # === SOC 2 ===
    user_soc2 = user_data.get("vendor_soc2", "").lower()
    user_says_soc2 = user_soc2 in ["true", "yes", "1"]
    research_has_soc2 = "soc 2 type ii" in report or "soc 2 type 2" in report or "soc 2 type i" in report

    if user_says_soc2 and research_has_soc2:
        status = "confirmed"
    elif not user_says_soc2 and research_has_soc2:
        status = "conflict"
    elif user_says_soc2 and not research_has_soc2:
        status = "unverified"
    else:
        status = "confirmed"  # Both say no

    comparisons.append({
        "field": "SOC 2 Certification",
        "user_input": "Yes" if user_says_soc2 else "No",
        "research_finding": "SOC 2 Type II Certified" if research_has_soc2 else "Not found",
        "status": status
    })

    # === HIPAA BAA (Three-state logic) ===
    user_baa = user_data.get("vendor_hipaa_baa", "").lower()
    user_says_baa = user_baa in ["true", "yes", "1"]

    # Gather all HIPAA BAA info from structured data
    hipaa_sources = [
        cert.get("hipaa_baa_status"),
        cert.get("hipaa_baa_availability"),
        cert.get("hipaa_baa"),
        data_handling.get("hipaa_baa_availability"),
        data_handling.get("hipaa_baa"),
    ]
    
    hipaa_values = []
    for source in hipaa_sources:
        if source:
            val = source.get("value", "").lower() if isinstance(source, dict) else str(source).lower()
            if val:
                hipaa_values.append(val)
    
    hipaa_combined = " ".join(hipaa_values)
    
    # Determine BAA status with explicit phrases
    baa_denied_phrases = [
        "not available", "no baa", "not sign", "does not sign",
        "unavailable", "not hipaa", "no hipaa", "not offered",
        "does not offer", "does not provide", "confirmed not"
    ]
    baa_confirmed_phrases = [
        "available", "offers baa", "provides baa", "signs baa",
        "baa offered", "hipaa compliant", "hipaa ready", "will sign"
    ]
    
    baa_denied = any(phrase in hipaa_combined for phrase in baa_denied_phrases)
    baa_confirmed = not baa_denied and any(phrase in hipaa_combined for phrase in baa_confirmed_phrases)
    baa_unknown = not baa_denied and not baa_confirmed

    # Determine research finding text and status
    if baa_denied:
        research_baa_text = "No HIPAA BAA available"
        if user_says_baa:
            status = "conflict"  # User says yes, research says explicitly no
        else:
            status = "confirmed"  # User says no, research confirms no
    elif baa_confirmed:
        research_baa_text = "HIPAA BAA available"
        if user_says_baa:
            status = "confirmed"  # User says yes, research confirms yes
        else:
            status = "conflict"  # User says no, research says yes
    else:
        research_baa_text = "HIPAA BAA status unknown"
        if user_says_baa:
            status = "unverified"  # User claims yes but research couldn't confirm
        else:
            status = "unknown"  # Neither user nor research knows

    comparisons.append({
        "field": "HIPAA BAA",
        "user_input": "Yes" if user_says_baa else "No",
        "research_finding": research_baa_text,
        "status": status
    })

    # === ISO 27001 ===
    research_iso = "iso 27001" in report or "iso/iec 27001" in report
    comparisons.append({
        "field": "ISO 27001",
        "user_input": "--",
        "research_finding": "Certified" if research_iso else "Not found",
        "status": "new_info" if research_iso else "unknown"
    })

    # === SSO Support ===
    user_sso = user_data.get("sso_support", "").lower()
    user_says_sso = user_sso in ["true", "yes", "1"]
    research_sso = "sso" in report or "saml" in report or "oidc" in report

    if user_says_sso and research_sso:
        status = "confirmed"
    elif not user_says_sso and research_sso:
        status = "conflict"
    elif user_says_sso and not research_sso:
        status = "unverified"
    else:
        status = "confirmed"

    comparisons.append({
        "field": "SSO Support",
        "user_input": "Yes" if user_says_sso else "No",
        "research_finding": "Confirmed" if research_sso else "Not found",
        "status": status
    })

    # === SCIM Provisioning ===
    user_scim = user_data.get("scim_provisioning", "").lower()
    user_says_scim = user_scim in ["true", "yes", "1"]
    research_scim = "scim" in report

    if user_says_scim and research_scim:
        status = "confirmed"
    elif not user_says_scim and research_scim:
        status = "conflict"
    elif user_says_scim and not research_scim:
        status = "unverified"
    else:
        status = "confirmed"

    comparisons.append({
        "field": "SCIM Provisioning",
        "user_input": "Yes" if user_says_scim else "No",
        "research_finding": "Confirmed" if research_scim else "Not found",
        "status": status
    })

    # === Training Opt-Out ===
    user_training = user_data.get("training_opt_out", "").lower()
    # Check for training opt-out in report
    has_training_optout = any(phrase in report for phrase in [
        "opt out", "opt-out", "no training", "zero retention",
        "never train", "not used for training", "privacy mode"
    ])
    
    if user_training == "unknown":
        user_display = "Unknown"
        if has_training_optout:
            status = "new_info"
        else:
            status = "unknown"
    elif user_training in ["true", "yes", "available", "opt out available"]:
        user_display = "Opt Out Available"
        status = "confirmed" if has_training_optout else "unverified"
    else:
        user_display = "No"
        status = "conflict" if has_training_optout else "confirmed"

    comparisons.append({
        "field": "Training Opt-Out",
        "user_input": user_display,
        "research_finding": "Available" if has_training_optout else "Not found",
        "status": status
    })

    # === Security Incidents ===
    user_incidents = user_data.get("security_incidents", "").lower()
    has_incidents = any(phrase in report for phrase in [
        "cve-", "breach", "incident", "vulnerability", "exploit",
        "malicious", "attack", "compromise"
    ])
    
    if user_incidents == "unknown":
        user_display = "unknown"
        status = "new_info" if has_incidents else "unknown"
    elif user_incidents in ["true", "yes", "1"]:
        user_display = "Yes"
        status = "confirmed" if has_incidents else "unverified"
    else:
        user_display = "No"
        status = "conflict" if has_incidents else "confirmed"

    comparisons.append({
        "field": "Security Incidents",
        "user_input": user_display,
        "research_finding": "Incidents found - see report" if has_incidents else "None found",
        "status": status
    })

    return comparisons
