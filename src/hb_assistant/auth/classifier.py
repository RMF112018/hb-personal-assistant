"""Token classification logic (strict, fail-closed) per 04_Auth_And_Permissions_Model.

This module never handles raw tokens — only claims dicts (safe for tests/evidence).
"""

from __future__ import annotations

from typing import Literal

from .exceptions import ClassificationError


TokenType = Literal["delegated", "app_only", "ambiguous", "invalid"]


def classify_token_claims(claims: dict | None) -> TokenType:
    """Classify a decoded JWT claims dict (or None) into one of four states.

    Rules (exact match to 04 spec):
    - Delegated: 'scp' present (truthy)
    - App-only: 'roles' present (truthy) AND 'scp' absent/empty
    - Ambiguous: both 'scp' and 'roles' present
    - Invalid: neither, or claims is None/empty
    """
    if not claims or not isinstance(claims, dict):
        return "invalid"

    has_scp = bool(claims.get("scp"))
    has_roles = bool(claims.get("roles"))

    if has_scp and has_roles:
        return "ambiguous"
    if has_scp:
        return "delegated"
    if has_roles:
        return "app_only"
    return "invalid"


def require_delegated(claims: dict | None, *, context: str = "") -> None:
    """Raise ClassificationError (fail-closed) unless the token is cleanly delegated.

    Used by runtime paths (providers, clients) before any mail/calendar/file work.
    """
    t = classify_token_claims(claims)
    if t != "delegated":
        msg = f"Delegated token required{t and ' (' + t + ')' or ''}"
        if context:
            msg += f" for {context}"
        raise ClassificationError(msg)


def safe_redact_claims(claims: dict | None) -> dict:
    """Return a redacted copy of claims safe for --json output, logs, evidence.

    Never includes access_token, id_token, refresh_token, or full 'scp' lists if long.
    """
    if not claims:
        return {}
    safe = {
        "aud": claims.get("aud"),
        "iss": claims.get("iss"),
        "tid": claims.get("tid"),
        "upn": claims.get("upn") or claims.get("unique_name"),
        "name": claims.get("name"),
        "oid": claims.get("oid"),
        "appid": claims.get("appid") or claims.get("azp"),
        "token_type": "delegated" if claims.get("scp") else ("app_only" if claims.get("roles") else "unknown"),
        "scp_count": len(str(claims.get("scp", "")).split()) if claims.get("scp") else 0,
        "roles": claims.get("roles") if isinstance(claims.get("roles"), list) else None,
        "exp": claims.get("exp"),
        "iat": claims.get("iat"),
    }
    return {k: v for k, v in safe.items() if v is not None}
