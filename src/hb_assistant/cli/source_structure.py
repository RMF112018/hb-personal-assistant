"""`hb-assistant source-structure` — out-of-band NAS source-structure layered index (V115).

Operator/scheduled tooling that BUILDS the layered index (root/folder/project classification,
summaries, routing hints, quality findings) from a printed folder-tree artifact or a bounded live
metadata scan. Nothing here runs in an MCP request path. Preview is the default for mutating
commands; ``--apply`` is the sole write signal. Live scanning refuses unconfigured roots.
"""

from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

import typer

app = typer.Typer(help="Build the NAS source-structure layered index (out-of-band, read surfaces elsewhere).")


@contextmanager
def _temp_env(name: str, value: str) -> Iterator[None]:
    """Set ``os.environ[name]`` for the block, restoring the prior state (incl. absence) on both
    normal exit and exception. Used to snapshot the gate ON/OFF exposure audit without leaking a
    mutated environment into the rest of the process."""
    sentinel = object()
    prior: Any = os.environ.get(name, sentinel)
    os.environ[name] = value
    try:
        yield
    finally:
        if prior is sentinel:
            os.environ.pop(name, None)
        else:
            os.environ[name] = prior


def _emit(payload: dict[str, Any], *, json_out: bool, exit_code: int = 0) -> None:
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(exit_code)


def _db_path(db: Optional[str]) -> str:
    if db:
        return db
    from hb_assistant.config.path_policy import PathPolicy

    return str(PathPolicy().get_db_path())


def _repo(db: Optional[str]):
    from hb_assistant.obsidian_mcp.source_structure_repository import SourceStructureRepository

    return SourceStructureRepository(_db_path(db))


def _app_config():
    from hb_assistant.config.loader import load_config

    return load_config()


