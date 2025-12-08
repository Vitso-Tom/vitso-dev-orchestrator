"""
VDO GitHub Integration Module

This module provides seamless integration between VDO and GitHub,
allowing VDO to create repositories and manage code synchronization.

Main Functions:
- create_project_repo: Create new GitHub repository and push code
- save_changes: Commit and push changes to existing repository
- sync_project: Automatically sync project with GitHub
- get_project_status: Get detailed project status information

Utility Functions:
- repo_exists: Check if a repository exists
- get_repo: Get repository information
- get_status: Get git status of local repository
- get_config: Get current configuration

Example Usage:
    from vdo_github import create_project_repo, save_changes
    
    # Create a new repository
    result = create_project_repo(
        project_name="my-new-project",
        project_path="/path/to/project",
        description="My awesome project created with VDO"
    )
    print(f"Created repository: {result['github_url']}")
    
    # Save changes later
    save_result = save_changes(
        project_path="/path/to/project",
        message="Updated project features"
    )
    print(f"Committed changes: {save_result['commit_sha']}")
"""

# Import main integration functions
from .integration import (
    create_project_repo,
    save_changes,
    sync_project,
    get_project_status
)

# Import utility functions
from .github_client import (
    repo_exists,
    get_repo
)

from .git_operations import (
    get_status
)

from .config import (
    get_config
)

# Import exceptions for error handling
from .exceptions import (
    VDOGitHubError,
    ConfigurationError,
    AuthenticationError,
    RepoExistsError,
    GitOperationError
)

# Define what gets imported with "from vdo_github import *"
__all__ = [
    # Main integration functions
    'create_project_repo',
    'save_changes',
    'sync_project',
    'get_project_status',
    
    # Utility functions
    'repo_exists',
    'get_repo',
    'get_status',
    'get_config',
    
    # Exceptions
    'VDOGitHubError',
    'ConfigurationError',
    'AuthenticationError',
    'RepoExistsError',
    'GitOperationError'
]

# Module metadata
__version__ = "1.0.0"
__author__ = "VDO Team"
__description__ = "GitHub integration module for VDO"

# Convenience function to check if module is properly configured
def is_configured() -> bool:
    """
    Check if the GitHub integration is properly configured.
    
    Returns:
        bool: True if GITHUB_TOKEN and GITHUB_USERNAME are available
    """
    try:
        config = get_config()
        return bool(config.get('token') and config.get('username'))
    except ConfigurationError:
        return False

def get_module_info() -> dict:
    """
    Get information about this module.
    
    Returns:
        dict: Module information including version and configuration status
    """
    return {
        'name': 'vdo-github',
        'version': __version__,
        'description': __description__,
        'configured': is_configured(),
        'available_functions': __all__
    }
