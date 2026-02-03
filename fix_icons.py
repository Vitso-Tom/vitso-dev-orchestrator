#!/usr/bin/env python3
"""Fix icons: Certified (3rd party) vs Compliant (self-attested)"""

with open('/mnt/demo-output/job-53/app.py', 'r') as f:
    content = f.read()

# Update the icon assignments in find_cert function
old_certified = '{"name": name, "status": "Certified", "icon": "✅", "confidence": "high"}'
new_certified = '{"name": name, "status": "Certified", "icon": "🏅", "confidence": "high"}'

old_compliant = '{"name": name, "status": "Compliant", "icon": "✅", "confidence": "medium"}'
new_compliant = '{"name": name, "status": "Compliant", "icon": "☑️", "confidence": "medium"}'

old_noted = '{"name": name, "status": "Noted", "icon": "ℹ️", "confidence": "low"}'
new_noted = '{"name": name, "status": "Noted", "icon": "📋", "confidence": "low"}'

content = content.replace(old_certified, new_certified)
content = content.replace(old_compliant, new_compliant)
content = content.replace(old_noted, new_noted)

# Also fix HIPAA BAA available
old_baa = '{"name": "HIPAA BAA", "status": "Available", "icon": "✅", "confidence": "high"}'
new_baa = '{"name": "HIPAA BAA", "status": "Available", "icon": "🏅", "confidence": "high"}'
content = content.replace(old_baa, new_baa)

with open('/mnt/demo-output/job-53/app.py', 'w') as f:
    f.write(content)

print("Updated icons: 🏅=Certified, ☑️=Compliant, ⚠️=Unverified, 🔄=In Progress, 📋=Noted")
