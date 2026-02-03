#!/usr/bin/env python3
"""Expand certification list and add discovery for unknown certs"""

with open('/mnt/demo-output/job-53/app.py', 'r') as f:
    content = f.read()

old_func_start = "def extract_certifications_from_report(report: str) -> dict:"
start_idx = content.find(old_func_start)
end_idx = content.find("app = Flask")

if start_idx > 0 and end_idx > start_idx:
    new_func = '''def extract_certifications_from_report(report: str) -> dict:
    """Extract certifications with expanded list + discovery for unknown certs."""
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
    
    found_names = set()  # Track what we've found to avoid duplicates
    
    def find_cert(report_lower: str, patterns: list, name: str) -> dict:
        """Find cert and determine status."""
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
        context = report_lower[max(0,idx-100):min(len(report_lower),idx+250)]
        
        # Skip if explicitly NOT available
        if any(neg in context for neg in ["not certified", "not compliant", "not available",
                                           "does not have", "❌"]):
            return None
        
        found_names.add(name)
        
        if "certified" in context and "not certified" not in context:
            return {"name": name, "status": "Certified", "icon": "🏅", "confidence": "high"}
        
        if "compliant" in context and "not compliant" not in context:
            return {"name": name, "status": "Compliant", "icon": "☑️", "confidence": "medium"}
        
        if any(w in context for w in ["conflicting", "unclear", "unconfirmed", "third-party claims"]):
            return {"name": name, "status": "Unverified", "icon": "⚠️", "confidence": "low"}
        
        if any(w in context for w in ["in progress", "pursuing", "planned", "expected"]):
            return {"name": name, "status": "In Progress", "icon": "🔄", "confidence": "medium"}
        
        return {"name": name, "status": "Noted", "icon": "📋", "confidence": "low"}
    
    # ============ AUDIT ============
    cert = find_cert(report_lower, ["soc 2 type ii", "soc 2 type 2"], "SOC 2 Type II")
    if cert: certifications["audit"].append(cert)
    else:
        cert = find_cert(report_lower, ["soc 2 type i", "soc 2 type 1"], "SOC 2 Type I")
        if cert: certifications["audit"].append(cert)
    
    cert = find_cert(report_lower, ["soc 1 type ii", "soc 1 type 2"], "SOC 1 Type II")
    if cert: certifications["audit"].append(cert)
    else:
        cert = find_cert(report_lower, ["soc 1"], "SOC 1")
        if cert: certifications["audit"].append(cert)
    
    # ============ ISO STANDARDS ============
    for patterns, name in [
        (["iso 27001", "iso/iec 27001"], "ISO 27001"),
        (["iso 27017", "iso/iec 27017"], "ISO 27017"),
        (["iso 27018", "iso/iec 27018"], "ISO 27018"),
        (["iso 27701", "iso/iec 27701"], "ISO 27701"),
        (["iso 42001", "iso/iec 42001", "ai management system"], "ISO 42001 (AI)"),
        (["iso 9001"], "ISO 9001"),
        (["iso 22301"], "ISO 22301 (BCM)"),
    ]:
        cert = find_cert(report_lower, patterns, name)
        if cert: certifications["iso"].append(cert)
    
    # ============ HEALTHCARE ============
    for patterns, name in [
        (["hitrust r2"], "HITRUST r2"),
        (["hitrust e1"], "HITRUST e1"),
        (["hitrust i1"], "HITRUST i1"),
        (["hitrust csf", "hitrust certified"], "HITRUST CSF"),
        (["ehnac"], "EHNAC"),
        (["urac"], "URAC"),
        (["caqh"], "CAQH"),
    ]:
        cert = find_cert(report_lower, patterns, name)
        if cert: certifications["healthcare"].append(cert)
    
    # HIPAA BAA - only if AVAILABLE
    if "hipaa baa" in report_lower or "business associate agreement" in report_lower:
        idx = report_lower.find("hipaa baa") if "hipaa baa" in report_lower else report_lower.find("business associate")
        context = report_lower[max(0,idx-50):min(len(report_lower),idx+150)]
        if any(p in context for p in ["baa available", "offers baa", "provides baa", "signs baa"]):
            if not any(n in context for n in ["not available", "no baa", "does not"]):
                if "HIPAA BAA" not in found_names:
                    found_names.add("HIPAA BAA")
                    certifications["healthcare"].append({"name": "HIPAA BAA", "status": "Available", "icon": "🏅", "confidence": "high"})
    
    # ============ GOVERNMENT ============
    # FedRAMP levels
    for patterns, name in [
        (["fedramp high"], "FedRAMP High"),
        (["fedramp moderate"], "FedRAMP Moderate"),
        (["fedramp low", "fedramp tailored", "fedramp li-saas"], "FedRAMP Low"),
    ]:
        cert = find_cert(report_lower, patterns, name)
        if cert: 
            certifications["government"].append(cert)
            break
    else:
        cert = find_cert(report_lower, ["fedramp authorized", "fedramp"], "FedRAMP")
        if cert: certifications["government"].append(cert)
    
    cert = find_cert(report_lower, ["stateramp"], "StateRAMP")
    if cert: certifications["government"].append(cert)
    
    # CMMC levels
    for patterns, name in [
        (["cmmc level 3", "cmmc l3"], "CMMC Level 3"),
        (["cmmc level 2", "cmmc l2"], "CMMC Level 2"),
        (["cmmc level 1", "cmmc l1"], "CMMC Level 1"),
    ]:
        cert = find_cert(report_lower, patterns, name)
        if cert:
            certifications["government"].append(cert)
            break
    
    cert = find_cert(report_lower, ["itar"], "ITAR")
    if cert: certifications["government"].append(cert)
    
    cert = find_cert(report_lower, ["fisma"], "FISMA")
    if cert: certifications["government"].append(cert)
    
    # ============ FRAMEWORKS ============
    for patterns, name in [
        (["nist csf", "nist cybersecurity framework"], "NIST CSF"),
        (["nist 800-53", "nist sp 800-53"], "NIST 800-53"),
        (["nist 800-171", "nist sp 800-171"], "NIST 800-171"),
        (["nist ai rmf", "ai risk management framework"], "NIST AI RMF"),
        (["cis controls", "cis benchmarks"], "CIS Controls"),
        (["cobit"], "COBIT"),
        (["itil"], "ITIL"),
    ]:
        cert = find_cert(report_lower, patterns, name)
        if cert: certifications["frameworks"].append(cert)
    
    # ============ PRIVACY ============
    cert = find_cert(report_lower, ["gdpr"], "GDPR")
    if cert: certifications["privacy"].append(cert)
    
    cert = find_cert(report_lower, ["ccpa", "cpra"], "CCPA/CPRA")
    if cert: certifications["privacy"].append(cert)
    
    cert = find_cert(report_lower, ["pipeda"], "PIPEDA")
    if cert: certifications["privacy"].append(cert)
    
    cert = find_cert(report_lower, ["lgpd"], "LGPD (Brazil)")
    if cert: certifications["privacy"].append(cert)
    
    cert = find_cert(report_lower, ["appi"], "APPI (Japan)")
    if cert: certifications["privacy"].append(cert)
    
    # ============ INDUSTRY ============
    for patterns, name in [
        (["pci dss", "pci-dss", "payment card industry"], "PCI DSS"),
        (["csa star level 2", "csa star 2"], "CSA STAR Level 2"),
        (["csa star", "csa level 1"], "CSA STAR"),
        (["soc for supply chain"], "SOC for Supply Chain"),
        (["c5", "cloud computing compliance"], "C5 (Germany)"),
        (["cyber essentials plus"], "Cyber Essentials Plus"),
        (["cyber essentials"], "Cyber Essentials"),
        (["irap"], "IRAP (Australia)"),
        (["ismap"], "ISMAP (Japan)"),
        (["k-isms"], "K-ISMS (Korea)"),
        (["mtcs"], "MTCS (Singapore)"),
    ]:
        cert = find_cert(report_lower, patterns, name)
        if cert: certifications["industry"].append(cert)
    
    # ============ DISCOVERY - catch others ============
    # Look for patterns like "X certified" or "X compliant" we might have missed
    import re
    discovery_patterns = [
        r'([A-Z][A-Za-z0-9\-/\s]{2,25})\s+certified',
        r'([A-Z][A-Za-z0-9\-/\s]{2,25})\s+compliant',
        r'([A-Z][A-Za-z0-9\-/\s]{2,25})\s+accredited',
        r'([A-Z][A-Za-z0-9\-/\s]{2,25})\s+attestation',
    ]
    
    report_original = report  # Need original case for discovery
    for pattern in discovery_patterns:
        matches = re.findall(pattern, report_original)
        for match in matches:
            name = match.strip()
            # Skip if already found or too generic
            if name in found_names or len(name) < 3:
                continue
            if name.lower() in ["is", "are", "was", "the", "and", "for", "our", "we", "they"]:
                continue
            # Skip common words that aren't certifications
            skip_words = ["company", "service", "platform", "product", "data", "system", "control"]
            if any(w in name.lower() for w in skip_words):
                continue
            
            found_names.add(name)
            certifications["discovered"].append({
                "name": name, 
                "status": "Discovered", 
                "icon": "🔍", 
                "confidence": "low"
            })
    
    # Remove empty categories
    return {k: v for k, v in certifications.items() if v}

'''
    
    content = content[:start_idx] + new_func + "\n" + content[end_idx:]
    
    with open('/mnt/demo-output/job-53/app.py', 'w') as f:
        f.write(content)
    print("Expanded certification list with discovery")
else:
    print("Could not find function")
