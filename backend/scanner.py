# backend/scanner.py
"""
Codebase Scanner for VDO Phase B1.
Scans project directories and builds structured index for AI context injection.
"""

import os
import ast
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Files to always skip
SKIP_DIRS = {
    '__pycache__', 'node_modules', '.git', '.venv', 'venv', 'env',
    '.idea', '.vscode', 'dist', 'build', '.next', '.nuxt',
    'coverage', '.pytest_cache', '.mypy_cache', 'eggs', '*.egg-info'
}

SKIP_FILES = {
    '.pyc', '.pyo', '.so', '.o', '.a', '.lib', '.dll', '.dylib',
    '.min.js', '.min.css', '.map', '.lock', '.log',
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.webp',
    '.woff', '.woff2', '.ttf', '.eot',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx',
    '.zip', '.tar', '.gz', '.rar'
}

# High-priority files to always include
PRIORITY_FILES = {
    'main.py': 100,
    'app.py': 100,
    'worker.py': 95,
    'models.py': 95,
    'schemas.py': 90,
    'routes.py': 90,
    'api.py': 90,
    'config.py': 85,
    'settings.py': 85,
    'database.py': 85,
    'orchestrator.py': 85,
    '__init__.py': 80,
    'requirements.txt': 75,
    'package.json': 75,
    'docker-compose.yml': 75,
    'Dockerfile': 70,
    'setup.py': 70,
    'pyproject.toml': 70,
}


def scan_project(project_path: str, max_files: int = 50) -> Dict[str, Any]:
    """
    Scan a project directory and return structured index.
    
    Args:
        project_path: Absolute path to project root
        max_files: Maximum number of files to index (for token budget)
        
    Returns:
        Structured project index with files, patterns, and metadata
    """
    project_path = os.path.abspath(project_path)
    
    if not os.path.exists(project_path):
        raise ValueError(f"Project path does not exist: {project_path}")
    
    logger.info(f"Scanning project: {project_path}")
    
    # Find all relevant files
    all_files = _find_files(project_path)
    logger.info(f"Found {len(all_files)} files")
    
    # Identify key files (prioritized)
    key_files = identify_key_files(all_files, max_files)
    logger.info(f"Selected {len(key_files)} key files for indexing")
    
    # Build file summaries
    files_index = {}
    for file_path in key_files:
        try:
            rel_path = os.path.relpath(file_path, project_path)
            summary = get_file_summary(file_path)
            files_index[rel_path] = summary
        except Exception as e:
            logger.warning(f"Failed to summarize {file_path}: {e}")
    
    # Detect patterns
    patterns = detect_patterns(files_index)
    
    # Build structure summary (directories)
    structure = _get_directory_structure(project_path)
    
    return {
        "root": project_path,
        "scanned_at": datetime.utcnow().isoformat(),
        "total_files": len(all_files),
        "indexed_files": len(files_index),
        "structure": structure,
        "key_files": files_index,
        "patterns": patterns
    }


def get_file_summary(file_path: str) -> Dict[str, Any]:
    """
    Extract metadata and summary from a single file.
    
    Args:
        file_path: Absolute path to file
        
    Returns:
        Dictionary with file metadata and content summary
    """
    file_path = os.path.abspath(file_path)
    stat = os.stat(file_path)
    ext = os.path.splitext(file_path)[1].lower()
    
    summary = {
        "type": _detect_file_type(file_path),
        "size": stat.st_size,
        "lines": 0,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
    }
    
    # Read file content for analysis
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
            summary["lines"] = len(lines)
            
            # Extract first 30 lines as preview
            summary["preview"] = '\n'.join(lines[:30])
    except Exception as e:
        logger.warning(f"Could not read {file_path}: {e}")
        return summary
    
    # Python-specific extraction using AST
    if ext == '.py':
        py_info = _analyze_python_file(content)
        summary.update(py_info)
    
    # JavaScript/TypeScript extraction (basic regex)
    elif ext in ('.js', '.jsx', '.ts', '.tsx'):
        js_info = _analyze_js_file(content)
        summary.update(js_info)
    
    # Config files
    elif ext in ('.json', '.yaml', '.yml', '.toml'):
        summary["type"] = "config"
    
    return summary


