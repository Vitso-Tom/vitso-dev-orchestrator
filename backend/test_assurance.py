#!/usr/bin/env python3
"""Quick test script for assurance_emitter with Tabnine data."""

import json
import sys
sys.path.insert(0, '.')
from assurance_emitter import build_assurance_section

# Load Tabnine cached data
with open('../vdo-tabine.json', 'r') as f:
    data = json.load(f)

structured_data = data.get('structured_data', {})
synthesized_report = data.get('synthesized_report', '')

result = build_assurance_section(
    vendor_name='Tabnine',
    product_name='Tabnine',
    structured_data=structured_data,
    synthesized_report=synthesized_report
)

print('=== ASSURANCE FINDINGS ===')
print(f'Total findings: {len(result["assurance_findings"])}')
print()
for f in result['assurance_findings']:
    print(f"Program: {f['program_id']} | Status: {f['status']} | Level: {f.get('level')} | Confidence: {f['confidence']} | Sources: {len(f['sources'])}")
    if f.get('notes'):
        print(f"  Notes: {f['notes']}")

print()
print('=== BLOCKED ACCESS ===')
print(json.dumps(result['blocked_access'], indent=2))
