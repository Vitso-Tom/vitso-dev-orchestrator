#!/usr/bin/env python3
"""Fix certification extraction - show all found certs, distinguish certified vs compliant"""

with open('/mnt/demo-output/job-53/app.py', 'r') as f:
    content = f.read()

old_func_start = "def extract_certifications_from_report(report: str) -> dict:"
start_idx = content.find(old_func_start)
end_idx = content.find("app = Flask")

if start_idx > 0 and end_idx > start_idx:
    new_func = '''def extract_certifications_from_report(report: str) -> dict:
    """Extract certifications - show all found, distinguish certified vs compliant."""
    report_lower = report.lower()
    
    certifications = {
        "audit": [],
        "iso": [],
        "healthcare": [],
        "government": [],
        "privacy": [],
        "industry": [],
    }
    
    def find_cert(report_lower: str, patterns: list, name: str) -> dict:
        """Find cert and determine status (certified > compliant > mentioned)."""
        found_pattern = None
        for p in patterns:
            if p in report_lower:
                found_pattern = p
                break
        
        if not found_pattern:
            return None
        
        # Get context around the mention
        idx = report_lower.find(found_pattern)
        context = report_lower[max(0,idx-100):min(len(report_lower),idx+250)]
        
        # Skip if explicitly NOT available/certified
        if any(neg in context for neg in ["not certified", "not compliant", "not available",
                                           "does not have", "no " + found_pattern.split()[0],
                                           "❌ " + name.lower()[:3]]):
            return None
        
        # Determine confidence level
        # CERTIFIED = highest confidence (has actual certificate)
        if "certified" in context and "not certified" not in context:
            return {"name": name, "status": "Certified", "icon": "✅", "confidence": "high"}
        
        # COMPLIANT = self-attested or meets requirements
        if "compliant" in context and "not compliant" not in context:
            return {"name": name, "status": "Compliant", "icon": "✅", "confidence": "medium"}
        
        # CONFLICTING INFO
        if any(w in context for w in ["conflicting", "unclear", "unconfirmed"]):
            return {"name": name, "status": "Unverified", "icon": "⚠️", "confidence": "low"}
        
        # IN PROGRESS
        if any(w in context for w in ["in progress", "pursuing", "planned", "expected"]):
            return {"name": name, "status": "In Progress", "icon": "🔄", "confidence": "medium"}
        
        # Found but status unclear - show as noted
        return {"name": name, "status": "Noted", "icon": "ℹ️", "confidence": "low"}
    
    # Audit - SOC certs
    cert = find_cert(report_lower, ["soc 2 type ii", "soc 2 type 2"], "SOC 2 Type II")
    if cert: 
        certifications["audit"].append(cert)
    else:
        cert = find_cert(report_lower, ["soc 2 type i", "soc 2 type 1"], "SOC 2 Type I")
        if cert: certifications["audit"].append(cert)
        else:
            cert = find_cert(report_lower, ["soc 2"], "SOC 2")
            if cert: certifications["audit"].append(cert)
    
    cert = find_cert(report_lower, ["soc 1"], "SOC 1")
    if cert: certifications["audit"].append(cert)
    
    # ISO Standards
    for patterns, name in [
        (["iso 27001", "iso/iec 27001"], "ISO 27001"),
        (["iso 27017", "iso/iec 27017"], "ISO 27017"),
        (["iso 27018", "iso/iec 27018"], "ISO 27018"),
        (["iso 27701", "iso/iec 27701"], "ISO 27701"),
        (["iso 42001", "iso/iec 42001"], "ISO 42001"),
    ]:
        cert = find_cert(report_lower, patterns, name)
        if cert: certifications["iso"].append(cert)
    
    # Healthcare
    for patterns, name in [
        (["hitrust r2"], "HITRUST r2"),
        (["hitrust e1"], "HITRUST e1"),
        (["hitrust i1"], "HITRUST i1"),
        (["hitrust csf", "hitrust certified"], "HITRUST CSF"),
    ]:
        cert = find_cert(report_lower, patterns, name)
        if cert:
            certifications["healthcare"].append(cert)
            break
    
    # HIPAA BAA - only show if AVAILABLE
    if "hipaa baa" in report_lower or "business associate agreement" in report_lower:
        idx = report_lower.find("hipaa baa") if "hipaa baa" in report_lower else report_lower.find("business associate")
        context = report_lower[max(0,idx-50):min(len(report_lower),idx+150)]
        # Only add if explicitly available
        if any(p in context for p in ["baa available", "offers baa", "provides baa", "signs baa", "baa offered"]):
            if not any(n in context for n in ["not available", "no baa", "does not"]):
                certifications["healthcare"].append({"name": "HIPAA BAA", "status": "Available", "icon": "✅", "confidence": "high"})
    
    # Government
    cert = find_cert(report_lower, ["fedramp high"], "FedRAMP High")
    if cert: 
        certifications["government"].append(cert)
    else:
        cert = find_cert(report_lower, ["fedramp moderate"], "FedRAMP Moderate")
        if cert: 
            certifications["government"].append(cert)
        else:
            cert = find_cert(report_lower, ["fedramp low", "fedramp tailored"], "FedRAMP Low")
            if cert: 
                certifications["government"].append(cert)
            else:
                cert = find_cert(report_lower, ["fedramp authorized", "fedramp compliant", "fedramp"], "FedRAMP")
                if cert: certifications["government"].append(cert)
    
    cert = find_cert(report_lower, ["stateramp"], "StateRAMP")
    if cert: certifications["government"].append(cert)
    
    for patterns, name in [
        (["cmmc level 3", "cmmc l3"], "CMMC L3"),
        (["cmmc level 2", "cmmc l2"], "CMMC L2"),
        (["cmmc level 1", "cmmc l1"], "CMMC L1"),
    ]:
        cert = find_cert(report_lower, patterns, name)
        if cert:
            certifications["government"].append(cert)
            break
    
    # Privacy
    cert = find_cert(report_lower, ["gdpr"], "GDPR")
    if cert: certifications["privacy"].append(cert)
    
    cert = find_cert(report_lower, ["ccpa"], "CCPA")
    if cert: certifications["privacy"].append(cert)
    
    # Industry
    cert = find_cert(report_lower, ["pci dss", "pci-dss", "payment card"], "PCI DSS")
    if cert: certifications["industry"].append(cert)
    
    cert = find_cert(report_lower, ["csa star", "csa level 1"], "CSA STAR")
    if cert: certifications["industry"].append(cert)
    
    # Remove empty categories
    return {k: v for k, v in certifications.items() if v}

'''
    
    content = content[:start_idx] + new_func + "\n" + content[end_idx:]
    
    with open('/mnt/demo-output/job-53/app.py', 'w') as f:
        f.write(content)
    print("Fixed: Shows all found certs with status")
else:
    print("Could not find function")
