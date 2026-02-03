#!/usr/bin/env python3
"""Update context card HTML for better print layout"""

with open('/mnt/demo-output/job-53/templates/results.html', 'r') as f:
    content = f.read()

# Find and replace the context card structure
old_context = '''<!-- Assessment Context (if provided) -->
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
                                <span class="value">{{ assessment.use_cases | format_use_cases | safe }}</span>
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

new_context = '''<!-- Assessment Context (if provided) -->
                {% if assessment.business_sponsor or assessment.requestor or assessment.use_cases or assessment.specific_concerns %}
                <div class="card context-card">
                    <div class="card-header">
                        <h3><i class="fas fa-clipboard-list"></i> Assessment Context</h3>
                    </div>
                    <div class="card-body">
                        {% if assessment.business_sponsor or assessment.requestor %}
                        <div class="context-inline">
                            {% if assessment.business_sponsor %}
                            <div class="context-inline-item">
                                <span class="label">Business Sponsor:</span>
                                <span class="value">{{ assessment.business_sponsor }}</span>
                            </div>
                            {% endif %}
                            {% if assessment.requestor %}
                            <div class="context-inline-item">
                                <span class="label">Requestor:</span>
                                <span class="value">{{ assessment.requestor }}</span>
                            </div>
                            {% endif %}
                        </div>
                        {% endif %}
                        {% if assessment.use_cases %}
                        <div class="context-section">
                            <div class="section-label">Intended Use Cases</div>
                            <div class="section-content use-cases-content">{{ assessment.use_cases | format_use_cases | safe }}</div>
                        </div>
                        {% endif %}
                        {% if assessment.specific_concerns %}
                        <div class="context-section concerns-section">
                            <div class="section-label"><i class="fas fa-exclamation-triangle"></i> Specific Concerns</div>
                            <div class="section-content">{{ assessment.specific_concerns }}</div>
                        </div>
                        {% endif %}
                    </div>
                </div>
                {% endif %}'''

if old_context in content:
    content = content.replace(old_context, new_context)
    print("Updated context card HTML")
else:
    print("Could not find context card - checking...")
    if "Assessment Context" in content:
        print("Found Assessment Context but structure differs")

with open('/mnt/demo-output/job-53/templates/results.html', 'w') as f:
    f.write(content)
