import os
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from werkzeug.exceptions import BadRequest
import uuid
import requests
import markdown

# Import our models and utilities
from models.assessment import Assessment
from models.risk_engine import RiskEngine
from models.sig_generator import SIGGenerator
from models.precedent_db import PrecedentDB
from models.scenario_modeler import ScenarioModeler
from models.retrospective import RetrospectiveAnalyzer
from utils.database import init_db, get_db
from utils.helpers import validate_assessment_data, format_risk_score, parse_form_data

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# Markdown filter for Jinja templates
@app.template_filter("markdown")
def markdown_filter(text):
    if text:
        return markdown.markdown(text, extensions=["tables", "fenced_code"])
    return ""

# Initialize database
init_db()

# Initialize components
risk_engine = RiskEngine()
sig_generator = SIGGenerator()
precedent_db = PrecedentDB()
scenario_modeler = ScenarioModeler()
retrospective_analyzer = RetrospectiveAnalyzer()

# In-memory assessment store (temporary until DB is fixed)
assessments_store = {}

# VDO Research API integration
VDO_API_URL = "http://localhost:8000"

def call_vendor_research(vendor_name, tool_name=None):
    """
    Call VDO Research Agent to gather vendor intelligence.
    Returns research results or None if failed.
    """
    try:
        response = requests.post(
            f"{VDO_API_URL}/api/research-vendor",
            json={
                "vendor_name": vendor_name,
                "product_name": tool_name or vendor_name,
                "save_to_db": True
            },
            timeout=300  # 5 min timeout for research
        )
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Research API error: {response.status_code}")
            return None
    except requests.exceptions.Timeout:
        print("Research API timeout")
        return None
    except Exception as e:
        print(f"Research API error: {e}")
        return None


def apply_research_overrides(risk_analysis, user_data, research):
    """
    Apply hard rules based on research findings.
    Uses structured_data for reliable boolean checks.
    """
    if not research or not research.get("success"):
        return risk_analysis
    
    structured = research.get("structured_data", {})
    cert = structured.get("certification", {})
    security = structured.get("security", {})
    
    overrides_applied = []
    
    # HARD RULE 1: PHI + No HIPAA BAA = NO-GO
    data_types = user_data.get("data_types", [])
    has_phi = "phi" in data_types if isinstance(data_types, list) else data_types == "phi"
    
    # Check structured data for HIPAA BAA
    hipaa_baa_info = cert.get("hipaa_baa_status") or cert.get("hipaa_baa_availability") or cert.get("hipaa_baa") or {}
    hipaa_baa_value = hipaa_baa_info.get("value", "").lower() if isinstance(hipaa_baa_info, dict) else str(hipaa_baa_info).lower()
    # Check baa_denied FIRST with specific phrases (order matters!)
    baa_denied = any(phrase in hipaa_baa_value for phrase in [
        "not available", "no baa", "not sign", "does not sign", 
        "unavailable", "not hipaa", "no hipaa", "not offered", "does not"
    ])
    # Only check baa_confirmed if NOT denied
    baa_confirmed = not baa_denied and any(word in hipaa_baa_value for word in [
        "available", "yes", "true", "offered", "provides", "signs baa"
    ])
    
    # If PHI selected and BAA not confirmed (either denied or unknown) = NO-GO
    if has_phi and not baa_confirmed:
        risk_analysis["recommendation"] = "no_go"
        if baa_denied:
            risk_analysis["rationale"] = "AUTOMATIC NO-GO: PHI data selected and HIPAA BAA confirmed UNAVAILABLE by vendor"
        else:
            risk_analysis["rationale"] = "AUTOMATIC NO-GO: PHI data selected but HIPAA BAA availability not verified"
        risk_analysis["overall_risk"] = "critical"
        risk_analysis["conditions"] = []
        overrides_applied.append("PHI_NO_BAA_CONFIRMED")
    
    # HARD RULE 2: Active CVEs increase risk
    breach_info = security.get("breach_history", {})
    breach_value = breach_info.get("value", "").lower() if isinstance(breach_info, dict) else str(breach_info).lower()
    
    # Also check the prose report for CVEs as backup
    report = research.get("synthesized_report", "").lower()
    if "cve-" in report or "cve-" in breach_value:
        cve_bump = 15
        risk_analysis["overall_score"] = min(100, risk_analysis.get("overall_score", 0) + cve_bump)
        overrides_applied.append("CVE_FOUND")
        if "ai_model_risk" in risk_analysis.get("category_scores", {}):
            risk_analysis["category_scores"]["ai_model_risk"] = min(100, 
                risk_analysis["category_scores"]["ai_model_risk"] + 10)
    
    # HARD RULE 3: Supply chain incidents
    if "supply chain" in report or "malicious npm" in report or "malicious package" in report:
        risk_analysis["overall_score"] = min(100, risk_analysis.get("overall_score", 0) + 10)
        overrides_applied.append("SUPPLY_CHAIN_RISK")
    
    # HARD RULE 4: Recalculate risk level after bumps
    score = risk_analysis.get("overall_score", 0)
    if risk_analysis.get("recommendation") != "no_go":
        if score >= 70:
            risk_analysis["overall_risk"] = "high"
            if score >= 85:
                risk_analysis["recommendation"] = "no_go"
                risk_analysis["rationale"] = f"Risk score {score:.0f} exceeds threshold due to security findings"
        elif score >= 40:
            risk_analysis["overall_risk"] = "moderate"
    
    # Track what we did
    risk_analysis["research_overrides"] = overrides_applied
    
    return risk_analysis
