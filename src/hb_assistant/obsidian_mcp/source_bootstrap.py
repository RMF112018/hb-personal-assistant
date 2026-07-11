"""Source-index bootstrap orchestration + reconciliation (out-of-band; never a request path).

Coordinates the two index layers over the EXISTING engines — it adds no parallel queue or scanner:

* file/content layer  -> ``source_indexer.scan_source_root`` (walk + index + delete-reconcile)
* folder/structure    -> ``source_structure`` service/repository IN-PROCESS (scan -> classify ->
                          persist), never a shelled-out CLI subprocess.

It records durable per-root readiness in ``source_index_bootstrap_state`` and marks a root
``watcher_ready`` only when the required baseline layers are present, so the watcher never silently
treats an empty index as "nothing there". Reconciliation is a bounded safety-net that enqueues targeted
work on the existing ``source_intelligence_events`` queue (reusing its ``reindex_requested`` / ``deleted``
vocabulary) and *flags* — never rebuilds — directory-architecture drift.

Root-key spaces are explicit: file roots are keyed by ``ExternalSourceRoot.source_root_key``; structure
roots are keyed in ``AppConfig.source_structure.scan_roots``. They are resolved by exact match or an
explicit operator map — never by fuzzy substring. ``root_key`` stored anywhere here is the file-index
key; no absolute host path is ever persisted to bootstrap state.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.store.source_index_bootstrap_repository import SourceIndexBootstrapRepository

from .config import ObsidianMcpConfig
from .config import load_config as load_obsidian_config
from .source_index_repository import SourceIndexRepository

# Watcher run-state enum (amendment 5) — reported by CLI run/status and projected into health.
RUN_STATE_DISABLED = "disabled_by_config"
RUN_STATE_NOT_BOOTSTRAPPED = "not_bootstrapped"
RUN_STATE_BACKEND_UNAVAILABLE = "backend_unavailable"
RUN_STATE_RUNNING = "running"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ----- root-key mapping (amendment 2) --------------------------------------------------------
def resolve_structure_key(
    file_key: str, scan_roots: dict[str, str], explicit_map: dict[str, str] | None = None
) -> str | None:
    """Resolve a file-index root_key to its structure ``scan_roots`` key, deterministically.

    Order: explicit operator map -> exact key match -> None (structure not configured for this root).
    No fuzzy/substring matching — an unmapped root is honestly reported, not silently paired.
    """
    if explicit_map and file_key in explicit_map:
        mapped = explicit_map[file_key]
        return mapped if mapped in scan_roots else None
    if file_key in scan_roots:
        return file_key
    return None


def map_roots(
    external_sources: list[Any],
    scan_roots: dict[str, str],
    explicit_map: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Explicit file-root -> structure-root mapping for every enabled external source."""
    mappings: list[dict[str, Any]] = []
    for root in external_sources:
        if not getattr(root, "enabled", True):
            continue
        skey = resolve_structure_key(root.source_root_key, scan_roots, explicit_map)
        mappings.append(
            {
                "file_key": root.source_root_key,
                "path": root.path,
                "sensitive": bool(getattr(root, "sensitive", False)),
                "structure_key": skey,
                "structure_configured": skey is not None,
            }
        )
    return mappings


# ----- file/content layer ---------------------------------------------------------------------
def _file_plan_counts(root: Any, config: ObsidianMcpConfig) -> dict[str, Any]:
    """Dry-run: bounded stat-only streaming walk reusing the indexer's skip predicates. No writes.

    Shares ``walk_source_tree`` with the apply path so the dry-run count matches what apply would
    scan, and it prunes excluded/hidden dir subtrees during traversal (so a huge low-value root does
    not hang the dry-run the way ``sorted(rglob("*"))`` did).
    """
    from .source_indexer import effective_max_files, walk_source_tree

    root_path = Path(root.path)
    if not root_path.is_dir():
        return {"root_found": False, "files_seen": 0, "would_index": 0}
    max_files = effective_max_files(root, config)
    seen = 0
    truncated = False
    for _kind, _abs_path, _rel_path in walk_source_tree(root_path, config):
        seen += 1
        if seen > max_files:
            truncated = True
            seen = max_files
            break
    return {"root_found": True, "files_seen": seen, "would_index": seen, "truncated": truncated}


