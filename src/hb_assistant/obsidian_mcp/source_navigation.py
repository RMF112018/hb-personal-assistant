"""Read-only source/card/note navigation service (N8C-3).

The single shared read layer behind BOTH the local backend API (``GET /api/assistant/*``) and the
remote NAS MCP ``assistant_*`` tools. It answers the "chat with my data" navigation questions —
what sources exist, which card represents a source, which source a card represents (ambiguity-aware),
what is stale / missing / duplicated / ambiguous, what changed recently, what is related, and give me
a bounded/complete note — by wrapping the N8C-2 identity layer (:mod:`.source_card_identity`) and the
existing :class:`.source_index_repository.SourceIndexRepository` read primitives.

Design invariants (every function):
  * **Read-only.** Only SELECTs. Every function accepts ``*, conn=None`` and threads it straight into
    the repo/identity calls, so a caller may pin a single read-only connection (the MCP surface opens
    ``mode=ro&immutable=1`` + ``PRAGMA query_only=ON`` and passes it here; there is no live-DB
    fallback). No DB mutation, no card write, no schema dependency beyond the V93/V99 tables.
  * **Relative paths only.** Path fields (``path`` / ``note_rel_path`` / ``source_rel_path``) are
    always vault-/root-relative plus ``source_root_key``; an absolute NAS mount path is never
    returned in a structural field.
  * **Stable shapes.** List responses always carry ``count`` + ``limit`` + ``truncated``; card→source
    always carries ``resolution`` ∈ {none, unique, ambiguous}; card state uses the ``STATE_*`` strings
    from :mod:`.source_card_identity`. These shapes are the frontend/MCP contract.

Content policy (N8C-3, Bobby-authorized): navigation returns **complete, unredacted** content — no PII
masking, and :func:`get_vault_note` returns the **whole** note (bounded only by a high absolute
ceiling for tunnel stability, never truncated for a normal document). Search ``snippet`` fields are
FTS previews (discovery), not redactions; use :func:`get_vault_note` / :func:`get_source` for full
content. The remote exposure of this content is a deliberate, operator-authorized posture; the
read-only / no-write / no-raw-SQL-or-shell / relative-path safeguards below are retained because they
do not withhold any of the user's content.
"""

from __future__ import annotations

from typing import Any

from . import source_card_identity as identity
from .config import ObsidianMcpConfig
from .source_index_repository import SourceIndexRepository
from .tools import ObsidianMcpToolError, read_file

# --- bounds (structural safety / tunnel stability, not content redaction) ---------------
DEFAULT_LIMIT = 25
MAX_LIMIT = 100
# Whole-document ceiling for a single content read: high enough to return any normal note/PDF/doc
# complete, low enough that one call cannot try to stream a pathological multi-GB file over the tunnel.
ASSISTANT_MAX_CONTENT_CHARS = 2_000_000
ASSISTANT_MAX_FILE_BYTES = 64_000_000
# Least-exposure default for the echoed source text_excerpt in get_source (the index stores up to 8000;
# callers opt into more via max_excerpt_chars). Metadata-first, then an explicit bounded read.
SOURCE_EXCERPT_DEFAULT_CHARS = 4_000

# Active card statuses (a source SHOULD have exactly one active card).
_ACTIVE = ("generated", "stale")


def _clamp(value: Any, *, default: int = DEFAULT_LIMIT, hi: int = MAX_LIMIT) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(n, hi))


def _list_envelope(items: list[dict[str, Any]], *, limit: int, key: str) -> dict[str, Any]:
    """Uniform bounded-list shape: ``{<key>: [...], count, limit, truncated}``.

    ``truncated`` is True when more rows existed than the (already clamped) ``limit`` returned.
    """
    truncated = len(items) > limit
    kept = items[:limit]
    return {key: kept, "count": len(kept), "limit": limit, "truncated": truncated}


# --- search -----------------------------------------------------------------------------
def search_sources(repo: SourceIndexRepository, query: str, *, limit: int = DEFAULT_LIMIT,
                   project_key: str | None = None, conn=None) -> dict[str, Any]:
    """FTS search over indexed external-file sources. Bounded; snippets are FTS previews."""
    lim = _clamp(limit)
    rows = repo.search_sources(str(query), limit=lim + 1, project_key=project_key or None, conn=conn)
    return _list_envelope(rows, limit=lim, key="sources")


