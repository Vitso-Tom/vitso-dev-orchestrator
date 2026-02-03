#!/bin/bash
# AITGP Three-Tier Patch Script
# Run from host: bash ~/vitso-dev-orchestrator/apply_three_tier_patch.sh

set -e

echo "=== AITGP Three-Tier Recommendation Patch ==="
echo ""

# Backup current files
echo "1. Creating backups..."
docker exec vitso-backend cp /mnt/demo-output/job-53/app.py /mnt/demo-output/job-53/app.py.bak.$(date +%Y%m%d%H%M%S)
docker exec vitso-backend cp /mnt/demo-output/job-53/templates/results.html /mnt/demo-output/job-53/templates/results.html.bak.$(date +%Y%m%d%H%M%S)

# Create the patched app.py functions
echo "2. Patching app.py..."

# Write the new functions to a temp file and apply via Python
docker exec vitso-backend python3 << 'PYTHON_PATCH'
import re

# Read current app.py
with open('/mnt/demo-output/job-53/app.py', 'r') as f:
    content = f.read()

# New apply_research_overrides
NEW_APPLY = '''def apply_research_overrides(risk_analysis, user_data, research):
    """
    Apply hard rules based on research findings.
    Three-tier recommendation system:
    - unqualified_go (Green): No blocking issues
    - conditional_no_go (Amber): Resolvable blockers - must resolve OR no-go
    - disqualified_no_go (Red): Definitive blockers - no resolution path
    """
    if not research or not research.get("success"):
        return risk_analysis

    structured = research.get("structured_data", {})
    cert = structured.get("certification", {})
    security = structured.get("security", {})
    data_handling = structured.get("data_handling", {})

    overrides_applied = []
    conditions_to_resolve = []
    disqualifiers = []

    # === ANALYZE PHI + HIPAA BAA STATUS ===
    data_types = user_data.get("data_types", [])
    has_phi = "phi" in data_types if isinstance(data_types, list) else data_types == "phi"

    hipaa_sources = [
        cert.get("hipaa_baa_status"),
        cert.get("hipaa_baa_availability"),
        cert.get("hipaa_baa"),
        data_handling.get("hipaa_baa_availability"),
        data_handling.get("hipaa_baa"),
        data_handling.get("baa_status"),
    ]
    
    hipaa_baa_values = []
    for source in hipaa_sources:
        if source:
            val = source.get("value", "").lower() if isinstance(source, dict) else str(source).lower()
            if val:
                hipaa_baa_values.append(val)
    
    hipaa_baa_combined = " ".join(hipaa_baa_values)
    
    baa_denied_phrases = [
        "not available", "no baa", "not sign", "does not sign",
        "unavailable", "not hipaa", "no hipaa", "not offered", 
        "does not offer", "does not provide", "confirmed not"
    ]
    baa_denied = any(phrase in hipaa_baa_combined for phrase in baa_denied_phrases)
    
    baa_confirmed_phrases = [
        "available", "offers baa", "provides baa", "signs baa",
        "baa offered", "hipaa compliant", "hipaa ready", "will sign"
    ]
    baa_confirmed = not baa_denied and any(phrase in hipaa_baa_combined for phrase in baa_confirmed_phrases)
    baa_unknown = not baa_denied and not baa_confirmed

    if has_phi:
        if baa_denied:
            disqualifiers.append({
                "issue": "HIPAA BAA Unavailable",
                "detail": "Vendor explicitly confirms BAA is NOT available",
                "resolution": "None - vendor policy prohibits BAA"
            })
            overrides_applied.append("PHI_BAA_DENIED")
        elif baa_unknown:
            conditions_to_resolve.append({
                "issue": "HIPAA BAA Status Unknown",
                "detail": "Research could not confirm BAA availability",
                "resolution": "Contact vendor to confirm BAA availability and obtain signed BAA"
            })
            overrides_applied.append("PHI_BAA_UNKNOWN")

    report = research.get("synthesized_report", "").lower()
    breach_info = security.get("breach_history", {})
    breach_value = breach_info.get("value", "").lower() if isinstance(breach_info, dict) else str(breach_info).lower()
    
    if "cve-" in report or "cve-" in breach_value:
        risk_analysis["overall_score"] = min(100, risk_analysis.get("overall_score", 0) + 15)
        overrides_applied.append("CVE_FOUND")
        conditions_to_resolve.append({
            "issue": "Active CVEs Found",
            "detail": "Security vulnerabilities disclosed",
            "resolution": "Review CVE details and confirm vendor remediation status"
        })
        if "ai_model_risk" in risk_analysis.get("category_scores", {}):
            risk_analysis["category_scores"]["ai_model_risk"] = min(100, risk_analysis["category_scores"]["ai_model_risk"] + 10)

    if "supply chain" in report or "malicious npm" in report or "malicious package" in report:
        risk_analysis["overall_score"] = min(100, risk_analysis.get("overall_score", 0) + 10)
        overrides_applied.append("SUPPLY_CHAIN_RISK")
        conditions_to_resolve.append({
            "issue": "Supply Chain Incident",
            "detail": "Historical supply chain security incident identified",
            "resolution": "Review incident details and confirm vendor remediation"
        })

    score = risk_analysis.get("overall_score", 0)
    
    if disqualifiers:
        risk_analysis["recommendation"] = "disqualified_no_go"
        risk_analysis["overall_risk"] = "critical"
        risk_analysis["rationale"] = f"DISQUALIFIED: {disqualifiers[0]['issue']} - {disqualifiers[0]['detail']}"
        risk_analysis["disqualifiers"] = disqualifiers
        risk_analysis["conditions"] = []
    elif conditions_to_resolve:
        risk_analysis["recommendation"] = "conditional_no_go"
        risk_analysis["overall_risk"] = "high" if score >= 50 else "moderate"
        risk_analysis["rationale"] = f"CONDITIONAL NO-GO: {len(conditions_to_resolve)} issue(s) must be resolved before approval. Failure to resolve = No-Go."
        risk_analysis["conditions"] = conditions_to_resolve
        risk_analysis["disqualifiers"] = []
    elif score >= 85:
        risk_analysis["recommendation"] = "disqualified_no_go"
        risk_analysis["overall_risk"] = "critical"
        risk_analysis["rationale"] = f"DISQUALIFIED: Risk score {score:.0f} exceeds maximum threshold"
        risk_analysis["disqualifiers"] = [{"issue": "Risk Score", "detail": f"Score {score:.0f} >= 85", "resolution": "None"}]
        risk_analysis["conditions"] = []
    elif score >= 70:
        risk_analysis["recommendation"] = "conditional_no_go"
        risk_analysis["overall_risk"] = "high"
        risk_analysis["rationale"] = f"CONDITIONAL NO-GO: Risk score {score:.0f} requires additional review"
        risk_analysis["conditions"] = [{"issue": "Elevated Risk Score", "detail": f"Score {score:.0f}", "resolution": "Conduct detailed security review"}]
        risk_analysis["disqualifiers"] = []
    else:
        risk_analysis["recommendation"] = "unqualified_go"
        risk_analysis["overall_risk"] = "moderate" if score >= 40 else "low"
        risk_analysis["rationale"] = "No blocking issues identified - approved for use"
        risk_analysis["conditions"] = []
        risk_analysis["disqualifiers"] = []

    risk_analysis["research_overrides"] = overrides_applied
    return risk_analysis
'''

