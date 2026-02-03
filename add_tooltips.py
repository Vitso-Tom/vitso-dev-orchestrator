#!/usr/bin/env python3
"""Add tooltips to category scores"""

with open('/mnt/demo-output/job-53/templates/results.html', 'r') as f:
    content = f.read()

# Define tooltip content for each category
tooltips = {
    'data_exposure': 'Measures risk from data sensitivity (PHI/PII), residency, subprocessors, and retention policies. Lower is better.',
    'identity_surface': 'Evaluates user scope, authentication method (SSO vs password), and authorization model (RBAC/ABAC). Lower is better.',
    'vendor_maturity': 'Assesses SOC 2, HIPAA BAA, security program, incident history, company size, and funding. Based on research findings.',
    'ai_model_risk': 'AI-specific risks: training on your data, prompt logging, model pinning, agent capabilities, plugins, MCP support.',
    'integration_risk': 'Architecture risks: deployment model, API access, SSO/SCIM support. Research-adjusted for enterprise features.',
    'operational_risk': 'Business continuity: data export, vendor lock-in, model provider concentration. Includes your specific concerns.'
}

# Old template section
old_section = '''                        <div class="category-scores">
                            <h4>Category Scores</h4>
                            {% for category, score in assessment.risk_analysis.category_scores.items() %}
                            <div class="category-row">
                                <span class="category-name">{{ category|replace('_', ' ')|title }}</span>
                                <div class="score-bar">
                                    <div class="score-fill {% if score < 30 %}low{% elif score < 60 %}moderate{% else %}high{% endif %}"
                                         style="width: {{ score }}%"></div>
                                </div>
                                <span class="score-value">{{ "%.0f"|format(score) }}</span>
                            </div>
                            {% endfor %}
                        </div>'''

# New template section with tooltips
new_section = '''                        <div class="category-scores">
                            <h4>Category Scores <span class="scores-help">(hover for details)</span></h4>
                            {% set tooltips = {
                                'data_exposure': 'Measures risk from data sensitivity (PHI/PII), residency, subprocessors, and retention policies. Lower is better.',
                                'identity_surface': 'Evaluates user scope, authentication method (SSO vs password), and authorization model (RBAC/ABAC). Lower is better.',
                                'vendor_maturity': 'Assesses SOC 2, HIPAA BAA, security program, incident history, company size, and funding. Based on research findings.',
                                'ai_model_risk': 'AI-specific risks: training on your data, prompt logging, model pinning, agent capabilities, plugins, MCP support.',
                                'integration_risk': 'Architecture risks: deployment model, API access, SSO/SCIM support. Research-adjusted for enterprise features.',
                                'operational_risk': 'Business continuity: data export, vendor lock-in, model provider concentration. Includes your specific concerns.'
                            } %}
                            {% for category, score in assessment.risk_analysis.category_scores.items() %}
                            <div class="category-row" data-tooltip="{{ tooltips.get(category, 'Risk score for this category') }}">
                                <span class="category-name">
                                    {{ category|replace('_', ' ')|title }}
                                    <i class="fas fa-question-circle tooltip-icon"></i>
                                </span>
                                <div class="score-bar">
                                    <div class="score-fill {% if score < 30 %}low{% elif score < 60 %}moderate{% else %}high{% endif %}"
                                         style="width: {{ score }}%"></div>
                                </div>
                                <span class="score-value">{{ "%.0f"|format(score) }}</span>
                            </div>
                            {% endfor %}
                        </div>'''

if old_section in content:
    content = content.replace(old_section, new_section)
    print("Added tooltips to category scores")
else:
    print("Could not find category scores section")

with open('/mnt/demo-output/job-53/templates/results.html', 'w') as f:
    f.write(content)
