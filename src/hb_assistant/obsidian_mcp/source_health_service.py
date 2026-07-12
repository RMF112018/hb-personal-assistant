"""Unified client-facing source index health (file index + structure map layers).

Read-only aggregation. Never returns absolute host paths. Bounded and deterministic.
"""

from __future__ import annotations

import contextlib
import time
from datetime import datetime, timezone
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
    """Path-safe per-root watcher run-state projection — delegates to the SHARED authority
    (``source_bootstrap.project_run_state``) so health and the CLI can never disagree (A3)."""
    from .source_bootstrap import project_run_state

    return project_run_state(
        enabled=bool(getattr(config, "external_source_watch_enabled", False)),
        ready=ready,
        backend=backend,
    )


def _freshness_state(
    *, last_indexed_at: str | None, is_active: bool = True, open_errors: int = 0
) -> str:
    if not is_active:
        return "blocked"
    if last_indexed_at is None:
        # ONLY a genuine never-run root (NULL timestamp). An empty string or garbage is a MALFORMED value
        # (a corrupt/partial write), not "never run" — it must fall through to the parser and fail closed
        # below, never read as ``never_succeeded`` (which is a benign not-yet-indexed state).
        return "never_succeeded"
    # Future-timestamp anomaly. The stored timestamp is UTC (repository ``_now`` uses
    # ``datetime.now(timezone.utc)``), so the comparison clock MUST be UTC too. The old
    # ``time.strftime`` (LOCAL wall clock) compared a UTC timestamp against local time, marking every
    # freshly-indexed root ``future_anomaly`` for the entire UTC-offset window (e.g. 4h on US-Eastern) and
    # falsely closing ``safe_for_client_answering`` on the deployment machine. Parse + normalize to UTC at
    # second granularity (a naive stored timestamp is treated as UTC, matching how the app writes it).
    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    try:
        parsed = datetime.fromisoformat(str(last_indexed_at))
        parsed = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        is_future = parsed.astimezone(timezone.utc).replace(microsecond=0) > now_utc
    except (ValueError, TypeError):
        # Unparseable/malformed timestamp: FAIL CLOSED. The old lexical fallback compared raw bytes, so a
        # garbage value sorting before "now" fell through to ``fresh`` and RE-OPENED trust. Return the
        # fail-closed ``unknown`` state — it is NOT in the ("fresh","degraded") trust set, so
        # index-layers/client/content/path answering all close (see the gates below).
        return "unknown"
    if is_future:
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
    app_config: Any = None,
    structure_repo: SourceStructureRepository | None = None,
    conn: Any = None,
    limit_errors: int = 5,
) -> dict[str, Any]:
    """Per-root health for connected clients to decide whether to trust search results.

    On NAS MCP the authoritative DB is a read-only snapshot mount. All nested repository
    reads MUST reuse the caller-supplied read-only ``conn`` (or open readonly). Opening a
    write connection against the snapshot fails with StoreReadinessError and must not
    surface as a raw gateway exception for an advertised health tool.

    ``app_config`` supplies the canonical A3 structure-root mapping (``source_structure.scan_roots`` +
    ``structure_root_map``). When omitted it is loaded internally (fail-open to empty on error), and the
    exact-match namespace falls back to the ingested structure roots so identity mappings still resolve.
    """
    t0 = time.perf_counter()
    try:
        return _source_index_health_body(
            repo,
            config,
            app_config=app_config,
            structure_repo=structure_repo,
            conn=conn,
            limit_errors=limit_errors,
            started=t0,
        )
    except Exception as exc:  # noqa: BLE001 — fail-closed structured envelope
        return {
            "ok": False,
            "error_code": "source_index_health_unavailable",
            "reason": "health_aggregation_failed",
            "message": str(exc)[:300],
            "safe_for_client_answering": False,
            "safe_for_metadata_discovery": False,
            "safe_for_path_lookup": False,
            "safe_for_content_answering": False,
            "roots": [],
            "elapsed_ms": int((time.perf_counter() - t0) * 1000),
        }


