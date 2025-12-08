# vdo-github/github_client.py
"""
GitHub API client for VDO integration.

This module provides high-level functions for interacting with the GitHub API
using PyGithub, including repository creation, existence checks, and retrieval.
"""

from typing import Dict, Optional
from github import Github, GithubException
from github.Repository import Repository

from .config import get_config
from .exceptions import AuthenticationError, RepoExistsError, ConfigurationError


class GitHubClient:
    """
    GitHub API client wrapper with authentication and error handling.
    """
    
    def __init__(self):
        """Initialize GitHub client with configuration."""
        try:
            config = get_config()
            self._token = config['token']
            self._username = config['username']
            self._github = Github(self._token)
            
            # Test authentication on initialization
            try:
                self._user = self._github.get_user()
                # Verify the username matches
                if self._user.login != self._username:
                    raise AuthenticationError(
                        f"Token belongs to user '{self._user.login}' but "
                        f"GITHUB_USERNAME is set to '{self._username}'"
                    )
            except GithubException as e:
                if e.status == 401:
                    raise AuthenticationError(
                        "Invalid GitHub token. Please check your GITHUB_TOKEN environment variable."
                    ) from e
                else:
                    raise AuthenticationError(f"GitHub API error: {e.data}") from e
                    
        except ConfigurationError:
            raise
        except Exception as e:
            raise AuthenticationError(f"Failed to initialize GitHub client: {str(e)}") from e
    
    def _get_repo_dict(self, repo: Repository) -> Dict[str, str]:
        """
        Convert GitHub repository object to dictionary.
        
        Args:
            repo: PyGithub Repository object
            
        Returns:
            dict: Repository information
        """
        return {
            'name': repo.name,
            'full_name': repo.full_name,
            'clone_url': repo.clone_url,
            'html_url': repo.html_url,
            'description': repo.description or "",
            'private': repo.private,
            'default_branch': repo.default_branch
        }


# Initialize global client instance
_client: Optional[GitHubClient] = None


def _get_client() -> GitHubClient:
    """Get or create GitHub client instance."""
    global _client
    if _client is None:
        _client = GitHubClient()
    return _client


def create_repo(name: str, description: str = "", private: bool = True) -> Dict[str, str]:
    """
    Create a new GitHub repository under the authenticated user.
    
    Args:
        name: Repository name (must be unique for the user)
        description: Repository description (optional)
        private: Whether the repository should be private (default: True)
        
    Returns:
        dict: Repository information containing:
            - name: Repository name
            - full_name: Full repository name (username/repo)
            - clone_url: HTTPS clone URL
            - html_url: GitHub web URL
            - description: Repository description
            - private: Whether repository is private
            - default_branch: Default branch name
    
    Raises:
        RepoExistsError: If repository with this name already exists
        AuthenticationError: If GitHub authentication fails
        
    Example:
        >>> repo_info = create_repo("my-project", "A VDO generated project")
        >>> print(f"Created: {repo_info['html_url']}")
    """
    try:
        client = _get_client()
        
        # Check if repository already exists
        if repo_exists(name):
            raise RepoExistsError(f"Repository '{name}' already exists for user '{client._username}'")
        
        # Create the repository
        repo = client._user.create_repo(
            name=name,
            description=description,
            private=private,
            auto_init=False,  # We'll initialize locally
            has_issues=True,
            has_wiki=True,
            has_downloads=True
        )
        
        return client._get_repo_dict(repo)
        
    except RepoExistsError:
        raise
    except GithubException as e:
        if e.status == 422:
            # Repository name already exists or invalid
            raise RepoExistsError(f"Repository '{name}' already exists or name is invalid") from e
        elif e.status == 401:
            raise AuthenticationError("Authentication failed. Please check your GitHub token.") from e
        elif e.status == 403:
            raise AuthenticationError("Access forbidden. Token may lack required permissions.") from e
        else:
            raise AuthenticationError(f"GitHub API error: {e.data}") from e
    except Exception as e:
        raise AuthenticationError(f"Unexpected error creating repository: {str(e)}") from e


def repo_exists(name: str) -> bool:
    """
    Check if a repository exists under the authenticated user.
    
    Args:
        name: Repository name to check
        
    Returns:
        bool: True if repository exists, False otherwise
        
    Example:
        >>> if repo_exists("my-project"):
        ...     print("Repository already exists")
        ... else:
        ...     print("Safe to create repository")
    """
    try:
        client = _get_client()
        client._github.get_repo(f"{client._username}/{name}")
        return True
    except GithubException as e:
        if e.status == 404:
            return False
        elif e.status == 401:
            raise AuthenticationError("Authentication failed. Please check your GitHub token.") from e
        else:
            # For other errors, assume repo doesn't exist or we can't access it
            return False
    except Exception:
        # For any other errors, assume repo doesn't exist
        return False


def get_repo(name: str) -> Optional[Dict[str, str]]:
    """
    Get repository information for an existing repository.
    
    Args:
        name: Repository name
        
    Returns:
        dict or None: Repository information if found, None if not found
            Dictionary contains same fields as create_repo()
            
    Raises:
        AuthenticationError: If GitHub authentication fails
        
    Example:
        >>> repo_info = get_repo("existing-project")
        >>> if repo_info:
        ...     print(f"Found repo: {repo_info['html_url']}")
        ... else:
        ...     print("Repository not found")
    """
    try:
        client = _get_client()
        repo = client._github.get_repo(f"{client._username}/{name}")
        return client._get_repo_dict(repo)
        
    except GithubException as e:
        if e.status == 404:
            return None
        elif e.status == 401:
            raise AuthenticationError("Authentication failed. Please check your GitHub token.") from e
        elif e.status == 403:
            raise AuthenticationError("Access forbidden. Token may lack required permissions.") from e
        else:
            raise AuthenticationError(f"GitHub API error: {e.data}") from e
    except Exception as e:
        raise AuthenticationError(f"Unexpected error retrieving repository: {str(e)}") from e


def get_user_info() -> Dict[str, str]:
    """
    Get authenticated user information.
    
    Returns:
        dict: User information containing login, name, email, etc.
        
    Raises:
        AuthenticationError: If GitHub authentication fails
        
    Example:
        >>> user_info = get_user_info()
        >>> print(f"Authenticated as: {user_info['login']}")
    """
    try:
        client = _get_client()
        user = client._user
        
        return {
            'login': user.login,
            'name': user.name or "",
            'email': user.email or "",
            'public_repos': user.public_repos,
            'private_repos': user.total_private_repos or 0,
            'html_url': user.html_url
        }
        
    except GithubException as e:
        if e.status == 401:
            raise AuthenticationError("Authentication failed. Please check your GitHub token.") from e
        else:
            raise AuthenticationError(f"GitHub API error: {e.data}") from e
    except Exception as e:
        raise AuthenticationError(f"Unexpected error getting user info: {str(e)}") from e
