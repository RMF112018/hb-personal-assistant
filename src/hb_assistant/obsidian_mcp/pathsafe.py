"""Shared vault path-safety policy for the UI-managed Obsidian MCP server.

Single source of truth for the hidden/system/protected-path rules applied by
every read, list, search, crawl, and write tool. Consolidates what used to be
three divergent checks (the curation crawler, the write policy, and — formerly
absent — the base read tools).

Rules:
* ``PROTECTED_SEGMENTS`` are *always* blocked, for everyone, even when hidden
  inspection is otherwise honored. Every member is dot-prefixed, so the generic
  hidden-segment rule covers them too; they are listed explicitly so the block
  is unconditional.
* Any other dot-prefixed path segment is blocked unless ``include_hidden`` is
  granted. OAuth clients are never granted ``include_hidden``; only a local
  operator (static bearer / no-auth / stdio) with the explicit
  ``curation_operator_hidden_inspection`` config opt-in may broaden inspection.
"""

from __future__ import annotations

from pathlib import Path

# Always-blocked top-level vault segments (each is also dot-prefixed).
PROTECTED_SEGMENTS = {".git", ".obsidian", ".trash", ".venv", ".smart-env", ".hb-assistant"}

# Principal kinds, used for receipts and to decide hidden-inspection eligibility.
PRINCIPAL_OAUTH = "oauth"
PRINCIPAL_STATIC_BEARER = "static_bearer"
PRINCIPAL_LOCAL = "local"


def path_blocked(rel: str, *, include_hidden: bool) -> bool:
    """Return True if a vault-relative path must be hidden from the caller."""
    for part in (p for p in rel.split("/") if p):
        if part in PROTECTED_SEGMENTS:
            return True
        if part.startswith(".") and not include_hidden:
            return True
    return False


def has_protected_segment(rel: str) -> bool:
    """Return True if any path segment is in the always-blocked protected set."""
    return any(part in PROTECTED_SEGMENTS for part in rel.split("/") if part)


def symlink_escapes(item: Path, root: Path) -> bool:
    """Return True if ``item`` is a symlink resolving outside ``root``."""
    if not item.is_symlink():
        return False
    try:
        item.resolve().relative_to(root)
    except ValueError:
        return True
    return False
