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

import time
from typing import Any

from .config import ObsidianMcpConfig
from .source_connector_models import (
    ORDER_RANK_PATH,
    ORDER_ROOT_PATH,
    READ_MODE_EXCERPT,
    SourceConnectorValidationError,
    clamp_limit,
    compute_query_digest,
    decode_cursor,
    encode_source_ref,
    mime_for_ext,
    page_envelope,
    shape_source_file,
)
from .source_content_provider import SourceContentProvider
from .source_index_repository import SourceIndexRepository
from .source_project_number import (
    match_explanation_for_row,
    query_project_candidates,
    rank_boost,
)

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
    """Configured source roots (key/enabled/sensitive) + indexed file counts. No absolute paths.

    When the runtime config has no ``external_sources`` (e.g. the internet-facing serve profile, which
    persists no root config), fall back to the roots the INDEX actually records so the list reflects
    reality instead of returning zero while indexed rows reference real roots. Each entry carries a
    ``provenance`` marker (``config`` vs ``index``); index-derived entries default ``sensitive`` unknown."""
    roots = []
    for root in config.external_sources:
        roots.append({
            "source_root_key": root.source_root_key,
            "enabled": bool(root.enabled),
            "sensitive": bool(root.sensitive),
            "sensitivity_known": True,
            "authorization_state": "authorized" if root.enabled else "denied",
            "source_kind": root.source_kind,
            "file_count": repo.count_source_files(root.source_root_key, conn=conn),
            "provenance": "config",
        })
    if not roots:
        for key in repo.distinct_indexed_root_keys(conn=conn):
            # A2: a configless (index-only) root is NOT trusted-by-default. Its authorization is UNVERIFIED
            # and its sensitivity is UNKNOWN — never `enabled=True, sensitive=False` (which would fail open).
            # Reads/answers are blocked by default (the trust authority returns `unverified` for it).
            roots.append({
                "source_root_key": key,
                "enabled": True,
                "sensitive": None,
                "sensitivity_known": False,
                "authorization_state": "unverified",
                "authoritative": False,
                "source_kind": "external_file",
                "file_count": repo.count_source_files(key, conn=conn),
                "provenance": "index",
            })
    roots.sort(key=lambda r: r["source_root_key"])
    return {"roots": roots, "count": len(roots)}


def _known_root_keys(repo: SourceIndexRepository, config: ObsidianMcpConfig, *, conn: Any = None) -> set[str]:
    """The valid source-root key set — configured roots, or the index's roots when config has none
    (mirrors list_source_roots' fallback on the internet-facing serve profile)."""
    keys = {root.source_root_key for root in config.external_sources}
    if not keys:
        keys = set(repo.distinct_indexed_root_keys(conn=conn))
    return keys


def _reject_unsafe_prefix(prefix: str | None) -> None:
    """Fail closed on a traversal/absolute rel_path prefix instead of silently matching nothing."""
    if prefix and (".." in prefix or str(prefix).startswith("/")):
        raise SourceConnectorValidationError("unsafe_prefix")


