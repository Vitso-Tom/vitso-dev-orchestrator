#!/usr/bin/env python3
"""Add certifications display to AITGP"""

with open('/mnt/demo-output/job-53/app.py', 'r') as f:
    content = f.read()

# Add certification extraction function after imports
cert_func = '''
def extract_certifications_from_report(report: str) -> dict:
    """Extract certification mentions from research report."""
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
    
    # SOC certifications
    if "soc 2 type ii" in report_lower or "soc 2 type 2" in report_lower:
        certifications["audit"].append({"name": "SOC 2 Type II", "status": "certified", "icon": "✅"})
    elif "soc 2 type i" in report_lower or "soc 2 type 1" in report_lower:
        certifications["audit"].append({"name": "SOC 2 Type I", "status": "certified", "icon": "✅"})
    elif "soc 2" in report_lower:
        certifications["audit"].append({"name": "SOC 2", "status": "certified", "icon": "✅"})
    
    if "soc 1" in report_lower:
        certifications["audit"].append({"name": "SOC 1", "status": "certified", "icon": "✅"})
    
    # ISO certifications
    iso_certs = [
        ("iso 27001", "ISO 27001"),
        ("iso/iec 27001", "ISO 27001"),
        ("iso 27017", "ISO 27017"),
        ("iso 27018", "ISO 27018"),
        ("iso 27701", "ISO 27701"),
        ("iso 42001", "ISO 42001 (AI)"),
    ]
    for pattern, name in iso_certs:
        if pattern in report_lower:
            certifications["iso"].append({"name": name, "status": "certified", "icon": "✅"})
    
    # Healthcare
    if "hipaa baa" in report_lower:
        if any(p in report_lower for p in ["not available", "no baa", "does not sign", "does not offer"]):
            certifications["healthcare"].append({"name": "HIPAA BAA", "status": "not_available", "icon": "❌"})
        elif any(p in report_lower for p in ["baa available", "offers baa", "signs baa", "hipaa compliant"]):
            certifications["healthcare"].append({"name": "HIPAA BAA", "status": "available", "icon": "✅"})
        else:
            certifications["healthcare"].append({"name": "HIPAA BAA", "status": "unknown", "icon": "❓"})
    
    hitrust_patterns = [
        ("hitrust r2", "HITRUST r2"),
        ("hitrust e1", "HITRUST e1"),
        ("hitrust i1", "HITRUST i1"),
        ("hitrust csf", "HITRUST CSF"),
        ("hitrust certified", "HITRUST"),
    ]
    for pattern, name in hitrust_patterns:
        if pattern in report_lower:
            certifications["healthcare"].append({"name": name, "status": "certified", "icon": "✅"})
            break
    
    # Government
    fedramp_patterns = [
        ("fedramp high", "FedRAMP High"),
        ("fedramp moderate", "FedRAMP Moderate"),
        ("fedramp low", "FedRAMP Low"),
        ("fedramp authorized", "FedRAMP"),
        ("fedramp compliant", "FedRAMP"),
    ]
    for pattern, name in fedramp_patterns:
        if pattern in report_lower:
            certifications["government"].append({"name": name, "status": "certified", "icon": "✅"})
            break
    
    if "stateramp" in report_lower:
        certifications["government"].append({"name": "StateRAMP", "status": "certified", "icon": "✅"})
    
    cmmc_patterns = [
        ("cmmc level 3", "CMMC Level 3"),
        ("cmmc level 2", "CMMC Level 2"),
        ("cmmc level 1", "CMMC Level 1"),
        ("cmmc l3", "CMMC Level 3"),
        ("cmmc l2", "CMMC Level 2"),
        ("cmmc l1", "CMMC Level 1"),
    ]
    for pattern, name in cmmc_patterns:
        if pattern in report_lower:
            certifications["government"].append({"name": name, "status": "certified", "icon": "✅"})
            break
    
    # Privacy
    if "gdpr" in report_lower:
        certifications["privacy"].append({"name": "GDPR", "status": "compliant", "icon": "✅"})
    if "ccpa" in report_lower:
        certifications["privacy"].append({"name": "CCPA", "status": "compliant", "icon": "✅"})
    
    # Industry
    if "pci dss" in report_lower or "pci-dss" in report_lower:
        certifications["industry"].append({"name": "PCI DSS", "status": "certified", "icon": "✅"})
    if "csa star" in report_lower:
        certifications["industry"].append({"name": "CSA STAR", "status": "certified", "icon": "✅"})
    
    # Healthcare discovery
    discovery = [
        ("ehnac", "EHNAC"),
        ("urac", "URAC"),
        ("caqh", "CAQH"),
    ]
    for pattern, name in discovery:
        if pattern in report_lower:
            certifications["other"].append({"name": name, "status": "certified", "icon": "✅"})
    
    return certifications

'''

# Find a good place to insert - after the imports
import_end = content.find("app = Flask")
if import_end > 0:
    content = content[:import_end] + cert_func + "\n" + content[import_end:]

# Now update the assessment route to include certifications
# Find where assessment_data is built and add certifications
old_assess = "'reconciliation': build_reconciliation(data, vendor_research),"
new_assess = """'reconciliation': build_reconciliation(data, vendor_research),
            'certifications': extract_certifications_from_report(vendor_research.get('synthesized_report', '')) if vendor_research else {},"""

content = content.replace(old_assess, new_assess)

with open('/mnt/demo-output/job-53/app.py', 'w') as f:
    f.write(content)

print("Added certification extraction to app.py")
