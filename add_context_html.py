#!/usr/bin/env python3
"""Add Assessment Context HTML section to results.html"""

with open('/mnt/demo-output/job-53/templates/results.html', 'r') as f:
    content = f.read()

# Find the spot - after Assessment Summary closes, before Risk Score Card
old_section = '''                </div>
                <!-- Risk Score Card -->
                <div class="card risk-results">
                    <div class="card-header">
                        <h3><i class="fas fa-chart-pie"></i> Risk Analysis</h3>'''

new_section = '''                </div>
                
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
                
                <!-- Risk Score Card -->
                <div class="card risk-results">
                    <div class="card-header">
                        <h3><i class="fas fa-chart-pie"></i> Risk Analysis</h3>'''

if old_section in content:
    content = content.replace(old_section, new_section)
    with open('/mnt/demo-output/job-53/templates/results.html', 'w') as f:
        f.write(content)
    print("Added Assessment Context HTML section")
else:
    print("Could not find insertion point - checking alternative...")
    # Try without the specific whitespace
    import re
    pattern = r'</div>\s*<!-- Risk Score Card -->'
    if re.search(pattern, content):
        print("Found with regex - manual fix needed")
    else:
        print("Pattern not found at all")