@app.command("ingest-tree")
def ingest_tree(
    input: str = typer.Option(..., "--input", help="Path to a printed folder-tree artifact."),
    root_key_map_json: Optional[str] = typer.Option(
        None, "--root-key-map-json", help='JSON {"header substring": "root_key"} overrides.'),
    max_nodes: Optional[int] = typer.Option(None, "--max-nodes", help="Cap parsed lines."),
    apply: bool = typer.Option(False, "--apply", help="Persist rows (default: dry-run preview)."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Parse + classify a printed folder tree; preview (dry-run) or persist (--apply)."""
    from hb_assistant.obsidian_mcp.source_structure_ingest import (
        generate_deterministic_summaries,
        generate_routing_hints,
        ingest_tree_text,
    )

    text = Path(input).read_text(encoding="utf-8", errors="replace")
    rk_map = None
    if root_key_map_json:
        rk_map = json.loads(root_key_map_json)
    else:
        cfg = _app_config()
        rk_map = cfg.source_structure.root_key_map or None

    repo = _repo(db)
    do_apply = apply  # --apply is the explicit write signal; --dry-run is the informational default
    run_id = uuid.uuid4().hex
    if do_apply:
        repo.start_run(run_id, "ingest_tree", roots=None, options={"input": input})
    try:
        result = ingest_tree_text(repo, text, root_key_map=rk_map, max_nodes=max_nodes,
                                  apply=do_apply)
        if do_apply:
            result["summaries"] = generate_deterministic_summaries(repo)
            result["hints"] = generate_routing_hints(repo)
            repo.finish_run(run_id, "completed", counts=result.get("counts"))
    except Exception as exc:  # noqa: BLE001 — surface failure, mark the run failed
        if do_apply:
            repo.finish_run(run_id, "failed", error_text=str(exc))
        _emit({"ok": False, "error": str(exc)}, json_out=json_out, exit_code=1)
    _emit({"ok": True, **result}, json_out=json_out)


@app.command("scan-roots")
def scan_roots_cmd(
    roots: Optional[str] = typer.Option(
        None, "--roots", help="Comma-separated configured root keys (default: all configured)."),
    apply: bool = typer.Option(False, "--apply"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Bounded live metadata scan of configured local roots (operator-only; refuses unconfigured)."""
    from hb_assistant.obsidian_mcp.source_structure_classifier import classify_tree
    from hb_assistant.obsidian_mcp.source_structure_ingest import (
        generate_deterministic_summaries,
        generate_routing_hints,
        persist_records,
    )
    from hb_assistant.obsidian_mcp.source_structure_scanner import ScanCaps, ScanError, scan_roots

    cfg = _app_config().source_structure
    configured = dict(cfg.scan_roots or {})
    if not configured:
        _emit({"ok": False, "error": "no scan roots configured (source_structure.scan_roots)"},
              json_out=json_out, exit_code=2)
    if roots:
        wanted = [r.strip() for r in roots.split(",") if r.strip()]
        unknown = [r for r in wanted if r not in configured]
        if unknown:
            _emit({"ok": False, "error": f"unconfigured roots refused: {unknown}"},
                  json_out=json_out, exit_code=2)
        scan_map = {k: configured[k] for k in wanted}
    else:
        scan_map = configured

    caps = ScanCaps(
        max_files_per_root=cfg.scan.max_files_per_root,
        max_folders_per_root=cfg.scan.max_folders_per_root,
        max_depth=cfg.scan.max_depth,
        timeout_seconds=cfg.scan.timeout_seconds,
        high_fanout_threshold=cfg.scan.high_fanout_threshold,
    )
    repo = _repo(db)
    do_apply = apply  # --apply is the explicit write signal; --dry-run is the informational default
    run_id = uuid.uuid4().hex
    try:
        tree = scan_roots(scan_map, caps)
    except ScanError as exc:
        _emit({"ok": False, "error": str(exc)}, json_out=json_out, exit_code=1)
    roots_map, records = classify_tree(tree)
    payload: dict[str, Any] = {"parsed_totals": tree.totals, "applied": False,
                               "root_keys": list(scan_map.keys())}
    if do_apply:
        repo.start_run(run_id, "scan_roots", roots=list(scan_map.keys()))
        payload["counts"] = persist_records(repo, roots_map, records)
        payload["summaries"] = generate_deterministic_summaries(repo)
        payload["hints"] = generate_routing_hints(repo)
        payload["applied"] = True
        repo.finish_run(run_id, "completed", counts=payload["counts"])
    _emit({"ok": True, **payload}, json_out=json_out)


@app.command("classify")
def classify_cmd(
    apply: bool = typer.Option(False, "--apply", help="Regenerate summaries + routing hints."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Regenerate deterministic summaries + routing hints from persisted folders (no re-scan)."""
    from hb_assistant.obsidian_mcp.source_structure_ingest import (
        generate_deterministic_summaries,
        generate_routing_hints,
    )

    repo = _repo(db)
    if not apply:
        _emit({"ok": True, "applied": False,
               "note": "pass --apply to regenerate summaries + routing hints"}, json_out=json_out)
    summaries = generate_deterministic_summaries(repo)
    hints = generate_routing_hints(repo)
    _emit({"ok": True, "applied": True, "summaries": summaries, "hints": hints}, json_out=json_out)


@app.command("summarize")
def summarize_cmd(
    apply: bool = typer.Option(False, "--apply"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Write bounded deterministic root/project summaries (Ollama enrichment is a later increment)."""
    from hb_assistant.obsidian_mcp.source_structure_ingest import generate_deterministic_summaries

    repo = _repo(db)
    if not apply:
        _emit({"ok": True, "applied": False, "note": "pass --apply to write summaries"},
              json_out=json_out)
    written = generate_deterministic_summaries(repo)
    _emit({"ok": True, "applied": True, "summaries": written}, json_out=json_out)


@app.command("quality")
def quality_cmd(
    apply: bool = typer.Option(False, "--apply"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Recompute deterministic quality findings (dry-run reports; --apply replaces the open set)."""
    from hb_assistant.obsidian_mcp.source_structure_quality import compute_findings

    repo = _repo(db)
    findings = compute_findings(repo)
    by_type: dict[str, int] = {}
    for f in findings:
        by_type[f["finding_type"]] = by_type.get(f["finding_type"], 0) + 1
    if apply:
        repo.replace_findings(findings)
    _emit({"ok": True, "applied": apply, "finding_count": len(findings), "by_type": by_type},
          json_out=json_out)


@app.command("inspect-root")
def inspect_root_cmd(
    root: str = typer.Option(..., "--root", help="Root key to inspect."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Operator-readable root summary (classification, counts, top folders)."""
    from hb_assistant.obsidian_mcp.source_structure_service import SourceStructureService

    svc = SourceStructureService(_db_path(db))
    roots = {r["root_key"]: r for r in svc.root_map()["roots"]}
    if root not in roots:
        _emit({"ok": False, "error": f"unknown root: {root}"}, json_out=json_out, exit_code=1)
    top = svc.folder_map(root_key=root, limit=25)
    _emit({"ok": True, "root": roots[root], "top_folders": top["folders"], "total": top["total"]},
          json_out=json_out)


@app.command("project-map")
def project_map_cmd(
    project: str = typer.Option(..., "--project", help="Project number, e.g. 21-801-01."),
    limit: int = typer.Option(50, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Operator-readable project → candidate-folder map with document-family coverage."""
    from hb_assistant.obsidian_mcp.source_structure_service import SourceStructureService

    svc = SourceStructureService(_db_path(db))
    _emit({"ok": True, **svc.project_map(project, limit=limit)}, json_out=json_out)


@app.command("export-evidence")
def export_evidence_cmd(
    output_dir: str = typer.Option(..., "--output-dir", help="Directory to write evidence JSON."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Export a read-only evidence bundle (status/roots/classification/quality) for audit."""
    db_path = _db_path(db)
    written = _write_evidence_bundle(db_path, Path(output_dir))
    _emit({"ok": True, "output_dir": str(output_dir), "files": written}, json_out=json_out)


def _build_evidence_files(db_path: str) -> dict[str, Any]:
    """Assemble the read-only evidence bundle {filename: payload}, incl. gate-off/gate-on snapshots."""
    from hb_assistant.nas_mcp.exposure_audit import build_exposure_audit
    from hb_assistant.obsidian_mcp.source_structure_service import SourceStructureService

    svc = SourceStructureService(db_path)
    roots = svc.root_map()["roots"]
    class_counts: dict[str, int] = {}
    fam_counts: dict[str, int] = {}
    for r in roots:
        for f in svc.folder_map(root_key=r["root_key"], include_noise=True, limit=200)["folders"]:
            class_counts[f["folder_class"]] = class_counts.get(f["folder_class"], 0) + 1
            if f.get("doc_family"):
                fam_counts[f["doc_family"]] = fam_counts.get(f["doc_family"], 0) + 1

    # Gate-OFF vs gate-ON exposure snapshots. Toggle the kill-switch transiently only — never leak a
    # mutated environment into the rest of the process — so the audit proves the three-state invariant
    # (78 client-exposed default / 7 installed-but-disabled / 85 exposed when the operator enables it).
    with _temp_env("HB_MCP_ASSISTANT_SOURCE_STRUCTURE", "0"):
        gate_off_audit = build_exposure_audit(db_path)
    with _temp_env("HB_MCP_ASSISTANT_SOURCE_STRUCTURE", "1"):
        gate_on_audit = build_exposure_audit(db_path)

    return {
        "source_structure_counts.json": svc.status(),
        "root_classification.json": roots,
        "folder_classification_summary.json": {"folder_class_counts": class_counts,
                                               "doc_family_counts": fam_counts},
        "quality_findings.json": svc.quality(limit=200),
        "index_readiness.json": svc.readiness(),
        "mcp_status_gate_off.json": gate_off_audit,
        "mcp_status_gate_on.json": gate_on_audit,
    }


def _write_evidence_bundle(db_path: str, out: Path) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name, payload in _build_evidence_files(db_path).items():
        p = out / name
        p.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        written.append(str(p))
    return written


@app.command("apply-override")
def apply_override_cmd(
    target: str = typer.Option(..., "--target", help="Override target: 'root' or 'folder'."),
    root: str = typer.Option(..., "--root", help="Root key the override applies to."),
    rel_path: str = typer.Option("", "--rel-path", help="Folder rel_path (folder targets only)."),
    reason: str = typer.Option(..., "--reason", help="Why the override exists (required)."),
    created_by: str = typer.Option(..., "--created-by", help="Operator identity (required)."),
    set_root_class: Optional[str] = typer.Option(None, "--set-root-class"),
    set_folder_class: Optional[str] = typer.Option(None, "--set-folder-class"),
    set_doc_family: Optional[str] = typer.Option(None, "--set-doc-family"),
    set_trust_tier: Optional[str] = typer.Option(None, "--set-trust-tier"),
    set_search_rank: Optional[int] = typer.Option(None, "--set-search-rank"),
    set_backup_mirror: Optional[bool] = typer.Option(
        None, "--set-backup-mirror/--clear-backup-mirror"),
    set_generated_output: Optional[bool] = typer.Option(
        None, "--set-generated-output/--clear-generated-output"),
    set_sensitive: Optional[bool] = typer.Option(None, "--set-sensitive/--clear-sensitive"),
    active: bool = typer.Option(True, "--active/--inactive"),
    apply: bool = typer.Option(False, "--apply", help="Persist (default: dry-run preview)."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Record an operator classification override for a root/folder (fails closed without --reason
    and --created-by). Overrides are applied at the next ingest, after project-number inheritance."""
    if target not in ("root", "folder"):
        _emit({"ok": False, "error": "target must be 'root' or 'folder'"},
              json_out=json_out, exit_code=2)
    if not reason.strip() or not created_by.strip():
        _emit({"ok": False, "error": "override requires a non-empty --reason and --created-by"},
              json_out=json_out, exit_code=2)

    fields = {
        "root_class": set_root_class, "folder_class": set_folder_class,
        "doc_family": set_doc_family, "trust_tier": set_trust_tier,
        "search_rank": set_search_rank, "is_backup_mirror": set_backup_mirror,
        "is_generated_output": set_generated_output, "is_sensitive": set_sensitive,
    }
    if all(v is None for v in fields.values()):
        _emit({"ok": False, "error": "no override fields set (nothing would change)"},
              json_out=json_out, exit_code=2)

    preview = {"target_type": target, "root_key": root,
               "rel_path": rel_path if target == "folder" else "",
               "reason": reason, "created_by": created_by, "active": active,
               **{k: v for k, v in fields.items() if v is not None}}
    if not apply:
        _emit({"ok": True, "applied": False, "override": preview,
               "note": "pass --apply to persist this override"}, json_out=json_out)

    repo = _repo(db)
    override_id = repo.upsert_override(
        target_type=target, root_key=root, rel_path=rel_path, reason=reason,
        created_by=created_by, active=active, **fields)
    _emit({"ok": True, "applied": True, "override_id": override_id, "override": preview},
          json_out=json_out)


@app.command("list-overrides")
def list_overrides_cmd(
    active_only: bool = typer.Option(False, "--active-only"),
    target: Optional[str] = typer.Option(None, "--target", help="Filter by 'root' or 'folder'."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """List recorded operator classification overrides."""
    repo = _repo(db)
    overrides = repo.list_overrides(active_only=active_only, target_type=target)
    _emit({"ok": True, "count": len(overrides), "overrides": overrides}, json_out=json_out)


@app.command("readiness")
def readiness_cmd(
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Conservative index-readiness rollup (gate-on recommended only when clean and non-empty)."""
    from hb_assistant.obsidian_mcp.source_structure_service import SourceStructureService

    svc = SourceStructureService(_db_path(db))
    _emit({"ok": True, **svc.readiness()}, json_out=json_out)


@app.command("refresh")
def refresh_cmd(
    output_root: str = typer.Option(
        ..., "--output-root", help="Parent dir for the timestamped evidence bundle."),
    apply: bool = typer.Option(False, "--apply", help="Run the cycle for real (default: preview)."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """One-shot out-of-band refresh cycle: scan-roots (if configured) → classify → quality →
    export-evidence into a timestamped dir. Bounded + idempotent; never runs in an MCP request path."""
    from datetime import datetime, timezone

    from hb_assistant.obsidian_mcp.source_structure_classifier import classify_tree
    from hb_assistant.obsidian_mcp.source_structure_ingest import (
        generate_deterministic_summaries,
        generate_routing_hints,
        persist_records,
    )
    from hb_assistant.obsidian_mcp.source_structure_quality import compute_findings
    from hb_assistant.obsidian_mcp.source_structure_scanner import ScanCaps, ScanError, scan_roots

    cfg = _app_config().source_structure
    db_path = _db_path(db)
    repo = _repo(db)
    steps: list[dict[str, Any]] = []

    # 1. scan-roots — only when live roots are configured; otherwise a clear no-op.
    configured = dict(cfg.scan_roots or {})
    if not configured:
        steps.append({"step": "scan_roots", "status": "skipped",
                      "reason": "no scan roots configured (source_structure.scan_roots)"})
    elif not apply:
        steps.append({"step": "scan_roots", "status": "preview", "root_keys": list(configured)})
    else:
        caps = ScanCaps(
            max_files_per_root=cfg.scan.max_files_per_root,
            max_folders_per_root=cfg.scan.max_folders_per_root,
            max_depth=cfg.scan.max_depth,
            timeout_seconds=cfg.scan.timeout_seconds,
            high_fanout_threshold=cfg.scan.high_fanout_threshold,
        )
        try:
            tree = scan_roots(configured, caps)
            roots_map, records = classify_tree(tree)
            counts = persist_records(repo, roots_map, records)
            steps.append({"step": "scan_roots", "status": "applied", "counts": counts})
        except ScanError as exc:
            steps.append({"step": "scan_roots", "status": "failed", "error": str(exc)})

    # 2. classify — regenerate deterministic summaries + routing hints.
    if apply:
        steps.append({"step": "classify", "status": "applied",
                      "summaries": generate_deterministic_summaries(repo),
                      "hints": generate_routing_hints(repo)})
    else:
        steps.append({"step": "classify", "status": "preview"})

    # 3. quality — recompute findings; replace the open set only on apply.
    findings = compute_findings(repo)
    if apply:
        repo.replace_findings(findings)
    steps.append({"step": "quality", "status": "applied" if apply else "preview",
                  "finding_count": len(findings)})

    # 4. export-evidence — write a timestamped bundle only on apply (preview stays side-effect-free).
    if apply:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = Path(output_root) / f"source-structure-{ts}"
        written = _write_evidence_bundle(db_path, out_dir)
        steps.append({"step": "export_evidence", "status": "applied",
                      "output_dir": str(out_dir), "files": written})
    else:
        steps.append({"step": "export_evidence", "status": "preview",
                      "output_root": output_root})

    _emit({"ok": True, "applied": apply, "steps": steps}, json_out=json_out)


@app.command("schedule-preview")
def schedule_preview_cmd(
    output_root: str = typer.Option(
        "~/source-structure-evidence", "--output-root",
        help="Evidence dir the scheduled refresh would write to."),
    executable_path: Optional[str] = typer.Option(None, "--executable-path"),
    working_directory: Optional[str] = typer.Option(None, "--working-directory"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """PREVIEW-ONLY: render the launchd job definition for the scheduled refresh. Never loads it —
    no plist is written and launchctl is never invoked (install is a separate future operator step)."""
    from hb_assistant.automation.source_structure_launchd import build_refresh_job

    schedule = _app_config().source_structure.schedule
    job = build_refresh_job(
        schedule, output_root=output_root,
        executable_path=executable_path, working_directory=working_directory,
    )
    _emit({"ok": True, **job}, json_out=json_out)
