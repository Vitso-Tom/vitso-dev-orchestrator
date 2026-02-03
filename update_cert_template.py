#!/usr/bin/env python3
"""Update template for new cert categories and legend"""

with open('/mnt/demo-output/job-53/templates/results.html', 'r') as f:
    content = f.read()

# Update legend to include discovered
old_legend = '''<span class="legend-item"><span class="legend-icon">🔄</span> In Progress</span>
                    </div>'''
new_legend = '''<span class="legend-item"><span class="legend-icon">🔄</span> In Progress</span>
                        <span class="legend-item"><span class="legend-icon">🔍</span> Discovered</span>
                    </div>'''

content = content.replace(old_legend, new_legend)

# Add frameworks and discovered categories to template
# Find where industry category ends and add new ones
old_industry_end = '''{% endif %}
                    </div>
                </div>
                {% endif %}
                
                <!-- Input vs Research'''

new_categories = '''{% endif %}
                        
                        {% if assessment.certifications.frameworks %}
                        <div class="cert-category">
                            <h4>Frameworks</h4>
                            {% for cert in assessment.certifications.frameworks %}
                            <span class="cert-badge cert-{{ cert.status }}">{{ cert.icon }} {{ cert.name }} <span class="cert-status">({{ cert.status }})</span></span>
                            {% endfor %}
                        </div>
                        {% endif %}
                        
                        {% if assessment.certifications.discovered %}
                        <div class="cert-category">
                            <h4>Other (Discovered)</h4>
                            {% for cert in assessment.certifications.discovered %}
                            <span class="cert-badge cert-{{ cert.status }}">{{ cert.icon }} {{ cert.name }} <span class="cert-status">({{ cert.status }})</span></span>
                            {% endfor %}
                        </div>
                        {% endif %}
                    </div>
                </div>
                {% endif %}
                
                <!-- Input vs Research'''

content = content.replace(old_industry_end, new_categories)

# Add CSS for discovered status
discovered_css = '''
        .cert-Discovered {
            background: rgba(139, 92, 246, 0.2);
            color: #a78bfa;
        }
'''

if '.cert-Discovered' not in content:
    content = content.replace('</style>', discovered_css + '\n        </style>')

with open('/mnt/demo-output/job-53/templates/results.html', 'w') as f:
    f.write(content)

print("Updated template with frameworks and discovered categories")
