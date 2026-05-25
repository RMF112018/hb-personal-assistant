"""Custom exceptions for auth provider and token cache (Phase 2).

All exceptions carry only safe, redacted information for logs/evidence.
"""

from __future__ import annotations


class AuthError(Exception):
    """Base class for auth-related errors (safe messages only)."""
    pass


class NoTokenError(AuthError):
    """No valid token available for the requested scopes / mode."""
    pass


class ClassificationError(AuthError):
    """Token claims could not be classified or failed closed per policy."""
    pass


class TokenCacheError(AuthError):
    """Error reading/writing/persisting the MSAL token cache files."""
    pass


class CertificateError(AuthError):
    """Problem loading or using the certificate bundle for app-only auth."""
    pass
