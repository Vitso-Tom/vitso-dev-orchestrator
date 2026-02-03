"""
File Extractor Module for VDO

Extracts code blocks from AI responses with proper filenames.
Supports explicit filename syntax: ```python:app.py
Falls back to heuristics when explicit names not provided.
"""

import re
from typing import List, Dict, Optional


# Extension mapping from language hints
LANGUAGE_EXTENSIONS = {
    "python": "py", "py": "py",
    "javascript": "js", "js": "js",
    "typescript": "ts", "ts": "ts",
    "bash": "sh", "sh": "sh", "shell": "sh",
    "json": "json",
    "html": "html", "jinja2": "html", "jinja": "html",
    "css": "css",
    "yaml": "yaml", "yml": "yaml",
    "sql": "sql",
    "markdown": "md", "md": "md",
    "dockerfile": "Dockerfile",
    "txt": "txt", "text": "txt",
    "xml": "xml",
    "toml": "toml",
    "ini": "ini",
    "cfg": "cfg",
    "requirements": "txt",
}


def extract_files_from_response(content: str, job_id: int, task_id: int) -> List[Dict]:
    """
    Extract all code blocks from an AI response with proper filenames.
    
    Supports two formats:
    1. Explicit: ```python:app.py (preferred)
    2. Implicit: ```python with filename in surrounding text (fallback)
    
    Returns a list of dicts with:
    - filename: str (may include path like templates/index.html)
    - content: str
    - language: str
    """
    
    files = []
    used_filenames = set()
    
    # Pattern 1: Explicit filename syntax - ```language:filepath
    # Matches: ```python:app.py, ```html:templates/index.html, etc.
    explicit_pattern = r'```(\w+):([^\s\n]+)\s*\n(.*?)```'
    
    for match in re.finditer(explicit_pattern, content, re.DOTALL):
        language = match.group(1).lower()
        filename = match.group(2).strip()
        code = match.group(3).strip()
        
        if not code:
            continue
        
        # Handle duplicate filenames
        original_filename = filename
        counter = 1
        while filename in used_filenames:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, 'txt')
            filename = f"{name}_{counter}.{ext}"
            counter += 1
        
        used_filenames.add(filename)
        
        files.append({
            'filename': filename,
            'content': code,
            'language': language,
        })
        print(f"[Extractor] Explicit: {filename}")
    
    # If we found explicit files, return them
    if files:
        return files
    
    # Pattern 2: Fallback - standard code blocks with context-based naming
    # Matches: ```python, ```html, etc.
    standard_pattern = r'```(\w*)\s*\n(.*?)```'
    
    last_end = 0
    for match in re.finditer(standard_pattern, content, re.DOTALL):
        language = match.group(1).lower() if match.group(1) else ''
        code = match.group(2).strip()
        
        if not code:
            continue
        
        # Get text before this code block for context
        text_before = content[last_end:match.start()]
        last_end = match.end()
        
        # Try to extract filename from context
        filename = _extract_filename_from_context(text_before, code, language)
        
        # If no filename found, infer from content
        if not filename:
            filename = _infer_filename_from_content(code, language, task_id, len(files))
        
        # Handle duplicate filenames
        original_filename = filename
        counter = 1
        while filename in used_filenames:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, 'txt')
            filename = f"{name}_{counter}.{ext}"
            counter += 1
        
        used_filenames.add(filename)
        
        # Determine language from filename if not set
        if not language and '.' in filename:
            ext = filename.rsplit('.', 1)[1].lower()
            for lang, lang_ext in LANGUAGE_EXTENSIONS.items():
                if lang_ext == ext:
                    language = lang
                    break
            if not language:
                language = ext
        
        files.append({
            'filename': filename,
            'content': code,
            'language': language or 'txt',
        })
        print(f"[Extractor] Inferred: {filename}")
    
    # Fallback: if no code blocks found but content looks like code
    if not files and len(content) > 100:
        code_indicators = [
            'def ', 'class ', 'import ', 'from ',
            'function ', 'const ', 'let ', 'var ',
            '<!DOCTYPE', '<html', '<div',
        ]
        
        if any(indicator in content for indicator in code_indicators):
            if 'def ' in content or 'import ' in content:
                lang, filename = 'python', f'generated_{task_id}_fallback.py'
            elif 'function ' in content or 'const ' in content:
                lang, filename = 'javascript', f'generated_{task_id}_fallback.js'
            elif '<!DOCTYPE' in content or '<html' in content:
                lang, filename = 'html', f'generated_{task_id}_fallback.html'
            else:
                lang, filename = 'txt', f'generated_{task_id}_fallback.txt'
            
            files.append({
                'filename': filename,
                'content': content.strip(),
                'language': lang,
            })
            print(f"[Extractor] Fallback: {filename}")
    
    return files


