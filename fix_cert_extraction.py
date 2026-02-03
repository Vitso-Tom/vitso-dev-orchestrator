#!/usr/bin/env python3
"""Fix certification extraction to check for negation and conflicting info"""

with open('/mnt/demo-output/job-53/app.py', 'r') as f:
    content = f.read()

# Replace the naive extraction function with a smarter one
old_func_start = "def extract_certifications_from_report(report: str) -> dict:"
old_func_end = "    return certifications\n\napp = Flask"

# Find and replace the function
start_idx = content.find(old_func_start)
end_idx = content.find("app = Flask")

if start_idx > 0 and end_idx > start_idx:
    new_func = '''def extract_certifications_from_report(report: str) -> dict:
    """Extract certification mentions with context awareness."""
    report_lower = report.lower()
    
    certifications = {
        "audit": [],
        "iso": [],
        "healthcare": [],
        "government": [],
        "privacy": [],
        "industry": [],
        "other": []
    }
    
    def check_cert_status(report: str, cert_pattern: str, cert_name: str) -> dict:
        """Check if certification is confirmed, denied, or conflicting."""
        report_lower = report.lower()
        
        if cert_pattern not in report_lower:
            return None
        
        # Find the context around the certification mention
        idx = report_lower.find(cert_pattern)
        context_start = max(0, idx - 100)
        context_end = min(len(report_lower), idx + 150)
        context = report_lower[context_start:context_end]
        
        # Check for explicit denial
        denial_phrases = ["not " + cert_pattern, "no " + cert_pattern, "not certified", 
                         "not compliant", "not available", "does not", "❌", 
                         "not fedramp", "not hipaa", "not offered"]
        if any(p in context for p in denial_phrases):
            return {"name": cert_name, "status": "not_available", "icon": "❌"}
        
        # Check for conflicting information
        conflict_phrases = ["conflicting", "unclear", "unconfirmed", "third-party claims", 
                          "lower confidence", "not confirmed", "unverified"]
        if any(p in context for p in conflict_phrases):
            return {"name": cert_name, "status": "unverified", "icon": "❓"}
        
        # Check for in-progress
        progress_phrases = ["in progress", "pursuing", "planned", "expected", "2026"]
        if any(p in context for p in progress_phrases):
            return {"name": cert_name, "status": "in_progress", "icon": "🔄"}
        
        # Check for confirmed
        confirm_phrases = ["certified", "compliant", "achieved", "✅", "confirmed", "available"]
        if any(p in context for p in confirm_phrases):
            return {"name": cert_name, "status": "certified", "icon": "✅"}
        
        # Default to unverified if just mentioned without clear status
        return {"name": cert_name, "status": "unverified", "icon": "❓"}
    
    # SOC certifications
    soc2_t2 = check_cert_status(report, "soc 2 type ii", "SOC 2 Type II") or check_cert_status(report, "soc 2 type 2", "SOC 2 Type II")
    if soc2_t2:
        certifications["audit"].append(soc2_t2)
    else:
        soc2_t1 = check_cert_status(report, "soc 2 type i", "SOC 2 Type I") or check_cert_status(report, "soc 2 type 1", "SOC 2 Type I")
        if soc2_t1:
            certifications["audit"].append(soc2_t1)
    
    # ISO certifications
    for pattern, name in [("iso 27001", "ISO 27001"), ("iso 27017", "ISO 27017"), 
                          ("iso 27018", "ISO 27018"), ("iso 27701", "ISO 27701"),
                          ("iso 42001", "ISO 42001 (AI)")]:
        cert = check_cert_status(report, pattern, name)
        if cert:
            certifications["iso"].append(cert)
    
    # Healthcare - HIPAA BAA special handling
    if "hipaa baa" in report_lower or "business associate agreement" in report_lower:
        idx = report_lower.find("hipaa baa") if "hipaa baa" in report_lower else report_lower.find("business associate")
        context = report_lower[max(0,idx-100):min(len(report_lower),idx+200)]
        
        if any(p in context for p in ["not available", "no baa", "not sign", "does not sign", 
                                       "unavailable", "❌", "not offered", "does not offer"]):
            certifications["healthcare"].append({"name": "HIPAA BAA", "status": "not_available", "icon": "❌"})
        elif any(p in context for p in ["available", "offers", "provides", "signs", "✅"]):
            certifications["healthcare"].append({"name": "HIPAA BAA", "status": "available", "icon": "✅"})
        else:
            certifications["healthcare"].append({"name": "HIPAA BAA", "status": "unknown", "icon": "❓"})
    
    # HITRUST
    for pattern, name in [("hitrust r2", "HITRUST r2"), ("hitrust e1", "HITRUST e1"),
                          ("hitrust i1", "HITRUST i1"), ("hitrust csf", "HITRUST CSF")]:
        cert = check_cert_status(report, pattern, name)
        if cert:
            certifications["healthcare"].append(cert)
            break
    
    # Government - FedRAMP with careful checking
    fedramp = check_cert_status(report, "fedramp", "FedRAMP")
    if fedramp:
        # Check for specific level
        if "fedramp high" in report_lower:
            fedramp["name"] = "FedRAMP High"
        elif "fedramp moderate" in report_lower:
            fedramp["name"] = "FedRAMP Moderate"
        certifications["government"].append(fedramp)
    
    # StateRAMP
    stateramp = check_cert_status(report, "stateramp", "StateRAMP")
    if stateramp:
        certifications["government"].append(stateramp)
    
    # CMMC
    for pattern, name in [("cmmc level 3", "CMMC L3"), ("cmmc level 2", "CMMC L2"),
                          ("cmmc level 1", "CMMC L1"), ("cmmc l3", "CMMC L3"),
                          ("cmmc l2", "CMMC L2"), ("cmmc l1", "CMMC L1")]:
        cert = check_cert_status(report, pattern, name)
        if cert:
            certifications["government"].append(cert)
            break
    
    # Privacy
    gdpr = check_cert_status(report, "gdpr", "GDPR")
    if gdpr:
        certifications["privacy"].append(gdpr)
    
    ccpa = check_cert_status(report, "ccpa", "CCPA")
    if ccpa:
        certifications["privacy"].append(ccpa)
    
    # Industry
    pci = check_cert_status(report, "pci dss", "PCI DSS") or check_cert_status(report, "pci-dss", "PCI DSS")
    if pci:
        certifications["industry"].append(pci)
    
    csa = check_cert_status(report, "csa star", "CSA STAR")
    if csa:
        certifications["industry"].append(csa)
    
    return certifications

'''
    
    content = content[:start_idx] + new_func + "\n" + content[end_idx:]
    
    with open('/mnt/demo-output/job-53/app.py', 'w') as f:
        f.write(content)
    print("Updated certification extraction with context awareness")
else:
    print(f"Could not find function. start_idx={start_idx}, end_idx={end_idx}")
