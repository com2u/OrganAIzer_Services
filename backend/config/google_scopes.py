"""
Google OAuth scopes configuration.

Defines all OAuth scopes required for Google integration.
Includes scope versioning to detect permission changes.
"""

import hashlib
from typing import List

# Google OAuth scopes required for the application
GOOGLE_SCOPES: List[str] = [
    # Full calendar access (required for creating events, listing calendars)
    'https://www.googleapis.com/auth/calendar',
    # Calendar events (redundant with full calendar, but kept for compatibility)
    'https://www.googleapis.com/auth/calendar.events',
    # Gmail scopes
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    # OpenID and user info
    'https://www.googleapis.com/auth/userinfo.email',
    'openid',
]


def compute_scope_hash(scopes: List[str]) -> str:
    """
    Compute a hash of scopes for version tracking.
    
    Args:
        scopes: List of OAuth scope URLs
        
    Returns:
        SHA-256 hash of sorted, joined scopes
    """
    # Sort scopes for consistent hashing
    sorted_scopes = sorted(scopes)
    # Join with newlines
    scope_string = '\n'.join(sorted_scopes)
    # Compute SHA-256 hash
    return hashlib.sha256(scope_string.encode()).hexdigest()[:16]


# Current scope hash for validation
CURRENT_SCOPE_HASH = compute_scope_hash(GOOGLE_SCOPES)
