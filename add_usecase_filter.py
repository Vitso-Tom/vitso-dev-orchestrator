#!/usr/bin/env python3
"""Add a Jinja filter to format use cases text"""

with open('/mnt/demo-output/job-53/app.py', 'r') as f:
    content = f.read()

# Find where filters are defined or add after app = Flask
filter_code = '''
# Custom Jinja filter for formatting use cases
@app.template_filter('format_use_cases')
def format_use_cases(text):
    """Format use cases text with proper capitalization, bold headings, and spacing."""
    if not text:
        return text
    
    import re
    
    # Capitalize first letter
    text = text[0].upper() + text[1:] if text else text
    
    # Split into lines
    lines = text.split('\\n')
    formatted_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check if line looks like a heading (short line, ends with colon, or all title case)
        is_heading = False
        
        # Lines ending with ":" that are relatively short
        if line.endswith(':') and len(line) < 80:
            is_heading = True
        # Short standalone lines that look like section headers (no period, relatively short)
        elif len(line) < 50 and not line.endswith('.') and not line.endswith(','):
            # Check if it's title-case-ish (most words capitalized)
            words = line.replace(':', '').split()
            if len(words) <= 5 and sum(1 for w in words if w[0].isupper()) >= len(words) * 0.6:
                is_heading = True
        
        # Lines with pattern "Something: description" - bold the "Something:" part
        colon_match = re.match(r'^([A-Z][^:]+:)\s*(.+)$', line)
        if colon_match and len(colon_match.group(1)) < 40:
            formatted_lines.append(f'<strong>{colon_match.group(1)}</strong> {colon_match.group(2)}')
        elif is_heading:
            formatted_lines.append(f'<strong>{line}</strong>')
        else:
            formatted_lines.append(line)
    
    # Join with proper spacing - add extra break before headings
    result = []
    for i, line in enumerate(formatted_lines):
        if '<strong>' in line and i > 0:
            result.append('<br>')
        result.append(line)
    
    return '<br>'.join(result)

'''

# Insert after the markdown filter or after app creation
if "@app.template_filter('markdown')" in content:
    # Insert after markdown filter
    idx = content.find("@app.template_filter('markdown')")
    # Find the end of that function
    next_def = content.find("\n@", idx + 10)
    next_func = content.find("\ndef ", idx + 10)
    insert_point = min(next_def, next_func) if next_def > 0 and next_func > 0 else max(next_def, next_func)
    
    content = content[:insert_point] + filter_code + content[insert_point:]
    print("Inserted filter after markdown filter")
elif "app = Flask" in content:
    # Insert after app creation
    idx = content.find("app = Flask")
    next_line = content.find("\n", idx)
    content = content[:next_line+1] + filter_code + content[next_line+1:]
    print("Inserted filter after app creation")
else:
    print("Could not find insertion point")
    exit(1)

with open('/mnt/demo-output/job-53/app.py', 'w') as f:
    f.write(content)

print("Added format_use_cases filter")
