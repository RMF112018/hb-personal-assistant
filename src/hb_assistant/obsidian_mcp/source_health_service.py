"""Unified client-facing source index health (file index + structure map layers).

Read-only aggregation. Never returns absolute host paths. Bounded and deterministic.
"""

from __future__ import annotations

import contextlib
import time
from typing import Any

from hb_assistant.store.source_index_bootstrap_repository import SourceIndexBootstrapRepository
from hb_assistant.store.source_index_scan_generations_repository import (
    SourceIndexScanGenerationsRepository,
)

from .config import ObsidianMcpConfig
from .source_connector_service import list_source_roots, source_status
from .source_index_repository import SourceIndexRepository
from .source_structure_repository import SourceStructureRepository


def _watchdog_available() -> bool:
    try:
        import watchdog.observers  # noqa: F401

        return True
    except Exception:
        return False


def _run_state(config: ObsidianMcpConfig, ready: bool, backend: bool) -> str:
    """Path-safe per-root watcher run-state projection (mirrors source_bootstrap.resolve_run_state)."""
    if not bool(getattr(config, "external_source_watch_enabled", False)):
        return "disabled_by_config"
    if not ready:
        return "not_bootstrapped"
    if not backend:
        return "backend_unavailable"
    return "running"


def _freshness_state(
    *, last_indexed_at: str | None, is_active: bool = True, open_errors: int = 0
) -> str:
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

    # Bootstrap readiness + watcher/queue/reconciliation state (V117). All path-safe: bootstrap_state
    # and reconciliation rows carry only root_key; queue_health carries counts; the watcher-owner blob
    # is read ONLY for its heartbeat timestamp (never cwd/db_path).
    bstate = SourceIndexBootstrapRepository(str(repo.db_path))
    bootstrap_by_root = {b["root_key"]: b for b in bstate.list_bootstrap_state()}
    # V122 durable generation truth per root (latest by start): completeness/readiness must derive from a
    # COMPLETED metadata walk (+ reconciliation), NOT the legacy all-or-nothing bootstrap-run status — a
    # failed/abandoned/running generation must never read as "complete".
    genrepo = SourceIndexScanGenerationsRepository(str(repo.db_path))
    latest_generation_by_root: dict[str, dict[str, Any]] = {}
    try:
        # Per-root newest generation (uncapped) — a global list cap could evict a root's latest row when
        # other roots have accumulated many generations, silently reading stale/legacy completeness.
        latest_generation_by_root = genrepo.latest_generations()
    except Exception:  # noqa: BLE001 — health must never fail on the generation read
        latest_generation_by_root = {}
    # Configured roots by key + the current policy fingerprint per root, so completeness can be checked
    # against CURRENT policy: a completed generation whose stored fingerprint no longer matches the
    # configured root (a sensitivity / exclusion / root-path / matcher change) must NOT read as complete or
    # watcher-ready until the corrective generation runs.
    from .source_indexer import _root_fingerprint

    configured_fp_by_root: dict[str, str] = {}
    for _er in getattr(config, "external_sources", []) or []:
        # Never fail health on a fingerprint computation — a root that can't be fingerprinted just
        # falls back to the no-current-policy case (policy_current defaults True) downstream.
        with contextlib.suppress(Exception):
            configured_fp_by_root[_er.source_root_key] = _root_fingerprint(_er, config)
    try:
        queue = repo.queue_health()
    except Exception:
        queue = {}
    watcher_heartbeat = None
    try:
        owner = repo.get_watcher_owner(ttl_seconds=900)
        if isinstance(owner, dict):
            watcher_heartbeat = owner.get("heartbeat_at")  # redacted: timestamp only, no paths
    except Exception:
        watcher_heartbeat = None
    backend_available = _watchdog_available()

    # Skip code rollup from file index
    skipped_by_code = dict(file_status.get("skipped_by_code") or {})

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
        # Real, index-scoped extraction breakdown for THIS root (never derived from fts_available, which
        # is an all-or-nothing table-existence proxy). content_searchable requires nonempty text;
        # metadata_searchable = has a path/project FTS row (V122 path-FTS invariant).
        try:
            counts = repo.content_status_counts(key, conn=conn)
        except Exception:  # noqa: BLE001 — health must never fail on a count query
            counts = {
                "metadata_indexed": 0,
                "metadata_searchable": 0,
                "content_extracted": 0,
                "content_searchable": 0,
                "content_eligible": 0,
                "content_pending": 0,
                "intentional_metadata_only": 0,
                "metadata_only": 0,
                "failed": 0,
                "unsupported": 0,
                "too_large": 0,
            }
        layers = {
            "folder_layer_populated": folder_count > 0,
            "metadata_layer_populated": file_count > 0,
            # Real per-root content coverage, NOT the fts_available table-existence proxy.
            "content_layer_populated": counts.get("content_searchable", 0) > 0,
            "metadata_search_layer_populated": counts.get("metadata_searchable", 0) > 0,
        }
        safe = state in ("fresh", "degraded") and (
            layers["metadata_layer_populated"] or layers["folder_layer_populated"]
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
            summary_bits.append(
                "index layers present; safe for bounded client answers"
                if safe
                else "partial/blocked — prefer health-aware routing"
            )

        file_index_status = (bootstrap_by_root.get(key) or {}).get("file_index_status")
        gen_row = latest_generation_by_root.get(key)
        # Metadata completeness is REPORTED SEPARATELY from content completeness (V122): a metadata-first
        # root can be fully metadata-indexed (searchable by path) with zero content extracted. Completeness
        # derives from DURABLE GENERATION TRUTH when a V122 generation exists — the metadata WALK must have
        # completed on a non-failed/non-abandoned generation; a failed/abandoned/running/partial generation
        # is NOT complete. Roots with no V122 generation yet fall back to the legacy bootstrap status.
        if gen_row is not None:
            # Only a fully COMPLETED generation certifies completeness. reconcile_pending means the deletion
            # sweep found indeterminate candidates (potential phantom rows still in the index), so its
            # metadata set is NOT certifiably complete — it must read partial, not complete (finding 5).
            # AND the completed generation must match CURRENT policy: a fingerprint mismatch (sensitivity /
            # exclusion / root-path / matcher / indexing-policy change) means the completion is stale, so it
            # reads partial and watcher-not-ready until the corrective generation runs (round-5 finding 4).
            current_fp = configured_fp_by_root.get(key)
            policy_current = current_fp is None or gen_row.get("policy_fingerprint") == current_fp
            reconciliation_done = gen_row.get("status") == "completed" and policy_current
            metadata_walk_done = reconciliation_done
        else:
            # Legacy fallback (root with no V122 generation): accept ONLY the explicit success sentinel
            # ("bootstrapped"). Any other value ("partial"/"conflict"/"failed"/None) is NOT complete
            # (finding 5) — the prior ``!= "partial"`` wrongly certified conflict/failed/unknown as done.
            metadata_walk_done = file_index_status == "bootstrapped"
            reconciliation_done = file_index_status == "bootstrapped"
        if counts["metadata_indexed"] == 0:
            metadata_completeness_state = "none"
        elif metadata_walk_done:
            metadata_completeness_state = "complete"
        else:
            metadata_completeness_state = "partial"
        if counts["metadata_indexed"] == 0 or (
            counts["content_extracted"] == 0 and counts["content_searchable"] == 0
        ):
            content_completeness_state = "none"
        elif (
            counts.get("content_pending", 0) > 0 or counts["failed"] > 0 or not reconciliation_done
        ):
            content_completeness_state = "partial"
        else:
            content_completeness_state = "complete"
        # Watcher readiness (V122): for a root the new architecture tracks, readiness is a COMPLETED
        # metadata+reconciliation generation AND structure truth (a folder map present) — NOT the persisted
        # legacy readiness bit, which could read ready off a partial/legacy bootstrap (finding 5). Roots
        # with no V122 generation yet fall back to the legacy bit.
        legacy_watcher_ready = bool((bootstrap_by_root.get(key) or {}).get("watcher_ready"))
        if gen_row is not None:
            watcher_ready = bool(reconciliation_done and folder_count > 0)
        else:
            watcher_ready = legacy_watcher_ready
        # Path/filename lookup is safe when the root has SEARCHABLE metadata (a path FTS row) or a folder
        # map — not merely a bare row count (V122).
        safe_for_path_lookup = counts.get("metadata_searchable", 0) > 0 or folder_count > 0
        if content_completeness_state == "complete" and state in ("fresh", "degraded"):
            safe_for_content_answering = "complete"
        elif counts["content_searchable"] > 0 and state in ("fresh", "degraded"):
            safe_for_content_answering = "partial"
        else:
            safe_for_content_answering = "none"

        per_root.append(
            {
                "root_key": key,
                "display_label": (sroot or {}).get("display_name") or key,
                "root_class": (sroot or {}).get("root_class")
                or root.get("source_kind")
                or "unknown",
                "enabled": bool(root.get("enabled", True)),
                "last_scan_started": (structure_status.get("last_run") or {}).get("started_at"),
                "last_scan_completed": (structure_status.get("last_run") or {}).get("finished_at"),
                "last_successful_scan": last_indexed,
                "scan_duration": None,
                "scan_status": (structure_status.get("last_run") or {}).get("status"),
                "indexing_watermark": last_indexed,
                "total_folders_indexed": folder_count,
                "total_files_indexed": file_count or struct_files,
                # Honest, index-scoped breakdown (replaces the fts_available all-or-nothing proxy).
                "content_indexed_file_count": counts["content_searchable"],
                "metadata_only_file_count": counts["metadata_only"],
                "metadata_indexed_file_count": counts["metadata_indexed"],
                "metadata_searchable_file_count": counts.get("metadata_searchable", 0),
                "content_eligible_file_count": counts.get("content_eligible", 0),
                "content_pending_file_count": counts.get("content_pending", 0),
                "intentional_metadata_only_file_count": counts.get("intentional_metadata_only", 0),
                "content_extracted_file_count": counts["content_extracted"],
                "content_searchable_file_count": counts["content_searchable"],
                "failed_file_count": counts["failed"],
                "too_large_file_count": counts["too_large"],
                "metadata_completeness_state": metadata_completeness_state,
                "content_completeness_state": content_completeness_state,
                "safe_for_path_lookup": safe_for_path_lookup,
                "safe_for_content_answering": safe_for_content_answering,
                "live_readable_file_count": None,  # not cheap; clients use metadata.read_status
                "unsupported_file_count": counts["unsupported"],
                "skipped_file_count": sum(int(v) for v in skipped_by_code.values())
                if len(roots_env.get("roots") or []) == 1
                else None,
                "skipped_directory_count": int((sroot or {}).get("noise_count") or 0),
                "largest_skipped_directories": [],
                "extension_type_distribution": [],
                "freshness_status": state,
                "scan_error_count": int(structure_status.get("open_finding_count") or 0),
                "recent_scan_errors": [],
                "layers": layers,
                "safe_for_client_answering": safe,
                "diagnostic_summary": "; ".join(summary_bits)[:400],
                "bootstrap": {
                    "file_index_bootstrapped": bool(
                        (bootstrap_by_root.get(key) or {}).get("file_index_bootstrapped")
                    ),
                    "structure_index_bootstrapped": bool(
                        (bootstrap_by_root.get(key) or {}).get("structure_index_bootstrapped")
                    ),
                    # V122-derived when a generation exists (completed reconciliation + folder map), else legacy.
                    "watcher_ready": watcher_ready,
                },
                "run_state": _run_state(config, watcher_ready, backend_available),
                **bstate.get_structure_drift(key),
            }
        )

    # Empty-roots handling
    if not per_root:
        per_root.append(
            {
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
            }
        )

    overall = "fresh"
    if all(r["freshness_status"] == "never_succeeded" for r in per_root):
        overall = "never_succeeded"
    elif any(r["freshness_status"] in ("blocked", "future_anomaly") for r in per_root):
        overall = "degraded"
    elif any(not r["safe_for_client_answering"] for r in per_root):
        overall = "partial"
    elif any(r["freshness_status"] == "stale" for r in per_root):
        overall = "stale"

    # --- V117 aggregate sections (bootstrap / watcher / file_index queue / structure drift /
    # reconciliation) + an operator action recommendation. Directory-architecture drift discovered by
    # reconciliation is surfaced even though the auto-rebuild bridge is deferred (dirty_bridge_enabled
    # is a constant False this branch), so clients know a folder map may lag and no auto-rebuild runs.
    real_roots = [r for r in per_root if r["root_key"] != "(none)"]
    any_unbootstrapped = (
        any(not r["bootstrap"]["watcher_ready"] for r in real_roots) or not real_roots
    )
    any_drift = any(r.get("directory_change_detected") for r in real_roots)
    last_light = bstate.last_reconciliation(scan_type="lightweight") or {}
    last_full = bstate.last_reconciliation(scan_type="full") or {}
    recommended = None
    if any_unbootstrapped:
        # Bounded, per-root guidance — NEVER an unbounded all-roots content walk (that is exactly the
        # operation that stalled/OOM'd a very large root). Each root resumes across bounded passes.
        recommended = (
            "bootstrap incomplete roots one at a time with bounded passes: "
            "`hb-assistant source-watch bootstrap --root-key <root>` (safe defaults apply; re-run to "
            "resume until bounded_out=false)"
        )
    elif any_drift:
        recommended = (
            "directory architecture changed — run `hb-assistant source-watch bootstrap "
            "--structure-only` for drifted roots (structure map may be stale)"
        )
    elif int(queue.get("error_count") or 0) > 0:
        recommended = (
            "investigate failed file-index queue items (`hb-assistant source-watch status`)"
        )

    top_safe = bool(real_roots) and any(r["safe_for_client_answering"] for r in real_roots)

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
        "bootstrap": {
            "all_roots_watcher_ready": bool(real_roots) and not any_unbootstrapped,
            "roots_ready": sum(1 for r in real_roots if r["bootstrap"]["watcher_ready"]),
            "roots_total": len(real_roots),
        },
        "watcher": {
            "enabled": bool(getattr(config, "external_source_watch_enabled", False)),
            "backend": "watchdog" if backend_available else "polling",
            "backend_available": backend_available,
            "last_heartbeat_at": watcher_heartbeat,
            "queue_depth": queue.get("queued_count"),
            "processing_count": queue.get("processing_count"),
            "oldest_pending_age_seconds": queue.get("oldest_processing_age_seconds"),
        },
        "file_index": {
            "last_incremental_update": queue.get("last_drain_at")
            or file_status.get("last_indexed_at"),
            "pending_queue_count": queue.get("queued_count"),
            "failed_queue_count": queue.get("error_count"),
        },
        "structure_index": {
            "last_structure_update": (structure_status.get("last_run") or {}).get("finished_at"),
            "directory_change_detected": any_drift,
            "structure_refresh_recommended": any_drift,
            "dirty_bridge_enabled": False,
        },
        "reconciliation": {
            "last_lightweight_reconciliation": last_light.get("finished_at"),
            "last_full_reconciliation": last_full.get("finished_at"),
        },
        "recommended_operator_action": recommended,
        "safe_for_client_answering": top_safe,
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
