#!/usr/bin/env python3
"""Fix certification extraction to use structured_data from research"""

with open('/mnt/demo-output/job-53/app.py', 'r') as f:
    content = f.read()

old_func_start = "def extract_certifications_from_report(report: str) -> dict:"
start_idx = content.find(old_func_start)
end_idx = content.find("app = Flask")

if start_idx > 0 and end_idx > start_idx:
    # Change function signature to accept structured_data
    new_func = '''def extract_certifications_from_research(research: dict) -> dict:
    """Extract certifications from structured research data."""
    
    certifications = {
        "audit": [],
        "iso": [],
        "healthcare": [],
        "government": [],
        "privacy": [],
        "industry": [],
        "frameworks": [],
    }
    
    if not research:
        return {}
    
    structured = research.get("structured_data", {})
    cert_data = structured.get("certification", {})
    security_data = structured.get("security", {})
    
    def get_value(data_dict, key):
        """Extract value from fact dict."""
        if key in data_dict:
            val = data_dict[key]
            if isinstance(val, dict):
                return val.get("value", "").lower()
            return str(val).lower()
        return ""
    
    def determine_status(value):
        """Determine certified vs compliant vs not available."""
        v = value.lower()
        if "not available" in v or "not offered" in v or "does not" in v:
            return None  # Don't show unavailable certs
        if "certified" in v:
            return {"status": "Certified", "icon": "🏅"}
        if "compliant" in v:
            return {"status": "Compliant", "icon": "☑️"}
        if "in progress" in v or "pursuing" in v:
            return {"status": "In Progress", "icon": "🔄"}
        if "conflicting" in v or "unclear" in v:
            return {"status": "Unverified", "icon": "⚠️"}
        return {"status": "Noted", "icon": "📋"}
    
    # SOC 2
    soc2_val = get_value(cert_data, "soc2_status") or get_value(security_data, "soc2_status")
    if soc2_val:
        status = determine_status(soc2_val)
        if status:
            name = "SOC 2 Type II" if "type ii" in soc2_val or "type 2" in soc2_val else "SOC 2"
            certifications["audit"].append({"name": name, **status})
    
    # ISO 27001
    iso_val = get_value(cert_data, "iso27001_status")
    if iso_val:
        status = determine_status(iso_val)
        if status:
            certifications["iso"].append({"name": "ISO 27001", **status})
    
    # Other ISO standards
    for key, name in [("iso27017_status", "ISO 27017"), ("iso27018_status", "ISO 27018"), 
                       ("iso27701_status", "ISO 27701"), ("iso42001_status", "ISO 42001")]:
        val = get_value(cert_data, key)
        if val:
            status = determine_status(val)
            if status:
                certifications["iso"].append({"name": name, **status})
    
    # HIPAA BAA - only show if AVAILABLE
    hipaa_val = get_value(cert_data, "hipaa_baa") or get_value(cert_data, "hipaa_baa_status")
    if hipaa_val and "available" in hipaa_val and "not available" not in hipaa_val:
        certifications["healthcare"].append({"name": "HIPAA BAA", "status": "Available", "icon": "🏅"})
    
    # HITRUST
    for key, name in [("hitrust_status", "HITRUST"), ("hitrust_r2", "HITRUST r2"),
                       ("hitrust_e1", "HITRUST e1"), ("hitrust_i1", "HITRUST i1")]:
        val = get_value(cert_data, key)
        if val:
            status = determine_status(val)
            if status:
                certifications["healthcare"].append({"name": name, **status})
                break
    
    # FedRAMP
    fedramp_val = get_value(cert_data, "fedramp_status")
    if fedramp_val:
        status = determine_status(fedramp_val)
        if status:
            # Determine level
            if "high" in fedramp_val:
                name = "FedRAMP High"
            elif "moderate" in fedramp_val:
                name = "FedRAMP Moderate"
            elif "low" in fedramp_val:
                name = "FedRAMP Low"
            else:
                name = "FedRAMP"
            certifications["government"].append({"name": name, **status})
    
    # StateRAMP
    stateramp_val = get_value(cert_data, "stateramp_status")
    if stateramp_val:
        status = determine_status(stateramp_val)
        if status:
            certifications["government"].append({"name": "StateRAMP", **status})
    
    # CMMC
    cmmc_val = get_value(cert_data, "cmmc_status")
    if cmmc_val:
        status = determine_status(cmmc_val)
        if status:
            if "level 3" in cmmc_val or "l3" in cmmc_val:
                name = "CMMC Level 3"
            elif "level 2" in cmmc_val or "l2" in cmmc_val:
                name = "CMMC Level 2"
            elif "level 1" in cmmc_val or "l1" in cmmc_val:
                name = "CMMC Level 1"
            else:
                name = "CMMC"
            certifications["government"].append({"name": name, **status})
    
    # GDPR
    gdpr_val = get_value(cert_data, "gdpr_status")
    if gdpr_val:
        status = determine_status(gdpr_val)
        if status:
            certifications["privacy"].append({"name": "GDPR", **status})
    
    # CCPA
    ccpa_val = get_value(cert_data, "ccpa_status")
    if not ccpa_val:
        # Check security compliance field for CCPA mention
        compliance_val = get_value(security_data, "compliance")
        if "ccpa" in compliance_val:
            certifications["privacy"].append({"name": "CCPA", "status": "Compliant", "icon": "☑️"})
    else:
        status = determine_status(ccpa_val)
        if status:
            certifications["privacy"].append({"name": "CCPA", **status})
    
    # CSA STAR
    csa_val = get_value(cert_data, "csa_star_status")
    if csa_val:
        status = determine_status(csa_val)
        if status:
            if "level 2" in csa_val:
                name = "CSA STAR Level 2"
            elif "level 1" in csa_val:
                name = "CSA STAR Level 1"
            else:
                name = "CSA STAR"
            certifications["industry"].append({"name": name, **status})
    
    # PCI DSS
    pci_val = get_value(cert_data, "pci_dss_status")
    if pci_val:
        status = determine_status(pci_val)
        if status:
            certifications["industry"].append({"name": "PCI DSS", **status})
    
    # NIST frameworks
    for key, name in [("nist_csf_status", "NIST CSF"), ("nist_800_53_status", "NIST 800-53"),
                       ("nist_800_171_status", "NIST 800-171")]:
        val = get_value(cert_data, key)
        if val:
            status = determine_status(val)
            if status:
                certifications["frameworks"].append({"name": name, **status})
    
    # Remove empty categories
    return {k: v for k, v in certifications.items() if v}

'''
    
    content = content[:start_idx] + new_func + "\n" + content[end_idx:]
    
    # Update the call site to use new function name and pass research instead of report
    old_call = "extract_certifications_from_report(vendor_research.get('synthesized_report', '')) if vendor_research else {}"
    new_call = "extract_certifications_from_research(vendor_research) if vendor_research else {}"
    content = content.replace(old_call, new_call)
    
    with open('/mnt/demo-output/job-53/app.py', 'w') as f:
        f.write(content)
    print("Fixed: Now reads from structured_data instead of parsing report text")
else:
    print("Could not find function")
