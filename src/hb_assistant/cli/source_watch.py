"""`hb-assistant source-watch` — out-of-band source-index bootstrap, reconciliation, and watcher gating.

Operator/scheduled tooling that BUILDS and keeps the source indexes current over the existing engine.
Nothing here runs in an MCP request path, and none of these commands are exposed to general MCP clients
(bootstrap/rebuild/drain stay operator/CLI-only). Dry-run is the default posture for ``bootstrap``;
``run`` refuses unbootstrapped roots unless explicitly told otherwise, and never launches a persistent
watcher without the explicit ``--start`` flag (production enablement is a separate authorized step).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

import typer

app = typer.Typer(help="Bootstrap, reconcile, and gate the NAS source-index watcher (out-of-band).")


def _emit(payload: dict[str, Any], *, json_out: bool, exit_code: int = 0, jsonl: bool = False) -> None:
    # In --jsonl mode the FINAL record is one-line JSON on stdout (so a consumer can read a clean stream
    # of one-line records); otherwise the final object is pretty-printed JSON (or repr with --no-json).
    if jsonl:
        text = json.dumps(payload, default=str)
    else:
        text = json.dumps(payload, indent=2, default=str) if json_out else str(payload)
    typer.echo(text)
    raise typer.Exit(exit_code)


def _db_path(db: Optional[str]) -> str:
    if db:
        return db
    from hb_assistant.config.path_policy import PathPolicy

    return str(PathPolicy().get_db_path())


def _obsidian_config():
    from hb_assistant.obsidian_mcp.config import load_config

    return load_config()


def _app_config():
    from hb_assistant.config.loader import load_config

    return load_config()


def _watchdog_available() -> bool:
    """Native FS-event backend present? (Absent => the watcher degrades to polling, not an error.)"""
    try:
        import watchdog.observers  # noqa: F401

        return True
    except Exception:
        return False


def _parse_map_json(value: Optional[str]) -> dict[str, str] | None:
    if not value:
        return None
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("structure-root-map-json must be a JSON object")
    return {str(k): str(v) for k, v in parsed.items()}


@app.command("bootstrap")
def bootstrap_cmd(
    root_key: Optional[str] = typer.Option(None, "--root-key", help="Bootstrap a single file-index root."),
    all_roots: bool = typer.Option(False, "--all-roots", help="Bootstrap every enabled root."),
    file_index_only: bool = typer.Option(False, "--file-index-only", help="Skip the structure layer."),
    structure_only: bool = typer.Option(False, "--structure-only", help="Skip the file/content layer."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan only; write nothing (no index, no state)."),
    force: bool = typer.Option(False, "--force", help="Bootstrap even if a layer looks already built."),
    structure_root_map_json: Optional[str] = typer.Option(
        None, "--structure-root-map-json", help='JSON {"file_root_key": "structure_root_key"} map.'),
    max_files_per_pass: Optional[int] = typer.Option(
        None, "--max-files-per-pass",
        help="Bound the file-layer pass to N NEWLY-INDEXED files (not files walked); re-run to resume a "
             "large root. Omit to use the conservative safe default."),
    max_seconds: Optional[float] = typer.Option(
        None, "--max-seconds", help="Bound the file-layer pass to N seconds; re-run to resume. Omit for "
                                    "the safe default."),
    unbounded: bool = typer.Option(
        False, "--unbounded",
        help="UNSAFE: remove BOTH per-pass bounds (no file/time cap). Only for controlled diagnostics on "
             "a small root — never the initial bootstrap of a very large root."),
    restart: bool = typer.Option(
        False, "--restart",
        help="Explicit operator recovery of a root blocked on a no-forward-progress failure (high fanout / "
             "generation ceiling / lost mount). Bypasses the no-auto-retry block for ONE fresh attempt; "
             "ordinary scheduled runs never use it. Prefer fixing the underlying cause (raise the fanout "
             "cap, restore the mount) first — restart re-attempts under the SAME config."),
    jsonl: bool = typer.Option(
        False, "--jsonl",
        help="Stream one-line JSONL progress records on stdout (final record included). Without it, "
             "progress goes to stderr and only the final summary is written to stdout."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Build file/content + structure indexes for one/all roots; record durable readiness. Idempotent.

    Bounded by default: omitting --max-files-per-pass / --max-seconds applies conservative safe defaults
    (never an unbounded content walk by omission). For a very large root, re-run until it reports
    completed (bounded_out=false); unchanged files are mtime+size fast-skipped on resume.
    """
    from hb_assistant.obsidian_mcp import source_bootstrap as sb

    if not all_roots and not root_key:
        _emit({"ok": False, "error": "specify --root-key or --all-roots"},
              json_out=json_out, exit_code=2, jsonl=jsonl)
    if file_index_only and structure_only:
        _emit({"ok": False, "error": "--file-index-only and --structure-only are mutually exclusive"},
              json_out=json_out, exit_code=2, jsonl=jsonl)
    if unbounded and (max_files_per_pass is not None or max_seconds is not None):
        _emit({"ok": False,
               "error": "--unbounded cannot be combined with --max-files-per-pass or --max-seconds"},
              json_out=json_out, exit_code=2, jsonl=jsonl)
    for _name, _val in (("--max-files-per-pass", max_files_per_pass), ("--max-seconds", max_seconds)):
        if _val is not None and _val <= 0:
            _emit({"ok": False, "error": f"{_name} must be a positive value"},
                  json_out=json_out, exit_code=2, jsonl=jsonl)
    try:
        explicit_map = _parse_map_json(structure_root_map_json)
    except (ValueError, json.JSONDecodeError) as exc:
        _emit({"ok": False, "error": str(exc)}, json_out=json_out, exit_code=2, jsonl=jsonl)

    def _emit_progress(payload: dict[str, Any]) -> None:
        # Progress is ALWAYS one-line JSON; --jsonl puts it on stdout, otherwise on stderr so the final
        # stdout object stays a single clean JSON document.
        typer.echo(json.dumps(payload, default=str), err=not jsonl)

    result = sb.bootstrap(
        db_path=_db_path(db),
        obsidian_config=_obsidian_config(),
        app_config=_app_config(),
        root_key=root_key,
        all_roots=all_roots,
        file_only=file_index_only,
        structure_only=structure_only,
        dry_run=dry_run,
        force=force,
        explicit_map=explicit_map,
        max_files_per_pass=max_files_per_pass,
        max_seconds=max_seconds,
        unbounded=unbounded,
        restart=restart,
        emit=None if dry_run else _emit_progress,
    )
    _emit(result, json_out=json_out, exit_code=0 if result.get("ok") else 1, jsonl=jsonl)