# New build_reconciliation
NEW_RECON = '''def build_reconciliation(user_data, research):
    """Compare user inputs against research findings with three-state BAA logic."""
    if not research or not research.get("success"):
        return []
    
    structured = research.get("structured_data", {})
    cert = structured.get("certification", {})
    data_handling = structured.get("data_handling", {})
    report = research.get("synthesized_report", "").lower()
    comparisons = []

    # SOC 2
    user_soc2 = user_data.get("vendor_soc2", "").lower()
    user_says_soc2 = user_soc2 in ["true", "yes", "1"]
    research_has_soc2 = "soc 2 type ii" in report or "soc 2 type 2" in report or "soc 2 type i" in report
    if user_says_soc2 and research_has_soc2: status = "confirmed"
    elif not user_says_soc2 and research_has_soc2: status = "conflict"
    elif user_says_soc2 and not research_has_soc2: status = "unverified"
    else: status = "confirmed"
    comparisons.append({"field": "SOC 2 Certification", "user_input": "Yes" if user_says_soc2 else "No", "research_finding": "SOC 2 Type II Certified" if research_has_soc2 else "Not found", "status": status})

    # HIPAA BAA (Three-state)
    user_baa = user_data.get("vendor_hipaa_baa", "").lower()
    user_says_baa = user_baa in ["true", "yes", "1"]
    hipaa_sources = [cert.get("hipaa_baa_status"), cert.get("hipaa_baa_availability"), cert.get("hipaa_baa"), data_handling.get("hipaa_baa_availability"), data_handling.get("hipaa_baa")]
    hipaa_values = []
    for source in hipaa_sources:
        if source:
            val = source.get("value", "").lower() if isinstance(source, dict) else str(source).lower()
            if val: hipaa_values.append(val)
    hipaa_combined = " ".join(hipaa_values)
    
    baa_denied = any(p in hipaa_combined for p in ["not available", "no baa", "not sign", "does not sign", "unavailable", "not hipaa", "no hipaa", "not offered", "does not offer"])
    baa_confirmed = not baa_denied and any(p in hipaa_combined for p in ["available", "offers baa", "provides baa", "signs baa", "hipaa compliant", "hipaa ready"])
    
    if baa_denied:
        research_baa_text = "No HIPAA BAA available"
        status = "confirmed" if not user_says_baa else "conflict"
    elif baa_confirmed:
        research_baa_text = "HIPAA BAA available"
        status = "confirmed" if user_says_baa else "conflict"
    else:
        research_baa_text = "HIPAA BAA status unknown"
        status = "unknown"
    comparisons.append({"field": "HIPAA BAA", "user_input": "Yes" if user_says_baa else "No", "research_finding": research_baa_text, "status": status})

    # ISO 27001
    research_iso = "iso 27001" in report or "iso/iec 27001" in report
    comparisons.append({"field": "ISO 27001", "user_input": "--", "research_finding": "Certified" if research_iso else "Not found", "status": "new_info" if research_iso else "unknown"})

    # SSO
    user_sso = user_data.get("sso_support", "").lower()
    user_says_sso = user_sso in ["true", "yes", "1"]
    research_sso = "sso" in report or "saml" in report or "oidc" in report
    if user_says_sso and research_sso: status = "confirmed"
    elif not user_says_sso and research_sso: status = "conflict"
    elif user_says_sso and not research_sso: status = "unverified"
    else: status = "confirmed"
    comparisons.append({"field": "SSO Support", "user_input": "Yes" if user_says_sso else "No", "research_finding": "Confirmed" if research_sso else "Not found", "status": status})

    # SCIM
    user_scim = user_data.get("scim_support", "").lower()
    user_says_scim = user_scim in ["true", "yes", "1"]
    research_scim = "scim" in report
    if user_says_scim and research_scim: status = "confirmed"
    elif not user_says_scim and research_scim: status = "conflict"
    elif user_says_scim and not research_scim: status = "unverified"
    else: status = "confirmed"
    comparisons.append({"field": "SCIM Provisioning", "user_input": "Yes" if user_says_scim else "No", "research_finding": "Confirmed" if research_scim else "Not found", "status": status})

    # Training Opt-Out
    user_training = user_data.get("training_on_inputs", "").lower()
    research_optout = any(p in report for p in ["opt-out", "opt out", "privacy mode", "zero retention", "no training"])
    user_display = "Unknown" if user_training in ["unknown", ""] else user_training.replace("_", " ").title()
    status = "new_info" if research_optout and user_training in ["unknown", ""] else ("confirmed" if research_optout else "unverified")
    comparisons.append({"field": "Training Opt-Out", "user_input": user_display, "research_finding": "Available" if research_optout else "Not found", "status": status})

    # Security Incidents
    user_incidents = user_data.get("vendor_incident_history", "").lower()
    research_incidents = any(p in report for p in ["cve-", "breach", "incident", "malicious"])
    user_display = "unknown" if user_incidents in ["unknown", ""] else user_incidents[:50]
    status = "new_info" if research_incidents else "unknown"
    comparisons.append({"field": "Security Incidents", "user_input": user_display, "research_finding": "Incidents found - see report" if research_incidents else "None found", "status": status})

    return comparisons
'''