def _bootstrap_file_layer(
    root: Any,
    repo: SourceIndexRepository,
    config: ObsidianMcpConfig,
    bstate: Any,
    *,
    max_files_per_pass: int | None = None,
    max_seconds: float | None = None,
    unbounded: bool = False,
    restart: bool = False,
    emit: Any = None,
) -> dict[str, Any]:
    """Apply one bounded, resumable, OBSERVED pass over a root via the common run_scan wrapper.

    Bounds are resolved inside run_scan from config defaults (never unbounded by omission — only an
    explicit ``unbounded`` removes them). ``success`` means the pass fully COMPLETED (walk exhausted +
    delete-reconcile ran) — only then is the file layer bootstrapped. ``bounded_out`` (a per-pass budget
    stopped early) is PARTIAL progress that needs a resume, not a failure. ``conflict`` means another live
    run holds the root (surfaced as an error for the interactive bootstrap path). ``restart`` forwards an
    explicit operator recovery that bypasses the no-forward-progress block for one attempt.
    """
    from .source_scan_runner import run_scan

    run = run_scan(
        root, repo, config, bstate, mode="bootstrap",
        max_files_per_pass=max_files_per_pass, max_seconds=max_seconds,
        unbounded=unbounded, restart=restart, emit=emit,
    )
    result: dict[str, Any] = run.report.as_dict() if run.report is not None else {
        "root_key": root.source_root_key
    }
    result["error_codes"] = list(run.report.error_codes) if run.report is not None else []
    result["run_id"] = run.run_id
    result["run_status"] = run.status
    result["conflict"] = run.conflict
    result["found"] = run.report is not None and "root_not_found" not in run.report.error_codes
    result["success"] = run.status == "completed"
    result["bounded_out"] = run.status == "partial"
    return result


# ----- folder/structure layer (in-process; amendment 3) --------------------------------------
def _structure_bootstrapped(srepo: Any, structure_key: str) -> bool:
    for r in srepo.list_roots(limit=500):
        if r.get("root_key") == structure_key and int(r.get("folder_count") or 0) >= 0:
            # A persisted root row (even with zero folders) means the structure layer ran for it.
            return True
    return False


def _structure_root_row(srepo: Any, structure_key: str) -> dict[str, Any] | None:
    for r in srepo.list_roots(limit=500):
        if r.get("root_key") == structure_key:
            return r
    return None


def _indexed_structure_folders(db_path: str, structure_key: str, *, cap: int = 50000) -> set[str]:
    """All root-relative folder rel_paths the structure index currently holds for a root (read-only)."""
    from hb_assistant.store.connection import borrow_connection

    with borrow_connection(None, db_path) as c:
        rows = c.execute(
            "SELECT rel_path FROM source_structure_folders WHERE root_key=? LIMIT ?",
            (structure_key, int(cap)),
        ).fetchall()
    return {r[0] for r in rows}


def _current_structure_folders(structure_key: str, path: str, app_config: Any) -> set[str]:
    """Folder rel_paths a fresh bounded structure scan would produce (SAME pruning as the index)."""
    from .source_structure_classifier import classify_tree
    from .source_structure_scanner import ScanCaps, scan_roots

    scfg = app_config.source_structure
    caps = ScanCaps(
        max_files_per_root=scfg.scan.max_files_per_root,
        max_folders_per_root=scfg.scan.max_folders_per_root,
        max_depth=scfg.scan.max_depth,
        timeout_seconds=scfg.scan.timeout_seconds,
        high_fanout_threshold=scfg.scan.high_fanout_threshold,
    )
    tree = scan_roots({structure_key: path}, caps)
    _roots, records = classify_tree(tree)
    return {r.rel_path for r in records if r.root_key == structure_key}