def build_reconciliation(user_data, research):
    """
    Compare user inputs against research findings.
    Returns list of comparison items with status.
    """
    if not research or not research.get("success"):
        return []
    structured = research.get("structured_data", {})
    cert = structured.get("certification", {})
    
    report = research.get("synthesized_report", "").lower()
    comparisons = []
    
    # --- SOC 2 ---
    user_soc2 = user_data.get("vendor_soc2", "").lower()
    user_says_soc2 = user_soc2 in ["true", "yes", "1"]
    research_has_soc2 = "soc 2 type ii" in report or "soc 2 type 2" in report or "soc 2 type i" in report
    
    if user_says_soc2 and research_has_soc2:
        status = "confirmed"
    elif not user_says_soc2 and research_has_soc2:
        status = "conflict"
    elif user_says_soc2 and not research_has_soc2:
        status = "unverified"
    else:
        status = "confirmed"
    
    comparisons.append({
        "field": "SOC 2 Certification",
        "user_input": "Yes" if user_says_soc2 else "No",
        "research_finding": "SOC 2 Type II Certified" if research_has_soc2 else "Not found",
        "status": status
    })
    
    # --- HIPAA BAA ---
    user_baa = user_data.get("vendor_hipaa_baa", "").lower()
    user_says_baa = user_baa in ["true", "yes", "1"]
    
    # Use structured data for HIPAA BAA
    hipaa_info = cert.get("hipaa_baa_status") or cert.get("hipaa_baa_availability") or cert.get("hipaa_baa") or {}
    hipaa_value = hipaa_info.get("value", "").lower() if isinstance(hipaa_info, dict) else str(hipaa_info).lower()
    
    # Determine BAA status from structured data
    baa_available = any(word in hipaa_value for word in ["available", "yes", "true", "offered", "provides", "signs"])
    baa_unavailable = any(word in hipaa_value for word in ["no", "not", "none", "unavailable", "false", "does not"])
    
    if baa_unavailable:
        research_baa_text = "No HIPAA BAA available"
        research_has_baa = False
        research_no_baa = True
    elif baa_available:
        research_baa_text = "HIPAA BAA available"
        research_has_baa = True
        research_no_baa = False
    else:
        research_baa_text = "Not found"
        research_has_baa = False
        research_no_baa = False
    
    if user_says_baa and research_no_baa:
        status = "conflict"
    elif not user_says_baa and research_has_baa:
        status = "conflict"
    elif user_says_baa and research_has_baa:
        status = "confirmed"
    elif not user_says_baa and research_no_baa:
        status = "confirmed"
    else:
        status = "unverified"
    
    comparisons.append({
        "field": "HIPAA BAA",
        "user_input": "Yes" if user_says_baa else "No",
        "research_finding": research_baa_text,
        "status": status
    })
    
    # --- ISO 27001 ---
    research_iso = "iso 27001" in report
    comparisons.append({
        "field": "ISO 27001",
        "user_input": "--",
        "research_finding": "Certified" if research_iso else "Not found",
        "status": "new_info" if research_iso else "unverified"
    })
    
    # --- SSO Support ---
    user_sso = user_data.get("sso_support", "").lower()
    user_says_sso = user_sso in ["true", "yes", "1"]
    research_sso = "sso" in report or "saml" in report or "oidc" in report
    
    if user_says_sso and research_sso:
        status = "confirmed"
    elif not user_says_sso and research_sso:
        status = "conflict"
    elif user_says_sso and not research_sso:
        status = "unverified"
    else:
        status = "confirmed"
    
    comparisons.append({
        "field": "SSO Support",
        "user_input": "Yes" if user_says_sso else "No",
        "research_finding": "Confirmed" if research_sso else "Not found",
        "status": status
    })
    
    # --- SCIM Support ---
    user_scim = user_data.get("scim_support", "").lower()
    user_says_scim = user_scim in ["true", "yes", "1"]
    research_scim = "scim" in report
    
    if user_says_scim and research_scim:
        status = "confirmed"
    elif not user_says_scim and research_scim:
        status = "conflict"
    elif user_says_scim and not research_scim:
        status = "unverified"
    else:
        status = "confirmed"
    
    comparisons.append({
        "field": "SCIM Provisioning",
        "user_input": "Yes" if user_says_scim else "No",
        "research_finding": "Confirmed" if research_scim else "Not found",
        "status": status
    })
    
    # --- Training Opt-Out ---
    user_training = user_data.get("training_on_inputs", "").lower()
    research_optout = "opt-out" in report or "opt out" in report or "privacy mode" in report
    
    comparisons.append({
        "field": "Training Opt-Out",
        "user_input": user_training.replace("_", " ").title() if user_training else "--",
        "research_finding": "Available" if research_optout else "Not found",
        "status": "confirmed" if research_optout else "unverified"
    })
    
    # --- Security Incidents ---
    research_incidents = "security incident" in report or "cve-" in report or "breach" in report or "vulnerability" in report
    user_incidents = user_data.get("vendor_incident_history", "")
    
    comparisons.append({
        "field": "Security Incidents",
        "user_input": user_incidents[:50] + "..." if len(user_incidents) > 50 else user_incidents or "--",
        "research_finding": "Incidents found - see report" if research_incidents else "None found",
        "status": "new_info" if research_incidents else "confirmed"
    })
    
    return comparisons