# Find and replace functions
pattern1 = r'def apply_research_overrides\(risk_analysis, user_data, research\):.*?return risk_analysis\n'
content = re.sub(pattern1, NEW_APPLY + '\n', content, flags=re.DOTALL)

pattern2 = r'def build_reconciliation\(user_data, research\):.*?return comparisons\n'
content = re.sub(pattern2, NEW_RECON + '\n', content, flags=re.DOTALL)

with open('/mnt/demo-output/job-53/app.py', 'w') as f:
    f.write(content)

print("app.py patched successfully")
PYTHON_PATCH

echo "3. Patching results.html..."

# Patch the template
docker exec vitso-backend python3 << 'HTML_PATCH'
with open('/mnt/demo-output/job-53/templates/results.html', 'r') as f:
    content = f.read()

# New recommendation box HTML
NEW_REC_BOX = '''<div class="recommendation-box {{ assessment.risk_analysis.recommendation }}">
                            <h4>Recommendation</h4>
                            <span class="recommendation-badge">
                                {% if assessment.risk_analysis.recommendation == 'unqualified_go' %}
                                    <i class="fas fa-check-circle"></i> GO
                                {% elif assessment.risk_analysis.recommendation == 'conditional_no_go' %}
                                    <i class="fas fa-exclamation-triangle"></i> CONDITIONAL NO-GO
                                {% elif assessment.risk_analysis.recommendation == 'disqualified_no_go' %}
                                    <i class="fas fa-times-circle"></i> DISQUALIFIED
                                {% elif assessment.risk_analysis.recommendation == 'go' %}
                                    <i class="fas fa-check-circle"></i> GO
                                {% elif assessment.risk_analysis.recommendation == 'conditional_go' %}
                                    <i class="fas fa-exclamation-circle"></i> CONDITIONAL GO
                                {% else %}
                                    <i class="fas fa-times-circle"></i> NO-GO
                                {% endif %}
                            </span>
                            <p>{{ assessment.risk_analysis.rationale }}</p>
                            
                            {% if assessment.risk_analysis.conditions %}
                            <div class="conditions-list">
                                <h5><i class="fas fa-clipboard-list"></i> Issues to Resolve Before Approval</h5>
                                <ul>
                                {% for condition in assessment.risk_analysis.conditions %}
                                    <li>
                                        <strong>{{ condition.issue }}</strong>: {{ condition.detail }}
                                        <br><em>Resolution: {{ condition.resolution }}</em>
                                    </li>
                                {% endfor %}
                                </ul>
                                <p class="conditions-warning"><i class="fas fa-exclamation-circle"></i> Failure to resolve these issues = Automatic No-Go</p>
                            </div>
                            {% endif %}
                            
                            {% if assessment.risk_analysis.disqualifiers %}
                            <div class="disqualifiers-list">
                                <h5><i class="fas fa-ban"></i> Disqualifying Issues (No Resolution Path)</h5>
                                <ul>
                                {% for dq in assessment.risk_analysis.disqualifiers %}
                                    <li>
                                        <strong>{{ dq.issue }}</strong>: {{ dq.detail }}
                                        <br><em>{{ dq.resolution }}</em>
                                    </li>
                                {% endfor %}
                                </ul>
                            </div>
                            {% endif %}
                        </div>
                        <div class="category-scores">'''

