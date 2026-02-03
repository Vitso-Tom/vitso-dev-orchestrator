#!/usr/bin/env python3
"""Replace Control Requirements with Assessment Context"""

with open('/mnt/demo-output/job-53/templates/results.html', 'r') as f:
    content = f.read()

# Remove the Assessment Context we added earlier near Risk Score Card
old_context = '''
                <!-- Assessment Context (if provided) -->
                {% if assessment.business_sponsor or assessment.requestor or assessment.use_cases or assessment.specific_concerns %}
                <div class="card context-card">
                    <div class="card-header">
                        <h3><i class="fas fa-clipboard-list"></i> Assessment Context</h3>
                    </div>
                    <div class="card-body">
                        <div class="context-grid">
                            {% if assessment.business_sponsor %}
                            <div class="context-item">
                                <span class="label">Business Sponsor</span>
                                <span class="value">{{ assessment.business_sponsor }}</span>
                            </div>
                            {% endif %}
                            {% if assessment.requestor %}
                            <div class="context-item">
                                <span class="label">Requestor</span>
                                <span class="value">{{ assessment.requestor }}</span>
                            </div>
                            {% endif %}
                            {% if assessment.use_cases %}
                            <div class="context-item full-width">
                                <span class="label">Intended Use Cases</span>
                                <span class="value">{{ assessment.use_cases }}</span>
                            </div>
                            {% endif %}
                            {% if assessment.specific_concerns %}
                            <div class="context-item full-width concerns">
                                <span class="label"><i class="fas fa-exclamation-triangle"></i> Specific Concerns</span>
                                <span class="value">{{ assessment.specific_concerns }}</span>
                            </div>
                            {% endif %}
                        </div>
                    </div>
                </div>
                {% endif %}

                <!-- Risk Score Card -->'''

if old_context in content:
    content = content.replace(old_context, '\n\n                <!-- Risk Score Card -->')
    print("Removed earlier Assessment Context block")

# Now replace Control Requirements with Assessment Context
old_control = '''<!-- Control Requirements Card -->
                {% if assessment.risk_analysis.control_requirements %}
                <div class="card">
                    <div class="card-header">
                        <h3><i class="fas fa-lock"></i> Control Requirements</h3>
                    </div>
                    <div class="card-body">
                        {% for category, controls in assessment.risk_analysis.control_requirements.items() %}
                        <div class="control-category">
                            <h5>{{ category|title }}</h5>
                            <ul>
                                {% for control in controls %}
                                <li>{{ control|replace('_', ' ')|title }}</li>
                                {% endfor %}
                            </ul>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                {% endif %}'''

new_context = '''<!-- Assessment Context (if provided) -->
                {% if assessment.business_sponsor or assessment.requestor or assessment.use_cases or assessment.specific_concerns %}
                <div class="card context-card">
                    <div class="card-header">
                        <h3><i class="fas fa-clipboard-list"></i> Assessment Context</h3>
                    </div>
                    <div class="card-body">
                        <div class="context-grid">
                            {% if assessment.business_sponsor %}
                            <div class="context-item">
                                <span class="label">Business Sponsor</span>
                                <span class="value">{{ assessment.business_sponsor }}</span>
                            </div>
                            {% endif %}
                            {% if assessment.requestor %}
                            <div class="context-item">
                                <span class="label">Requestor</span>
                                <span class="value">{{ assessment.requestor }}</span>
                            </div>
                            {% endif %}
                            {% if assessment.use_cases %}
                            <div class="context-item full-width">
                                <span class="label">Intended Use Cases</span>
                                <span class="value">{{ assessment.use_cases }}</span>
                            </div>
                            {% endif %}
                            {% if assessment.specific_concerns %}
                            <div class="context-item full-width concerns">
                                <span class="label"><i class="fas fa-exclamation-triangle"></i> Specific Concerns</span>
                                <span class="value">{{ assessment.specific_concerns }}</span>
                            </div>
                            {% endif %}
                        </div>
                    </div>
                </div>
                {% endif %}'''

if old_control in content:
    content = content.replace(old_control, new_context)
    print("Replaced Control Requirements with Assessment Context")
else:
    print("Control Requirements block not found exactly - trying to locate...")
    idx = content.find("Control Requirements Card")
    if idx > 0:
        print(f"Found at index {idx}")

with open('/mnt/demo-output/job-53/templates/results.html', 'w') as f:
    f.write(content)

print("Done")
