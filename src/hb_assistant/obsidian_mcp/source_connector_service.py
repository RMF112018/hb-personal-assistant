"""Read-only NAS source-root connector service (N8C-12).

The single shared read layer behind the local backend API (``GET /api/assistant/source-*``), the local
``hb-assistant source-connector`` CLI, and the remote NAS MCP ``assistant_source_*`` tools. It makes indexed
NAS source-root FILES first-class: searchable, listable, root-aware, cursor-paged, with bounded metadata and
bounded reads — reusing the existing V93/V94 source index (no new tables, no schema bump).

Invariants:
* read-only — every function takes ``*, conn=None`` threaded straight into ``SourceIndexRepository``;
* NEVER a live recursive scan in the request path (search/list read indexed rows; a single bounded read
  opens exactly one configured file via ``SourceContentProvider``);
* every file row carries ``source_root_key`` + root-relative ``rel_path`` + an opaque ``source_ref``;
* NO absolute host path, NO raw SQL, NO card generation, NO scan/reindex, NO mutation.
"""

from __future__ import annotations

from typing import Any

from .config import ObsidianMcpConfig
from .source_connector_models import (
    ORDER_RANK_PATH,
    ORDER_ROOT_PATH,
    SourceConnectorValidationError,
    clamp_limit,
    compute_query_digest,
    decode_cursor,
    encode_source_ref,
    mime_for_ext,
    page_envelope,
    resolve_source_id,
    shape_source_file,
)
from .source_content_provider import SourceContentProvider
from .source_index_repository import SourceIndexRepository

_MAX_NEIGHBORS = 20
_MAX_CHILD_FOLDERS = 50


def source_status(repo: SourceIndexRepository, config: ObsidianMcpConfig, *,
                  conn: Any = None) -> dict[str, Any]:
    """Index status for the source-file connector. Drops the raw ``configured_roots`` state blob (it can
    carry absolute host paths) in favour of a path-free root summary."""
    status = dict(repo.index_status(conn=conn))
    status.pop("configured_roots", None)
    roots = list_source_roots(repo, config, conn=conn)
    return {
        **status,
        "index_enabled": bool(getattr(config, "external_source_index_enabled", False)),
        "configured_root_count": roots["count"],
        "roots": roots["roots"],
        "search_backend": "source_index",
    }


def list_source_roots(repo: SourceIndexRepository, config: ObsidianMcpConfig, *,
                      conn: Any = None) -> dict[str, Any]:
    """Configured source roots (key/enabled/sensitive) + indexed file counts. No absolute paths."""
    roots = []
    for root in config.external_sources:
        roots.append({
            "source_root_key": root.source_root_key,
            "enabled": bool(root.enabled),
            "sensitive": bool(root.sensitive),
            "source_kind": root.source_kind,
            "file_count": repo.count_source_files(root.source_root_key, conn=conn),
        })
    roots.sort(key=lambda r: r["source_root_key"])
    return {"roots": roots, "count": len(roots)}


def search_source_files(repo: SourceIndexRepository, config: ObsidianMcpConfig, *, query: str,
                        source_root_key: str | None = None, file_ext: str | None = None,
                        limit: int = 25, cursor: str | None = None,
                        conn: Any = None) -> dict[str, Any]:
    """Root-aware FTS search over indexed source files, deterministic keyset cursor. Read-only."""
    del config
    limit = clamp_limit(limit)
    order = ORDER_RANK_PATH
    filters = {"op": "search", "query": query, "source_root_key": source_root_key,
               "file_ext": file_ext}
    query_digest = compute_query_digest(filters)
    after: tuple[float, str, str, str] | None = None
    if cursor:
        raw = decode_cursor(cursor, query_digest=query_digest, order=order)
        if len(raw) != 4:
            raise SourceConnectorValidationError("invalid_cursor")
        after = (float(raw[0]), str(raw[1]), str(raw[2]), str(raw[3]))
    rows = repo.search_source_files(query, source_root_key=source_root_key, file_ext=file_ext,
                                    limit=limit + 1, after=after, conn=conn)
    has_more = len(rows) > limit
    page = rows[:limit]
    next_after = None
    if has_more and page:
        last = page[-1]
        next_after = [last["score"], last["source_root_key"], last["rel_path"], last["source_id"]]
    items = [shape_source_file(r, snippet=r.get("snippet"), include_snippet=True) for r in page]
    env = page_envelope(items, limit=limit, order=order, query_digest=query_digest,
                        next_after=next_after, cursor=cursor)
    return {**env, "query": query, "search_backend": "source_index"}