def _bootstrap_structure_layer(
    structure_key: str, path: str, db_path: str, app_config: Any, *, apply: bool
) -> dict[str, Any]:
    """Scan -> classify -> (persist) one structure root in-process. Dry-run stops before persist."""
    from .source_structure_classifier import classify_tree
    from .source_structure_ingest import (
        generate_deterministic_summaries,
        generate_routing_hints,
        persist_records,
    )
    from .source_structure_repository import SourceStructureRepository
    from .source_structure_scanner import ScanCaps, ScanError, scan_roots

    scfg = app_config.source_structure
    caps = ScanCaps(
        max_files_per_root=scfg.scan.max_files_per_root,
        max_folders_per_root=scfg.scan.max_folders_per_root,
        max_depth=scfg.scan.max_depth,
        timeout_seconds=scfg.scan.timeout_seconds,
        high_fanout_threshold=scfg.scan.high_fanout_threshold,
    )
    try:
        tree = scan_roots({structure_key: path}, caps)
    except ScanError as exc:
        return {"success": False, "error": str(exc), "applied": False}
    roots_map, records = classify_tree(tree)
    out: dict[str, Any] = {"parsed_totals": tree.totals, "applied": False, "success": True}
    if not apply:
        return out
    srepo = SourceStructureRepository(db_path)
    run_id = uuid.uuid4().hex
    srepo.start_run(run_id, "scan_roots", roots=[structure_key])
    try:
        out["counts"] = persist_records(srepo, roots_map, records)
        generate_deterministic_summaries(srepo)
        generate_routing_hints(srepo)
        srepo.finish_run(run_id, "completed", counts=out.get("counts"))
        out["applied"] = True
        out["success"] = _structure_bootstrapped(srepo, structure_key)
    except Exception as exc:  # noqa: BLE001 — mark run failed; previous good rows are untouched
        srepo.finish_run(run_id, "failed", error_text=str(exc))
        out["success"] = False
        out["error"] = str(exc)
    return out


# ----- readiness ------------------------------------------------------------------------------
def compute_watcher_ready(file_ok: bool, structure_ok: bool) -> bool:
    """Conservative: a root is watcher-ready only when BOTH baseline layers are bootstrapped."""
    return bool(file_ok and structure_ok)


