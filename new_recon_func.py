def build_reconciliation(user_data, research):
    """Compare user inputs against research with three-state BAA."""
    if not research or not research.get("success"):
        return []
    structured = research.get("structured_data", {})
    cert = structured.get("certification", {})
    data_handling = structured.get("data_handling", {})
    report = research.get("synthesized_report", "").lower()
    comparisons = []

    user_soc2 = user_data.get("vendor_soc2", "").lower()
    user_says_soc2 = user_soc2 in ["true", "yes", "1"]
    has_soc2 = "soc 2 type ii" in report or "soc 2 type 2" in report or "soc 2 type i" in report
    if user_says_soc2 and has_soc2: status = "confirmed"
    elif not user_says_soc2 and has_soc2: status = "conflict"
    elif user_says_soc2 and not has_soc2: status = "unverified"
    else: status = "confirmed"
    comparisons.append({"field": "SOC 2 Certification", "user_input": "Yes" if user_says_soc2 else "No", "research_finding": "SOC 2 Type II Certified" if has_soc2 else "Not found", "status": status})

    user_baa = user_data.get("vendor_hipaa_baa", "").lower()
    user_says_baa = user_baa in ["true", "yes", "1"]
    hipaa_sources = [cert.get("hipaa_baa_status"), cert.get("hipaa_baa_availability"), cert.get("hipaa_baa"), data_handling.get("hipaa_baa_availability"), data_handling.get("hipaa_baa")]
    hipaa_vals = [src.get("value", "").lower() if isinstance(src, dict) else str(src).lower() for src in hipaa_sources if src]
    hipaa_combined = " ".join(hipaa_vals)
    baa_denied = any(p in hipaa_combined for p in ["not available", "no baa", "not sign", "does not", "unavailable"])
    baa_confirmed = not baa_denied and any(p in hipaa_combined for p in ["available", "offers", "provides", "hipaa compliant"])
    if baa_denied:
        baa_text, status = "No HIPAA BAA available", "confirmed" if not user_says_baa else "conflict"
    elif baa_confirmed:
        baa_text, status = "HIPAA BAA available", "confirmed" if user_says_baa else "conflict"
    else:
        baa_text, status = "HIPAA BAA status unknown", "unknown"
    comparisons.append({"field": "HIPAA BAA", "user_input": "Yes" if user_says_baa else "No", "research_finding": baa_text, "status": status})

    has_iso = "iso 27001" in report
    comparisons.append({"field": "ISO 27001", "user_input": "--", "research_finding": "Certified" if has_iso else "Not found", "status": "new_info" if has_iso else "unknown"})

    user_sso = user_data.get("sso_support", "").lower() in ["true", "yes", "1"]
    has_sso = "sso" in report or "saml" in report or "oidc" in report
    if user_sso and has_sso: status = "confirmed"
    elif not user_sso and has_sso: status = "conflict"
    elif user_sso and not has_sso: status = "unverified"
    else: status = "confirmed"
    comparisons.append({"field": "SSO Support", "user_input": "Yes" if user_sso else "No", "research_finding": "Confirmed" if has_sso else "Not found", "status": status})

    user_scim = user_data.get("scim_support", "").lower() in ["true", "yes", "1"]
    has_scim = "scim" in report
    if user_scim and has_scim: status = "confirmed"
    elif not user_scim and has_scim: status = "conflict"
    elif user_scim and not has_scim: status = "unverified"
    else: status = "confirmed"
    comparisons.append({"field": "SCIM Provisioning", "user_input": "Yes" if user_scim else "No", "research_finding": "Confirmed" if has_scim else "Not found", "status": status})

    user_train = user_data.get("training_on_inputs", "").lower()
    has_optout = any(p in report for p in ["opt-out", "opt out", "privacy mode", "zero retention"])
    comparisons.append({"field": "Training Opt-Out", "user_input": user_train.replace("_", " ").title() if user_train else "Unknown", "research_finding": "Available" if has_optout else "Not found", "status": "new_info" if has_optout else "unknown"})

    has_incidents = any(p in report for p in ["cve-", "breach", "incident", "malicious"])
    user_inc = user_data.get("vendor_incident_history", "")
    comparisons.append({"field": "Security Incidents", "user_input": user_inc[:30] if user_inc else "unknown", "research_finding": "Incidents found - see report" if has_incidents else "None found", "status": "new_info" if has_incidents else "unknown"})

    return comparisons
