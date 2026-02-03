#!/usr/bin/env python3
with open('/mnt/demo-output/job-53/templates/results.html', 'r') as f:
    c = f.read()

# Replace the badge section
old_badge = """{% if assessment.risk_analysis.recommendation == 'go' %}
                                    <i class="fas fa-check-circle"></i> GO
                                {% elif assessment.risk_analysis.recommendation == 'conditional_go' %}
                                    <i class="fas fa-exclamation-circle"></i> CONDITIONAL GO
                                {% else %}
                                    <i class="fas fa-times-circle"></i> NO-GO
                                {% endif %}"""

new_badge = """{% if assessment.risk_analysis.recommendation == 'unqualified_go' %}
                                    <i class="fas fa-check-circle"></i> GO
                                {% elif assessment.risk_analysis.recommendation == 'conditional_no_go' %}
                                    <i class="fas fa-exclamation-triangle"></i> CONDITIONAL NO-GO
                                {% elif assessment.risk_analysis.recommendation == 'disqualified_no_go' %}
                                    <i class="fas fa-ban"></i> DISQUALIFIED
                                {% elif assessment.risk_analysis.recommendation == 'go' %}
                                    <i class="fas fa-check-circle"></i> GO
                                {% elif assessment.risk_analysis.recommendation == 'conditional_go' %}
                                    <i class="fas fa-exclamation-circle"></i> CONDITIONAL GO
                                {% else %}
                                    <i class="fas fa-times-circle"></i> NO-GO
                                {% endif %}"""

c = c.replace(old_badge, new_badge)

# Add conditions/disqualifiers after rationale
old_rat = '<p>{{ assessment.risk_analysis.rationale }}</p>\n                        </div>'
new_rat = """<p>{{ assessment.risk_analysis.rationale }}</p>
                            {% if assessment.risk_analysis.conditions %}
                            <div style="margin-top:1rem;padding:1rem;border-left:3px solid #f59e0b;background:rgba(0,0,0,0.2);border-radius:0.375rem;">
                                <h5 style="margin:0 0 0.5rem 0;color:#f1f5f9;font-size:0.875rem;">Issues to Resolve</h5>
                                <ul style="margin:0;padding-left:1.25rem;">{% for x in assessment.risk_analysis.conditions %}<li style="margin-bottom:0.5rem;color:#cbd5e1;font-size:0.8rem;"><b>{{ x.issue }}</b>: {{ x.detail }}<br><em style="color:#94a3b8;">→ {{ x.resolution }}</em></li>{% endfor %}</ul>
                                <p style="margin-top:0.5rem;color:#f59e0b;font-size:0.75rem;">⚠ Failure to resolve = No-Go</p>
                            </div>
                            {% endif %}
                            {% if assessment.risk_analysis.disqualifiers %}
                            <div style="margin-top:1rem;padding:1rem;border-left:3px solid #ef4444;background:rgba(0,0,0,0.2);border-radius:0.375rem;">
                                <h5 style="margin:0 0 0.5rem 0;color:#f1f5f9;font-size:0.875rem;">Disqualifying Issues</h5>
                                <ul style="margin:0;padding-left:1.25rem;">{% for x in assessment.risk_analysis.disqualifiers %}<li style="margin-bottom:0.5rem;color:#cbd5e1;font-size:0.8rem;"><b>{{ x.issue }}</b>: {{ x.detail }}<br><em style="color:#94a3b8;">{{ x.resolution }}</em></li>{% endfor %}</ul>
                            </div>
                            {% endif %}
                        </div>"""

c = c.replace(old_rat, new_rat)

# Add CSS for new recommendation types
css_add = """
        .recommendation-box.unqualified_go .recommendation-badge { background: rgba(16,185,129,0.2); color: #10b981; }
        .recommendation-box.conditional_no_go .recommendation-badge { background: rgba(245,158,11,0.2); color: #f59e0b; }
        .recommendation-box.disqualified_no_go .recommendation-badge { background: rgba(239,68,68,0.2); color: #ef4444; }
        .status-unknown { background: rgba(100,116,139,0.2); color: #94a3b8; }
"""
c = c.replace('</style>', css_add + '\n        </style>')

with open('/mnt/demo-output/job-53/templates/results.html', 'w') as f:
    f.write(c)

print("Template updated!")
