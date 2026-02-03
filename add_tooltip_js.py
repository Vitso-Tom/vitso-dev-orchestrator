#!/usr/bin/env python3
"""Add tooltip JavaScript to results page"""

with open('/mnt/demo-output/job-53/templates/results.html', 'r') as f:
    content = f.read()

# Add JavaScript before closing </body>
tooltip_js = '''
<script>
// Category score tooltips
const categoryTooltips = {
    'data exposure': 'Measures risk from data sensitivity (PHI/PII), residency, subprocessors, and retention policies. Lower is better.',
    'identity surface': 'Evaluates user scope, authentication method (SSO vs password), and authorization model (RBAC/ABAC). Lower is better.',
    'vendor maturity': 'Assesses SOC 2, HIPAA BAA, security program, incident history, company size, and funding. Based on research findings.',
    'ai model risk': 'AI-specific risks: training on your data, prompt logging, model pinning, agent capabilities, plugins, MCP support.',
    'integration risk': 'Architecture risks: deployment model, API access, SSO/SCIM support. Research-adjusted for enterprise features.',
    'operational risk': 'Business continuity: data export, vendor lock-in, model provider concentration. Includes your specific concerns.'
};

document.addEventListener('DOMContentLoaded', function() {
    const categoryRows = document.querySelectorAll('.category-row');
    
    categoryRows.forEach(row => {
        const nameSpan = row.querySelector('.category-name');
        if (nameSpan) {
            const categoryName = nameSpan.textContent.trim().toLowerCase();
            const tooltip = categoryTooltips[categoryName];
            
            if (tooltip) {
                // Add question mark icon
                const icon = document.createElement('i');
                icon.className = 'fas fa-question-circle tooltip-icon';
                nameSpan.appendChild(icon);
                
                // Create tooltip element
                const tooltipEl = document.createElement('div');
                tooltipEl.className = 'category-tooltip';
                tooltipEl.textContent = tooltip;
                row.appendChild(tooltipEl);
                
                // Show/hide on hover
                row.addEventListener('mouseenter', () => {
                    tooltipEl.style.opacity = '1';
                    tooltipEl.style.visibility = 'visible';
                });
                row.addEventListener('mouseleave', () => {
                    tooltipEl.style.opacity = '0';
                    tooltipEl.style.visibility = 'hidden';
                });
            }
        }
    });
});
</script>
'''

# Insert before </body>
if '</body>' in content:
    content = content.replace('</body>', tooltip_js + '\n</body>')
    print("Added tooltip JavaScript")
else:
    print("Could not find </body>")

with open('/mnt/demo-output/job-53/templates/results.html', 'w') as f:
    f.write(content)
