"""Join URL fencing (local_db_only policy)."""

from __future__ import annotations

JOIN_URL_POLICY_LOCAL = "local_db_only"


def fence_join_url(url: str | None, *, emit_external: bool = False) -> str | None:
    if not url:
        return None
    if emit_external:
        return "[REDACTED_JOIN_URL]"
    return url  # retained locally only