# Replace recommendation box
import re
pattern = r'<div class="recommendation-box.*?</div>\s*<div class="category-scores">'
content = re.sub(pattern, NEW_REC_BOX, content, flags=re.DOTALL)

# Add new CSS styles
NEW_CSS = '''
        /* Three-tier recommendation styles */
        .recommendation-box.unqualified_go .recommendation-badge {
            background: rgba(16, 185, 129, 0.2);
            color: #10b981;
        }
        .recommendation-box.conditional_no_go .recommendation-badge {
            background: rgba(245, 158, 11, 0.2);
            color: #f59e0b;
        }
        .recommendation-box.disqualified_no_go .recommendation-badge {
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
        }
        .conditions-list, .disqualifiers-list {
            margin-top: 1.5rem;
            padding: 1rem;
            border-radius: 0.375rem;
            background: rgba(0, 0, 0, 0.2);
        }
        .conditions-list { border-left: 3px solid #f59e0b; }
        .disqualifiers-list { border-left: 3px solid #ef4444; }
        .conditions-list h5, .disqualifiers-list h5 {
            margin: 0 0 0.75rem 0;
            color: #f1f5f9;
            font-size: 0.9rem;
        }
        .conditions-list ul, .disqualifiers-list ul {
            margin: 0;
            padding-left: 1.25rem;
        }
        .conditions-list li, .disqualifiers-list li {
            margin-bottom: 0.75rem;
            color: #cbd5e1;
            font-size: 0.875rem;
        }
        .conditions-list li em, .disqualifiers-list li em {
            color: #94a3b8;
            font-size: 0.8rem;
        }
        .conditions-warning {
            margin-top: 1rem;
            padding: 0.5rem;
            background: rgba(245, 158, 11, 0.1);
            border-radius: 0.25rem;
            color: #f59e0b;
            font-size: 0.8rem;
            font-weight: 500;
        }
        .status-unknown {
            background: rgba(100, 116, 139, 0.2);
            color: #94a3b8;
        }
'''

content = content.replace('</style>', NEW_CSS + '\n        </style>')

with open('/mnt/demo-output/job-53/templates/results.html', 'w') as f:
    f.write(content)

print("results.html patched successfully")
HTML_PATCH

echo ""
echo "4. Restarting Flask..."
docker exec vitso-backend pkill -f "flask run.*5050" 2>/dev/null || true
sleep 2
docker exec -d vitso-backend bash -c "cd /mnt/demo-output/job-53 && flask run --host=0.0.0.0 --port=5050"

echo ""
echo "=== Patch Complete ==="
echo "Test with:"
echo "  - Cursor (should be DISQUALIFIED - BAA explicitly denied)"
echo "  - Tabnine (should be CONDITIONAL NO-GO - BAA unknown)"
