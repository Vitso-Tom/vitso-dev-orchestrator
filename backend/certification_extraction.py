# Certification categories for enhanced extraction
# Add to research_agent_v2.py

CERTIFICATION_TARGETS = {
    # Core Security/Compliance
    "soc1_type1": {"names": ["SOC 1 Type I", "SOC 1 Type 1", "SSAE 16"], "category": "audit"},
    "soc1_type2": {"names": ["SOC 1 Type II", "SOC 1 Type 2"], "category": "audit"},
    "soc2_type1": {"names": ["SOC 2 Type I", "SOC 2 Type 1"], "category": "audit"},
    "soc2_type2": {"names": ["SOC 2 Type II", "SOC 2 Type 2"], "category": "audit"},
    
    # ISO Standards
    "iso_27001": {"names": ["ISO 27001", "ISO/IEC 27001"], "category": "iso"},
    "iso_27017": {"names": ["ISO 27017", "ISO/IEC 27017"], "category": "iso"},
    "iso_27018": {"names": ["ISO 27018", "ISO/IEC 27018"], "category": "iso"},
    "iso_27701": {"names": ["ISO 27701", "ISO/IEC 27701"], "category": "iso"},
    "iso_42001": {"names": ["ISO 42001", "ISO/IEC 42001", "AI Management System"], "category": "iso"},
    
    # Healthcare
    "hipaa_baa": {"names": ["HIPAA BAA", "Business Associate Agreement", "BAA"], "category": "healthcare"},
    "hitrust_i1": {"names": ["HITRUST i1", "HITRUST Implemented"], "category": "healthcare"},
    "hitrust_e1": {"names": ["HITRUST e1", "HITRUST Essentials"], "category": "healthcare"},
    "hitrust_r2": {"names": ["HITRUST r2", "HITRUST Risk-based"], "category": "healthcare"},
    "hitrust": {"names": ["HITRUST CSF", "HITRUST Certified"], "category": "healthcare"},
    
    # Government
    "fedramp_high": {"names": ["FedRAMP High"], "category": "government"},
    "fedramp_moderate": {"names": ["FedRAMP Moderate"], "category": "government"},
    "fedramp_low": {"names": ["FedRAMP Low", "FedRAMP Tailored"], "category": "government"},
    "fedramp": {"names": ["FedRAMP", "FedRAMP Authorized"], "category": "government"},
    "stateramp": {"names": ["StateRAMP"], "category": "government"},
    "cmmc_l1": {"names": ["CMMC Level 1", "CMMC L1"], "category": "government"},
    "cmmc_l2": {"names": ["CMMC Level 2", "CMMC L2"], "category": "government"},
    "cmmc_l3": {"names": ["CMMC Level 3", "CMMC L3"], "category": "government"},
    "cmmc": {"names": ["CMMC", "Cybersecurity Maturity Model"], "category": "government"},
    
    # Privacy
    "gdpr": {"names": ["GDPR", "General Data Protection Regulation"], "category": "privacy"},
    "ccpa": {"names": ["CCPA", "California Consumer Privacy Act"], "category": "privacy"},
    
    # Industry Specific
    "pci_dss": {"names": ["PCI DSS", "PCI-DSS", "Payment Card Industry"], "category": "industry"},
    "csa_star": {"names": ["CSA STAR", "Cloud Security Alliance"], "category": "industry"},
    
    # Healthcare Discovery
    "ehnac": {"names": ["EHNAC"], "category": "healthcare_discovery"},
    "ars": {"names": ["ARS", "Accountable Care"], "category": "healthcare_discovery"},
    "urac": {"names": ["URAC"], "category": "healthcare_discovery"},
    "caqh": {"names": ["CAQH"], "category": "healthcare_discovery"},
}

CERTIFICATION_EXTRACTION_PROMPT = """
For the vendor {vendor_name} ({product_name}), extract detailed certification information.

For EACH certification found, provide:
- certification_id: Unique identifier (e.g., "soc2_type2", "iso_27001")
- certification_name: Full name (e.g., "SOC 2 Type II")
- status: One of: "certified", "in_progress", "expired", "not_available", "unknown"
- level_or_type: Specific level if applicable (e.g., "Type II", "Level 2", "r2")
- date_issued: Date certified (if found)
- date_expires: Expiration date (if found)
- scope: What's covered (e.g., "Cursor IDE cloud services")
- certifying_body: Who issued it (e.g., "Schellman", "A-LIGN")
- source_url: Where this was found
- confidence: 0.0-1.0 based on source reliability
- notes: Any caveats or additional context

Look specifically for these certifications:
- SOC 1/2 Type I/II
- ISO 27001, 27017, 27018, 27701, 42001
- HIPAA BAA availability
- HITRUST (i1, e1, r2)
- FedRAMP (any level)
- CMMC (any level)
- StateRAMP
- GDPR compliance
- PCI DSS
- CSA STAR
- Any healthcare-specific: EHNAC, URAC, CAQH

Return as JSON array of certification objects.
"""


def build_certifications_summary(facts: list) -> dict:
    """
    Build structured certifications summary from extracted facts.
    Groups by category and includes all metadata.
    """
    certifications = {
        "audit": [],       # SOC 1/2
        "iso": [],         # ISO standards
        "healthcare": [],  # HIPAA, HITRUST
        "government": [],  # FedRAMP, CMMC, StateRAMP
        "privacy": [],     # GDPR, CCPA
        "industry": [],    # PCI, CSA
        "other": []        # Discovered certs not in main list
    }
    
    # Track what we've found
    found_certs = set()
    
    for fact in facts:
        if fact.category == "certification" or "cert" in fact.category.lower():
            cert_key = fact.key.lower()
            
            # Determine category
            cat = "other"
            for cert_id, cert_info in CERTIFICATION_TARGETS.items():
                if cert_id in cert_key or any(n.lower() in cert_key for n in cert_info["names"]):
                    cat = cert_info["category"]
                    break
            
            cert_entry = {
                "key": fact.key,
                "value": fact.value,
                "source": fact.source_url,
                "confidence": fact.confidence,
                "status": _infer_status(fact.value)
            }
            
            if fact.key not in found_certs:
                certifications[cat].append(cert_entry)
                found_certs.add(fact.key)
    
    return certifications


def _infer_status(value: str) -> str:
    """Infer certification status from value text."""
    v = value.lower()
    if any(w in v for w in ["not available", "no ", "does not", "unavailable", "not offered"]):
        return "not_available"
    elif any(w in v for w in ["in progress", "pursuing", "planned", "expected"]):
        return "in_progress"
    elif any(w in v for w in ["expired", "lapsed"]):
        return "expired"
    elif any(w in v for w in ["certified", "compliant", "achieved", "yes", "available", "offers"]):
        return "certified"
    return "unknown"
