#!/usr/bin/env python3
"""Add weights to category labels and explanatory text"""

with open('/mnt/demo-output/job-53/templates/results.html', 'r') as f:
    content = f.read()

# 1. Update category row to show weight percentage
old_row = '''<div class="category-row">
                                <span class="category-name">{{ category|replace('_', ' ')|title }} <i class="fas fa-question-circle tooltip-icon"></i></span>'''

new_row = '''{% set weights = {'data_exposure': 20, 'identity_surface': 15, 'vendor_maturity': 20, 'ai_model_risk': 20, 'integration_risk': 10, 'operational_risk': 15} %}
                            <div class="category-row">
                                <span class="category-name">{{ category|replace('_', ' ')|title }} <span class="weight-label">({{ weights.get(category, 15) }}%)</span> <i class="fas fa-question-circle tooltip-icon"></i></span>'''

content = content.replace(old_row, new_row)

# 2. Update tooltips to include contribution calculation
old_tips = '''{% set cat_tips = {"data_exposure": "Data sensitivity, residency, subprocessors, retention. Lower=better", "identity_surface": "User scope, auth method, authorization model. Lower=better", "vendor_maturity": "SOC2, BAA, security program, size, funding. Research-adjusted", "ai_model_risk": "Training on data, logging, agents, plugins, MCP. Lower=better", "integration_risk": "Deployment, API, SSO/SCIM. Research-adjusted", "operational_risk": "Data export, lock-in, provider risk. Includes your concerns"} %}'''

# We need to compute contribution dynamically in the tooltip
new_tips = '''{% set cat_tips = {"data_exposure": "Data sensitivity, residency, subprocessors, retention. Lower=better", "identity_surface": "User scope, auth method, authorization model. Lower=better", "vendor_maturity": "SOC2, BAA, security program, size, funding. Research-adjusted", "ai_model_risk": "Training on data, logging, agents, plugins, MCP. Lower=better", "integration_risk": "Deployment, API, SSO/SCIM. Research-adjusted", "operational_risk": "Data export, lock-in, provider risk. Includes your concerns"} %}'''

# This stays the same for now - we'll enhance via JS

with open('/mnt/demo-output/job-53/templates/results.html', 'w') as f:
    f.write(content)

print("Added weight labels to categories")
