# vdo-github/exceptions.py
"""
Custom exceptions for VDO GitHub Integration Module.

This module defines all custom exceptions used throughout the VDO GitHub
integration system, providing clear error handling and debugging information.
"""


class VDOGitHubError(Exception):
    """
    Base exception for all VDO GitHub integration errors.
    
    All other custom exceptions in this module inherit from this base class,
    allowing for broad exception handling when needed.
    """
    pass


class ConfigurationError(VDOGitHubError):
    """
    Raised when configuration is missing or invalid.
    
    This includes missing environment variables (GITHUB_TOKEN, GITHUB_USERNAME)
    or invalid configuration values that prevent the module from functioning.
    
    Examples:
        - Missing GITHUB_TOKEN environment variable
        - Missing GITHUB_USERNAME environment variable
        - Invalid or malformed configuration values
    """
    pass


class AuthenticationError(VDOGitHubError):
    """
    Raised when GitHub authentication fails.
    
    This occurs when the provided GitHub token is invalid, expired, or lacks
    the necessary permissions to perform the requested operation.
    
    Examples:
        - Invalid GitHub personal access token
        - Expired token
        - Token without required 'repo' scope
        - Rate limit exceeded
    """
    pass


class RepoExistsError(VDOGitHubError):
    """
    Raised when attempting to create a repository that already exists.
    
    This prevents accidental overwrites and provides clear feedback when
    repository creation fails due to naming conflicts.
    
    Examples:
        - Creating a repo with a name that already exists for the user
        - Attempting to initialize a project that's already on GitHub
    """
    pass


class GitOperationError(VDOGitHubError):
    """
    Raised when local git operations fail.
    
    This covers failures in local git commands such as init, add, commit,
    push, or other git operations performed through GitPython.
    
    Examples:
        - Failed to initialize git repository
        - Commit failed due to no changes
        - Push failed due to authentication or network issues
        - Invalid git repository state
    """
    pass