def search_cards(repo: SourceIndexRepository, query: str, *, limit: int = DEFAULT_LIMIT,
                 path_prefix: str | None = None, conn=None) -> dict[str, Any]:
    """FTS search over indexed obsidian notes (source cards + user notes). Bounded."""
    lim = _clamp(limit)
    rows = repo.search_notes(str(query), limit=lim + 1, path_prefix=path_prefix or None, conn=conn)
    return _list_envelope(rows, limit=lim, key="cards")


# --- source detail + linkage ------------------------------------------------------------
def get_source(repo: SourceIndexRepository, source_id: str, *,
               max_excerpt_chars: int = SOURCE_EXCERPT_DEFAULT_CHARS, conn=None) -> dict[str, Any] | None:
    """DB detail for a source + its primary card linkage. Relative paths only; ``None`` if absent.

    Pure-DB (no vault file read) so it works against the read-only snapshot without vault access. The
    stored ``text_excerpt`` is echoed **bounded** to ``max_excerpt_chars`` (least-exposure default 4000;
    the index physically stores up to ``source_index_max_excerpt_chars``, default 8000). A truncated
    excerpt is flagged with ``text_excerpt_truncated`` + ``text_excerpt_full_chars`` so a caller can ask
    for more; whole-file content is via :func:`get_vault_note` / the source-connector bounded read.
    """
    detail = repo.get_source_detail(str(source_id), conn=conn)
    if detail is None:
        return None
    excerpt = detail.get("text_excerpt")
    if isinstance(excerpt, str):
        cap = max(200, min(int(max_excerpt_chars or SOURCE_EXCERPT_DEFAULT_CHARS), ASSISTANT_MAX_CONTENT_CHARS))
        if len(excerpt) > cap:
            detail = {**detail, "text_excerpt": excerpt[:cap], "text_excerpt_truncated": True,
                      "text_excerpt_full_chars": len(excerpt)}
    card = identity.get_card_for_source(repo, str(source_id), conn=conn)
    dup = identity.detect_duplicate_cards(repo, str(source_id), conn=conn)
    return {
        "source": detail,  # rel_path + source_root_key (relative), never absolute
        "card": card,      # primary active card {note_rel_path, card_id, generation_status, ...} or None
        "is_duplicate": dup.is_duplicate,
        "active_card_paths": dup.active_card_paths,
    }


def get_card_for_source(repo: SourceIndexRepository, source_id: str, *, conn=None) -> dict[str, Any]:
    """The primary active card for a source (prefers generated over stale), ambiguity noted."""
    card = identity.get_card_for_source(repo, str(source_id), conn=conn)
    dup = identity.detect_duplicate_cards(repo, str(source_id), conn=conn)
    return {"source_id": str(source_id), "card": card, "is_duplicate": dup.is_duplicate,
            "active_card_paths": dup.active_card_paths}


def get_source_for_card(repo: SourceIndexRepository, note_rel_path: str, *, conn=None) -> dict[str, Any]:
    """Reverse lookup card path -> source(s). Ambiguity-aware: never picks arbitrarily."""
    rl = identity.get_source_for_card(repo, str(note_rel_path), conn=conn)
    return {"note_rel_path": rl.note_rel_path, "resolution": rl.resolution,
            "source_id": rl.source_id, "sources": rl.sources, "count": len(rl.sources)}


def get_card_state(repo: SourceIndexRepository, config: ObsidianMcpConfig, source_id: str, *,
                   conn=None) -> dict[str, Any]:
    """Roll-up card state for a source (current/stale/missing/duplicate/source_deleted/no_card).

    Vault-aware (reads the card file to confirm presence/digest), so it needs ``config.vault_root``.
    Read-only — reports source-deleted-but-card-active, never retires/deletes/rewrites.
    """
    st = identity.classify_card_state(repo, config.vault_root, str(source_id), conn=conn)
    return {"source_id": st.source_id, "state": st.state, "card_paths": st.card_paths,
            "reason": st.reason, "legacy_flags": list(st.legacy_flags)}


# --- health listings (stale / duplicate / ambiguous) ------------------------------------
def list_stale_cards(repo: SourceIndexRepository, *, limit: int = DEFAULT_LIMIT,
                     conn=None) -> dict[str, Any]:
    """Cards the index has marked stale (source changed/removed). Bounded."""
    lim = _clamp(limit)
    rows = repo.list_stale_generated_notes(limit=lim + 1, conn=conn)
    return _list_envelope(rows, limit=lim, key="stale_cards")


