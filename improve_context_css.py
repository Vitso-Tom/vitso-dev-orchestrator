#!/usr/bin/env python3
"""Improve Assessment Context card styling"""

with open('/mnt/demo-output/job-53/templates/results.html', 'r') as f:
    content = f.read()

old_css = '''        /* Assessment Context Card */
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
        }'''

new_css = '''        /* Assessment Context Card */
        .context-card {
            margin-bottom: 1.5rem;
        }
        .context-card .card-body {
            padding: 1rem 1.5rem;
        }
        .context-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1.25rem;
        }
        .context-item {
            display: flex;
            flex-direction: column;
            gap: 0.35rem;
        }
        .context-item.full-width {
            grid-column: 1 / -1;
        }
        .context-item .label {
            font-size: 0.7rem;
            text-transform: uppercase;
            color: #94a3b8;
            letter-spacing: 0.05em;
            font-weight: 600;
        }
        .context-item .value {
            color: #e2e8f0;
            line-height: 1.6;
            font-size: 0.9rem;
            white-space: pre-wrap;
            max-height: 150px;
            overflow-y: auto;
        }
        .context-item.full-width .value {
            background: rgba(30, 41, 59, 0.5);
            border-radius: 0.375rem;
            padding: 0.75rem 1rem;
            max-height: 200px;
        }
        .context-item.concerns {
            background: rgba(245, 158, 11, 0.1);
            border: 1px solid rgba(245, 158, 11, 0.3);
            border-radius: 0.5rem;
            padding: 1rem;
            margin-top: 0.5rem;
        }
        .context-item.concerns .label {
            color: #f59e0b;
            font-size: 0.75rem;
        }
        .context-item.concerns .value {
            color: #fcd34d;
            background: transparent;
            padding: 0;
            max-height: 120px;
        }'''

if old_css in content:
    content = content.replace(old_css, new_css)
    with open('/mnt/demo-output/job-53/templates/results.html', 'w') as f:
        f.write(content)
    print("Updated Assessment Context styling")
else:
    print("CSS block not found exactly")
