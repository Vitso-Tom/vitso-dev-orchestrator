"""
Git operations module for VDO GitHub Integration.
Handles local git repository operations using GitPython.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional
import git
from git import Repo, InvalidGitRepositoryError, GitCommandError
from urllib.parse import urlparse, urlunparse

from .exceptions import GitOperationError, ConfigurationError
from .config import get_config


def _get_authenticated_url(remote_url: str) -> str:
    """
    Convert a GitHub URL to include authentication credentials.
    
    Args:
        remote_url: GitHub repository URL (HTTPS)
        
    Returns:
        Authenticated URL with token credentials
        
    Raises:
        ConfigurationError: If GitHub credentials are missing
    """
    config = get_config()
    username = config['username']
    token = config['token']
    
    # Parse the URL
    parsed = urlparse(remote_url)
    
    # Reconstruct with authentication
    auth_netloc = f"{username}:{token}@{parsed.netloc}"
    auth_url = urlunparse((
        parsed.scheme,
        auth_netloc,
        parsed.path,
        parsed.params,
        parsed.query,
        parsed.fragment
    ))
    
    return auth_url


def init_and_push(local_path: str, remote_url: str, branch: str = "main") -> str:
    """
    Initialize git repository and push to remote.
    
    Args:
        local_path: Path to local project directory
        remote_url: GitHub repository clone URL
        branch: Branch name to create and push to (default: "main")
        
    Returns:
        Commit SHA of the initial commit
        
    Raises:
        GitOperationError: If any git operation fails
    """
    try:
        local_path = Path(local_path).resolve()
        
        if not local_path.exists():
            raise GitOperationError(f"Local path does not exist: {local_path}")
        
        # Check if already a git repository
        try:
            repo = Repo(local_path)
        except InvalidGitRepositoryError:
            # Initialize new repository
            repo = Repo.init(local_path)
            print(f"Initialized git repository in {local_path}")
        
        # Configure user if not set globally
        try:
            config = get_config()
            if not repo.config_reader().has_option('user', 'name'):
                repo.config_writer().set_value('user', 'name', config['username']).release()
            if not repo.config_reader().has_option('user', 'email'):
                # Use GitHub noreply email format
                noreply_email = f"{config['username']}@users.noreply.github.com"
                repo.config_writer().set_value('user', 'email', noreply_email).release()
        except Exception as e:
            print(f"Warning: Could not configure git user: {e}")
        
        # Add remote origin (remove existing if present)
        auth_url = _get_authenticated_url(remote_url)
        
        if 'origin' in [remote.name for remote in repo.remotes]:
            repo.delete_remote('origin')
        
        origin = repo.create_remote('origin', auth_url)
        print(f"Added remote origin: {remote_url}")
        
        # Add all files
        repo.git.add(A=True)
        
        # Check if there are files to commit
        # Note: In a fresh repo, HEAD doesn't exist yet, so we check differently
        try:
            has_staged = bool(repo.index.diff("HEAD"))
        except git.exc.BadName:
            # No HEAD yet (fresh repo) - check if index has entries
            has_staged = len(repo.index.entries) > 0
        
        if not has_staged and not repo.untracked_files:
            raise GitOperationError("No files to commit in repository")
        
        # Create initial commit
        commit = repo.index.commit("Initial commit from VDO")
        commit_sha = commit.hexsha
        print(f"Created initial commit: {commit_sha[:8]}")
        
        # Create and checkout main branch if needed
        if branch != repo.active_branch.name:
            try:
                repo.git.checkout('-b', branch)
            except GitCommandError:
                # Branch might already exist
                repo.git.checkout(branch)
        
        # Push to remote
        origin.push(refspec=f"{branch}:{branch}", set_upstream=True)
        print(f"Pushed to remote branch: {branch}")
        
        return commit_sha
        
    except GitCommandError as e:
        raise GitOperationError(f"Git command failed: {e}")
    except Exception as e:
        raise GitOperationError(f"Failed to initialize and push repository: {e}")


def commit_and_push(local_path: str, message: str) -> str:
    """
    Add changes, commit, and push to remote repository.
    
    Args:
        local_path: Path to local git repository
        message: Commit message
        
    Returns:
        Commit SHA of the new commit
        
    Raises:
        GitOperationError: If any git operation fails
    """
    try:
        local_path = Path(local_path).resolve()
        
        if not local_path.exists():
            raise GitOperationError(f"Local path does not exist: {local_path}")
        
        # Open repository
        try:
            repo = Repo(local_path)
        except InvalidGitRepositoryError:
            raise GitOperationError(f"Not a git repository: {local_path}")
        
        # Add all changes
        repo.git.add(A=True)
        
        # Check if there are changes to commit
        if not repo.index.diff("HEAD") and not repo.untracked_files:
            print("No changes to commit")
            # Return the current HEAD commit SHA
            return repo.head.commit.hexsha
        
        # Create commit
        commit = repo.index.commit(message)
        commit_sha = commit.hexsha
        print(f"Created commit: {commit_sha[:8]} - {message}")
        
        # Push to remote
        if repo.remotes:
            origin = repo.remotes.origin
            current_branch = repo.active_branch.name
            origin.push(refspec=f"{current_branch}:{current_branch}")
            print(f"Pushed changes to remote")
        else:
            print("Warning: No remote configured, changes committed locally only")
        
        return commit_sha
        
    except GitCommandError as e:
        raise GitOperationError(f"Git command failed: {e}")
    except Exception as e:
        raise GitOperationError(f"Failed to commit and push changes: {e}")


def get_status(local_path: str) -> Dict:
    """
    Get the current status of the git repository.
    
    Args:
        local_path: Path to local git repository
        
    Returns:
        Dictionary containing:
        - branch: Current branch name
        - clean: True if working directory is clean
        - modified_files: List of modified files
        - untracked_files: List of untracked files
        - staged_files: List of files staged for commit
        - behind: Number of commits behind remote (if available)
        - ahead: Number of commits ahead of remote (if available)
        
    Raises:
        GitOperationError: If repository access fails
    """
    try:
        local_path = Path(local_path).resolve()
        
        if not local_path.exists():
            raise GitOperationError(f"Local path does not exist: {local_path}")
        
        # Open repository
        try:
            repo = Repo(local_path)
        except InvalidGitRepositoryError:
            raise GitOperationError(f"Not a git repository: {local_path}")
        
        # Get current branch
        try:
            current_branch = repo.active_branch.name
        except TypeError:
            # Detached HEAD state
            current_branch = "HEAD (detached)"
        
        # Get file status
        modified_files = [item.a_path for item in repo.index.diff(None)]
        untracked_files = repo.untracked_files
        staged_files = [item.a_path for item in repo.index.diff("HEAD")]
        
        # Check if working directory is clean
        is_clean = len(modified_files) == 0 and len(untracked_files) == 0 and len(staged_files) == 0
        
        # Try to get remote tracking info
        behind = 0
        ahead = 0
        
        try:
            if repo.remotes and current_branch != "HEAD (detached)":
                origin = repo.remotes.origin
                # Fetch to get latest remote info
                origin.fetch()
                
                # Get tracking branch
                tracking_branch = repo.active_branch.tracking_branch()
                if tracking_branch:
                    # Count commits behind and ahead
                    behind = len(list(repo.iter_commits(f'{current_branch}..{tracking_branch}')))
                    ahead = len(list(repo.iter_commits(f'{tracking_branch}..{current_branch}')))
        except Exception as e:
            # Remote tracking info not available
            print(f"Warning: Could not get remote tracking info: {e}")
        
        status = {
            'branch': current_branch,
            'clean': is_clean,
            'modified_files': modified_files,
            'untracked_files': list(untracked_files),
            'staged_files': staged_files,
            'behind': behind,
            'ahead': ahead
        }
        
        return status
        
    except GitCommandError as e:
        raise GitOperationError(f"Git command failed: {e}")
    except Exception as e:
        raise GitOperationError(f"Failed to get repository status: {e}")


def clone_repository(remote_url: str, local_path: str, branch: str = "main") -> str:
    """
    Clone a repository from remote URL.
    
    Args:
        remote_url: GitHub repository clone URL
        local_path: Local path where to clone the repository
        branch: Branch to clone (default: "main")
        
    Returns:
        Path to the cloned repository
        
    Raises:
        GitOperationError: If clone operation fails
    """
    try:
        local_path = Path(local_path).resolve()
        
        # Ensure parent directory exists
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Remove existing directory if it exists and is empty
        if local_path.exists():
            if local_path.is_dir() and not any(local_path.iterdir()):
                local_path.rmdir()
            elif local_path.exists():
                raise GitOperationError(f"Directory already exists and is not empty: {local_path}")
        
        # Get authenticated URL
        auth_url = _get_authenticated_url(remote_url)
        
        # Clone repository
        repo = Repo.clone_from(auth_url, local_path, branch=branch)
        print(f"Cloned repository to: {local_path}")
        
        return str(local_path)
        
    except GitCommandError as e:
        raise GitOperationError(f"Git clone failed: {e}")
    except Exception as e:
        raise GitOperationError(f"Failed to clone repository: {e}")


def is_git_repository(local_path: str) -> bool:
    """
    Check if a directory is a git repository.
    
    Args:
        local_path: Path to check
        
    Returns:
        True if directory is a git repository, False otherwise
    """
    try:
        local_path = Path(local_path).resolve()
        if not local_path.exists():
            return False
        
        Repo(local_path)
        return True
    except InvalidGitRepositoryError:
        return False
    except Exception:
        return False


def get_remote_url(local_path: str, remote_name: str = "origin") -> Optional[str]:
    """
    Get the URL of a remote repository.
    
    Args:
        local_path: Path to local git repository
        remote_name: Name of the remote (default: "origin")
        
    Returns:
        Remote URL without authentication credentials, or None if not found
        
    Raises:
        GitOperationError: If repository access fails
    """
    try:
        local_path = Path(local_path).resolve()
        
        if not local_path.exists():
            raise GitOperationError(f"Local path does not exist: {local_path}")
        
        try:
            repo = Repo(local_path)
        except InvalidGitRepositoryError:
            raise GitOperationError(f"Not a git repository: {local_path}")
        
        if remote_name not in [remote.name for remote in repo.remotes]:
            return None
        
        remote = repo.remotes[remote_name]
        url = remote.url
        
        # Remove authentication from URL for display
        parsed = urlparse(url)
        if '@' in parsed.netloc:
            # Remove username:password@ part
            netloc = parsed.netloc.split('@')[-1]
            clean_url = urlunparse((
                parsed.scheme,
                netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))
            return clean_url
        
        return url
        
    except Exception as e:
        raise GitOperationError(f"Failed to get remote URL: {e}")