def list_source_files(repo: SourceIndexRepository, config: ObsidianMcpConfig, *, source_root_key: str,
                      prefix: str | None = None, limit: int = 25, cursor: str | None = None,
                      conn: Any = None) -> dict[str, Any]:
    """Index-backed listing under one root/prefix, keyset-paged. Advisory child folders derived from the
    returned page (``child_folders_partial`` when more pages remain). Read-only, never a filesystem scan."""
    del config
    if not source_root_key:
        raise SourceConnectorValidationError("source_root_key_required")
    limit = clamp_limit(limit)
    order = ORDER_ROOT_PATH
    filters = {"op": "list", "source_root_key": source_root_key, "prefix": prefix or ""}
    query_digest = compute_query_digest(filters)
    after: tuple[str, str] | None = None
    if cursor:
        raw = decode_cursor(cursor, query_digest=query_digest, order=order)
        if len(raw) != 2:
            raise SourceConnectorValidationError("invalid_cursor")
        after = (str(raw[0]), str(raw[1]))
    rows = repo.list_source_files(source_root_key, prefix=prefix, limit=limit + 1, after=after,
                                  conn=conn)
    has_more = len(rows) > limit
    page = rows[:limit]
    next_after = None
    if has_more and page:
        next_after = [page[-1]["rel_path"], page[-1]["source_id"]]
    items = [{**shape_source_file(r), "entry_type": "file"} for r in page]
    env = page_envelope(items, limit=limit, order=order, query_digest=query_digest,
                        next_after=next_after, cursor=cursor)
    return {**env, "source_root_key": source_root_key, "prefix": prefix,
            "child_folders": _child_folders(page, prefix), "child_folders_partial": has_more}


def _child_folders(rows: list[dict[str, Any]], prefix: str | None) -> list[str]:
    """Immediate child folder segments under ``prefix`` derived from the current page (advisory)."""
    base = (prefix or "").rstrip("/")
    base = f"{base}/" if base else ""
    seen: list[str] = []
    for r in rows:
        rel = str(r.get("rel_path") or "")
        if base and not rel.startswith(base):
            continue
        remainder = rel[len(base):]
        if "/" in remainder:
            seg = remainder.split("/", 1)[0]
            if seg and seg not in seen:
                seen.append(seg)
        if len(seen) >= _MAX_CHILD_FOLDERS:
            break
    return sorted(seen)


def source_file_metadata(repo: SourceIndexRepository, config: ObsidianMcpConfig, *,
                         source_id: str | None = None, source_ref: str | None = None,
                         conn: Any = None) -> dict[str, Any]:
    """Metadata for one source file by stable id/ref. Distinguishes the ORIGINAL source file (primary)
    from a generated source card (supplemental) and vault notes (separate). Never forces card lookup."""
    del config
    sid = resolve_source_id(source_id=source_id, source_ref=source_ref)
    detail = repo.get_source_detail(sid, conn=conn)
    if detail is None:
        raise SourceConnectorValidationError("source_not_found")
    cards = repo.list_cards_for_source(sid, conn=conn)
    active_cards = [c for c in cards if c.get("generation_status") in ("generated", "stale")]
    ext = (str(detail.get("file_ext")).lower().lstrip(".") if detail.get("file_ext") else None)
    neighbors = _neighbors(repo, detail, sid, conn=conn)
    return {
        "object_type": "source_file",
        "is_source_file": True,
        "source_id": sid,
        "source_ref": encode_source_ref(sid),
        "source_root_key": detail.get("source_root_key"),
        "rel_path": detail.get("rel_path"),
        "source_kind": detail.get("source_kind"),
        "extension": ext,
        "mime_type": mime_for_ext(ext),
        "size_bytes": detail.get("size_bytes"),
        "mtime_ns": detail.get("mtime_ns"),
        "content_digest": detail.get("content_sha256"),
        "page_count": detail.get("page_count"),
        "paragraph_count": detail.get("paragraph_count"),
        "sheet_count": detail.get("sheet_count"),
        "extraction_status": detail.get("extraction_status"),
        "indexed_text_available": detail.get("text_excerpt") is not None,
        "source_state": "deleted" if detail.get("deleted") else "active",
        "generated_card_available": bool(active_cards),
        "generated_card_rel_path": (active_cards[0]["note_rel_path"] if active_cards else None),
        "generated_card_status": (active_cards[0]["generation_status"] if active_cards else None),
        "generated_card_note": "supplemental artifact; the original source file is the primary object",
        "neighbors": neighbors,
    }


def _neighbors(repo: SourceIndexRepository, detail: dict[str, Any], sid: str, *,
               conn: Any = None) -> list[dict[str, Any]]:
    """Bounded sibling source files in the same folder (advisory context). No absolute paths."""
    root_key = detail.get("source_root_key")
    rel = str(detail.get("rel_path") or "")
    parent = rel.rsplit("/", 1)[0] + "/" if (root_key and "/" in rel) else ""
    rows = repo.list_source_files(str(root_key), prefix=parent or None, limit=_MAX_NEIGHBORS + 1,
                                  conn=conn) if root_key else []
    out: list[dict[str, Any]] = []
    for r in rows:
        if r["source_id"] == sid:
            continue
        out.append({"source_ref": encode_source_ref(r["source_id"]), "rel_path": r["rel_path"],
                    "source_root_key": r["source_root_key"]})
        if len(out) >= _MAX_NEIGHBORS:
            break
    return out


def read_source_file(repo: SourceIndexRepository, config: ObsidianMcpConfig, *,
                     source_id: str | None = None, source_ref: str | None = None,
                     max_chars: int | None = None, prefer_live: bool = True,
                     conn: Any = None) -> dict[str, Any]:
    """Bounded, extension-gated, single-file read via ``SourceContentProvider``. Falls back to the
    indexed excerpt (labelled ``indexed_excerpt_fallback``) when a live read is not permitted."""
    sid = resolve_source_id(source_id=source_id, source_ref=source_ref)
    provider = SourceContentProvider(repo, config)
    return provider.read(sid, max_chars=max_chars, prefer_live=prefer_live, conn=conn)