@app.route('/')
def index():
    """Main dashboard and assessment form"""
    return render_template('index.html')

@app.route('/assess', methods=['POST'])
def assess_tool():
    """Main assessment endpoint - handles both form and JSON data"""
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
        else:
            data = parse_form_data(request.form)
        
        # Validate input data
        validation_result = validate_assessment_data(data)
        if not validation_result['valid']:
            if request.is_json:
                return jsonify({
                    'success': False,
                    'error': validation_result['errors']
                }), 400
            else:
                for error in validation_result['errors']:
                    flash(error, 'error')
                return redirect(url_for('index'))
        
        # Create assessment
        assessment_id = str(uuid.uuid4())
        
        # Call VDO Research Agent for vendor intelligence
        vendor_research = call_vendor_research(data["vendor"], data.get("tool_name"))
        # Run risk analysis
        risk_analysis = risk_engine.assess_tool(data)
        # Apply research-based overrides (hard rules)
        risk_analysis = apply_research_overrides(risk_analysis, data, vendor_research)
        
        # Generate SIG responses
        sig_responses = sig_generator.generate_responses(data, risk_analysis)
        
        # Find similar precedents
        precedent_matches = precedent_db.find_similar_precedents(data, risk_analysis)
        
        # Run scenario modeling
        scenarios = scenario_modeler.run_scenarios(data, risk_analysis)
        
        # Create assessment object
        assessment_data = {
            'id': assessment_id,
            'tool_name': data['tool_name'],
            'vendor': data['vendor'],
            'timestamp': datetime.utcnow(),
            'inputs': data,
            'risk_analysis': risk_analysis,
            'sig_responses': sig_responses,
            'precedent_matches': precedent_matches,
            'scenarios': scenarios,
            'vendor_research': vendor_research,
            'reconciliation': build_reconciliation(data, vendor_research),
        }
        
        # Save to in-memory store
        assessments_store[assessment_id] = assessment_data
        
        if request.is_json:
            return jsonify({
                'success': True,
                'data': {
                    'assessment_id': assessment_id,
                    'recommendation': risk_analysis['recommendation'],
                    'overall_risk': risk_analysis['overall_risk'],
                    'risk_score': risk_analysis['overall_score']
                }
            })
        else:
            return redirect(url_for('view_results', assessment_id=assessment_id))
            
    except Exception as e:
        app.logger.error(f"Assessment error: {str(e)}")
        if request.is_json:
            return jsonify({
                'success': False,
                'error': 'Internal server error during assessment'
            }), 500
        else:
            flash('An error occurred during assessment. Please try again.', 'error')
            return redirect(url_for('index'))

@app.route('/results/<assessment_id>')
def view_results(assessment_id):
    """Display assessment results"""
    try:
        result = assessments_store.get(assessment_id)
        
        if not result:
            flash('Assessment not found', 'error')
            return redirect(url_for('index'))
        
        return render_template('results.html', assessment=result)
        
    except Exception as e:
        app.logger.error(f"Error loading results: {str(e)}")
        flash('Error loading assessment results', 'error')
        return redirect(url_for('index'))

