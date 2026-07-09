"""`hb-assistant source-structure` — out-of-band NAS source-structure layered index (V115).

Operator/scheduled tooling that BUILDS the layered index (root/folder/project classification,
summaries, routing hints, quality findings) from a printed folder-tree artifact or a bounded live
metadata scan. Nothing here runs in an MCP request path. ``--dry-run`` is the default for
mutating commands; ``--apply`` is required to write. Live scanning refuses unconfigured roots.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Optional

import typer

app = typer.Typer(help="Build the NAS source-structure layered index (out-of-band, read surfaces elsewhere).")


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
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run"),
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
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run"),
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
    from hb_assistant.obsidian_mcp.source_structure_service import SourceStructureService

    svc = SourceStructureService(_db_path(db))
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    roots = svc.root_map()["roots"]
    class_counts: dict[str, int] = {}
    fam_counts: dict[str, int] = {}
    for r in roots:
        for f in svc.folder_map(root_key=r["root_key"], include_noise=True, limit=200)["folders"]:
            class_counts[f["folder_class"]] = class_counts.get(f["folder_class"], 0) + 1
            if f.get("doc_family"):
                fam_counts[f["doc_family"]] = fam_counts.get(f["doc_family"], 0) + 1
    findings = svc.quality(limit=200)

    files = {
        "source_structure_counts.json": svc.status(),
        "root_classification.json": roots,
        "folder_classification_summary.json": {"folder_class_counts": class_counts,
                                               "doc_family_counts": fam_counts},
        "quality_findings.json": findings,
    }
    written = []
    for name, payload in files.items():
        p = out / name
        p.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        written.append(str(p))
    _emit({"ok": True, "output_dir": str(out), "files": written}, json_out=json_out)
