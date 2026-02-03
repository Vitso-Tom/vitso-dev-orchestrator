#!/usr/bin/env python3
"""Add certifications display section to results.html"""

with open('/mnt/demo-output/job-53/templates/results.html', 'r') as f:
    content = f.read()

# Add certifications section - insert before reconciliation table
certs_html = '''
                <!-- Certifications Summary -->
                {% if assessment.certifications %}
                <div class="results-card">
                    <h3><i class="fas fa-certificate"></i> Certifications & Compliance</h3>
                    <div class="certs-grid">
                        {% if assessment.certifications.audit %}
                        <div class="cert-category">
                            <h4>Audit</h4>
                            {% for cert in assessment.certifications.audit %}
                            <span class="cert-badge cert-{{ cert.status }}">{{ cert.icon }} {{ cert.name }}</span>
                            {% endfor %}
                        </div>
                        {% endif %}
                        
                        {% if assessment.certifications.iso %}
                        <div class="cert-category">
                            <h4>ISO Standards</h4>
                            {% for cert in assessment.certifications.iso %}
                            <span class="cert-badge cert-{{ cert.status }}">{{ cert.icon }} {{ cert.name }}</span>
                            {% endfor %}
                        </div>
                        {% endif %}
                        
                        {% if assessment.certifications.healthcare %}
                        <div class="cert-category">
                            <h4>Healthcare</h4>
                            {% for cert in assessment.certifications.healthcare %}
                            <span class="cert-badge cert-{{ cert.status }}">{{ cert.icon }} {{ cert.name }}</span>
                            {% endfor %}
                        </div>
                        {% endif %}
                        
                        {% if assessment.certifications.government %}
                        <div class="cert-category">
                            <h4>Government</h4>
                            {% for cert in assessment.certifications.government %}
                            <span class="cert-badge cert-{{ cert.status }}">{{ cert.icon }} {{ cert.name }}</span>
                            {% endfor %}
                        </div>
                        {% endif %}
                        
                        {% if assessment.certifications.privacy %}
                        <div class="cert-category">
                            <h4>Privacy</h4>
                            {% for cert in assessment.certifications.privacy %}
                            <span class="cert-badge cert-{{ cert.status }}">{{ cert.icon }} {{ cert.name }}</span>
                            {% endfor %}
                        </div>
                        {% endif %}
                        
                        {% if assessment.certifications.industry %}
                        <div class="cert-category">
                            <h4>Industry</h4>
                            {% for cert in assessment.certifications.industry %}
                            <span class="cert-badge cert-{{ cert.status }}">{{ cert.icon }} {{ cert.name }}</span>
                            {% endfor %}
                        </div>
                        {% endif %}
                        
                        {% if assessment.certifications.other %}
                        <div class="cert-category">
                            <h4>Other</h4>
                            {% for cert in assessment.certifications.other %}
                            <span class="cert-badge cert-{{ cert.status }}">{{ cert.icon }} {{ cert.name }}</span>
                            {% endfor %}
                        </div>
                        {% endif %}
                    </div>
                </div>
                {% endif %}
                
'''

# Find reconciliation section and insert before it
recon_marker = '<!-- Input vs Research Reconciliation -->'
if recon_marker in content:
    content = content.replace(recon_marker, certs_html + '\n                ' + recon_marker)
else:
    # Try alternative - find reconciliation heading
    alt_marker = '<h3><i class="fas fa-balance-scale"></i> Input vs Research Reconciliation</h3>'
    if alt_marker in content:
        content = content.replace(alt_marker, certs_html + '\n                ' + alt_marker)

# Add CSS for certifications
certs_css = '''
        /* Certifications grid */
        .certs-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }
        .cert-category {
            background: rgba(0,0,0,0.2);
            padding: 1rem;
            border-radius: 0.5rem;
        }
        .cert-category h4 {
            margin: 0 0 0.75rem 0;
            color: #94a3b8;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .cert-badge {
            display: inline-block;
            padding: 0.25rem 0.5rem;
            margin: 0.25rem;
            border-radius: 0.25rem;
            font-size: 0.8rem;
            font-weight: 500;
        }
        .cert-certified, .cert-compliant, .cert-available {
            background: rgba(16, 185, 129, 0.2);
            color: #10b981;
        }
        .cert-not_available {
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
        }
        .cert-in_progress {
            background: rgba(245, 158, 11, 0.2);
            color: #f59e0b;
        }
        .cert-unknown {
            background: rgba(100, 116, 139, 0.2);
            color: #94a3b8;
        }
'''

content = content.replace('</style>', certs_css + '\n        </style>')

with open('/mnt/demo-output/job-53/templates/results.html', 'w') as f:
    f.write(content)

print("Added certifications display to results.html")