# ----- bootstrap entry point ------------------------------------------------------------------
def bootstrap(
    *,
    db_path: str,
    obsidian_config: ObsidianMcpConfig | None = None,
    app_config: Any = None,
    root_key: str | None = None,
    all_roots: bool = False,
    file_only: bool = False,
    structure_only: bool = False,
    dry_run: bool = False,
    force: bool = False,
    explicit_map: dict[str, str] | None = None,
    max_files_per_pass: int | None = None,
    max_seconds: float | None = None,
    unbounded: bool = False,
    restart: bool = False,
    emit: Any = None,
) -> dict[str, Any]:
    """Bootstrap one/all roots across both layers; record durable readiness. Idempotent + fail-closed.

    ``file_only`` / ``structure_only`` request a partial bootstrap (each preserves the other layer's
    recorded state). ``dry_run`` writes nothing (no index rows, no bootstrap_state) and returns a plan.
    ``max_files_per_pass`` / ``max_seconds`` bound the file-layer pass so a very large root indexes across
    repeated resumable invocations; a bounded (incomplete) pass reports ``bounded_out`` and leaves the
    root not-yet-bootstrapped without failing. ``restart`` is an explicit operator recovery that bypasses the
    no-forward-progress block (fanout / generation-ceiling / lost-mount) for one attempt on the file layer.
    """
    if obsidian_config is None:
        obsidian_config = load_obsidian_config()
    if app_config is None:
        from hb_assistant.config.loader import load_config as load_app_config

        app_config = load_app_config()

    repo = SourceIndexRepository(db_path)
    bstate = SourceIndexBootstrapRepository(db_path)
    scan_roots_cfg = dict(getattr(app_config.source_structure, "scan_roots", {}) or {})
    mappings = map_roots(obsidian_config.external_sources, scan_roots_cfg, explicit_map)

    if not all_roots and root_key is not None:
        mappings = [m for m in mappings if m["file_key"] == root_key]
    do_file = not structure_only
    do_structure = not file_only

    roots_out: list[dict[str, Any]] = []
    any_fail = False
    for m in mappings:
        fkey = m["file_key"]
        root_obj = next(
            r for r in obsidian_config.external_sources if r.source_root_key == fkey
        )
        entry: dict[str, Any] = {
            "root_key": fkey,
            "structure_key": m["structure_key"],
            "structure_configured": m["structure_configured"],
            "dry_run": dry_run,
        }

        # --- file layer ---
        file_ok: bool | None = None
        if do_file:
            if dry_run:
                entry["file_index"] = _file_plan_counts(root_obj, obsidian_config)
            else:
                res = _bootstrap_file_layer(
                    root_obj, repo, obsidian_config, bstate,
                    max_files_per_pass=max_files_per_pass, max_seconds=max_seconds,
                    unbounded=unbounded, restart=restart, emit=emit,
                )
                entry["file_index"] = res
                file_ok = bool(res["success"])  # bootstrapped only on a completed pass
                # A bounded partial pass is progress, not a failure — a missing root OR a live-run
                # conflict fails (the interactive bootstrap surfaces the conflict as an error).
                any_fail = any_fail or (
                    not bool(res.get("found", True)) and not bool(res.get("bounded_out"))
                )

        # --- structure layer ---
        structure_ok: bool | None = None
        if do_structure:
            if not m["structure_configured"]:
                entry["structure_index"] = {"status": "not_configured", "success": False}
                structure_ok = False
            else:
                res = _bootstrap_structure_layer(
                    m["structure_key"], m["path"], db_path, app_config, apply=not dry_run
                )
                entry["structure_index"] = res
                if not dry_run:
                    structure_ok = bool(res.get("success"))
                    any_fail = any_fail or not structure_ok

        # --- record durable state (apply only) ---
        if not dry_run:
            fields: dict[str, Any] = {}
            prior = bstate.get_bootstrap_state(fkey) or {}
            if do_file:
                # First-class ``partial``: a bounded-out pass is resumable progress, distinct from a
                # genuine ``failed`` (missing root / systemic error) and from a live-run ``conflict``.
                # Only a completed pass sets file_index_bootstrapped=1, so watcher run-state (which keys
                # off that flag, NOT this string) correctly stays not_bootstrapped until the layer is
                # complete.
                if file_ok:
                    file_status = "bootstrapped"
                elif res.get("conflict"):
                    file_status = "conflict"
                elif res.get("bounded_out"):
                    file_status = "partial"
                else:
                    file_status = "failed"
                fields.update(
                    file_index_bootstrapped=1 if file_ok else 0,
                    file_index_last_bootstrap_at=_now(),
                    file_index_status=file_status,
                )
                if file_ok:
                    fields["file_index_last_success_at"] = _now()
            if do_structure:
                fields.update(
                    structure_index_bootstrapped=1 if structure_ok else 0,
                    structure_index_last_bootstrap_at=_now(),
                    structure_index_status=(
                        "not_configured"
                        if not m["structure_configured"]
                        else ("bootstrapped" if structure_ok else "failed")
                    ),
                )
                if structure_ok:
                    fields["structure_index_last_success_at"] = _now()
            # Effective readiness reads current+updated layer truth (partial runs keep the other side).
            eff_file = file_ok if do_file else bool(prior.get("file_index_bootstrapped"))
            eff_struct = structure_ok if do_structure else bool(
                prior.get("structure_index_bootstrapped")
            )
            ready = compute_watcher_ready(bool(eff_file), bool(eff_struct))
            fields["watcher_ready"] = 1 if ready else 0
            fields["last_health_check_at"] = _now()
            bstate.upsert_bootstrap_state(fkey, **fields)
            entry["watcher_ready"] = ready

        roots_out.append(entry)

    return {
        "ok": not (any_fail and not (file_only or structure_only) and not dry_run),
        "dry_run": dry_run,
        "mode": "dry_run" if dry_run else ("partial" if (file_only or structure_only) else "full"),
        "roots": roots_out,
        "root_count": len(roots_out),
    }