def _source_index_health_body(
    repo: SourceIndexRepository,
    config: ObsidianMcpConfig,
    *,
    app_config: Any = None,
    structure_repo: SourceStructureRepository | None = None,
    conn: Any = None,
    limit_errors: int = 5,
    started: float,
) -> dict[str, Any]:
    """Inner health aggregation; requires conn threading for RO snapshot safety."""
    t0 = started
    file_status = source_status(repo, config, conn=conn)
    roots_env = list_source_roots(repo, config, conn=conn)
    srepo = structure_repo or SourceStructureRepository(str(repo.db_path))
    structure_status = srepo.status(conn=conn)
    structure_roots = {r["root_key"]: r for r in srepo.list_roots(limit=100, conn=conn)}
    # A3 canonical structure-root mapping inputs — FAIL CLOSED. The application configuration is the mapping
    # authority. An explicitly injected config (even a valid EMPTY one) is trusted and still permits exact
    # identity matching; but a FAILED or INVALID load must NOT be read as an empty valid config — otherwise
    # health could call a root structure-ready without knowing the canonical mapping. A load/validation
    # failure is distinguishable from a valid empty config: mapping_config_available is False, there is no
    # identity fallback, and every root resolves to `mapping_configuration_unavailable` (structure_ready=False).
    mapping_config_available = True
    if app_config is None:
        try:
            from hb_assistant.config.loader import load_config as _load_app_config

            app_config = _load_app_config()
        except Exception:
            mapping_config_available = False
            app_config = None
    if mapping_config_available:
        _app_ss = getattr(app_config, "source_structure", None)
        structure_scan_roots = dict(getattr(_app_ss, "scan_roots", {}) or {})
        structure_root_map = dict(getattr(_app_ss, "structure_root_map", {}) or {})
        # Exact-match namespace: prefer the declared config scan_roots; fall back to ingested structure roots
        # so identity mappings still resolve for a valid config that did not declare scan_roots.
        structure_namespace = list(structure_scan_roots.keys()) or list(structure_roots.keys())
    else:
        # No trustworthy mapping authority: no explicit map, no identity fallback. Fail closed.
        structure_scan_roots = {}
        structure_root_map = {}
        structure_namespace = []

    # Bootstrap readiness + watcher/queue/reconciliation state (V117). All path-safe: bootstrap_state
    # and reconciliation rows carry only root_key; queue_health carries counts; the watcher-owner blob
    # is read ONLY for its heartbeat timestamp (never cwd/db_path).
    bstate = SourceIndexBootstrapRepository(str(repo.db_path))
    # CRITICAL: pass conn so RO snapshot mounts do not open a write connection.
    bootstrap_by_root = {b["root_key"]: b for b in bstate.list_bootstrap_state(conn=conn)}
    # V122 durable generation truth per root (latest by start): completeness/readiness must derive from a
    # COMPLETED metadata walk (+ reconciliation), NOT the legacy all-or-nothing bootstrap-run status — a
    # failed/abandoned/running generation must never read as "complete".
    genrepo = SourceIndexScanGenerationsRepository(str(repo.db_path))
    latest_generation_by_root: dict[str, dict[str, Any]] = {}
    try:
        # Per-root newest generation (uncapped) — a global list cap could evict a root's latest row when
        # other roots have accumulated many generations, silently reading stale/legacy completeness.
        latest_generation_by_root = genrepo.latest_generations(conn=conn)
    except Exception:  # noqa: BLE001 — health must never fail on the generation read
        latest_generation_by_root = {}
    # Configured roots by key + the current policy fingerprint per root, so completeness can be checked
    # against CURRENT policy: a completed generation whose stored fingerprint no longer matches the
    # configured root (a sensitivity / exclusion / root-path / matcher change) must NOT read as complete or
    # watcher-ready until the corrective generation runs.
    from .source_indexer import _root_fingerprint, derive_watcher_ready

    configured_fp_by_root: dict[str, str] = {}
    for _er in getattr(config, "external_sources", []) or []:
        # Never fail health on a fingerprint computation — a root that can't be fingerprinted just
        # falls back to the no-current-policy case (policy_current defaults True) downstream.
        with contextlib.suppress(Exception):
            configured_fp_by_root[_er.source_root_key] = _root_fingerprint(_er, config)
    try:
        queue = repo.queue_health(conn=conn)
    except Exception:
        queue = {}
    watcher_heartbeat = None
    try:
        owner = repo.get_watcher_owner(ttl_seconds=900, conn=conn)
        if isinstance(owner, dict):
            watcher_heartbeat = owner.get("heartbeat_at")  # redacted: timestamp only, no paths
    except Exception:
        watcher_heartbeat = None
    backend_available = _watchdog_available()

    # Skip code rollup from file index
    skipped_by_code = dict(file_status.get("skipped_by_code") or {})

    per_root: list[dict[str, Any]] = []
    from .source_root_mapping import (
        REASON_CONFIG_UNAVAILABLE,
        StructureRootMapping,
        normalize_root_key,
        resolve_structure_mapping,
    )

    for root in roots_env.get("roots") or []:
        key = root["source_root_key"]
        # A3: the ONE canonical exact/explicit resolver (no fuzzy substring / `syn-` strip / first-row).
        # When the mapping authority is unavailable/invalid, fail closed — never resolve, never identity-fall-back.
        if mapping_config_available:
            struct_mapping = resolve_structure_mapping(
                key, structure_namespace, config_map=structure_root_map
            )
        else:
            struct_mapping = StructureRootMapping(
                normalize_root_key(key), None, REASON_CONFIG_UNAVAILABLE
            )
        sroot = (
            structure_roots.get(struct_mapping.structure_key)
            if struct_mapping.structure_key is not None
            else None
        )
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
        gen_row = latest_generation_by_root.get(key)
        # POLICY CERTIFICATION (round-7 blocker 2). Trust is certified from the AUTHORITATIVE LATEST
        # generation overall — never from an independently-selected latest-COMPLETED row, which a newer
        # running/partial/failed corrective pass would mask (reopening trust before reconciliation completes).
        # A completed generation whose stored fingerprint no longer matches the configured root (a sensitivity
        # / exclusion / root-path / matcher / indexing-policy change) may serve plaintext-when-now-sensitive or
        # newly-excluded rows, so EVERY trust output fails closed until a COMPLETED generation under CURRENT
        # policy exists. ``policy_verification`` reports this honestly instead of collapsing three distinct
        # situations into one boolean:
        #   current      — latest generation is ``completed`` AND its fingerprint matches current policy
        #   stale        — a generation exists but the latest is not a current-policy completion (policy
        #                  changed, or a corrective pass is running/partial/failed) → fail closed
        #   uncertified  — configured root with NO generation yet (legacy transitional) → fail closed for
        #                  answering, but completeness still uses the legacy bootstrap fallback below
        #   unavailable  — no configured policy to verify against (configless / index-only serving profile):
        #                  verification is impossible, so "verified safe" is honestly false, while the root may
        #                  still be served ADVISORILY (see ``index_only_available``) — available ≠ verified-safe
        current_fp = configured_fp_by_root.get(key)
        # Completeness/watcher currency (unchanged semantics): matches current policy, or unverifiable.
        policy_current = current_fp is None or (
            gen_row is not None and gen_row.get("policy_fingerprint") == current_fp
        )
        if current_fp is None:
            policy_verification = "unavailable"
        elif (
            gen_row is not None
            and gen_row.get("status") == "completed"
            and gen_row.get("policy_fingerprint") == current_fp
        ):
            policy_verification = "current"
        elif gen_row is None:
            policy_verification = "uncertified"
        else:
            policy_verification = "stale"
        policy_certified = policy_verification == "current"
        layers = {
            "folder_layer_populated": folder_count > 0,
            "metadata_layer_populated": file_count > 0,
            # Real per-root content coverage, NOT the fts_available table-existence proxy.
            "content_layer_populated": counts.get("content_searchable", 0) > 0,
            "metadata_search_layer_populated": counts.get("metadata_searchable", 0) > 0,
        }
        index_layers_ready = state in ("fresh", "degraded") and (
            layers["metadata_layer_populated"] or layers["folder_layer_populated"]
        )
        # Advisory availability: serving is POSSIBLE from the index layers even when policy cannot be verified
        # (configless / index-only profile). This is NOT "verified safe" — a client answering off it proceeds
        # without policy certification (blocker 2: available ≠ verified-safe). ``safe`` requires certification.
        index_only_available = index_layers_ready
        safe = policy_certified and index_layers_ready
        summary_bits = []
        if policy_verification == "stale":
            summary_bits.append(
                "indexing policy changed since the last completed scan — reindex required; "
                "not safe for answering until the corrective scan completes"
            )
        elif policy_verification == "uncertified":
            summary_bits.append(
                "no completed scan under current policy for this root — not safe for answering until the "
                "initial scan completes"
            )
        elif policy_verification == "unavailable":
            summary_bits.append(
                "policy verification unavailable — no configured policy for this root; index-only serving "
                "is advisory, not verified safe"
            )
        if not layers["folder_layer_populated"]:
            summary_bits.append("folder map empty — run source-structure ingest")
        if not layers["metadata_layer_populated"]:
            summary_bits.append("no indexed files for this root")
        if state == "never_succeeded":
            summary_bits.append("never successfully indexed")
        if state == "future_anomaly":
            summary_bits.append("last_indexed_at is in the future")
        if state == "unknown":
            summary_bits.append(
                "last_indexed_at is unparseable/invalid — index integrity uncertain"
            )
        if not summary_bits:
            summary_bits.append(
                "index layers present; safe for bounded client answers"
                if safe
                else "partial/blocked — prefer health-aware routing"
            )

        file_index_status = (bootstrap_by_root.get(key) or {}).get("file_index_status")
        # Metadata completeness is REPORTED SEPARATELY from content completeness (V122): a metadata-first
        # root can be fully metadata-indexed (searchable by path) with zero content extracted. Completeness
        # derives from DURABLE GENERATION TRUTH when a V122 generation exists — the metadata WALK must have
        # completed on a non-failed/non-abandoned generation; a failed/abandoned/running/partial generation
        # is NOT complete. Roots with no V122 generation yet fall back to the legacy bootstrap status.
        if gen_row is not None:
            # Only a fully COMPLETED generation certifies completeness. reconcile_pending means the deletion
            # sweep found indeterminate candidates (potential phantom rows still in the index), so its
            # metadata set is NOT certifiably complete — it must read partial, not complete (finding 5).
            # AND it must match CURRENT policy: a fingerprint mismatch (``policy_current`` is False above)
            # means the completion is stale, so it reads partial and watcher-not-ready until the corrective run.
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
        # Shared authority (V122 blocker 2): identical rule used by ``resolve_run_state`` so the CLI can
        # never launch a watcher this projection reports as not-ready. FAIL-CLOSED on an unverifiable policy
        # (``current_fp is None``) — stricter than the content-completeness ``policy_current`` above, which
        # legitimately treats an absent current policy as "nothing to contradict".
        watcher_ready = derive_watcher_ready(
            gen_row=gen_row,
            current_fp=current_fp,
            folder_count=folder_count,
            legacy_ready=legacy_watcher_ready,
        )
        # Path/filename lookup is safe when the root has SEARCHABLE metadata (a path FTS row) or a folder
        # map — not merely a bare row count (V122) — AND the completion matches current policy (finding 2:
        # a policy-stale root may index newly-excluded paths, so path lookup fails closed too) — AND the
        # freshness timestamp is not MALFORMED (blocker 3: an unparseable ``last_indexed_at`` is a corrupt
        # index signal; closing only client/content answering would leave the full trust surface open).
        safe_for_path_lookup = (
            policy_certified
            and state != "unknown"
            and (counts.get("metadata_searchable", 0) > 0 or folder_count > 0)
        )
        if not policy_certified:
            # Uncertified/stale/unavailable policy may serve plaintext-when-now-sensitive or newly-excluded
            # content → fail closed. Serving without verification goes through ``index_only_available``.
            safe_for_content_answering = "none"
        elif content_completeness_state == "complete" and state in ("fresh", "degraded"):
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
                "folder_count": folder_count,
                # A3 canonical structure-root mapping provenance for this file root (never fuzzy).
                "structure_mapping_reason": struct_mapping.reason,
                "structure_key": struct_mapping.structure_key,
                # A root can only be structure-ready when the canonical authority resolved it to a structure
                # key. A config-load/validation failure (structure_key None, reason
                # mapping_configuration_unavailable) can therefore never report structure_ready True.
                "structure_ready": struct_mapping.structure_key is not None,
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
                # Honest policy state (blocker 2): current | stale | uncertified | unavailable. Trust booleans
                # require ``current``; ``index_only_available`` is advisory serving without verification.
                "policy_verification": policy_verification,
                "index_only_available": index_only_available,
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
                **bstate.get_structure_drift(key, conn=conn),
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
    elif any(r["freshness_status"] in ("blocked", "future_anomaly", "unknown") for r in per_root):
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
    last_light = bstate.last_reconciliation(scan_type="lightweight", conn=conn) or {}
    last_full = bstate.last_reconciliation(scan_type="full", conn=conn) or {}
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
        # A3 fail-closed observability: False means the canonical mapping authority (app config) could not be
        # loaded/validated, so every root's structure mapping is reported unavailable and never structure-ready.
        "structure_mapping_config_available": mapping_config_available,
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
