from flask import Flask, render_template, request, jsonify, redirect, url_for
import os
import json
from datetime import datetime
from models.risk_assessment import RiskAssessment
from utils.report_generator import ReportGenerator
import config

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

risk_assessor = RiskAssessment()
report_gen = ReportGenerator()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/evaluate', methods=['POST'])
def evaluate_tool():
    try:
        # Extract form data
        tool_data = {
            'tool_name': request.form.get('tool_name'),
            'vendor': request.form.get('vendor'),
            'intended_users': request.form.getlist('intended_users'),
            'use_cases': request.form.get('use_cases'),
            'data_types': request.form.getlist('data_types'),
            'data_sensitivity': request.form.get('data_sensitivity'),
            'auth_model': request.form.get('auth_model'),
            'authz_model': request.form.get('authz_model'),
            'data_storage': request.form.get('data_storage'),
            'data_retention': request.form.get('data_retention'),
            'model_interactions': request.form.getlist('model_interactions'),
            'deployment_model': request.form.get('deployment_model'),
            'integration_points': request.form.getlist('integration_points'),
            'timeline_pressure': request.form.get('timeline_pressure'),
            'executive_pressure': request.form.get('executive_pressure')
        }
        
        # Perform risk assessment
        assessment = risk_assessor.evaluate(tool_data)
        
        # Generate reports
        evaluation_report = report_gen.generate_evaluation_report(tool_data, assessment)
        executive_summary = report_gen.generate_executive_summary(tool_data, assessment)
        
        return render_template('evaluation_report.html', 
                             tool_data=tool_data,
                             assessment=assessment,
                             report=evaluation_report,
                             timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/risk-assessment', methods=['POST'])
def api_risk_assessment():
    try:
        tool_data = request.get_json()
        assessment = risk_assessor.evaluate(tool_data)
        return jsonify(assessment)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/quick-risk', methods=['POST'])
def quick_risk_check():
    try:
        data = request.get_json()
        quick_assessment = risk_assessor.quick_risk_calculation(
            data.get('data_sensitivity', 'low'),
            data.get('deployment_model', 'saas'),
            data.get('data_types', [])
        )
        return jsonify(quick_assessment)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/executive-summary/<tool_id>')
def executive_summary(tool_id):
    # In a real app, you'd fetch from database
    # For demo, we'll use session or mock data
    return render_template('executive_summary.html', tool_id=tool_id)

@app.route('/report/<report_id>')
def view_report(report_id):
    # In a real app, you'd fetch from database
    return render_template('evaluation_report.html', report_id=report_id)

@app.errorhandler(404)
def not_found(error):
    return render_template('index.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
