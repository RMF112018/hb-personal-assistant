"""Request-path query layer for the source-intelligence index.

Pure, bounded, strict-JSON functions called by the service facade (run off the event loop by
``_run_tool``). These NEVER scan directories — broad queries hit FTS or return a structured
index-status; they never fall back to a live recursive scan.
"""

from __future__ import annotations

from typing import Any

from .config import ObsidianMcpConfig
from .source_index_repository import SourceIndexRepository

_MAX_LIMIT = 50
_MAX_SNIPPET = 240


def _clamp(limit: int | None) -> int:
    return min(max(1, int(limit or 10)), _MAX_LIMIT)


def _freshness(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "fts_available": status.get("fts_available", False),
        "queued_count": status.get("queued_count", 0),
        "processing_count": status.get("processing_count", 0),
        "sources_total": status.get("sources_total", 0),
        "last_indexed_at": status.get("last_indexed_at"),
        "stale_note_count": status.get("stale_note_count", 0),
    }


def _bound_snippet(value: str | None) -> str | None:
    if value is None:
        return None
    return value[:_MAX_SNIPPET]


def search_sources(repo: SourceIndexRepository, config: ObsidianMcpConfig, *, query: str,
                   limit: int | None = None, project_key: str | None = None,
                   operator_mode: bool = False) -> dict[str, Any]:
    status = repo.index_status()
    if not status.get("fts_available"):
        return {"query": query, "results": [], "search_backend": "index_unavailable",
                "index": _freshness(status)}
    rows = repo.search_sources(query, limit=_clamp(limit), project_key=project_key)
    for r in rows:
        r["snippet"] = _bound_snippet(r.get("snippet"))
    return {"query": query, "results": rows, "search_backend": "source_index",
            "index": _freshness(status)}


def search_knowledge(repo: SourceIndexRepository, config: ObsidianMcpConfig, *, query: str,
                     limit: int | None = None, path_scope: str | None = None,
                     operator_mode: bool = False) -> dict[str, Any]:
    status = repo.index_status()
    if not status.get("fts_available"):
        return {"query": query, "results": [], "search_backend": "index_unavailable",
                "index": _freshness(status)}
    lim = _clamp(limit)
    notes = repo.search_notes(query, limit=lim, path_prefix=(path_scope or None))
    sources = repo.search_sources(query, limit=lim)
    merged = notes + sources
    # bm25: lower is better — sort ascending, then clamp to limit.
    merged.sort(key=lambda r: r.get("score", 0.0))
    merged = merged[:lim]
    for r in merged:
        r["snippet"] = _bound_snippet(r.get("snippet"))
    return {"query": query, "results": merged, "search_backend": "knowledge_index",
            "index": _freshness(status)}


def source_index_status(repo: SourceIndexRepository, config: ObsidianMcpConfig,
                        *, watcher: dict[str, Any] | None = None) -> dict[str, Any]:
    status = repo.index_status()
    status["index_enabled"] = bool(getattr(config, "external_source_index_enabled", True))
    status["watch_enabled"] = bool(getattr(config, "external_source_watch_enabled", False))
    status["configured_source_count"] = len(getattr(config, "external_sources", []) or [])
    status["exclusion_policy"] = {
        "excluded_path_parts": list(getattr(config, "source_index_excluded_path_parts", []) or [])
    }
    status["deferred_policy"] = {
        "deferred_path_parts": list(getattr(config, "source_index_deferred_path_parts", []) or [])
    }
    # PM Source Value Policy (A1.11): what gets auto-carded first / deferred / metadata-only / skipped.
    status["source_value_policy"] = {
        "high_priority_path_signals": list(getattr(config, "source_value_high_priority_path_signals", []) or []),
        "normal_priority_path_signals": list(getattr(config, "source_value_normal_priority_path_signals", []) or []),
        "metadata_only_file_types": list(getattr(config, "source_index_metadata_only_file_types", []) or []),
        "unsupported_file_types": list(getattr(config, "source_index_unsupported_file_types", []) or []),
        "deferred_path_parts": list(getattr(config, "source_index_deferred_path_parts", []) or []),
        "auto_card_metadata_only_enabled": bool(getattr(config, "source_card_auto_metadata_only_enabled", False)),
    }
    # Coarse, bounded queue-composition diagnostic (path/ext-only — NOT authoritative; document_type
    # is unavailable for not-yet-indexed events, so high/normal here is filename-signal-based).
    status["queued_by_disposition"] = _queued_by_disposition(repo, config)
    status["search_backend"] = "source_index"
    if watcher is not None:
        status["watcher"] = watcher
    return status


def _queued_by_disposition(repo: SourceIndexRepository, config: ObsidianMcpConfig,
                           *, sample_limit: int = 500) -> dict[str, Any]:
    """Bounded path/ext-only classification of queued events (coarse diagnostic)."""
    from .source_value import SourceValueDisposition, classify_path_disposition

    counts: dict[str, int] = {d.value: 0 for d in SourceValueDisposition}
    sampled = 0
    try:
        events = repo.sample_queued_events(limit=sample_limit)
    except Exception:  # noqa: BLE001 - diagnostic must never break status
        return {"sampled": 0, "sample_limit": sample_limit, "counts": counts, "note": "unavailable"}
    from pathlib import PurePosixPath

    for ev in events:
        sampled += 1
        rel = ev.get("rel_path") or ""
        ext = PurePosixPath(rel.replace("\\", "/")).suffix if rel else ""
        disp = classify_path_disposition(rel, ext, config)
        counts[disp.value] += 1
    return {
        "sampled": sampled,
        "sample_limit": sample_limit,
        "counts": counts,
        "note": "coarse path/ext-only sample; document_type-based high/normal is approximate",
    }


def search_vault_indexed(repo: SourceIndexRepository, config: ObsidianMcpConfig, *, query: str,
                         path_scope: str | None = None, file_types: list[str] | None = None,
                         limit: int | None = None, include_content_snippet: bool = True,
                         operator_mode: bool = False) -> dict[str, Any]:
    """Index-backed broad search over the curated Obsidian-note FTS. Preserves the search_vault
    result shape. Returns a structured index-status (never a live scan) when empty/unavailable."""
    status = repo.index_status()
    note_count = status.get("by_kind", {}).get("obsidian_note", 0)
    if not status.get("fts_available") or note_count == 0:
        backend = "index_unavailable" if not status.get("fts_available") else "note_index_empty"
        return {"query": query, "results": [], "search_backend": backend, "index": _freshness(status)}
    rows = repo.search_notes(query, limit=_clamp(limit), path_prefix=(path_scope or None))
    results = [
        {"path": r["path"], "file_type": "md", "score": r["score"],
         "snippet": _bound_snippet(r.get("snippet")) if include_content_snippet else None}
        for r in rows
    ]
    return {"query": query, "results": results, "search_backend": "note_index",
            "index": _freshness(status)}
