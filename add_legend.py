#!/usr/bin/env python3
"""Add legend to certifications section"""

with open('/mnt/demo-output/job-53/templates/results.html', 'r') as f:
    content = f.read()

# Add legend after the h3 title
old_title = '<h3><i class="fas fa-certificate"></i> Certifications & Compliance</h3>'
new_title = '''<h3><i class="fas fa-certificate"></i> Certifications & Compliance</h3>
                    <div class="cert-legend">
                        <span class="legend-item"><span class="legend-icon">🏅</span> Certified (3rd party verified)</span>
                        <span class="legend-item"><span class="legend-icon">☑️</span> Compliant (self-attested)</span>
                        <span class="legend-item"><span class="legend-icon">⚠️</span> Unverified (conflicting info)</span>
                        <span class="legend-item"><span class="legend-icon">🔄</span> In Progress</span>
                    </div>'''

content = content.replace(old_title, new_title)

# Add CSS for legend
legend_css = '''
        .cert-legend {
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            margin: 0.5rem 0 1rem 0;
            padding: 0.5rem;
            background: rgba(0,0,0,0.2);
            border-radius: 0.375rem;
            font-size: 0.75rem;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 0.25rem;
            color: #94a3b8;
        }
        .legend-icon {
            font-size: 0.875rem;
        }
'''

if '.cert-legend' not in content:
    content = content.replace('</style>', legend_css + '\n        </style>')

with open('/mnt/demo-output/job-53/templates/results.html', 'w') as f:
    f.write(content)

print("Added certification legend")
