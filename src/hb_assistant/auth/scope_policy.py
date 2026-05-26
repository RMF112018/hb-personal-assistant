"""Central scope sanitizer for delegated Microsoft Graph auth.

Removes MSAL-reserved scopes (openid, profile, offline_access) before
any acquire_token_* call. Preserves Graph scopes, de-duplicates while
preserving order, and provides diagnostic visibility.

This fixes the delegated login blocker where offline_access (and siblings)
were passed to MSAL, which rejects them.
"""

from __future__ import annotations

from typing import Iterable, List

# MSAL-reserved scopes that must never be sent in the delegated acquire request.
# See: https://github.com/AzureAD/microsoft-authentication-library-for-python
RESERVED_SCOPES: frozenset[str] = frozenset({
    "openid",
    "profile",
    "offline_access",
})

# Canonical Graph scopes we expect to keep (case-insensitive match on input).
# We preserve whatever non-reserved scopes the user configured.
EXPECTED_GRAPH_SCOPES = {
    "user.read",
    "mail.read",
    "calendars.read",
    "files.read.all",
}


def _normalize(s: str) -> str:
    return s.strip().lower()


def sanitize_delegated_scopes(scopes: Iterable[str]) -> List[str]:
    """Return a clean list of scopes safe to pass to MSAL for delegated login.

    Rules (per defect fix spec):
    - Remove only the three reserved scopes (case-insensitive).
    - Preserve all other scopes (especially Graph read scopes).
    - De-duplicate while preserving original order of first occurrence.
    - Return list (MSAL accepts list or tuple).
    """
    seen: dict[str, str] = {}  # normalized -> original casing (first seen)
    removed: List[str] = []

    for raw in scopes:
        if not raw or not isinstance(raw, str):
            continue
        norm = _normalize(raw)
        if norm in RESERVED_SCOPES:
            removed.append(raw)
            continue
        if norm not in seen:
            seen[norm] = raw  # keep first casing seen

    effective = list(seen.values())
    return effective


def get_scope_diagnostics(configured: Iterable[str]) -> dict:
    """Return structured view for diagnostics (auth status, graph, proof)."""
    configured_list = [s for s in configured if isinstance(s, str) and s.strip()]
    effective = sanitize_delegated_scopes(configured_list)
    removed = [s for s in configured_list if _normalize(s) in RESERVED_SCOPES]

    return {
        "configured_scopes": configured_list,
        "effective_msal_scopes": effective,
        "removed_reserved_scopes": removed,
    }
