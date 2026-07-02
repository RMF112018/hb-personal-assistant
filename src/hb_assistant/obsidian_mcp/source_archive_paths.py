"""Centralized Email Archive path routing (Phase 10L-B) — the single source of truth for where email
archive notes and attachment binaries live under the self-index-guarded ``Email Archive`` root.

Corrects the pre-10L double-domain defect: the earlier archive-note builder hardcoded a ``/Work/``
segment and *then* appended the real domain folder, producing ``Email Archive/Work/Work|Home|Shared/…``.
Archive notes now route DIRECTLY under their domain folder — ``Email Archive/{Work,Home,Shared}/…``.

Domain routing reuses the deterministic :func:`source_notes._domain_for` (source-root-key based), so the
archive-note domain, the attachment domain, and the generated source-card domain always agree.

Attachments were never affected by the double-domain defect: they always lived at
``Email Archive/Work/Attachments/`` which, under the per-domain scheme, is exactly the *work* attachments
root. This module generalizes that to ``Email Archive/{Work,Home,Shared}/Attachments/`` while keeping the
work path byte-identical to the pre-10L layout.

Self-index protection for every path this module produces comes from
:func:`source_indexer.is_email_archive_path` (keyed on the ``Email Archive/`` top-level prefix).
"""

from __future__ import annotations

from typing import Any

from .source_indexer import EMAIL_ARCHIVE_FOLDER
from .source_notes import _DOMAIN_FOLDER, _domain_for, _safe_basename

# The three domain subfolders directly under the ``Email Archive`` root.
ARCHIVE_DOMAIN_FOLDERS = ("Work", "Home", "Shared")
_ATTACHMENTS_LEAF = "Attachments"

# Pre-10L double-domain NOTE prefixes (the hardcoded ``/Work/`` + real domain folder). Detected and
# reported for cleanup, never re-emitted. NOTE: ``Email Archive/Work/Attachments/`` is intentionally NOT
# legacy — it is the correct *work* attachments root under the per-domain scheme.
LEGACY_ARCHIVE_PREFIXES = tuple(
    f"{EMAIL_ARCHIVE_FOLDER}/Work/{domain}/" for domain in ARCHIVE_DOMAIN_FOLDERS
)


def domain_folder_for(detail: dict[str, Any]) -> str:
    """The ``Work``/``Home``/``Shared`` archive subfolder for a source detail (single source of truth)."""
    return _DOMAIN_FOLDER.get(_domain_for(detail), "Shared")


def archive_note_rel_path(detail: dict[str, Any]) -> str:
    """Full-email archive note path: ``Email Archive/<Domain>/<safe>__<id12>.md`` (Phase 10L-B).

    Routes DIRECTLY under the domain folder — no intermediate ``Work/`` segment. Lives in the top-level
    ``Email Archive`` root (never a Source-Notes card / DB-tracked generated note); self-index protection
    comes from ``is_email_archive_path``.
    """
    sid = str(detail["source_id"])[:12]
    return f"{EMAIL_ARCHIVE_FOLDER}/{domain_folder_for(detail)}/{_safe_basename(detail)}__{sid}.md"


def attachments_subdir(domain_folder: str) -> str:
    """Attachments subtree for a domain: ``Email Archive/<Domain>/Attachments`` (Shared fallback)."""
    domain = domain_folder if domain_folder in ARCHIVE_DOMAIN_FOLDERS else "Shared"
    return f"{EMAIL_ARCHIVE_FOLDER}/{domain}/{_ATTACHMENTS_LEAF}"


def is_attachments_path(rel_path: str) -> bool:
    """True if ``rel_path`` is under any domain's ``Email Archive/<Domain>/Attachments/`` subtree."""
    norm = str(rel_path).replace("\\", "/").strip("/").lower()
    return any(
        norm.startswith(attachments_subdir(domain).lower() + "/")
        for domain in ARCHIVE_DOMAIN_FOLDERS
    )


def attachments_root_for_rel(rel_path: str) -> str | None:
    """Return the ``Email Archive/<Domain>/Attachments`` root that owns ``rel_path`` (or None)."""
    norm = str(rel_path).replace("\\", "/").strip("/")
    for domain in ARCHIVE_DOMAIN_FOLDERS:
        root = attachments_subdir(domain)
        if norm.lower().startswith(root.lower() + "/"):
            return root
    return None


def is_legacy_archive_path(rel_path: str) -> bool:
    """True if ``rel_path`` uses a pre-10L ``Email Archive/Work/<Domain>/`` (double-domain) note prefix."""
    norm = str(rel_path).replace("\\", "/").strip("/")
    return any(norm.lower().startswith(prefix.lower()) for prefix in LEGACY_ARCHIVE_PREFIXES)
