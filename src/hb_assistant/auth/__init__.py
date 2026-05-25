"""Auth provider package (Phase 2).

Exports:
- TokenCacheManager
- DelegatedAuthProvider, AppOnlyAuthProvider
- classify_token_claims, require_delegated, safe_redact_claims
- Custom exceptions
"""

from .classifier import (
    TokenType,
    classify_token_claims,
    require_delegated,
    safe_redact_claims,
)
from .exceptions import (
    AuthError,
    CertificateError,
    ClassificationError,
    NoTokenError,
    TokenCacheError,
)
from .providers import AppOnlyAuthProvider, DelegatedAuthProvider
from .token_cache_manager import TokenCacheManager

__all__ = [
    "TokenCacheManager",
    "DelegatedAuthProvider",
    "AppOnlyAuthProvider",
    "classify_token_claims",
    "require_delegated",
    "safe_redact_claims",
    "TokenType",
    "AuthError",
    "NoTokenError",
    "ClassificationError",
    "TokenCacheError",
    "CertificateError",
]
