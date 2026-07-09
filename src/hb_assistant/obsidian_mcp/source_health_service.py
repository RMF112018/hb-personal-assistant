"""Unified client-facing source index health (file index + structure map layers).

Read-only aggregation. Never returns absolute host paths. Bounded and deterministic.
"""

from __future__ import annotations

import time
from typing import Any

from .config import ObsidianMcpConfig
from .source_connector_service import list_source_roots, source_status
from .source_index_repository import SourceIndexRepository
from .source_structure_repository import SourceStructureRepository


def _freshness_state(*, last_indexed_at: str | None, is_active: bool = True,
                     open_errors: int = 0) -> str:
    if not is_active:
        return "blocked"
    if not last_indexed_at:
        return "never_succeeded"
    # Future timestamp anomaly (ISO lexical compare against now prefix)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    if str(last_indexed_at)[:19] > now:
        return "future_anomaly"
    if open_errors:
        return "degraded"
    # Age: if missing or unparsable, treat as unknown; if present, assume operator-indexed = fresh enough
    # without hard SLA (operator tools set last_indexed_at). Stale is raised when structure never indexed.
    return "fresh"


def source_index_health(
    repo: SourceIndexRepository,
    config: ObsidianMcpConfig,
    *,
    structure_repo: SourceStructureRepository | None = None,
    conn: Any = None,
    limit_errors: int = 5,
) -> dict[str, Any]:
    """Per-root health for connected clients to decide whether to trust search results."""
    t0 = time.perf_counter()
    file_status = source_status(repo, config, conn=conn)
    roots_env = list_source_roots(repo, config, conn=conn)
    srepo = structure_repo or SourceStructureRepository(str(repo.db_path))
    structure_status = srepo.status()
    structure_roots = {r["root_key"]: r for r in srepo.list_roots(limit=100)}

    # Skip code rollup from file index
    skipped_by_code = dict(file_status.get("skipped_by_code") or {})
    unsupported_skip = int(skipped_by_code.get("unsupported_file_type") or 0)

    per_root: list[dict[str, Any]] = []
    for root in roots_env.get("roots") or []:
        key = root["source_root_key"]
        sroot = structure_roots.get(key) or structure_roots.get(key.replace("syn-", ""))
        # Map common keys
        if sroot is None:
            for sk, sr in structure_roots.items():
                if sk in key or key in sk:
                    sroot = sr
                    break
        folder_count = int((sroot or {}).get("folder_count") or 0)
        struct_files = int((sroot or {}).get("file_count") or 0)
        file_count = int(root.get("file_count") or 0)
        last_indexed = (sroot or {}).get("last_indexed_at") or file_status.get("last_indexed_at")
        state = _freshness_state(
            last_indexed_at=last_indexed,
            is_active=bool(root.get("enabled", True)),
        )
        layers = {
            "folder_layer_populated": folder_count > 0,
            "metadata_layer_populated": file_count > 0,
            "content_layer_populated": bool(file_status.get("fts_available")),
        }
        safe = (
            state in ("fresh", "degraded")
            and (layers["metadata_layer_populated"] or layers["folder_layer_populated"])
        )
        summary_bits = []
        if not layers["folder_layer_populated"]:
            summary_bits.append("folder map empty — run source-structure ingest")
        if not layers["metadata_layer_populated"]:
            summary_bits.append("no indexed files for this root")
        if state == "never_succeeded":
            summary_bits.append("never successfully indexed")
        if state == "future_anomaly":
            summary_bits.append("last_indexed_at is in the future")
        if not summary_bits:
            summary_bits.append("index layers present; safe for bounded client answers" if safe
                                else "partial/blocked — prefer health-aware routing")

        per_root.append({
            "root_key": key,
            "display_label": (sroot or {}).get("display_name") or key,
            "root_class": (sroot or {}).get("root_class") or root.get("source_kind") or "unknown",
            "enabled": bool(root.get("enabled", True)),
            "last_scan_started": (structure_status.get("last_run") or {}).get("started_at"),
            "last_scan_completed": (structure_status.get("last_run") or {}).get("finished_at"),
            "last_successful_scan": last_indexed,
            "scan_duration": None,
            "scan_status": (structure_status.get("last_run") or {}).get("status"),
            "indexing_watermark": last_indexed,
            "total_folders_indexed": folder_count,
            "total_files_indexed": file_count or struct_files,
            "content_indexed_file_count": file_count if file_status.get("fts_available") else 0,
            "metadata_only_file_count": max(0, (file_count or struct_files) - (
                file_count if file_status.get("fts_available") else 0
            )),
            "live_readable_file_count": None,  # not cheap; clients use metadata.read_status
            "unsupported_file_count": unsupported_skip if key == (roots_env.get("roots") or [{}])[0].get(
                "source_root_key"
            ) else 0,
            "skipped_file_count": sum(int(v) for v in skipped_by_code.values()) if len(
                roots_env.get("roots") or []
            ) == 1 else None,
            "skipped_directory_count": int((sroot or {}).get("noise_count") or 0),
            "largest_skipped_directories": [],
            "extension_type_distribution": [],
            "freshness_status": state,
            "scan_error_count": int(structure_status.get("open_finding_count") or 0),
            "recent_scan_errors": [],
            "layers": layers,
            "safe_for_client_answering": safe,
            "diagnostic_summary": "; ".join(summary_bits)[:400],
        })

    # Empty-roots handling
    if not per_root:
        per_root.append({
            "root_key": "(none)",
            "display_label": "no source roots configured or indexed",
            "root_class": "unknown",
            "enabled": False,
            "last_scan_started": None,
            "last_scan_completed": None,
            "last_successful_scan": None,
            "scan_duration": None,
            "scan_status": "never_succeeded",
            "indexing_watermark": None,
            "total_folders_indexed": 0,
            "total_files_indexed": 0,
            "content_indexed_file_count": 0,
            "metadata_only_file_count": 0,
            "live_readable_file_count": 0,
            "unsupported_file_count": 0,
            "skipped_file_count": 0,
            "skipped_directory_count": 0,
            "largest_skipped_directories": [],
            "extension_type_distribution": [],
            "freshness_status": "never_succeeded",
            "scan_error_count": 0,
            "recent_scan_errors": [],
            "layers": {
                "folder_layer_populated": False,
                "metadata_layer_populated": False,
                "content_layer_populated": False,
            },
            "safe_for_client_answering": False,
            "diagnostic_summary": "No source roots available — configure external sources and run index.",
        })

    overall = "fresh"
    if all(r["freshness_status"] == "never_succeeded" for r in per_root):
        overall = "never_succeeded"
    elif any(r["freshness_status"] in ("blocked", "future_anomaly") for r in per_root):
        overall = "degraded"
    elif any(not r["safe_for_client_answering"] for r in per_root):
        overall = "partial"
    elif any(r["freshness_status"] == "stale" for r in per_root):
        overall = "stale"

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    return {
        "overall_freshness": overall,
        "structure_status": {
            "root_count": structure_status.get("root_count"),
            "folder_count": structure_status.get("folder_count"),
            "open_finding_count": structure_status.get("open_finding_count"),
            "last_run": structure_status.get("last_run"),
        },
        "file_index_status": {
            "fts_available": file_status.get("fts_available"),
            "last_indexed_at": file_status.get("last_indexed_at"),
            "skipped_by_code": skipped_by_code,
            "index_enabled": file_status.get("index_enabled"),
        },
        "roots": per_root[:50],
        "root_count": len(per_root),
        "truncated": len(per_root) > 50,
        "telemetry": {
            "elapsed_ms": elapsed_ms,
            "candidate_count": len(per_root),
            "returned_count": min(len(per_root), 50),
            "truncated": len(per_root) > 50,
            "cursor_present": False,
            "layers_used": ["source_intelligence", "source_structure"],
            "fallback_used": None,
            "rank_strategy": "n/a",
            "freshness_basis": "last_indexed_at+structure_runs",
        },
    }
