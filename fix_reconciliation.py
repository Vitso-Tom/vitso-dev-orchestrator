#!/usr/bin/env python3
"""Fix reconciliation to handle Unknown inputs properly"""

with open('/mnt/demo-output/job-53/app.py', 'r') as f:
    content = f.read()

old_func = '''def build_reconciliation(user_data, research):
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
    else: status = "confirmed"'''

new_func = '''def build_reconciliation(user_data, research):
    """Compare user inputs against research with three-state handling (Yes/No/Unknown)."""
    if not research or not research.get("success"):
        return []
    structured = research.get("structured_data", {})
    cert = structured.get("certification", {})
    data_handling = structured.get("data_handling", {})
    report = research.get("synthesized_report", "").lower()
    comparisons = []

    def get_user_tristate(value):
        """Return 'yes', 'no', or 'unknown' from user input."""
        v = str(value).lower().strip()
        if v in ["true", "yes", "1"]:
            return "yes"
        elif v in ["false", "no", "0"]:
            return "no"
        return "unknown"
    
    def display_input(tristate):
        """Display value for reconciliation table."""
        if tristate == "yes": return "Yes"
        if tristate == "no": return "No"
        return "Unknown"

    # SOC 2
    user_soc2 = get_user_tristate(user_data.get("vendor_soc2", ""))
    has_soc2 = "soc 2 type ii" in report or "soc 2 type 2" in report or "soc 2 type i" in report
    if user_soc2 == "yes" and has_soc2: status = "confirmed"
    elif user_soc2 == "no" and has_soc2: status = "conflict"
    elif user_soc2 == "yes" and not has_soc2: status = "unverified"
    elif user_soc2 == "unknown" and has_soc2: status = "new_info"
    elif user_soc2 == "unknown" and not has_soc2: status = "unknown"
    else: status = "confirmed"
    comparisons.append({"field": "SOC 2 Certification", "user_input": display_input(user_soc2), "research_finding": "SOC 2 Type II Certified" if has_soc2 else "Not found", "status": status})

    # HIPAA BAA
    user_baa = get_user_tristate(user_data.get("vendor_hipaa_baa", ""))
    hipaa_sources = [cert.get("hipaa_baa_status"), cert.get("hipaa_baa_availability"), cert.get("hipaa_baa"), data_handling.get("hipaa_baa_availability"), data_handling.get("hipaa_baa")]
    hipaa_vals = [src.get("value", "").lower() if isinstance(src, dict) else str(src).lower() for src in hipaa_sources if src]
    hipaa_combined = " ".join(hipaa_vals)
    baa_denied = any(p in hipaa_combined for p in ["not available", "no baa", "not sign", "does not", "unavailable"])
    baa_confirmed = not baa_denied and any(p in hipaa_combined for p in ["available", "offers", "provides", "hipaa compliant"])
    if baa_denied:
        baa_text = "No HIPAA BAA available"
        if user_baa == "no" or user_baa == "unknown": status = "confirmed"
        else: status = "conflict"
    elif baa_confirmed:
        baa_text = "HIPAA BAA available"
        if user_baa == "yes" or user_baa == "unknown": status = "confirmed"
        else: status = "conflict"
    else:
        baa_text, status = "HIPAA BAA status unknown", "unknown"
    comparisons.append({"field": "HIPAA BAA", "user_input": display_input(user_baa), "research_finding": baa_text, "status": status})

    # ISO 27001
    has_iso = "iso 27001" in report
    comparisons.append({"field": "ISO 27001", "user_input": "--", "research_finding": "Certified" if has_iso else "Not found", "status": "new_info" if has_iso else "unknown"})

    # SSO Support
    user_sso = get_user_tristate(user_data.get("sso_support", ""))
    has_sso = "sso" in report or "saml" in report or "oidc" in report
    if user_sso == "yes" and has_sso: status = "confirmed"
    elif user_sso == "no" and has_sso: status = "conflict"
    elif user_sso == "yes" and not has_sso: status = "unverified"
    elif user_sso == "unknown" and has_sso: status = "new_info"
    elif user_sso == "unknown" and not has_sso: status = "unknown"
    else: status = "confirmed"
    comparisons.append({"field": "SSO Support", "user_input": display_input(user_sso), "research_finding": "Confirmed" if has_sso else "Not found", "status": status})

    # SCIM Support
    user_scim = get_user_tristate(user_data.get("scim_support", ""))
    has_scim = "scim" in report
    if user_scim == "yes" and has_scim: status = "confirmed"
    elif user_scim == "no" and has_scim: status = "conflict"
    elif user_scim == "yes" and not has_scim: status = "unverified"
    elif user_scim == "unknown" and has_scim: status = "new_info"
    elif user_scim == "unknown" and not has_scim: status = "unknown"
    else: status = "confirmed"'''

content = content.replace(old_func, new_func)

with open('/mnt/demo-output/job-53/app.py', 'w') as f:
    f.write(content)

print("Fixed: Reconciliation now handles Unknown inputs properly")
