"""
High-level integration functions for VDO GitHub module.
These are the main functions that VDO will call to interact with GitHub.
"""

import os
from typing import Dict, Optional
from .config import get_config
from .github_client import create_repo, repo_exists
from .git_operations import init_and_push, commit_and_push, get_status
from .exceptions import VDOGitHubError, RepoExistsError, GitOperationError


def create_project_repo(project_name: str, project_path: str, description: str = "") -> Dict[str, str]:
    """
    Create a new GitHub repository and push local project code to it.
    
    This is the main function VDO will use to create new repositories.
    It handles the complete workflow: check if repo exists, create it,
    initialize git, and push the code.
    
    Args:
        project_name (str): Name for the GitHub repository
        project_path (str): Local path to the project directory
        description (str, optional): Repository description
        
    Returns:
        dict: Repository information containing:
            - name: Repository name
            - github_url: Web URL to view the repository
            - clone_url: URL to clone the repository
            - local_path: Local project path
            - commit_sha: SHA of the initial commit
            
    Raises:
        RepoExistsError: If repository already exists
        GitOperationError: If git operations fail
        VDOGitHubError: For other GitHub-related errors
    """
    try:
        # Validate inputs
        if not project_name or not project_name.strip():
            raise VDOGitHubError("Project name cannot be empty")
            
        if not os.path.exists(project_path):
            raise VDOGitHubError(f"Project path does not exist: {project_path}")
            
        # Clean project name for GitHub (replace spaces, special chars)
        clean_name = project_name.strip().replace(" ", "-").lower()
        clean_name = "".join(c for c in clean_name if c.isalnum() or c in "-_")
        
        # Check if repository already exists
        if repo_exists(clean_name):
            raise RepoExistsError(f"Repository '{clean_name}' already exists")
            
        # Create repository on GitHub
        repo_info = create_repo(clean_name, description, private=True)
        
        # Initialize git and push code
        try:
            commit_sha = init_and_push(project_path, repo_info['clone_url'])
        except Exception as e:
            raise GitOperationError(f"Failed to initialize git and push code: {str(e)}")
            
        return {
            'name': repo_info['name'],
            'github_url': repo_info['html_url'],
            'clone_url': repo_info['clone_url'],
            'local_path': project_path,
            'commit_sha': commit_sha
        }
        
    except (RepoExistsError, GitOperationError, VDOGitHubError):
        raise
    except Exception as e:
        raise VDOGitHubError(f"Unexpected error creating project repository: {str(e)}")


def save_changes(project_path: str, message: str) -> Dict[str, str]:
    """
    Save and push changes from a local project to its GitHub repository.
    
    This function commits all changes in the project directory and pushes
    them to the remote GitHub repository.
    
    Args:
        project_path (str): Local path to the project directory
        message (str): Commit message describing the changes
        
    Returns:
        dict: Commit information containing:
            - commit_sha: SHA of the new commit
            - message: The commit message used
            - branch: Branch that was updated
            - files_changed: Number of files that were modified
            
    Raises:
        GitOperationError: If git operations fail
        VDOGitHubError: For other errors
    """
    try:
        # Validate inputs
        if not os.path.exists(project_path):
            raise VDOGitHubError(f"Project path does not exist: {project_path}")
            
        if not message or not message.strip():
            raise VDOGitHubError("Commit message cannot be empty")
            
        # Check git status to see what's changed
        status = get_status(project_path)
        
        # Check if there are any changes to commit
        if status['clean']:
            return {
                'commit_sha': '',
                'message': 'No changes to commit',
                'branch': status['branch'],
                'files_changed': 0
            }
            
        # Count total files changed
        files_changed = len(status['modified_files']) + len(status['untracked_files'])
        
        # Commit and push changes
        try:
            commit_sha = commit_and_push(project_path, message.strip())
        except Exception as e:
            raise GitOperationError(f"Failed to commit and push changes: {str(e)}")
            
        return {
            'commit_sha': commit_sha,
            'message': message.strip(),
            'branch': status['branch'],
            'files_changed': files_changed
        }
        
    except (GitOperationError, VDOGitHubError):
        raise
    except Exception as e:
        raise VDOGitHubError(f"Unexpected error saving changes: {str(e)}")


def sync_project(project_path: str, auto_message: bool = True) -> Dict[str, str]:
    """
    Automatically sync a project with its GitHub repository.
    
    This is a convenience function that automatically generates commit messages
    based on the changes detected, useful for automated syncing.
    
    Args:
        project_path (str): Local path to the project directory
        auto_message (bool): Whether to generate automatic commit messages
        
    Returns:
        dict: Same as save_changes()
        
    Raises:
        GitOperationError: If git operations fail
        VDOGitHubError: For other errors
    """
    try:
        # Get current status
        status = get_status(project_path)
        
        if status['clean']:
            return {
                'commit_sha': '',
                'message': 'No changes to sync',
                'branch': status['branch'],
                'files_changed': 0
            }
            
        # Generate automatic commit message if requested
        if auto_message:
            modified_count = len(status['modified_files'])
            new_count = len(status['untracked_files'])
            
            message_parts = []
            if modified_count > 0:
                message_parts.append(f"Updated {modified_count} file{'s' if modified_count != 1 else ''}")
            if new_count > 0:
                message_parts.append(f"Added {new_count} new file{'s' if new_count != 1 else ''}")
                
            message = "VDO Auto-sync: " + ", ".join(message_parts)
        else:
            message = "VDO project sync"
            
        return save_changes(project_path, message)
        
    except Exception as e:
        raise VDOGitHubError(f"Failed to sync project: {str(e)}")


def get_project_status(project_path: str) -> Dict:
    """
    Get detailed status information about a project's git repository.
    
    Args:
        project_path (str): Local path to the project directory
        
    Returns:
        dict: Extended status information including git status and summary
        
    Raises:
        VDOGitHubError: If unable to get status
    """
    try:
        if not os.path.exists(project_path):
            raise VDOGitHubError(f"Project path does not exist: {project_path}")
            
        status = get_status(project_path)
        
        # Add summary information
        total_changes = len(status['modified_files']) + len(status['untracked_files'])
        
        return {
            **status,
            'total_changes': total_changes,
            'has_changes': not status['clean'],
            'summary': f"{total_changes} file{'s' if total_changes != 1 else ''} changed" if total_changes > 0 else "No changes"
        }
        
    except Exception as e:
        raise VDOGitHubError(f"Failed to get project status: {str(e)}")