def identify_key_files(file_paths: List[str], max_files: int = 50) -> List[str]:
    """
    Identify important files to index based on priority heuristics.
    
    Args:
        file_paths: List of all file paths found
        max_files: Maximum number of files to return
        
    Returns:
        List of prioritized file paths
    """
    scored_files = []
    
    for file_path in file_paths:
        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()
        
        # Base score from priority list
        score = PRIORITY_FILES.get(filename, 0)
        
        # Boost Python files
        if ext == '.py':
            score += 30
        # Boost JS/TS files
        elif ext in ('.js', '.jsx', '.ts', '.tsx'):
            score += 25
        # Config files
        elif ext in ('.json', '.yaml', '.yml', '.toml'):
            score += 15
        # Docker/infra
        elif filename in ('Dockerfile', 'docker-compose.yml', 'docker-compose.yaml'):
            score += 20
        
        # Boost files in key directories
        path_lower = file_path.lower()
        if '/backend/' in path_lower or '/src/' in path_lower:
            score += 15
        if '/api/' in path_lower or '/routes/' in path_lower:
            score += 10
        if '/models/' in path_lower:
            score += 10
        
        # Penalize test files slightly (still useful but lower priority)
        if 'test' in filename.lower() or '/tests/' in path_lower:
            score -= 10
        
        scored_files.append((score, file_path))
    
    # Sort by score descending, take top N
    scored_files.sort(key=lambda x: x[0], reverse=True)
    return [f[1] for f in scored_files[:max_files]]


def detect_patterns(files_index: Dict[str, Dict]) -> Dict[str, Any]:
    """
    Infer tech stack and patterns from indexed files.
    
    Args:
        files_index: Dictionary of file paths to summaries
        
    Returns:
        Detected patterns and tech stack
    """
    patterns = {
        "tech_stack": [],
        "frameworks": [],
        "database": None,
        "api_style": None,
        "common_imports": []
    }
    
    all_imports = []
    
    for file_path, summary in files_index.items():
        imports = summary.get("imports", [])
        all_imports.extend(imports)
        
        # Detect frameworks from imports
        for imp in imports:
            if 'fastapi' in imp.lower():
                if 'FastAPI' not in patterns["frameworks"]:
                    patterns["frameworks"].append("FastAPI")
                patterns["api_style"] = "REST"
            elif 'flask' in imp.lower():
                if 'Flask' not in patterns["frameworks"]:
                    patterns["frameworks"].append("Flask")
                patterns["api_style"] = "REST"
            elif 'django' in imp.lower():
                if 'Django' not in patterns["frameworks"]:
                    patterns["frameworks"].append("Django")
            elif 'sqlalchemy' in imp.lower():
                patterns["database"] = "SQLAlchemy"
            elif 'redis' in imp.lower():
                if 'Redis' not in patterns["tech_stack"]:
                    patterns["tech_stack"].append("Redis")
            elif 'celery' in imp.lower() or 'rq' in imp.lower():
                if 'Task Queue' not in patterns["tech_stack"]:
                    patterns["tech_stack"].append("Task Queue")
            elif 'anthropic' in imp.lower():
                if 'Claude API' not in patterns["tech_stack"]:
                    patterns["tech_stack"].append("Claude API")
            elif 'openai' in imp.lower():
                if 'OpenAI API' not in patterns["tech_stack"]:
                    patterns["tech_stack"].append("OpenAI API")
            elif 'google.generativeai' in imp.lower():
                if 'Gemini API' not in patterns["tech_stack"]:
                    patterns["tech_stack"].append("Gemini API")
    
    # Check for package files
    for file_path in files_index.keys():
        if file_path == 'requirements.txt':
            patterns["tech_stack"].append("Python")
        elif file_path == 'package.json':
            patterns["tech_stack"].append("Node.js")
        elif 'docker-compose' in file_path:
            patterns["tech_stack"].append("Docker")
    
    # Find most common imports
    import_counts = {}
    for imp in all_imports:
        # Get top-level module
        top_level = imp.split('.')[0]
        if top_level not in ('os', 'sys', 'typing', 'datetime', 'json'):
            import_counts[top_level] = import_counts.get(top_level, 0) + 1
    
    patterns["common_imports"] = sorted(
        import_counts.keys(), 
        key=lambda x: import_counts[x], 
        reverse=True
    )[:10]
    
    return patterns