# ----- reconciliation -------------------------------------------------------------------------
def reconcile_root(
    *,
    db_path: str,
    file_key: str,
    obsidian_config: ObsidianMcpConfig | None = None,
    app_config: Any = None,
    scan_type: str = "lightweight",
    explicit_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Safety-net scan of one root: enqueue targeted file work + flag structure drift. Records a run."""
    if obsidian_config is None:
        obsidian_config = load_obsidian_config()
    if app_config is None:
        from hb_assistant.config.loader import load_config as load_app_config

        app_config = load_app_config()

    from .source_indexer import effective_max_files, walk_source_tree

    repo = SourceIndexRepository(db_path)
    bstate = SourceIndexBootstrapRepository(db_path)
    root_obj = next(
        (r for r in obsidian_config.external_sources if r.source_root_key == file_key), None
    )
    run_id = uuid.uuid4().hex
    bstate.start_reconciliation_run(run_id, file_key, scan_type)
    files_seen = folders_seen = changes = enqueued = errors = 0
    last_error: str | None = None
    reconcile_status = "completed"
    try:
        if root_obj is None:
            raise ValueError("unconfigured_root")
        root_path = Path(root_obj.path)
        if not root_path.is_dir():
            raise ValueError("root_not_found")

        if scan_type == "full":
            # Full reconcile now runs through the common bounded/observed wrapper. Its V118 run row is the
            # authoritative lifecycle record (it can hold ``partial``); the legacy receipt CHECK has no
            # 'partial', so a bounded pass is recorded fail-closed ('failed' + resume note) rather than a
            # coverage-overstating 'completed'.
            from .source_scan_runner import run_scan

            run = run_scan(root_obj, repo, obsidian_config, bstate, mode="reconcile")
            if run.conflict:
                # A live run already holds this root: reconcile is RETRYABLE (deferred to the next
                # cycle), never discarded and never a hard failure.
                bstate.finish_reconciliation_run(
                    run_id, status="failed", last_error="deferred_active_run_conflict"
                )
                return {"ok": True, "run_id": run_id, "root_key": file_key, "scan_type": scan_type,
                        "deferred": True, "reason": "active_run_conflict"}
            report = run.report
            files_seen = report.scanned if report is not None else 0
            changes = (report.indexed + report.deleted) if report is not None else 0
            if run.status == "partial":
                reconcile_status = "failed"
                last_error = "bounded_out_partial_resume_pending"
            elif run.status == "failed":
                reconcile_status = "failed"
                last_error = run.error_code
        else:  # lightweight: stat-compare + enqueue, don't index inline
            max_files = effective_max_files(root_obj, obsidian_config)
            seen_rel: set[str] = set()
            live_dirs: set[str] = set()
            walk_complete = True  # False if we truncate at max_files (an INCOMPLETE walk)
            # Streaming walk (dirs + files): skip predicates + dir-subtree pruning happen inside
            # walk_source_tree, so a huge low-value root does not front-load a full sorted tree.
            for kind, abs_path, rel_path in walk_source_tree(
                root_path, obsidian_config, want_dirs=True
            ):
                if kind == "dir":
                    live_dirs.add(rel_path)
                    continue
                files_seen += 1
                if files_seen > max_files:
                    files_seen = max_files
                    walk_complete = False
                    break
                seen_rel.add(rel_path)
                existing = repo.lookup_by_path(
                    "external_file", rel_path, source_root_key=file_key
                )
                try:
                    st = abs_path.stat()
                except OSError:
                    continue
                # Fast gate: mtime OR size mismatch (or missing/deleted row) => enqueue a targeted
                # refresh. Comparing size as well as mtime catches same-mtime content edits. Content-sha
                # confirmation happens when the drainer re-indexes, so this stays a bounded stat-only walk.
                changed = (
                    existing is None
                    or existing.get("deleted")
                    or existing.get("mtime_ns") != st.st_mtime_ns
                    or existing.get("size_bytes") != st.st_size
                )
                if changed:
                    repo.enqueue_event(
                        event_type="reindex_requested", rel_path=rel_path, source_root_key=file_key
                    )
                    changes += 1
                    enqueued += 1
            # deletions: active indexed files no longer on disk. ONLY enqueue after a COMPLETE walk — on a
            # truncated (bounded) walk, an unseen path is "not reached", NOT gone (false-deletion guard).
            if walk_complete:
                for gone in repo.active_rel_paths(file_key) - seen_rel:
                    repo.enqueue_event(
                        event_type="deleted", rel_path=gone, source_root_key=file_key
                    )
                    changes += 1
                    enqueued += 1
            folders_seen = len(live_dirs)

        # --- structure drift signal (flag only; dirty-bridge deferred) ---
        # Compare the indexed folder set to a fresh bounded structure scan of the same root. Both sides
        # use the identical scanner pruning, so the symmetric difference is real added/removed
        # architecture — not a noise/count artifact. Only meaningful once structure is bootstrapped.
        skey = resolve_structure_key(
            file_key, dict(getattr(app_config.source_structure, "scan_roots", {}) or {}), explicit_map
        )
        drift = False
        if skey is not None:
            indexed = _indexed_structure_folders(db_path, skey)
            if indexed:
                try:
                    current = _current_structure_folders(skey, str(root_path), app_config)
                    drift = bool(indexed.symmetric_difference(current))
                except Exception:  # noqa: BLE001 — drift detection is advisory; never fail reconcile
                    drift = False
            bstate.set_structure_drift(file_key, detected=drift, refresh_recommended=drift)
        bstate.finish_reconciliation_run(
            run_id,
            status=reconcile_status,
            files_seen=files_seen,
            folders_seen=folders_seen,
            changes_detected=changes,
            events_enqueued=enqueued,
            errors_count=errors,
            last_error=last_error,
        )
        return {
            "ok": reconcile_status == "completed",
            "run_id": run_id,
            "root_key": file_key,
            "scan_type": scan_type,
            "bounded_out": reconcile_status != "completed" and last_error == "bounded_out_partial_resume_pending",
            "files_seen": files_seen,
            "folders_seen": folders_seen,
            "changes_detected": changes,
            "events_enqueued": enqueued,
            "directory_change_detected": drift,
            "structure_refresh_recommended": drift,
        }
    except Exception as exc:  # noqa: BLE001 — record the failed run, surface the error
        errors = 1
        last_error = str(exc)
        bstate.finish_reconciliation_run(
            run_id, status="failed", files_seen=files_seen, folders_seen=folders_seen,
            changes_detected=changes, events_enqueued=enqueued, errors_count=errors,
            last_error=last_error,
        )
        return {"ok": False, "run_id": run_id, "root_key": file_key, "error": last_error}


# ----- watcher run-state resolution (amendment 5) --------------------------------------------
def resolve_run_state(
    file_key: str, *, db_path: str, obsidian_config: ObsidianMcpConfig, backend_available: bool
) -> str:
    """Deterministic per-root run state for `source-watch run`/`status` and the health projection."""
    if not bool(getattr(obsidian_config, "external_source_watch_enabled", False)):
        return RUN_STATE_DISABLED
    state = SourceIndexBootstrapRepository(db_path).get_bootstrap_state(file_key) or {}
    if not state.get("watcher_ready"):
        return RUN_STATE_NOT_BOOTSTRAPPED
    if not backend_available:
        return RUN_STATE_BACKEND_UNAVAILABLE
    return RUN_STATE_RUNNING
