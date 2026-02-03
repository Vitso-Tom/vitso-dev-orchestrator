#!/usr/bin/env python3
"""Update template to show certification status text"""

with open('/mnt/demo-output/job-53/templates/results.html', 'r') as f:
    content = f.read()

# Update the cert badge display to show status
old_badge = '{{ cert.icon }} {{ cert.name }}'
new_badge = '{{ cert.icon }} {{ cert.name }} <span class="cert-status">({{ cert.status }})</span>'

content = content.replace(old_badge, new_badge)

# Add CSS for status text
status_css = '''
        .cert-status {
            font-size: 0.7rem;
            opacity: 0.8;
            font-weight: normal;
        }
        .cert-Certified, .cert-Available {
            background: rgba(16, 185, 129, 0.2);
            color: #10b981;
        }
        .cert-Compliant, .cert-Noted {
            background: rgba(16, 185, 129, 0.15);
            color: #10b981;
        }
        .cert-Unverified {
            background: rgba(245, 158, 11, 0.2);
            color: #f59e0b;
        }
        .cert-in_progress, .cert-In_Progress {
            background: rgba(59, 130, 246, 0.2);
            color: #3b82f6;
        }
'''

# Add CSS if not present
if '.cert-status' not in content:
    content = content.replace('</style>', status_css + '\n        </style>')

with open('/mnt/demo-output/job-53/templates/results.html', 'w') as f:
    f.write(content)

print("Updated template with status display")