def _find_files(project_path: str) -> List[str]:
    """Find all relevant files in project, respecting skip lists."""
    files = []
    
    for root, dirs, filenames in os.walk(project_path):
        # Filter out skip directories
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
        
        for filename in filenames:
            # Skip by extension
            ext = os.path.splitext(filename)[1].lower()
            if ext in SKIP_FILES:
                continue
            
            # Skip hidden files
            if filename.startswith('.'):
                continue
                
            files.append(os.path.join(root, filename))
    
    return files


def _get_directory_structure(project_path: str, max_depth: int = 3) -> List[str]:
    """Get top-level directory structure."""
    structure = []
    
    for root, dirs, files in os.walk(project_path):
        # Filter skip dirs
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
        
        depth = root.replace(project_path, '').count(os.sep)
        if depth >= max_depth:
            continue
            
        rel_path = os.path.relpath(root, project_path)
        if rel_path == '.':
            continue
            
        structure.append(rel_path + '/')
    
    return sorted(structure)[:30]  # Limit to 30 directories


def _detect_file_type(file_path: str) -> str:
    """Detect file type/category."""
    filename = os.path.basename(file_path).lower()
    ext = os.path.splitext(filename)[1]
    
    if ext == '.py':
        return 'python'
    elif ext in ('.js', '.jsx'):
        return 'javascript'
    elif ext in ('.ts', '.tsx'):
        return 'typescript'
    elif ext in ('.json', '.yaml', '.yml', '.toml', '.ini', '.cfg'):
        return 'config'
    elif ext in ('.md', '.rst', '.txt'):
        return 'documentation'
    elif ext in ('.html', '.css', '.scss', '.less'):
        return 'web'
    elif ext in ('.sql',):
        return 'database'
    elif filename in ('dockerfile', 'docker-compose.yml', 'docker-compose.yaml'):
        return 'infrastructure'
    else:
        return 'other'


def _analyze_python_file(content: str) -> Dict[str, Any]:
    """Analyze Python file using AST."""
    result = {
        "classes": [],
        "functions": [],
        "imports": [],
        "decorators": []
    }
    
    try:
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            # Extract class names
            if isinstance(node, ast.ClassDef):
                result["classes"].append(node.name)
                # Get class decorators
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Name):
                        result["decorators"].append(dec.id)
                    elif isinstance(dec, ast.Attribute):
                        result["decorators"].append(dec.attr)
            
            # Extract function names (top-level only for brevity)
            elif isinstance(node, ast.FunctionDef):
                if not node.name.startswith('_') or node.name in ('__init__', '__call__'):
                    result["functions"].append(node.name)
            
            # Extract imports
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    result["imports"].append(alias.name)
            
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    result["imports"].append(node.module)
        
        # Deduplicate
        result["classes"] = list(dict.fromkeys(result["classes"]))[:10]
        result["functions"] = list(dict.fromkeys(result["functions"]))[:15]
        result["imports"] = list(dict.fromkeys(result["imports"]))[:20]
        result["decorators"] = list(dict.fromkeys(result["decorators"]))[:10]
        
    except SyntaxError as e:
        logger.warning(f"Could not parse Python file: {e}")
    
    return result


def _analyze_js_file(content: str) -> Dict[str, Any]:
    """Basic analysis of JS/TS files using regex."""
    import re
    
    result = {
        "classes": [],
        "functions": [],
        "imports": [],
        "exports": []
    }
    
    # Find class definitions
    class_pattern = r'class\s+(\w+)'
    result["classes"] = re.findall(class_pattern, content)[:10]
    
    # Find function definitions
    func_pattern = r'(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s*)?\()'
    matches = re.findall(func_pattern, content)
    result["functions"] = [m[0] or m[1] for m in matches if m[0] or m[1]][:15]
    
    # Find imports
    import_pattern = r"(?:import|from)\s+['\"]([^'\"]+)['\"]"
    result["imports"] = re.findall(import_pattern, content)[:20]
    
    # Find exports
    export_pattern = r'export\s+(?:default\s+)?(?:class|function|const)\s+(\w+)'
    result["exports"] = re.findall(export_pattern, content)[:10]
    
    return result


# Convenience function to check if scanner is available
def is_available() -> bool:
    """Check if scanner module is properly loaded."""
    return True
