# vdo-github/config.py
"""
Configuration module for VDO GitHub Integration.
Loads GitHub credentials from environment variables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from .exceptions import ConfigurationError


def _find_env_file():
    """
    Find the .env file by checking multiple possible locations.
    
    Returns:
        Path: Path to the .env file
        
    Raises:
        ConfigurationError: If .env file is not found
    """
    current_dir = Path(__file__).parent
    possible_paths = [
        # Check parent directory (.env)
        current_dir.parent / '.env',
        # Check backend directory (backend/.env)
        current_dir.parent / 'backend' / '.env',
        # Check current directory
        current_dir / '.env',
        # Check if we're already in backend directory
        current_dir / '../.env'
    ]
    
    for env_path in possible_paths:
        if env_path.exists() and env_path.is_file():
            return env_path
    
    raise ConfigurationError(
        f"Could not find .env file. Searched in: {[str(p) for p in possible_paths]}"
    )


def _load_environment():
    """
    Load environment variables from .env file if available.
    Falls back to existing environment variables if no file found.
    """
    try:
        env_file = _find_env_file()
        load_dotenv(env_file)
    except ConfigurationError:
        # No .env file found - that's OK, env vars may already be set
        pass
    except Exception as e:
        # Other errors - log but don't fail
        print(f"Warning: Could not load .env file: {e}")


def get_config():
    """
    Get GitHub configuration from environment variables.
    
    Returns:
        dict: Configuration dictionary with keys:
            - token (str): GitHub personal access token
            - username (str): GitHub username
            
    Raises:
        ConfigurationError: If required environment variables are missing or invalid
    """
    # Load environment variables from .env file
    _load_environment()
    
    # Get required environment variables
    token = os.getenv('GITHUB_TOKEN')
    username = os.getenv('GITHUB_USERNAME')
    
    # Validate that both variables are present and non-empty
    missing_vars = []
    if not token or token.strip() == '':
        missing_vars.append('GITHUB_TOKEN')
    if not username or username.strip() == '':
        missing_vars.append('GITHUB_USERNAME')
    
    if missing_vars:
        raise ConfigurationError(
            f"Missing required environment variables: {', '.join(missing_vars)}. "
            f"Please set them in your .env file."
        )
    
    # Basic validation for token format (should start with 'ghp_' or similar)
    token = token.strip()
    username = username.strip()
    
    if len(token) < 20:
        raise ConfigurationError(
            "GITHUB_TOKEN appears to be invalid (too short). "
            "Please ensure you're using a valid GitHub Personal Access Token."
        )
    
    if not username.replace('-', '').replace('_', '').isalnum():
        raise ConfigurationError(
            "GITHUB_USERNAME contains invalid characters. "
            "GitHub usernames can only contain alphanumeric characters, hyphens, and underscores."
        )
    
    return {
        'token': token,
        'username': username
    }


def validate_config():
    """
    Validate the current configuration without returning sensitive data.
    
    Returns:
        dict: Validation result with keys:
            - valid (bool): Whether configuration is valid
            - username (str): GitHub username (safe to display)
            - token_length (int): Length of token (for verification without exposing)
            - errors (list): List of validation errors if any
    """
    try:
        config = get_config()
        return {
            'valid': True,
            'username': config['username'],
            'token_length': len(config['token']),
            'errors': []
        }
    except ConfigurationError as e:
        return {
            'valid': False,
            'username': None,
            'token_length': 0,
            'errors': [str(e)]
        }


def get_github_auth_url(username, token):
    """
    Generate authenticated GitHub URL for git operations.
    
    Args:
        username (str): GitHub username
        token (str): GitHub token
        
    Returns:
        str: Base URL for authenticated GitHub operations
    """
    return f"https://{username}:{token}@github.com"


def get_repo_url(repo_name, username=None, token=None):
    """
    Generate full repository URL for git operations.
    
    Args:
        repo_name (str): Repository name
        username (str, optional): GitHub username (loads from config if not provided)
        token (str, optional): GitHub token (loads from config if not provided)
        
    Returns:
        str: Full repository URL with authentication
        
    Raises:
        ConfigurationError: If configuration cannot be loaded
    """
    if username is None or token is None:
        config = get_config()
        username = username or config['username']
        token = token or config['token']
    
    return f"https://{username}:{token}@github.com/{username}/{repo_name}.git"