@app.route('/precedents')
def view_precedents():
    """Precedent browser interface"""
    try:
        assessments = Assessment().get_all()
        categories = precedent_db.get_tool_categories()
        vendors = precedent_db.get_vendors()
        
        return render_template('precedents.html', 
                             assessments=assessments,
                             categories=categories,
                             vendors=vendors)
    except Exception as e:
        app.logger.error(f"Error loading precedents: {str(e)}")
        flash('Error loading precedents', 'error')
        return redirect(url_for('index'))

@app.route('/retrospective/<assessment_id>')
def view_retrospective(assessment_id):
    """Retrospective analysis interface"""
    try:
        result = assessments_store.get(assessment_id)
        
        if not result:
            flash('Assessment not found', 'error')
            return redirect(url_for('index'))
        
        return render_template('retrospective.html', assessment=result)
        
    except Exception as e:
        app.logger.error(f"Error loading retrospective: {str(e)}")
        flash('Error loading retrospective analysis', 'error')
        return redirect(url_for('index'))

@app.route('/api/risk-preview', methods=['POST'])
def risk_preview():
    """Client-side risk calculation preview"""
    try:
        data = request.get_json()
        
        # Run quick risk calculation without full assessment
        risk_analysis = risk_engine.quick_assess(data)
        
        return jsonify({
            'success': True,
            'data': {
                'overall_risk': risk_analysis['overall_risk'],
                'risk_score': risk_analysis['overall_score'],
                'category_scores': risk_analysis['category_scores'],
                'preliminary_recommendation': risk_analysis['preliminary_recommendation']
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Error calculating risk preview'
        }), 500

@app.route('/api/precedent-search', methods=['POST'])
def search_precedents():
    """Search precedents by criteria"""
    try:
        criteria = request.get_json()
        results = precedent_db.find_similar_precedents(criteria)
        
        return jsonify({
            'success': True,
            'matches': results
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Error searching precedents'
        }), 500

@app.route('/api/compare-precedents', methods=['POST'])
def compare_precedents():
    """Compare multiple assessments"""
    try:
        assessment_ids = request.get_json().get('assessment_ids', [])
        
        if len(assessment_ids) < 2:
            return jsonify({
                'success': False,
                'error': 'At least 2 assessments required for comparison'
            }), 400
        
        comparison = precedent_db.compare_assessments(assessment_ids)
        
        return jsonify({
            'success': True,
            'data': comparison
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Error comparing assessments'
        }), 500

@app.route('/api/scenario-model', methods=['POST'])
def model_scenario():
    """Run scenario modeling with different pressures"""
    try:
        data = request.get_json()
        tool_data = data.get('tool_data')
        scenario_name = data.get('scenario')
        
        base_risk = risk_engine.assess_tool(tool_data)
        scenario_result = scenario_modeler.run_scenario(tool_data, base_risk, scenario_name)
        
        return jsonify({
            'success': True,
            'data': scenario_result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Error running scenario model'
        }), 500

@app.route('/api/retrospective', methods=['POST'])
def add_retrospective():
    """Add retrospective analysis to existing assessment"""
    try:
        data = request.get_json()
        assessment_id = data.get('assessment_id')
        retrospective_data = data.get('retrospective_context')
        
        # Get original assessment
        assessment = Assessment()
        original = assessment.get_by_id(assessment_id)
        
        if not original:
            return jsonify({
                'success': False,
                'error': 'Assessment not found'
            }), 404
        
        # Generate retrospective analysis
        retrospective = retrospective_analyzer.analyze(original, retrospective_data)
        
        # Update assessment with retrospective
        assessment.add_retrospective(assessment_id, retrospective)
        
        return jsonify({
            'success': True,
            'data': retrospective
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Error generating retrospective analysis'
        }), 500

@app.route('/api/export/<assessment_id>/<format>')
def export_assessment(assessment_id, format):
    """Export assessment in various formats"""
    try:
        result = assessments_store.get(assessment_id)
        
        if not result:
            return jsonify({
                'success': False,
                'error': 'Assessment not found'
            }), 404
        
        if format == 'json':
            return jsonify({
                'success': True,
                'data': result
            })
        elif format == 'sig-csv':
            # Generate SIG CSV format
            csv_data = sig_generator.export_csv(result['sig_responses'])
            return jsonify({
                'success': True,
                'data': csv_data,
                'content_type': 'text/csv'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Unsupported export format: {format}'
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Error exporting assessment'
        }), 500

@app.errorhandler(404)
def not_found_error(error):
    return render_template('index.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('index.html'), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)