#!/usr/bin/env python3
"""Fix certification extraction to handle variable key names from research"""

with open('/mnt/demo-output/job-53/app.py', 'r') as f:
    content = f.read()

old_func_start = "def extract_certifications_from_research(research: dict) -> dict:"
start_idx = content.find(old_func_start)
end_idx = content.find("\napp = Flask")

if start_idx > 0 and end_idx > start_idx:
    new_func = '''def extract_certifications_from_research(research: dict) -> dict:
    """Extract certifications from structured research data - flexible key matching."""
    
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
    
    def find_key(data_dict, patterns):
        """Find a key matching any of the patterns."""
        for key in data_dict.keys():
            key_lower = key.lower()
            for pattern in patterns:
                if pattern in key_lower:
                    return key
        return None
    
    def get_value(data_dict, patterns):
        """Get value from first matching key."""
        key = find_key(data_dict, patterns)
        if key:
            val = data_dict[key]
            if isinstance(val, dict):
                return val.get("value", "").lower()
            return str(val).lower()
        return ""
    
    def determine_status(value):
        """Determine certified vs compliant vs not available."""
        v = value.lower()
        if "not available" in v or "not offered" in v or "does not" in v or "unavailable" in v:
            return None  # Don't show unavailable certs
        if "certified" in v:
            return {"status": "Certified", "icon": "🏅"}
        if "compliant" in v:
            return {"status": "Compliant", "icon": "☑️"}
        if "in progress" in v or "pursuing" in v:
            return {"status": "In Progress", "icon": "🔄"}
        if "conflicting" in v or "unclear" in v:
            return {"status": "Unverified", "icon": "⚠️"}
        # If just "available" or similar positive indicator
        if any(p in v for p in ["available", "yes", "true", "confirmed"]):
            return {"status": "Certified", "icon": "🏅"}
        return None
    
    # SOC 2 - look for soc2, soc_2, soc 2
    soc2_val = get_value(cert_data, ["soc2", "soc_2", "soc 2"]) or get_value(security_data, ["soc2", "soc_2"])
    if soc2_val:
        status = determine_status(soc2_val)
        if status:
            name = "SOC 2 Type II" if "type ii" in soc2_val or "type 2" in soc2_val or "type2" in soc2_val else "SOC 2"
            certifications["audit"].append({"name": name, **status})
    
    # ISO 27001
    iso_val = get_value(cert_data, ["iso27001", "iso_27001", "iso 27001"])
    if iso_val:
        status = determine_status(iso_val)
        if status:
            certifications["iso"].append({"name": "ISO 27001", **status})
    
    # ISO 27017
    iso17_val = get_value(cert_data, ["iso27017", "iso_27017"])
    if iso17_val:
        status = determine_status(iso17_val)
        if status:
            certifications["iso"].append({"name": "ISO 27017", **status})
    
    # ISO 27018
    iso18_val = get_value(cert_data, ["iso27018", "iso_27018"])
    if iso18_val:
        status = determine_status(iso18_val)
        if status:
            certifications["iso"].append({"name": "ISO 27018", **status})
    
    # ISO 27701
    iso701_val = get_value(cert_data, ["iso27701", "iso_27701"])
    if iso701_val:
        status = determine_status(iso701_val)
        if status:
            certifications["iso"].append({"name": "ISO 27701", **status})
    
    # HIPAA BAA - only show if AVAILABLE
    hipaa_val = get_value(cert_data, ["hipaa", "baa"]) or get_value(security_data, ["hipaa", "baa"])
    if hipaa_val and "available" in hipaa_val and "not available" not in hipaa_val and "unavailable" not in hipaa_val:
        certifications["healthcare"].append({"name": "HIPAA BAA", "status": "Available", "icon": "🏅"})
    
    # HITRUST
    hitrust_val = get_value(cert_data, ["hitrust"])
    if hitrust_val:
        status = determine_status(hitrust_val)
        if status:
            certifications["healthcare"].append({"name": "HITRUST", **status})
    
    # FedRAMP
    fedramp_val = get_value(cert_data, ["fedramp", "fed_ramp", "fed ramp"])
    if fedramp_val:
        status = determine_status(fedramp_val)
        if status:
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
    stateramp_val = get_value(cert_data, ["stateramp", "state_ramp"])
    if stateramp_val:
        status = determine_status(stateramp_val)
        if status:
            certifications["government"].append({"name": "StateRAMP", **status})
    
    # GDPR
    gdpr_val = get_value(cert_data, ["gdpr"]) or get_value(security_data, ["gdpr"])
    if gdpr_val:
        status = determine_status(gdpr_val)
        if status:
            certifications["privacy"].append({"name": "GDPR", **status})
    
    # CCPA
    ccpa_val = get_value(cert_data, ["ccpa"]) or get_value(security_data, ["ccpa"])
    if not ccpa_val:
        # Check compliance field for CCPA mention
        compliance_val = get_value(security_data, ["compliance"])
        if "ccpa" in compliance_val:
            certifications["privacy"].append({"name": "CCPA", "status": "Compliant", "icon": "☑️"})
    else:
        status = determine_status(ccpa_val)
        if status:
            certifications["privacy"].append({"name": "CCPA", **status})
    
    # CSA STAR
    csa_val = get_value(cert_data, ["csa", "star"])
    if csa_val:
        status = determine_status(csa_val)
        if status:
            if "level 2" in csa_val or "level2" in csa_val:
                name = "CSA STAR Level 2"
            elif "level 1" in csa_val or "level1" in csa_val:
                name = "CSA STAR Level 1"
            else:
                name = "CSA STAR"
            certifications["industry"].append({"name": name, **status})
    
    # PCI DSS
    pci_val = get_value(cert_data, ["pci"])
    if pci_val:
        status = determine_status(pci_val)
        if status:
            certifications["industry"].append({"name": "PCI DSS", **status})
    
    # Remove empty categories
    return {k: v for k, v in certifications.items() if v}

'''
    
    content = content[:start_idx] + new_func + "\n" + content[end_idx:]
    
    with open('/mnt/demo-output/job-53/app.py', 'w') as f:
        f.write(content)
    print("Fixed: Certification extraction now uses flexible key matching")
else:
    print(f"Could not find function. start_idx={start_idx}, end_idx={end_idx}")