@app.command("run")
def run_cmd(
    require_bootstrap: bool = typer.Option(
        True, "--require-bootstrap/--no-require-bootstrap",
        help="Refuse to watch a root that is not watcher-ready (default)."),
    bootstrap_if_needed: bool = typer.Option(
        False, "--bootstrap-if-needed", help="Bootstrap an unready root instead of refusing it."),
    start: bool = typer.Option(
        False, "--start", help="Actually launch the watcher (blocking). Off by default — safe gating."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Gate + (optionally) launch the watcher. Reports a distinct per-root run-state for each root."""
    from hb_assistant.obsidian_mcp import source_bootstrap as sb

    dbp = _db_path(db)
    ocfg = _obsidian_config()
    acfg = _app_config()
    backend = _watchdog_available()

    roots_report: list[dict[str, Any]] = []
    refused = False
    for root in [r for r in getattr(ocfg, "external_sources", []) or [] if r.enabled]:
        fkey = root.source_root_key
        state = sb.resolve_run_state(
            fkey, db_path=dbp, obsidian_config=ocfg, app_config=acfg, backend_available=backend
        )
        if state == sb.RUN_STATE_NOT_BOOTSTRAPPED and bootstrap_if_needed:
            sb.bootstrap(db_path=dbp, obsidian_config=ocfg, app_config=acfg, root_key=fkey)
            state = sb.resolve_run_state(
                fkey, db_path=dbp, obsidian_config=ocfg, app_config=acfg, backend_available=backend
            )
        if state == sb.RUN_STATE_NOT_BOOTSTRAPPED and require_bootstrap:
            refused = True
        roots_report.append({"root_key": fkey, "run_state": state})

    report: dict[str, Any] = {
        "ok": not refused,
        "backend_available": backend,
        "watch_enabled": bool(getattr(ocfg, "external_source_watch_enabled", False)),
        "roots": roots_report,
        "started": False,
    }
    if refused:
        report["error"] = "one or more roots not bootstrapped (use --bootstrap-if-needed or run bootstrap)"
        _emit(report, json_out=json_out, exit_code=2)
    if not start:
        _emit(report, json_out=json_out, exit_code=0)

    # Explicit operator start: launch the real watcher and hold the foreground until interrupted.
    from hb_assistant.obsidian_mcp.source_watch import SourceWatcher

    watcher = SourceWatcher(dbp, ocfg)
    watcher.start()
    report["started"] = True
    typer.echo(json.dumps(report, default=str) if json_out else str(report))
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:  # pragma: no cover — operator Ctrl-C
        watcher.stop()


@app.command("status")
def status_cmd(
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Redacted, path-safe projection of bootstrap readiness + queue + watcher heartbeat state."""
    from hb_assistant.obsidian_mcp import source_bootstrap as sb
    from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
    from hb_assistant.store.source_index_bootstrap_repository import SourceIndexBootstrapRepository

    dbp = _db_path(db)
    ocfg = _obsidian_config()
    acfg = _app_config()
    backend = _watchdog_available()
    repo = SourceIndexRepository(dbp)
    bstate = SourceIndexBootstrapRepository(dbp)

    try:
        queue = repo.queue_health()
    except Exception:
        queue = {}
    owner = None
    try:
        owner = repo.get_watcher_owner(ttl_seconds=900)
    except Exception:
        owner = None
    # Redact absolute host paths from the watcher-owner blob (pid/cwd/db_path/roots_hash) — keep only
    # heartbeat freshness, never a path.
    heartbeat = (owner or {}).get("heartbeat_at") if isinstance(owner, dict) else None

    roots_report = []
    for root in [r for r in getattr(ocfg, "external_sources", []) or [] if r.enabled]:
        fkey = root.source_root_key
        st = bstate.get_bootstrap_state(fkey) or {}
        roots_report.append({
            "root_key": fkey,
            "file_index_bootstrapped": bool(st.get("file_index_bootstrapped")),
            "structure_index_bootstrapped": bool(st.get("structure_index_bootstrapped")),
            "watcher_ready": bool(st.get("watcher_ready")),
            "run_state": sb.resolve_run_state(
                fkey, db_path=dbp, obsidian_config=ocfg, app_config=acfg, backend_available=backend
            ),
            "last_reconciliation": (bstate.last_reconciliation(fkey) or {}).get("finished_at"),
            **bstate.get_structure_drift(fkey),
        })

    _emit({
        "ok": True,
        "backend_available": backend,
        "watcher_heartbeat_at": heartbeat,
        "queue": {
            "queued_count": queue.get("queued_count"),
            "processing_count": queue.get("processing_count"),
            "error_count": queue.get("error_count"),
            "oldest_processing_age_seconds": queue.get("oldest_processing_age_seconds"),
            "last_drain_at": queue.get("last_drain_at"),
        },
        "roots": roots_report,
    }, json_out=json_out)


@app.command("drain")
def drain_cmd(
    max_items: int = typer.Option(500, "--max-items", help="Cap events processed this invocation."),
    max_seconds: int = typer.Option(300, "--max-seconds", help="Wall-clock cap for the drain."),
    batch: int = typer.Option(50, "--batch", help="Events claimed per drain pass."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Drain the existing file-index event queue (bounded). Wraps source_indexer.drain_queue."""
    from hb_assistant.obsidian_mcp.source_indexer import drain_queue

    dbp = _db_path(db)
    ocfg = _obsidian_config()
    from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository

    repo = SourceIndexRepository(dbp)
    deadline = time.monotonic() + max(1, max_seconds)
    processed = 0
    passes = 0
    while processed < max_items and time.monotonic() < deadline:
        n = drain_queue(repo, ocfg, batch=min(batch, max_items - processed))
        passes += 1
        processed += n
        if n == 0:  # queue drained
            break
    _emit({"ok": True, "processed": processed, "passes": passes}, json_out=json_out)


@app.command("reconcile")
def reconcile_cmd(
    root_key: Optional[str] = typer.Option(None, "--root-key", help="Reconcile a single root."),
    all_roots: bool = typer.Option(False, "--all-roots", help="Reconcile every enabled root."),
    scan_type: str = typer.Option("lightweight", "--scan-type", help="lightweight | full."),
    structure_root_map_json: Optional[str] = typer.Option(
        None, "--structure-root-map-json", help='JSON {"file_root_key": "structure_root_key"} map.'),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Safety-net scan: enqueue targeted file work + flag structure drift. Records a reconciliation run."""
    from hb_assistant.obsidian_mcp import source_bootstrap as sb

    if scan_type not in ("lightweight", "full"):
        _emit({"ok": False, "error": "scan-type must be lightweight or full"},
              json_out=json_out, exit_code=2)
    if not all_roots and not root_key:
        _emit({"ok": False, "error": "specify --root-key or --all-roots"},
              json_out=json_out, exit_code=2)
    try:
        explicit_map = _parse_map_json(structure_root_map_json)
    except (ValueError, json.JSONDecodeError) as exc:
        _emit({"ok": False, "error": str(exc)}, json_out=json_out, exit_code=2)

    dbp = _db_path(db)
    ocfg = _obsidian_config()
    acfg = _app_config()
    targets = (
        [r.source_root_key for r in getattr(ocfg, "external_sources", []) or [] if r.enabled]
        if all_roots
        else [root_key]
    )
    results = [
        sb.reconcile_root(
            db_path=dbp, file_key=fkey, obsidian_config=ocfg, app_config=acfg,
            scan_type=scan_type, explicit_map=explicit_map,
        )
        for fkey in targets
    ]
    _emit({"ok": all(r.get("ok") for r in results), "scan_type": scan_type, "results": results},
          json_out=json_out)


@app.command("vault-reconcile")
def vault_reconcile_cmd(
    allow_confirmed_empty: bool = typer.Option(
        False, "--allow-confirmed-empty",
        help="One-shot override for the empty-root blast-radius guard (still requires a certified scan)."),
    confirm: bool = typer.Option(
        False, "--confirm", help="Explicit operator confirmation (required to mutate index state)."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Operator-only, LOCAL recovery for a vault that legitimately emptied.

    A normal vault scan fail-closes its deletion reconciliation whenever a certified-complete scan
    observes zero eligible notes while the index still holds active rows (the empty-root blast-radius
    guard) — so an established vault that scans empty stays protected indefinitely. This command is the
    only escape: it acquires a LOCAL operation lease, performs its OWN fresh certified-complete vault
    scan (never trusting a caller-supplied scan result), and only then reconciles confirmed-gone rows,
    writing a redacted audit receipt. It mutates index state only (never a source file) and is not
    exposed to any remote MCP client.
    """
    import os
    import uuid

    if not allow_confirmed_empty or not confirm:
        _emit(
            {"ok": False, "error": "vault-reconcile requires BOTH --allow-confirmed-empty and --confirm "
                                   "(operator-only, mutates index state)."},
            json_out=json_out, exit_code=2)

    from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
    from hb_assistant.obsidian_mcp.source_indexer import scan_vault_notes

    dbp = _db_path(db)
    ocfg = _obsidian_config()
    op_dir = Path(dbp).parent
    op_dir.mkdir(parents=True, exist_ok=True)

    # Local operation ownership: a non-blocking advisory lock so two recovery runs cannot race. No durable
    # DB/generation/cursor state is introduced for the vault (A1 constraint) — the lease is process-local.
    lock_path = op_dir / "vault_reconcile.lock"
    lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            import fcntl

            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            # Lease held by another process (OS-backed flock). Fail closed; the finally clause closes the fd.
            _emit(
                {"ok": False, "error": "another vault-reconcile operation holds the local lease"},
                json_out=json_out, exit_code=2)

        repo = SourceIndexRepository(dbp)
        # Perform our OWN fresh, certified-complete scan; the override only lifts the empty-root guard.
        report = scan_vault_notes(repo, ocfg, allow_confirmed_empty_recovery=True)
        reconciled = report.completeness == "complete"
        receipt = {
            "receipt_id": uuid.uuid4().hex,
            "operation": "vault_reconcile_confirmed_empty",
            "completeness": report.completeness,
            "deletion_reconciliation_allowed": report.deletion_reconciliation_allowed,
            "eligible_files_seen": report.eligible_files_seen,
            "active_rows_before_scan": report.active_rows_before_scan,
            "deleted": report.deleted,
            "walk_error_count": report.walk_error_count,
            "per_file_error_count": report.per_file_error_count,
            "truncated": report.truncated,
            "interrupted": report.interrupted,
            "error_codes": sorted(set(report.error_codes)),
        }
        receipts_dir = op_dir / "vault_reconcile_receipts"
        receipts_dir.mkdir(parents=True, exist_ok=True)
        receipt_path = receipts_dir / f"vault-reconcile-{receipt['receipt_id']}.json"
        receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    finally:
        os.close(lock_fd)

    payload = {"ok": reconciled, "reconciled": reconciled,
               "receipt_path": str(receipt_path), "receipt": receipt}
    if not reconciled:
        payload["note"] = ("no deletion performed — the fresh scan was not certified-complete "
                           f"(completeness={report.completeness})")
    _emit(payload, json_out=json_out)


@app.command("prune-generations")
def prune_generations_cmd(
    root_key: Optional[str] = typer.Option(None, "--root-key", help="Prune a single root."),
    all_roots: bool = typer.Option(False, "--all-roots", help="Prune every root with generations."),
    keep: Optional[int] = typer.Option(
        None, "--keep", help="Keep at most N most-recent generations per root (default: config)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Report counts without deleting."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Bounded generation retention: prune old scan-generation rows, keeping the N most recent per root.

    FAIL-CLOSED — never removes the active generation or the latest COMPLETED generation (health/watcher
    trust them). Wire this into the scheduler to keep source_index_scan_generations bounded over time."""
    from hb_assistant.store.source_index_scan_generations_repository import (
        SourceIndexScanGenerationsRepository,
    )

    if not all_roots and not root_key:
        _emit({"ok": False, "error": "specify --root-key or --all-roots"},
              json_out=json_out, exit_code=2)
    dbp = _db_path(db)
    ocfg = _obsidian_config()
    keep_n = keep if keep is not None else int(
        getattr(ocfg, "source_index_generation_retention_count", 20)
    )
    repo = SourceIndexScanGenerationsRepository(dbp)
    result = repo.prune_generations(
        None if all_roots else root_key, keep=keep_n, dry_run=dry_run
    )
    _emit({"ok": True, **result}, json_out=json_out)


@app.command("quarantine-list")
def quarantine_list_cmd(
    root_key: Optional[str] = typer.Option(None, "--root-key", help="Filter to one root."),
    state: str = typer.Option(
        "unresolved", "--state", help="unresolved | resolved | confirmed_absent | all."),
    limit: int = typer.Option(100, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """READ-ONLY: list poison-file quarantine records (rel_path only; no absolute paths). Not a mutation."""
    from hb_assistant.obsidian_mcp.source_quarantine_ops import list_quarantine

    _emit(
        list_quarantine(
            _db_path(db), root_key=root_key,
            resolution_state=None if state == "all" else state, limit=limit,
        ),
        json_out=json_out,
    )


@app.command("quarantine-inspect")
def quarantine_inspect_cmd(
    quarantine_id: str = typer.Argument(..., help="The quarantine_id to inspect."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """READ-ONLY: show one quarantine record's sanitized detail. Not a mutation."""
    from hb_assistant.obsidian_mcp.source_quarantine_ops import inspect_quarantine

    res = inspect_quarantine(_db_path(db), quarantine_id)
    _emit(res, json_out=json_out, exit_code=0 if res.get("ok") else 2)


@app.command("quarantine-retry")
def quarantine_retry_cmd(
    root_key: str = typer.Option(..., "--root-key", help="Root whose quarantine(s) to retry."),
    quarantine_id: Optional[str] = typer.Option(
        None, "--quarantine-id", help="Retry ONE record; omit to retry a bounded batch for the root."),
    max_items: int = typer.Option(
        1, "--max-items", help="Bounded cap on records retried this invocation (batch mode)."),
    confirm: bool = typer.Option(
        False, "--confirm", help="Explicit operator confirmation (required — this mutates index state)."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Operator-only, LOCAL bounded retry of poison-file quarantine(s).

    Re-observes each targeted path and resolves it ONLY on a trustworthy observation (readable → resolved;
    trustworthily absent → confirmed_absent); otherwise the unresolved quarantine is RETAINED. Never writes a
    source file, has no remote MCP surface, and offers NO blanket "ignore"/waiver. Resolving the last
    quarantine does not itself complete a generation — a fresh scan must verify + reconcile first."""
    if not confirm:
        _emit(
            {"ok": False, "error": "quarantine-retry requires --confirm (operator-only, mutates index state)."},
            json_out=json_out, exit_code=2,
        )
    from hb_assistant.obsidian_mcp.source_quarantine_ops import retry_quarantine

    res = retry_quarantine(
        _db_path(db), _obsidian_config(), root_key=root_key,
        quarantine_id=quarantine_id, max_items=max(1, int(max_items)),
    )
    _emit(res, json_out=json_out, exit_code=0 if res.get("ok") else 2)
