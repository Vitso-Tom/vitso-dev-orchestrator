#!/usr/bin/env python3
"""Fix certification status detection - check context more carefully"""

with open('/mnt/demo-output/job-53/app.py', 'r') as f:
    content = f.read()

old_func_start = "def extract_certifications_from_report(report: str) -> dict:"
start_idx = content.find(old_func_start)
end_idx = content.find("app = Flask")

if start_idx > 0 and end_idx > start_idx:
    new_func = '''def extract_certifications_from_report(report: str) -> dict:
    """Extract certifications - fixed status detection."""
    report_lower = report.lower()
    
    certifications = {
        "audit": [],
        "iso": [],
        "healthcare": [],
        "government": [],
        "privacy": [],
        "industry": [],
        "frameworks": [],
        "discovered": [],
    }
    
    found_names = set()
    
    def find_cert(report_lower: str, patterns: list, name: str, category: str = None) -> dict:
        """Find cert and determine status based on immediate context."""
        found_pattern = None
        for p in patterns:
            if p in report_lower:
                found_pattern = p
                break
        
        if not found_pattern:
            return None
        
        if name in found_names:
            return None
        
        idx = report_lower.find(found_pattern)
        # Get tighter context - just around this specific mention
        context = report_lower[max(0,idx-50):min(len(report_lower),idx+100)]
        
        # Check for conflicting info FIRST (before denial check)
        if any(w in context for w in ["conflicting", "unclear", "unconfirmed"]):
            found_names.add(name)
            return {"name": name, "status": "Unverified", "icon": "⚠️", "confidence": "low"}
        
        # Skip if explicitly NOT available in immediate context
        denial_patterns = [found_pattern + " not", "not " + found_pattern, 
                          "no " + found_pattern.split()[0], "❌", "not certified", "not compliant"]
        if any(neg in context for neg in denial_patterns):
            return None
        
        found_names.add(name)
        
        # Check IN ORDER - most specific first
        # For this specific cert, is it "certified" or "compliant"?
        cert_pattern = found_pattern + " certified"
        comp_pattern = found_pattern + " compliant"
        
        # Check immediate context for this cert's status
        if cert_pattern in context or (found_pattern + ": certified" in context):
            return {"name": name, "status": "Certified", "icon": "🏅", "confidence": "high"}
        
        if comp_pattern in context or (found_pattern + ": compliant" in context):
            return {"name": name, "status": "Compliant", "icon": "☑️", "confidence": "medium"}
        
        # Check for standalone status words near the pattern
        # Split context to see what comes after the pattern
        after_pattern = context[context.find(found_pattern):]
        
        if "certified" in after_pattern[:30] and "not certified" not in after_pattern[:30]:
            return {"name": name, "status": "Certified", "icon": "🏅", "confidence": "high"}
        
        if "compliant" in after_pattern[:30] and "not compliant" not in after_pattern[:30]:
            return {"name": name, "status": "Compliant", "icon": "☑️", "confidence": "medium"}
        
        if any(w in context for w in ["in progress", "pursuing", "planned"]):
            return {"name": name, "status": "In Progress", "icon": "🔄", "confidence": "medium"}
        
        # Default - found but status unclear
        return {"name": name, "status": "Noted", "icon": "📋", "confidence": "low"}
    
    # ============ AUDIT ============
    cert = find_cert(report_lower, ["soc 2 type ii", "soc 2 type 2"], "SOC 2 Type II")
    if cert: certifications["audit"].append(cert)
    else:
        cert = find_cert(report_lower, ["soc 2 type i", "soc 2 type 1"], "SOC 2 Type I")
        if cert: certifications["audit"].append(cert)
    
    # ============ ISO STANDARDS ============
    for patterns, name in [
        (["iso 27001", "iso/iec 27001"], "ISO 27001"),
        (["iso 27017"], "ISO 27017"),
        (["iso 27018"], "ISO 27018"),
        (["iso 27701"], "ISO 27701"),
        (["iso 42001"], "ISO 42001 (AI)"),
        (["iso 9001"], "ISO 9001"),
    ]:
        cert = find_cert(report_lower, patterns, name)
        if cert: certifications["iso"].append(cert)
    
    # ============ HEALTHCARE ============
    for patterns, name in [
        (["hitrust r2"], "HITRUST r2"),
        (["hitrust e1"], "HITRUST e1"),
        (["hitrust i1"], "HITRUST i1"),
        (["hitrust csf"], "HITRUST CSF"),
    ]:
        cert = find_cert(report_lower, patterns, name)
        if cert: certifications["healthcare"].append(cert)
    
    # HIPAA BAA
    if "hipaa baa" in report_lower or "business associate agreement" in report_lower:
        idx = report_lower.find("hipaa baa") if "hipaa baa" in report_lower else report_lower.find("business associate")
        context = report_lower[max(0,idx-30):min(len(report_lower),idx+80)]
        if any(p in context for p in ["available", "offers", "provides", "signs baa"]):
            if not any(n in context for n in ["not available", "no baa", "does not", "unavailable"]):
                if "HIPAA BAA" not in found_names:
                    found_names.add("HIPAA BAA")
                    certifications["healthcare"].append({"name": "HIPAA BAA", "status": "Available", "icon": "🏅", "confidence": "high"})
    
    # ============ GOVERNMENT ============
    # FedRAMP - check for conflicting info first
    if "fedramp" in report_lower:
        idx = report_lower.find("fedramp")
        context = report_lower[max(0,idx-80):min(len(report_lower),idx+200)]
        
        if "conflicting" in context:
            certifications["government"].append({"name": "FedRAMP", "status": "Unverified", "icon": "⚠️", "confidence": "low"})
            found_names.add("FedRAMP")
        elif "not fedramp" in context or "not certified" in context:
            pass  # Skip - not certified
        else:
            # Check level
            if "fedramp high" in context:
                certifications["government"].append({"name": "FedRAMP High", "status": "Certified", "icon": "🏅", "confidence": "high"})
            elif "fedramp moderate" in context:
                certifications["government"].append({"name": "FedRAMP Moderate", "status": "Certified", "icon": "🏅", "confidence": "high"})
            elif "fedramp low" in context:
                certifications["government"].append({"name": "FedRAMP Low", "status": "Certified", "icon": "🏅", "confidence": "high"})
            elif "fedramp compliant" in context:
                certifications["government"].append({"name": "FedRAMP", "status": "Compliant", "icon": "☑️", "confidence": "medium"})
            elif "fedramp authorized" in context:
                certifications["government"].append({"name": "FedRAMP", "status": "Authorized", "icon": "🏅", "confidence": "high"})
            found_names.add("FedRAMP")
    
    cert = find_cert(report_lower, ["stateramp"], "StateRAMP")
    if cert: certifications["government"].append(cert)
    
    for patterns, name in [
        (["cmmc level 3", "cmmc l3"], "CMMC Level 3"),
        (["cmmc level 2", "cmmc l2"], "CMMC Level 2"),
        (["cmmc level 1", "cmmc l1"], "CMMC Level 1"),
    ]:
        cert = find_cert(report_lower, patterns, name)
        if cert:
            certifications["government"].append(cert)
            break
    
    # ============ FRAMEWORKS ============
    for patterns, name in [
        (["nist csf", "nist cybersecurity framework"], "NIST CSF"),
        (["nist 800-53", "nist sp 800-53"], "NIST 800-53"),
        (["nist 800-171"], "NIST 800-171"),
    ]:
        cert = find_cert(report_lower, patterns, name)
        if cert: certifications["frameworks"].append(cert)
    
    # ============ PRIVACY ============
    # GDPR - check specific context
    if "gdpr" in report_lower:
        idx = report_lower.find("gdpr")
        context = report_lower[max(0,idx-20):min(len(report_lower),idx+50)]
        if "gdpr compliant" in context or "gdpr: compliant" in context:
            certifications["privacy"].append({"name": "GDPR", "status": "Compliant", "icon": "☑️", "confidence": "medium"})
        elif "gdpr certified" in context:
            certifications["privacy"].append({"name": "GDPR", "status": "Certified", "icon": "🏅", "confidence": "high"})
        else:
            certifications["privacy"].append({"name": "GDPR", "status": "Noted", "icon": "📋", "confidence": "low"})
        found_names.add("GDPR")
    
    # CCPA
    if "ccpa" in report_lower:
        idx = report_lower.find("ccpa")
        context = report_lower[max(0,idx-20):min(len(report_lower),idx+50)]
        if "ccpa compliant" in context or "ccpa: compliant" in context:
            certifications["privacy"].append({"name": "CCPA", "status": "Compliant", "icon": "☑️", "confidence": "medium"})
        elif "ccpa certified" in context:
            certifications["privacy"].append({"name": "CCPA", "status": "Certified", "icon": "🏅", "confidence": "high"})
        else:
            certifications["privacy"].append({"name": "CCPA", "status": "Noted", "icon": "📋", "confidence": "low"})
        found_names.add("CCPA")
    
    # ============ INDUSTRY ============
    cert = find_cert(report_lower, ["pci dss", "pci-dss"], "PCI DSS")
    if cert: certifications["industry"].append(cert)
    
    # CSA STAR
    if "csa star" in report_lower or "csa level" in report_lower:
        idx = report_lower.find("csa star") if "csa star" in report_lower else report_lower.find("csa level")
        context = report_lower[max(0,idx-20):min(len(report_lower),idx+60)]
        if "level 2" in context:
            certifications["industry"].append({"name": "CSA STAR Level 2", "status": "Certified", "icon": "🏅", "confidence": "high"})
        elif "level 1" in context:
            certifications["industry"].append({"name": "CSA STAR Level 1", "status": "Compliant", "icon": "☑️", "confidence": "medium"})
        elif "compliant" in context:
            certifications["industry"].append({"name": "CSA STAR", "status": "Compliant", "icon": "☑️", "confidence": "medium"})
        else:
            certifications["industry"].append({"name": "CSA STAR", "status": "Noted", "icon": "📋", "confidence": "low"})
        found_names.add("CSA STAR")
    
    # Remove empty categories
    return {k: v for k, v in certifications.items() if v}

'''
    
    content = content[:start_idx] + new_func + "\n" + content[end_idx:]
    
    with open('/mnt/demo-output/job-53/app.py', 'w') as f:
        f.write(content)
    print("Fixed certification status detection")
else:
    print("Could not find function")
