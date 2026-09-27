"""
Google OAuth2 Authentication for PorpoiseID Annotation Platform.
Provides Google Sign-In with email whitelist access control.
"""
import os
import json
import time
import logging
import secrets
import tempfile
import threading
from pathlib import Path
from urllib.parse import quote
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from functools import wraps
from contextlib import contextmanager
import jwt
_jwt_secret = None
JWT_EXPIRY_HOURS = 24

def set_jwt_secret(secret: str):
    """Set the JWT secret (call from app.py after loading the shared secret key)."""
    ...
_fallback_secret = None

def _get_jwt_secret() -> str:
    """Return JWT secret, falling back to a cached per-process random if not set."""
    ...

def _legacy_token_filename(email: str) -> str:
    """The pre-fix name. NOT injective — kept only so existing logins survive."""
    ...

def _legacy_name_is_unambiguous(email: str) -> bool:
    """Could any OTHER address have produced this address's legacy filename?

    The old scheme collapsed both "@"->"_at_" and "."->"_", so `ada.lovelace@x`
    and `ada_lovelace@x` produced the SAME file. Only the LOCAL part can collide
    in practice (registrable domains do not contain underscores), so a local part
    with neither a dot nor an underscore has exactly one possible source address
    and its legacy file is provably its own.

    Anything else re-authenticates instead of reading a file that might belong to
    somebody else. One extra sign-in is a far better outcome than handing one
    person another person's Google credentials.
    """
    ...

def token_path(email: str) -> Path:
    """Where this account's cached Google credentials live.

    Percent-encoded rather than character-substituted, because the old scheme

        email.replace("@", "_at_").replace(".", "_")

    is not injective: two real addresses differing only by dot-vs-underscore in
    the local part mapped to one file, so whoever signed in second silently
    overwrote the first one's token — and every later Drive/Sheets call made on
    behalf of the first user then ran as the second. `quote(..., safe="")` is
    reversible, so distinct addresses cannot collide.

    Lower-cased first: Google returns a canonical lower-case address, but callers
    pass whatever they are holding, and two casings must not become two files.
    """
    ...

def _resolve_token_path(email: str) -> Path:
    """The canonical path, adopting a legacy file when it is provably this user's.

    Migrates by rename so the old, ambiguous name stops being consulted at all.
    """
    ...

def _atomic_write_json(path: Path, data: str) -> None:
    """Write text to `path` atomically: a temp file in the same directory, fsync,
    then os.replace() (an atomic rename on POSIX). A reader therefore always sees
    either the old complete file or the new complete file — never a torn one."""
    ...

@contextmanager
def _token_file_lock(token_path: Path):
    """Cross-process exclusive lock for one user's token, so only one worker
    refreshes/writes it at a time (the threading lock covers only one process).
    Advisory flock is released automatically if the holder dies. No-op where
    fcntl is unavailable."""
    ...

class AuthError(Exception):
    """Authentication error"""

class User:
    """Authenticated user"""

    def __init__(self, email: str, name: str='', picture: str='', is_admin: bool=False, credentials: Optional[Credentials]=None):
        ...

    def to_dict(self) -> Dict[str, Any]:
        ...

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        ...

class GoogleAuth:
    """
    Google OAuth2 authentication manager.

    Usage:
        auth = GoogleAuth()

        # Start OAuth flow
        auth_url, state = auth.get_auth_url(redirect_uri)

        # Handle callback
        user = auth.handle_callback(code, state, redirect_uri)

        # Create session token
        token = auth.create_session_token(user)

        # Verify session
        user = auth.verify_session_token(token)
    """

    def __init__(self, credentials_path: str=None, allowed_users_path: str=None):
        """
        Initialize Google Auth.

        Args:
            credentials_path: Path to OAuth credentials JSON
            allowed_users_path: Path to allowed users file
        """
        ...

    def _load_allowed_users(self):
        """Load whitelist of allowed email addresses"""
        ...

    def is_whitelisted(self, email: str) -> bool:
        """Check if email is in whitelist"""
        ...

    def is_admin(self, email: str) -> bool:
        """Check if email is an admin"""
        ...

    def add_allowed_user(self, email: str, is_admin: bool=False):
        """Add user to whitelist (in memory, not persisted)"""
        ...

    def get_auth_url(self, redirect_uri: str) -> tuple:
        """
        Get Google OAuth authorization URL.

        Args:
            redirect_uri: Callback URL after authentication

        Returns:
            Tuple of (auth_url, state, code_verifier)
        """
        ...

    def handle_callback(self, code: str, state: str, redirect_uri: str, code_verifier: str='') -> 'User':
        """
        Handle OAuth callback.

        Args:
            code: Authorization code from Google
            state: State parameter for CSRF validation
            redirect_uri: Must match the one used in get_auth_url
            code_verifier: PKCE code_verifier from cookie (for multi-worker support)

        Returns:
            Authenticated User object

        Raises:
            AuthError: If authentication fails or user not whitelisted
        """
        ...

    def _get_user_info(self, credentials: Credentials) -> Dict[str, Any]:
        """Get user profile info from Google"""
        ...

    def _save_user_credentials(self, email: str, credentials: Credentials):
        """Cache user credentials for later use.

        If the new credentials lack a refresh_token (e.g. select_account login
        for a returning user), preserve the existing cached refresh_token so
        Drive API calls continue to work.
        """
        ...

    def get_user_credentials(self, email: str) -> Optional[Credentials]:
        """Retrieve cached credentials for a user"""
        ...

    def create_session_token(self, user: 'User') -> str:
        """
        Create a JWT session token for authenticated user.

        Args:
            user: Authenticated user

        Returns:
            JWT token string
        """
        ...

    def verify_session_token(self, token: str) -> Optional['User']:
        """
        Verify JWT session token.

        Args:
            token: JWT token string

        Returns:
            User object if valid, None otherwise
        """
        ...

    def logout(self, email: str):
        """
        Logout user (clear cached credentials).

        Args:
            email: User email
        """
        ...

class SessionManager:
    """
    Session manager for Gradio apps.
    Stores session state in memory (suitable for single-instance deployment).
    """

    def __init__(self):
        ...

    @property
    def auth(self) -> GoogleAuth:
        """Lazy-load GoogleAuth"""
        ...

    def create_session(self, user: User) -> str:
        """Create session for user, return session token"""
        ...

    def get_user(self, token: str) -> Optional[User]:
        """Get user from session token"""
        ...

    def end_session(self, token: str):
        """End session"""
        ...

def require_auth(func):
    """
    Decorator to require authentication for a function.
    The decorated function must accept 'session_token' as first argument.
    """
    ...

def require_admin(func):
    """
    Decorator to require admin privileges.
    """
    ...

def setup_allowed_users():
    """Interactive setup for allowed users file"""
    ...