def _extract_filename_from_context(text_before: str, code: str, language: str) -> Optional[str]:
    """Extract filename from text before a code block or first lines of code."""
    
    # Patterns for text BEFORE code block
    before_patterns = [
        # Backtick: `app.py` or `templates/index.html`
        r'`([a-zA-Z0-9_\-./]+\.[a-zA-Z0-9]+)`\s*(?::|$)',
        # Bold: **app.py**
        r'\*\*([a-zA-Z0-9_\-./]+\.[a-zA-Z0-9]+)\*\*',
        # File:/Filename: pattern
        r'(?:file|filename)\s*:\s*`?([a-zA-Z0-9_\-./]+\.[a-zA-Z0-9]+)`?',
        # Create/Save pattern
        r'(?:create|save|write|add)\s+(?:the\s+)?(?:file\s+)?`?([a-zA-Z0-9_\-./]+\.[a-zA-Z0-9]+)`?',
        # Header: ### app.py
        r'^#{1,4}\s+([a-zA-Z0-9_\-./]+\.[a-zA-Z0-9]+)\s*$',
    ]
    
    text_to_check = text_before[-500:] if len(text_before) > 500 else text_before
    
    for pattern in before_patterns:
        matches = re.findall(pattern, text_to_check, re.IGNORECASE | re.MULTILINE)
        if matches:
            filename = matches[-1]
            if _is_valid_filename(filename):
                return filename
    
    # Patterns for INSIDE the code block (first few lines)
    first_lines = '\n'.join(code.split('\n')[:5])
    
    inside_patterns = [
        # Python/Shell: # app.py or # File: app.py
        r'^#\s*(?:file(?:name)?:?\s*)?([a-zA-Z0-9_\-./]+\.[a-zA-Z0-9]+)\s*$',
        # JS/CSS: // app.js
        r'^//\s*(?:file(?:name)?:?\s*)?([a-zA-Z0-9_\-./]+\.[a-zA-Z0-9]+)\s*$',
        # HTML: <!-- templates/index.html -->
        r'^<!--\s*(?:file(?:name)?:?\s*)?([a-zA-Z0-9_\-./]+\.[a-zA-Z0-9]+)\s*-->',
    ]
    
    for pattern in inside_patterns:
        matches = re.findall(pattern, first_lines, re.IGNORECASE | re.MULTILINE)
        if matches:
            filename = matches[0]
            if _is_valid_filename(filename):
                return filename
    
    return None


def _is_valid_filename(filename: str) -> bool:
    """Check if a string looks like a valid filename."""
    if not filename or '.' not in filename:
        return False
    
    # Reject obvious non-filenames
    reject_patterns = [
        r'^\d+\.\d+$',  # Version numbers
        r'^v\d',
        r'example\.com',
        r'http',
    ]
    
    for pattern in reject_patterns:
        if re.search(pattern, filename, re.IGNORECASE):
            return False
    
    ext = filename.rsplit('.', 1)[-1].lower()
    valid_extensions = set(LANGUAGE_EXTENSIONS.values()) | {
        'py', 'js', 'ts', 'jsx', 'tsx', 'html', 'css', 'scss',
        'json', 'yaml', 'yml', 'xml', 'md', 'txt', 'sh',
        'sql', 'env', 'gitignore', 'dockerfile', 'toml', 'ini',
    }
    
    return ext in valid_extensions or len(ext) <= 4


def _infer_filename_from_content(code: str, language: str, task_id: int, idx: int) -> str:
    """Infer a reasonable filename based on code content."""
    
    # Flask app
    if 'from flask import' in code or 'Flask(__name__)' in code:
        return 'app.py'
    
    # FastAPI
    if 'from fastapi import' in code or 'FastAPI()' in code:
        return 'main.py'
    
    # Requirements
    if language in ('txt', 'requirements', ''):
        lines = code.strip().split('\n')
        if lines and all(re.match(r'^[a-zA-Z0-9_\-]+([=<>!]+.*)?$', line.strip()) for line in lines[:5] if line.strip()):
            return 'requirements.txt'
    
    # HTML template
    if '<!DOCTYPE' in code or '<html' in code:
        if '{{' in code or '{%' in code:
            return 'templates/index.html'
        return 'index.html'
    
    # CSS
    if language == 'css' or ('{' in code and ':' in code and ';' in code and re.search(r'[.#]?\w+\s*{', code)):
        return 'static/css/style.css'
    
    # JavaScript
    if language in ('javascript', 'js'):
        if 'document.' in code or 'getElementById' in code or 'fetch(' in code:
            return 'static/js/app.js'
        return 'static/js/app.js'
    
    # Default
    ext = LANGUAGE_EXTENSIONS.get(language, language if language else 'txt')
    if ext == language and language not in LANGUAGE_EXTENSIONS.values():
        ext = 'txt'
    
    return f"generated_{task_id}_{idx}.{ext}"