def list_duplicate_cards(repo: SourceIndexRepository, *, limit: int = DEFAULT_LIMIT,
                         conn=None) -> dict[str, Any]:
    """Sources with more than one active card path (a duplicate the DB UNIQUE does not prevent).

    Bounded scan of active generated-note rows grouped by source_id; ``truncated`` set if the scan
    hit the cap before exhausting candidates.
    """
    lim = _clamp(limit)
    rows = repo.list_generated_notes(statuses=_ACTIVE, conn=conn)
    by_source: dict[str, list[str]] = {}
    for r in rows:
        by_source.setdefault(r["source_id"], []).append(r["note_rel_path"])
    dups = [{"source_id": sid, "active_card_paths": paths, "card_count": len(paths)}
            for sid, paths in by_source.items() if len(paths) > 1]
    dups.sort(key=lambda d: d["source_id"])
    return _list_envelope(dups, limit=lim, key="duplicate_cards")


def list_ambiguous_card_links(repo: SourceIndexRepository, *, limit: int = DEFAULT_LIMIT,
                              conn=None) -> dict[str, Any]:
    """Card paths claimed by more than one source (reverse-lookup ambiguity). Bounded."""
    lim = _clamp(limit)
    rows = repo.list_generated_notes(statuses=_ACTIVE, conn=conn)
    by_path: dict[str, list[str]] = {}
    for r in rows:
        srcs = by_path.setdefault(r["note_rel_path"], [])
        if r["source_id"] not in srcs:
            srcs.append(r["source_id"])
    amb = [{"note_rel_path": path, "source_ids": sids, "source_count": len(sids)}
           for path, sids in by_path.items() if len(sids) > 1]
    amb.sort(key=lambda d: d["note_rel_path"])
    return _list_envelope(amb, limit=lim, key="ambiguous_card_links")


# --- recent changes + related -----------------------------------------------------------
def recent_changes(repo: SourceIndexRepository, *, limit: int = DEFAULT_LIMIT,
                   event_types: tuple[str, ...] | None = None, conn=None) -> dict[str, Any]:
    """Most-recent indexer events (created/modified/deleted/reindex/rebuild), newest first. Bounded."""
    lim = _clamp(limit)
    rows = repo.list_recent_events(limit=lim + 1, event_types=event_types, conn=conn)
    return _list_envelope(rows, limit=lim, key="changes")


def get_related_sources(repo: SourceIndexRepository, source_id: str, *, conn=None) -> dict[str, Any]:
    """Outgoing relationships for a source (belongs_to_project / mentions / derived_from / links_to)."""
    rows = repo.list_relationships(str(source_id), conn=conn)
    return {"source_id": str(source_id), "related": rows, "count": len(rows)}


# --- bounded / complete vault-note retrieval --------------------------------------------
def get_vault_note(config: ObsidianMcpConfig, note_rel_path: str, *,
                   max_chars: int | None = None) -> dict[str, Any]:
    """Complete, unredacted content of a vault note (md/txt/pdf/docx).

    Path-safe (:func:`.tools.resolve_safe_path` rejects absolute paths, ``..`` traversal, NUL, and
    symlink escape via ``.resolve()`` containment; :func:`.pathsafe.path_blocked` rejects protected /
    hidden folders — ``.git``/``.obsidian``/``.trash``/``.venv``/``.smart-env``/``.hb-assistant`` and
    any dotfile). Returns the whole document (no truncation for a normal file) up to a high absolute
    ceiling for tunnel stability; content is NOT redacted (Bobby-authorized). Raises
    :class:`.tools.ObsidianMcpToolError` on any unsafe / unsupported / missing path.
    """
    if "\x00" in (note_rel_path or ""):
        raise ObsidianMcpToolError("nul_byte_in_path")
    cap = ASSISTANT_MAX_CONTENT_CHARS if max_chars is None else _bounded_cap(max_chars)
    # Raise the read caps so a normal note/PDF/doc comes back COMPLETE; retain an absolute ceiling.
    content_config = config.model_copy(update={
        "max_result_chars": cap,
        "max_file_bytes": max(int(getattr(config, "max_file_bytes", 0) or 0), ASSISTANT_MAX_FILE_BYTES),
    })
    result = read_file(content_config, path=str(note_rel_path), max_chars=cap, operator_mode=False)
    # read_file already returns a vault-relative ``path``; carry the note classification for callers.
    result["note_type"] = identity.classify_note(
        result.get("content", "") if result.get("file_type") in {"md", "txt"} else "",
        result.get("path", ""), config,
    )
    return result


def _bounded_cap(max_chars: Any) -> int:
    try:
        n = int(max_chars)
    except (TypeError, ValueError):
        return ASSISTANT_MAX_CONTENT_CHARS
    return max(1, min(n, ASSISTANT_MAX_CONTENT_CHARS))
