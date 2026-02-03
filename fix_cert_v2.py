#!/usr/bin/env python3
"""Fix certification extraction - only show found certs, use yellow for unverified"""

with open('/mnt/demo-output/job-53/app.py', 'r') as f:
    content = f.read()

old_func_start = "def extract_certifications_from_report(report: str) -> dict:"
start_idx = content.find(old_func_start)
end_idx = content.find("app = Flask")

if start_idx > 0 and end_idx > start_idx:
    new_func = '''def extract_certifications_from_report(report: str) -> dict:
    """Extract certifications - only show what vendor HAS (green=confirmed, yellow=unverified)."""
    report_lower = report.lower()
    
    certifications = {
        "audit": [],
        "iso": [],
        "healthcare": [],
        "government": [],
        "privacy": [],
        "industry": [],
    }
    
    def check_cert(report_lower: str, patterns: list, name: str) -> dict:
        """Check if cert is mentioned and determine confidence level."""
        found = False
        for p in patterns:
            if p in report_lower:
                found = True
                break
        
        if not found:
            return None
        
        # Find context
        for p in patterns:
            if p in report_lower:
                idx = report_lower.find(p)
                break
        context = report_lower[max(0,idx-150):min(len(report_lower),idx+200)]
        
        # Skip if explicitly NOT available
        if any(neg in context for neg in ["not available", "not certified", "not compliant", 
                                           "does not offer", "does not sign", "no baa",
                                           "❌ not", "unavailable"]):
            return None
        
        # Check confidence level
        if any(w in context for w in ["conflicting", "unclear", "third-party", "unconfirmed",
                                       "lower confidence", "not confirmed", "claimed"]):
            return {"name": name, "status": "unverified", "icon": "⚠️"}
        
        if any(w in context for w in ["in progress", "planned", "expected 2026", "pursuing"]):
            return {"name": name, "status": "in_progress", "icon": "🔄"}
        
        # Confirmed
        return {"name": name, "status": "confirmed", "icon": "✅"}
    
    # Audit
    cert = check_cert(report_lower, ["soc 2 type ii", "soc 2 type 2"], "SOC 2 Type II")
    if cert: certifications["audit"].append(cert)
    else:
        cert = check_cert(report_lower, ["soc 2 type i", "soc 2 type 1"], "SOC 2 Type I")
        if cert: certifications["audit"].append(cert)
    
    cert = check_cert(report_lower, ["soc 1"], "SOC 1")
    if cert: certifications["audit"].append(cert)
    
    # ISO
    for patterns, name in [
        (["iso 27001", "iso/iec 27001"], "ISO 27001"),
        (["iso 27017"], "ISO 27017"),
        (["iso 27018"], "ISO 27018"),
        (["iso 27701"], "ISO 27701"),
        (["iso 42001"], "ISO 42001 (AI)"),
    ]:
        cert = check_cert(report_lower, patterns, name)
        if cert: certifications["iso"].append(cert)
    
    # Healthcare (only positive certs - BAA handled separately in disqualifiers)
    for patterns, name in [
        (["hitrust r2"], "HITRUST r2"),
        (["hitrust e1"], "HITRUST e1"),
        (["hitrust i1"], "HITRUST i1"),
        (["hitrust csf", "hitrust certified"], "HITRUST"),
    ]:
        cert = check_cert(report_lower, patterns, name)
        if cert:
            certifications["healthcare"].append(cert)
            break
    
    # Check for HIPAA BAA only if AVAILABLE
    if "hipaa baa" in report_lower or "business associate" in report_lower:
        idx = report_lower.find("hipaa baa") if "hipaa baa" in report_lower else report_lower.find("business associate")
        context = report_lower[max(0,idx-100):min(len(report_lower),idx+200)]
        if any(p in context for p in ["available", "offers baa", "provides baa", "signs baa", "✅"]):
            if not any(n in context for n in ["not available", "unavailable", "does not"]):
                certifications["healthcare"].append({"name": "HIPAA BAA", "status": "confirmed", "icon": "✅"})
    
    # Government
    cert = check_cert(report_lower, ["fedramp high"], "FedRAMP High")
    if cert: certifications["government"].append(cert)
    elif check_cert(report_lower, ["fedramp moderate"], "FedRAMP Moderate"):
        certifications["government"].append(check_cert(report_lower, ["fedramp moderate"], "FedRAMP Moderate"))
    elif check_cert(report_lower, ["fedramp low"], "FedRAMP Low"):
        certifications["government"].append(check_cert(report_lower, ["fedramp low"], "FedRAMP Low"))
    elif check_cert(report_lower, ["fedramp"], "FedRAMP"):
        certifications["government"].append(check_cert(report_lower, ["fedramp"], "FedRAMP"))
    
    cert = check_cert(report_lower, ["stateramp"], "StateRAMP")
    if cert: certifications["government"].append(cert)
    
    for patterns, name in [
        (["cmmc level 3", "cmmc l3"], "CMMC L3"),
        (["cmmc level 2", "cmmc l2"], "CMMC L2"),
        (["cmmc level 1", "cmmc l1"], "CMMC L1"),
    ]:
        cert = check_cert(report_lower, patterns, name)
        if cert:
            certifications["government"].append(cert)
            break
    
    # Privacy
    cert = check_cert(report_lower, ["gdpr compliant", "gdpr"], "GDPR")
    if cert: certifications["privacy"].append(cert)
    
    cert = check_cert(report_lower, ["ccpa compliant", "ccpa"], "CCPA")
    if cert: certifications["privacy"].append(cert)
    
    # Industry
    cert = check_cert(report_lower, ["pci dss", "pci-dss"], "PCI DSS")
    if cert: certifications["industry"].append(cert)
    
    cert = check_cert(report_lower, ["csa star", "csa level"], "CSA STAR")
    if cert: certifications["industry"].append(cert)
    
    # Remove empty categories
    return {k: v for k, v in certifications.items() if v}

'''
    
    content = content[:start_idx] + new_func + "\n" + content[end_idx:]
    
    with open('/mnt/demo-output/job-53/app.py', 'w') as f:
        f.write(content)
    print("Fixed: Only shows found certs, yellow for unverified")
else:
    print(f"Could not find function")
