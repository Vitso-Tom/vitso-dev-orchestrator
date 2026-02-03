#!/usr/bin/env python3
"""Add Assessment Context section to results.html"""

with open('/mnt/demo-output/job-53/templates/results.html', 'r') as f:
    content = f.read()

# Find the spot after Assessment Summary card closes, before Risk Score card
old_section = '''                </div>
                <!-- Risk Score Card -->
                <div class="card risk-results">'''

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
                <div class="card risk-results">'''

content = content.replace(old_section, new_section)

# Add CSS for the context card
old_style_end = '</style>'
new_styles = '''
        /* Assessment Context Card */
        .context-card {
            margin-bottom: 1.5rem;
        }
        .context-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1rem;
        }
        .context-item {
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }
        .context-item.full-width {
            grid-column: 1 / -1;
        }
        .context-item .label {
            font-size: 0.75rem;
            text-transform: uppercase;
            color: #94a3b8;
            letter-spacing: 0.05em;
        }
        .context-item .value {
            color: #e2e8f0;
            line-height: 1.5;
        }
        .context-item.concerns {
            background: rgba(245, 158, 11, 0.1);
            border: 1px solid rgba(245, 158, 11, 0.3);
            border-radius: 0.5rem;
            padding: 1rem;
        }
        .context-item.concerns .label {
            color: #f59e0b;
        }
        .context-item.concerns .value {
            color: #fcd34d;
        }
</style>'''

content = content.replace(old_style_end, new_styles)

with open('/mnt/demo-output/job-53/templates/results.html', 'w') as f:
    f.write(content)

print("Added Assessment Context section to results.html")