def _blocked_page_envelope(
    status: str,
    *,
    root_key: str | None,
    decision: Any,
    limit: int,
    order: str,
    extra: dict[str, Any] | None = None,
    excluded: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """A2 fail-closed serving envelope: NO items, NO metadata, ``authoritative:false``, embedded sanitized
    ``root_readiness``. Shared by search + list so an unsafe/unknown root can never return stale rows."""
    from .source_root_trust import RC_UNKNOWN_ROOT, RESULT_UNKNOWN_ROOT, root_readiness_envelope

    if decision is not None:
        readiness = root_readiness_envelope(decision)
    else:
        readiness = {
            "root_key": root_key,
            "trust_state": "unknown",
            "authorization_state": "unverified",
            "reason_codes": [RC_UNKNOWN_ROOT] if status == RESULT_UNKNOWN_ROOT else [],
        }
    env: dict[str, Any] = {
        "status": status,
        "items": [],
        "count": 0,
        "limit": limit,
        "limit_applied": True,
        "order": order,
        "has_more": False,
        "next_cursor": None,
        "cursor": None,
        "truncated": False,
        "authoritative": False,
        "root_readiness": readiness,
        "excluded_root_readiness": excluded or [],
        "excluded_root_keys": [r.get("root_key") for r in (excluded or [])],
    }
    if extra:
        env.update(extra)
    return env


def _safe_roots_for_scope(
    repo: SourceIndexRepository, config: ObsidianMcpConfig, *, conn: Any = None
) -> tuple[set[str], list[dict[str, Any]]]:
    """Partition the known roots into (safe-for-path-lookup keys, sanitized readiness of the excluded).
    Used by UNSCOPED search so one safe root never implies universal safety."""
    from .source_root_trust import load_root_trust, root_readiness_envelope

    allowed: set[str] = set()
    excluded: list[dict[str, Any]] = []
    for key in sorted(_known_root_keys(repo, config, conn=conn)):
        decision = load_root_trust(repo, config, None, key, conn=conn)
        if decision.safe_for_client_answering:
            allowed.add(key)
        else:
            excluded.append(root_readiness_envelope(decision))
    return allowed, excluded


def search_source_files(repo: SourceIndexRepository, config: ObsidianMcpConfig, *, query: str,
                        source_root_key: str | None = None, file_ext: str | None = None,
                        limit: int = 25, cursor: str | None = None,
                        conn: Any = None) -> dict[str, Any]:
    """Root-aware FTS search over indexed source files, deterministic keyset cursor. Read-only.

    A2 fail-closed: an explicitly requested UNSAFE root returns a ``blocked_root_unready`` envelope with
    zero items; an UNKNOWN root returns ``unknown_root``; an UNSCOPED search is restricted to safe roots
    only and discloses ``excluded_root_keys`` (one safe root never implies universal safety)."""
    from .source_root_trust import (
        RESULT_BLOCKED_ROOT_UNREADY,
        RESULT_OK,
        RESULT_UNKNOWN_ROOT,
        load_root_trust,
        root_readiness_envelope,
    )

    limit = clamp_limit(limit)
    order = ORDER_RANK_PATH
    excluded_readiness: list[dict[str, Any]] = []
    if source_root_key is not None:
        if source_root_key not in _known_root_keys(repo, config, conn=conn):
            return _blocked_page_envelope(
                RESULT_UNKNOWN_ROOT, root_key=source_root_key, decision=None, limit=limit, order=order
            )
        _decision = load_root_trust(repo, config, None, source_root_key, conn=conn)
        if not _decision.safe_for_client_answering:
            return _blocked_page_envelope(
                RESULT_BLOCKED_ROOT_UNREADY, root_key=source_root_key, decision=_decision,
                limit=limit, order=order,
            )
        allowed_roots: set[str] = {source_root_key}
    else:
        allowed_roots, excluded_readiness = _safe_roots_for_scope(repo, config, conn=conn)
        if not allowed_roots:
            return _blocked_page_envelope(
                RESULT_BLOCKED_ROOT_UNREADY, root_key=None, decision=None, limit=limit, order=order,
                excluded=excluded_readiness,
            )
    filters = {"op": "search", "query": query, "source_root_key": source_root_key,
               "file_ext": file_ext}
    query_digest = compute_query_digest(filters)
    after: tuple[float, str, str, str] | None = None
    if cursor:
        raw = decode_cursor(cursor, query_digest=query_digest, order=order)
        if len(raw) != 4:
            raise SourceConnectorValidationError("invalid_cursor")
        after = (float(raw[0]), str(raw[1]), str(raw[2]), str(raw[3]))
    t0 = time.perf_counter()
    rows = repo.search_source_files(query, source_root_key=source_root_key, file_ext=file_ext,
                                    limit=limit + 1, after=after, conn=conn)
    has_more = len(rows) > limit
    page = rows[:limit]
    projects = query_project_candidates(query)
    # Multi-stage within-page re-rank; preserve BM25 as base_score for rollback diagnostics.
    ranked = []
    for r in page:
        boost = rank_boost(r, query=query, project_numbers=projects)
        ranked.append((boost, -float(r.get("score") or 0.0), r))
    ranked.sort(key=lambda t: (-t[0], -t[1], t[2].get("source_root_key") or "",
                               t[2].get("rel_path") or "", t[2].get("source_id") or ""))
    next_after = None
    if has_more and page:
        # Cursor stays BM25-order based for stable keyset continuation across pages.
        last = page[-1]
        next_after = [last["score"], last["source_root_key"], last["rel_path"], last["source_id"]]
    items = []
    for idx, (boost, _neg_bm25, r) in enumerate(ranked):
        # A2: never surface a row from a root that is not safe-for-path-lookup (unscoped safe-root filter).
        if r.get("source_root_key") not in allowed_roots:
            continue
        shaped = shape_source_file(r, snippet=r.get("snippet"), include_snippet=True)
        shaped["base_score"] = float(r.get("score") or 0.0)
        shaped["bm25_rank"] = float(r.get("score") or 0.0)
        shaped["rank_boost"] = boost
        shaped["reranked_position"] = idx
        shaped["match_explanation"] = match_explanation_for_row(
            r, query=query, project_numbers=projects,
        )
        items.append(shaped)
    env = page_envelope(items, limit=limit, order=order, query_digest=query_digest,
                        next_after=next_after, cursor=cursor)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    return {
        **env, "query": query, "search_backend": "source_index",
        "status": RESULT_OK,
        "authoritative": True,
        "scope": "root" if source_root_key is not None else "unscoped_safe_roots",
        "safe_root_keys": sorted(allowed_roots),
        "excluded_root_keys": [r.get("root_key") for r in excluded_readiness],
        "excluded_root_readiness": excluded_readiness,
        "root_readiness": (
            root_readiness_envelope(_decision) if source_root_key is not None else None
        ),
        "ranking_strategy": "project_path_filename_content_fts",
        "detected_project_numbers": projects,
        "telemetry": {
            "elapsed_ms": elapsed_ms,
            "candidate_count": len(rows),
            "returned_count": len(items),
            "truncated": has_more,
            "cursor_present": bool(cursor) or has_more,
            "layers_used": ["source_intelligence_fts", "path_project_rerank"],
            "fallback_used": None,
            "rank_strategy": "project_path_filename_content_fts",
            "freshness_basis": "indexed_rows",
        },
    }


def list_source_files(repo: SourceIndexRepository, config: ObsidianMcpConfig, *, source_root_key: str,
                      prefix: str | None = None, limit: int = 25, cursor: str | None = None,
                      conn: Any = None) -> dict[str, Any]:
    """Index-backed listing under one root/prefix, keyset-paged. Advisory child folders derived from the
    returned page (``child_folders_partial`` when more pages remain). Read-only, never a filesystem scan."""
    from .source_root_trust import (
        RESULT_BLOCKED_ROOT_UNREADY,
        RESULT_OK,
        RESULT_UNKNOWN_ROOT,
        load_root_trust,
        root_readiness_envelope,
    )

    if not source_root_key:
        raise SourceConnectorValidationError("source_root_key_required")
    _reject_unsafe_prefix(prefix)
    limit = clamp_limit(limit)
    order = ORDER_ROOT_PATH
    if source_root_key not in _known_root_keys(repo, config, conn=conn):
        return _blocked_page_envelope(
            RESULT_UNKNOWN_ROOT, root_key=source_root_key, decision=None, limit=limit, order=order,
            extra={"source_root_key": source_root_key, "prefix": prefix, "child_folders": [],
                   "child_folders_partial": False},
        )
    _decision = load_root_trust(repo, config, None, source_root_key, conn=conn)
    if not _decision.safe_for_client_answering:
        return _blocked_page_envelope(
            RESULT_BLOCKED_ROOT_UNREADY, root_key=source_root_key, decision=_decision,
            limit=limit, order=order,
            extra={"source_root_key": source_root_key, "prefix": prefix, "child_folders": [],
                   "child_folders_partial": False},
        )
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
            "status": RESULT_OK, "authoritative": True,
            "root_readiness": root_readiness_envelope(_decision),
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
    from a generated source card (supplemental) and vault notes (separate). Never forces card lookup.

    A2 fail-closed: metadata for a file whose root is not safe-for-path-lookup is BLOCKED — no advisory
    item metadata is exposed, only the sanitized root_readiness envelope."""
    from .source_root_trust import (
        RESULT_BLOCKED_ROOT_UNREADY,
        RESULT_OK,
        load_root_trust,
        root_readiness_envelope,
    )

    # Fail-closed DB-aware resolution to a durable entity (PI-WI-03a): v2 entity ref → the entity;
    # v1/bare legacy handle → the DISTINCT legacy resolver; UNRESOLVED → source_not_found.
    sid = repo.resolve_entity(source_id=source_id, source_ref=source_ref, conn=conn)
    if sid is None:
        raise SourceConnectorValidationError("source_not_found")
    detail = repo.get_source_detail(sid, conn=conn)
    if detail is None:
        raise SourceConnectorValidationError("source_not_found")
    _root_key = detail.get("source_root_key")
    _decision = load_root_trust(repo, config, None, str(_root_key), conn=conn)
    if not _decision.safe_for_client_answering:
        return {
            "object_type": "source_file",
            "is_source_file": True,
            "status": RESULT_BLOCKED_ROOT_UNREADY,
            "authoritative": False,
            "source_id": sid,
            "source_ref": encode_source_ref(sid),
            "source_root_key": _root_key,
            "root_readiness": root_readiness_envelope(_decision),
        }
    cards = repo.list_cards_for_source(sid, conn=conn)
    active_cards = [c for c in cards if c.get("generation_status") in ("generated", "stale")]
    ext = (str(detail.get("file_ext")).lower().lstrip(".") if detail.get("file_ext") else None)
    neighbors = _neighbors(repo, detail, sid, conn=conn)
    extraction = str(detail.get("extraction_status") or "")
    unsupported = extraction == "unsupported" or (ext or "") in {"xer", "mpp", "pln"}
    from .source_project_number import extract_project_numbers_from_path  # noqa: PLC0415
    projects = extract_project_numbers_from_path(str(detail.get("rel_path") or ""))
    return {
        "object_type": "source_file",
        "is_source_file": True,
        "status": RESULT_OK,
        "authoritative": True,
        "root_readiness": root_readiness_envelope(_decision),
        "source_id": sid,
        "source_ref": encode_source_ref(sid),
        "source_root_key": detail.get("source_root_key"),
        "rel_path": detail.get("rel_path"),
        "path_display": f"{detail.get('source_root_key')}/{detail.get('rel_path')}" if detail.get("rel_path") else detail.get("source_root_key"),
        "source_kind": detail.get("source_kind"),
        "extension": ext,
        "file_type": ext,
        "mime_type": mime_for_ext(ext),
        "size_bytes": detail.get("size_bytes"),
        "mtime_ns": detail.get("mtime_ns"),
        "content_digest": detail.get("content_sha256"),
        "page_count": detail.get("page_count"),
        "paragraph_count": detail.get("paragraph_count"),
        "sheet_count": detail.get("sheet_count"),
        "extraction_status": detail.get("extraction_status"),
        "indexed_text_available": detail.get("text_excerpt") is not None,
        "indexed_metadata_available": True,
        "content_extraction_unsupported": unsupported,
        "parser_available": False if unsupported else None,
        "likely_project_numbers": projects,
        "folder_classification": None,
        "recommended_next_action": (
            "Use metadata + nearby readable siblings; do not invent XER/P6 content."
            if unsupported else "assistant_source_file_read for bounded content."
        ),
        "source_state": "deleted" if detail.get("deleted") else "active",
        "generated_card_available": bool(active_cards),
        "generated_card_rel_path": (active_cards[0]["note_rel_path"] if active_cards else None),
        "generated_card_status": (active_cards[0]["generation_status"] if active_cards else None),
        "generated_card_note": "supplemental artifact; the original source file is the primary object",
        "neighbors": neighbors,
        "nearby_readable_siblings": [n for n in neighbors if not str(n.get("rel_path") or "").lower().endswith((".xer", ".mpp"))],
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
                     max_chars: int | None = None, max_bytes: int | None = None,
                     prefer_live: bool = True, mode: str = READ_MODE_EXCERPT,
                     conn: Any = None) -> dict[str, Any]:
    """Read one NAS source FILE via ``SourceContentProvider``.

    ``mode='excerpt'`` (default) returns a bounded, extension-gated excerpt, degrading to the indexed
    excerpt (``indexed_excerpt_fallback``) when a live read is not permitted. ``mode='complete'`` returns
    a complete-or-explicit-failure read (subprocess-isolated for pdf/docx/xlsx/eml) with an explicit
    ``retrieval_state``/``content_state``/``completeness_state``; it never truncates and labels the result
    complete. Prefer a ``source_ref`` handoff from a search result; absolute paths are never accepted or
    returned."""
    # Fail-closed DB-aware resolution to a durable entity (PI-WI-03a); the content provider then receives
    # an already-resolved entity id (it is NOT modified).
    sid = repo.resolve_entity(source_id=source_id, source_ref=source_ref, conn=conn)
    if sid is None:
        raise SourceConnectorValidationError("source_not_found")
    provider = SourceContentProvider(repo, config)
    return provider.read(sid, max_chars=max_chars, max_bytes=max_bytes,
                         prefer_live=prefer_live, mode=mode, conn=conn)
