"""diagnostics subcommands.

Phase 1: Only `env --json` is fully functional and safe (no secrets ever emitted).
Phase 12: automation readiness + bounded scan-sensitive implemented (primary is automation status).
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer

from hb_assistant.auth.classifier import safe_redact_claims
from hb_assistant.auth.providers import DelegatedAuthProvider
from hb_assistant.config.loader import load_config
from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.graph.http_client import GraphHttpClient, GraphHttpError

app = typer.Typer(help="Safe diagnostics and proof commands (read-only).")


def _repair_recommendation(path: str, exists: bool, writable: bool, kind: str) -> list[str]:
    recs: list[str] = []
    quoted = f'"{path}"'
    if not exists:
        recs.append(f"mkdir -p {quoted}")
    if not writable:
        recs.append(f"chmod u+rwx {quoted}")
    if kind == "auth_dir":
        recs.append(f"chmod 700 {quoted}")
    elif kind.startswith("logs") or kind in {"db_dir", "cache_root", "evidence_dir", "app_support_root"}:
        recs.append(f"chmod 755 {quoted}")
    recs.append(f"# If ownership is wrong and local chmod fails: sudo chown -R $(whoami) {quoted}")
    return recs


def _safe_git_sha() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parents[4],  # repo root
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        ).strip()
        return out
    except Exception:
        return None


@app.command("env")
def env_cmd(
    json_out: bool = typer.Option(True, "--json", help="Always emit machine-readable JSON (default)"),
) -> None:
    """Environment and path discovery (safe, no tokens/keys/bodies/PEMs)."""
    pp = PathPolicy()
    summary = pp.summary()

    data: Dict[str, Any] = {
        "phase": 1,
        "python": {
            "version": sys.version.split()[0],
            "executable": sys.executable,
            "platform": platform.platform(),
        },
        "git": {
            "sha": _safe_git_sha(),
        },
        "paths": summary,
        "permissions": pp.check_perms(strict=False),
        "notes": "All values are safe for logging/evidence. No secret material is present.",
    }

    # Always pretty JSON for diagnostics (human + machine)
    typer.echo(json.dumps(data, indent=2, sort_keys=True))
    raise typer.Exit(0)


@app.command("paths")
def paths_cmd(
    repair_dry_run: bool = typer.Option(False, "--repair-dry-run", help="Show repair simulation only."),
    repair: bool = typer.Option(False, "--repair", help="Attempt local non-sudo repair operations."),
    json_out: bool = typer.Option(True, "--json", help="Emit machine-readable JSON (default)."),
) -> None:
    """Inspect app-support path permissions and provide local repair guidance."""
    pp = PathPolicy()
    ensure_report = pp.ensure_dirs(create_sensitive=True, strict_sensitive=False, return_report=True)

    paths: list[dict[str, Any]] = []
    repair_attempts: list[dict[str, Any]] = []
    for p in ensure_report.get("paths", []):
        if not isinstance(p, dict):
            continue
        path = str(p.get("path", ""))
        kind = str(p.get("kind", "unknown"))
        exists = bool(p.get("exists", False))
        writable = bool(p.get("writable", False))
        item = dict(p)
        item["repair_recommendation"] = _repair_recommendation(path, exists, writable, kind)
        paths.append(item)

        if repair and path:
            target = Path(path)
            attempted = False
            success = True
            error: str | None = None
            try:
                if not target.exists():
                    target.mkdir(parents=True, exist_ok=True)
                    attempted = True
                if kind == "auth_dir":
                    os.chmod(target, 0o700)
                    attempted = True
                elif kind in {"app_support_root", "db_dir", "cache_root", "evidence_dir", "logs_root", "logs_run", "logs_error", "cache_files", "cache_extracted_text", "cache_embeddings"}:
                    os.chmod(target, 0o755)
                    attempted = True
            except Exception as e:
                success = False
                error = str(e)
            repair_attempts.append({"path": path, "kind": kind, "attempted": attempted, "success": success, "error": error})

    status = "ok" if ensure_report.get("ok", False) else "warnings"
    payload: Dict[str, Any] = {
        "diagnostics": "paths",
        "status": status,
        "repair_mode": "repair" if repair else "repair_dry_run" if repair_dry_run else "none",
        "paths": paths,
        "warnings": ensure_report.get("warnings", []),
        "failures": ensure_report.get("failures", []),
        "repair_attempts": repair_attempts,
        "note": "No sudo commands are executed automatically. Recommendations may include manual sudo guidance.",
    }
    typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
    raise typer.Exit(0)


@app.command("auth")
def auth_cmd(json_out: bool = typer.Option(False, "--json")) -> None:
    """Safe auth/cache status using TokenClassifier + TokenCacheManager (Phase 2)."""
    cfg = load_config()
    pp = PathPolicy(cfg)
    del_prov = DelegatedAuthProvider(cfg.identity.tenant_id, cfg.identity.client_id, cfg.identity.delegated_scopes, path_policy=pp)
    info = del_prov.status_info()
    payload = {"diagnostics": "auth", "delegated": info, "note": "App-only status available via `hb-assistant auth status --app-only --json`"}
    typer.echo(json.dumps(payload, indent=2))
    raise typer.Exit(0)


@app.command("graph")
def graph_cmd(
    safe: bool = typer.Option(True, "--safe"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Safe Graph probe using the new GraphHttpClient (Phase 2 base, no full models)."""
    try:
        cfg = load_config()
        pp = PathPolicy(cfg)
        del_prov = DelegatedAuthProvider(cfg.identity.tenant_id, cfg.identity.client_id, cfg.identity.delegated_scopes, path_policy=pp)

        def token_getter(scopes: Optional[List[str]] = None) -> Dict[str, Any]:
            try:
                return del_prov.get_token(scopes or ["User.Read"])
            except Exception as e:
                return {"error": str(e)[:100], "no_token": True}

        client = GraphHttpClient(token_getter)
        result: Dict[str, Any] = {"safe": safe, "probes": []}
        try:
            me = client.get("/me?$select=id,displayName,userPrincipalName,mail")
            result["probes"].append({"path": "/me", "status": 200, "sample": {"id_present": bool(me.get("id")), "upn": me.get("userPrincipalName")}})
        except GraphHttpError as e:
            result["probes"].append({"path": "/me", "status": e.status, "error": e.message[:150]})
        except Exception as e:
            result["probes"].append({"path": "/me", "error": str(e)[:150]})

        # Also report cache state
        result["cache"] = del_prov.status_info().get("cache", {})
        typer.echo(json.dumps(result, indent=2))
        raise typer.Exit(0)
    except typer.Exit:
        raise
    except Exception as e:
        payload = {"safe": safe, "probes": [], "status": "graph_diagnostics_error", "error": str(e)[:200]}
        typer.echo(json.dumps(payload, indent=2))
        raise typer.Exit(1)


@app.command("scan-sensitive")
def scan_sensitive(
    repo: str = typer.Option(".", "--repo"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Bounded sensitive scan (Phase 12), content-aware and redacted."""
    from hb_assistant.security import SensitiveScanner

    payload = SensitiveScanner().scan(repo=repo)
    typer.echo(json.dumps(payload, indent=2) if json_out else json.dumps(payload, indent=2))
    raise typer.Exit(0)


@app.command("automation")
def automation_status(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Automation / launchd readiness (Phase 12 primary diagnostics).

    Reports exact status for plist, config, ledger, gates, paths, permissions, Obsidian readiness.
    """
    from hb_assistant.automation import LaunchdManager
    from hb_assistant.config.loader import load_config
    from hb_assistant.config.path_policy import PathPolicy

    mgr = LaunchdManager()
    st = mgr.status()
    auto_cfg = load_config().automation
    cfg = auto_cfg.morning_run
    pp = PathPolicy()

    payload = {
        "implemented": True,
        "phase": 12,
        "launchd": st,
        "config": {
            "morning_run_time": cfg.time,
            "timezone": cfg.timezone,
            "catch_up_if_wakes_after": cfg.catch_up_if_machine_wakes_after,
            "weekend_behavior": cfg.weekend_behavior,
            "launchd_overrides": {
                "executable_path": auto_cfg.launchd.executable_path,
                "working_directory": auto_cfg.launchd.working_directory,
                "label": auto_cfg.launchd.label,
                "python_path": auto_cfg.launchd.python_path,
            },
        },
        "paths": {
            "app_support": str(pp.get_app_support()).replace(str(Path.home()), "~"),
            "logs": str(pp.get_logs_dir()).replace(str(Path.home()), "~"),
            "obsidian_vault": str(pp.get_vault_root()).replace(str(Path.home()), "~"),
        },
        "readiness": {
            "plist_present": st.get("plist_exists", False),
            "logs_writable": st.get("readiness", {}).get("log_directories_writable", False),
            "launchd_blocking": st.get("readiness", {}).get("blocking", True),
            "launchd_ready": st.get("readiness", {}).get("ready", False),
            "obsidian_daily_notes_ready": (pp.get_vault_root() / "Daily Notes").exists(),
        },
        "note": "Use with run morning --dry-run for full gate evaluation. launchctl status is best viewed via `automation` commands too.",
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


@app.command("proof")
def proof_cmd(
    proof_name: str | None = typer.Argument(None, help="Proof name (canonical: delegated-graph)"),
    delegated_graph: bool = typer.Option(False, "--delegated-graph", help="Backward-compatible alias for delegated-graph proof"),
    step: str = typer.Option("all", "--step", help="Specific step number or 'all'"),
    json_out: bool = typer.Option(True, "--json", help="Emit structured evidence (default)"),
    safe: bool = typer.Option(True, "--safe", help="Safe/read-only mode (no writes beyond evidence)"),
) -> None:
    """Delegated Graph Capability Proof runner.

    This is the mandatory gate before production mail/calendar/file retrieval.
    Proof uses current CLI/auth/runtime code paths and writes sanitized evidence.

    Usage examples:
      hb-assistant diagnostics proof delegated-graph --json
      hb-assistant diagnostics proof --delegated-graph --json
    """
    selected = proof_name
    if delegated_graph and selected is None:
        selected = "delegated-graph"

    if selected is None:
        payload = {
            "available_proofs": ["delegated-graph"],
            "note": "Use `hb-assistant diagnostics proof delegated-graph --json`.",
        }
        typer.echo(json.dumps(payload, indent=2))
        raise typer.Exit(0)

    if selected != "delegated-graph":
        payload = {
            "status": "runtime_error",
            "error": f"Unsupported proof '{selected}'.",
            "available_proofs": ["delegated-graph"],
        }
        typer.echo(json.dumps(payload, indent=2))
        raise typer.Exit(1)

    from hb_assistant.graph.proof_runner import run_delegated_graph_proof

    proof = run_delegated_graph_proof(safe=safe, repo=".")
    proof["step_filter"] = step
    typer.echo(json.dumps(proof, indent=2))
    raise typer.Exit(0 if proof.get("status") == "pass" else 1)


@app.command("mail")
def mail_sample(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Safe, redacted sample of recent inbound mail (Phase 4 verification)."""
    from hb_assistant.config.loader import load_config
    from hb_assistant.config.path_policy import PathPolicy
    from hb_assistant.auth.providers import DelegatedAuthProvider
    from hb_assistant.graph.http_client import GraphHttpClient
    from hb_assistant.graph.mail_client import MailClient

    cfg = load_config()
    pp = PathPolicy(cfg)
    prov = DelegatedAuthProvider(cfg.identity.tenant_id, cfg.identity.client_id, cfg.identity.delegated_scopes, path_policy=pp)

    def token_getter(scopes=None):
        return prov.get_token(scopes or ["Mail.Read", "User.Read"])

    client = GraphHttpClient(token_getter)
    mail = MailClient(client, cfg)
    items = mail.list_inbound(top=3)
    payload = {"count": len(items), "samples": [i.model_dump() for i in items]}
    typer.echo(json.dumps(payload, indent=2))
    raise typer.Exit(0)


@app.command("calendar")
def calendar_sample(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Safe, redacted sample of upcoming calendar events (Phase 4 verification)."""
    from hb_assistant.config.loader import load_config
    from hb_assistant.config.path_policy import PathPolicy
    from hb_assistant.auth.providers import DelegatedAuthProvider
    from hb_assistant.graph.http_client import GraphHttpClient
    from hb_assistant.graph.calendar_client import CalendarClient

    cfg = load_config()
    pp = PathPolicy(cfg)
    prov = DelegatedAuthProvider(cfg.identity.tenant_id, cfg.identity.client_id, cfg.identity.delegated_scopes, path_policy=pp)

    def token_getter(scopes=None):
        return prov.get_token(scopes or ["Calendars.ReadWrite.Shared", "User.Read"])

    client = GraphHttpClient(token_getter)
    cal = CalendarClient(client, cfg)
    items = cal.list_events(top=3)
    payload = {"count": len(items), "samples": [i.model_dump() for i in items]}
    typer.echo(json.dumps(payload, indent=2))
    raise typer.Exit(0)


@app.command("store")
def store_status(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Safe, redacted summary of the local SQLite store (Phase 5)."""
    from hb_assistant.links.registry import SourceLinkRegistry

    reg = SourceLinkRegistry()
    summary = reg.store.get_summary()
    # Never expose full paths or PII in CLI output
    safe = {
        "db_exists": "db_path" in summary,
        "counts": {k: v for k, v in summary.items() if k not in ("db_path", "last_run")},
        "last_run": summary.get("last_run"),
        "note": "All values are counts or redacted metadata only.",
    }
    typer.echo(json.dumps(safe, indent=2))
    raise typer.Exit(0)


@app.command("classify")
def classify_sample(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Safe, redacted body-mention classification sample (Phase 6, preview-only).

    Runs the deterministic detector + classifier on synthetic redacted previews.
    Never reads full bodies, never mutates the store in sample mode.
    """
    from hb_assistant.classification import EmailClassifier, ClassificationResult
    from hb_assistant.normalize.email import Email

    # Synthetic redacted previews (never real full bodies)
    samples = [
        Email(
            id="synth-1",
            folder="inbox",
            subject_redacted="[redacted:s1]",
            sender_domain="ex.com",
            body_preview_redacted="Hey Bobby, quick update on the project timeline...",
            source_record_id=999001,
        ),
        Email(
            id="synth-2",
            folder="inbox",
            subject_redacted="[redacted:s2]",
            sender_domain="partner.com",
            body_preview_redacted="Can you review the Q3 numbers by Friday?",
            source_record_id=999002,
        ),
        Email(
            id="synth-3",
            folder="sent",
            subject_redacted="[redacted:s3]",
            sender_domain="ex.com",
            body_preview_redacted="Thanks, I will handle the follow-up with the vendor.",
            source_record_id=999003,
        ),
    ]

    clf = EmailClassifier()
    results = []
    for e in samples:
        # In sample mode we do NOT call the store update path (use detector directly for safety)
        det = clf.detector.detect(e.body_preview_redacted)
        classifications = []
        if det["body_mention_detected"]:
            classifications.append("bobby_mention")
        if "possible_direct_ask_or_waiting" in det.get("signals", []):
            classifications.append("possible_action_or_waiting")
        res = ClassificationResult(
            message_source_record_id=str(e.source_record_id),
            classifications=classifications,
            body_mention_detected=det["body_mention_detected"],
            confidence=det["confidence"],
        )
        results.append(res.model_dump())

    payload = {
        "mode": "sample-preview-only",
        "count": len(results),
        "results": results,
        "note": "All inputs/outputs are redacted previews only. No store mutation in sample mode.",
    }
    typer.echo(json.dumps(payload, indent=2))
    raise typer.Exit(0)


@app.command("brief")
def brief_sample(
    json_out: bool = typer.Option(True, "--json"),
    dry_run: bool = typer.Option(True, "--dry-run"),
) -> None:
    """Safe, redacted Daily Brief preview (Phase 8, marker-bounded writer dry-run)."""
    from datetime import date

    from hb_assistant.obsidian import DailyBriefGenerator, MarkerBoundedWriter

    gen = DailyBriefGenerator()
    writer = MarkerBoundedWriter()

    target = date.today()
    inner, fm = gen.generate_for_date(target)

    # Always dry-run in sample mode (never mutate real vault)
    would_be = writer.write_bounded_section(
        target,
        inner,
        frontmatter_updates=fm,
        dry_run=True,
    )

    payload = {
        "mode": "brief-preview-dry-run",
        "target_date": target.isoformat(),
        "preview_length": len(would_be) if isinstance(would_be, str) else 0,
        "note": "This is a redacted preview only. No files were written to your vault. Use the full morning run for real writes.",
        "markers_used": ["<!-- HB-DAILY-BRIEF:START -->", "<!-- HB-DAILY-BRIEF:END -->"],
    }
    if json_out:
        typer.echo(json.dumps(payload, indent=2))
    else:
        typer.echo(would_be[:2000] if isinstance(would_be, str) else str(payload))
    raise typer.Exit(0)


@app.command("files")
def files_sample(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Safe, redacted file/attachment selective sample (Phase 10: relevance + eligibility + decision preview, dry-run)."""
    # Thin: no Graph, no DL, no real service (safe even unauthed). Shows new selective fields.
    # Real ingest via `hb-assistant files ingest --dry-run`
    payload = {
        "mode": "files-selective-preview-v1.0",
        "pending": [
            {
                "type": "attachment",
                "name": "[redacted].pdf",
                "size_mb": 1.2,
                "relevance": {"score": 0.42, "worth_ingesting": True, "reasons": ["bobby_mention", "supported_type"]},
                "eligibility": {"eligible": True, "reason": "ok", "requires_manual_approval": False, "size_mb": 1.2},
                "decision": "would_ingest",
            },
            {
                "type": "drive_item",
                "name": "Q3 Report.xlsx",
                "size_mb": 4.5,
                "relevance": {"score": 0.61, "worth_ingesting": True, "reasons": ["name_kw:report", "action_signal", "supported_type"]},
                "eligibility": {"eligible": True, "reason": "ok", "requires_manual_approval": False, "size_mb": 4.5},
                "decision": "would_ingest",
            },
            {
                "type": "drive_item",
                "name": "huge_archive.zip",
                "size_mb": 320.0,
                "relevance": {"score": 0.15, "worth_ingesting": False, "reasons": ["supported_type", "very_large_penalty"]},
                "eligibility": {"eligible": False, "reason": "manual_approval_required", "requires_manual_approval": True, "size_mb": 320.0},
                "decision": "manual_approval_required",
            },
        ],
        "note": "Phase 10 selective: relevance (Phase 6 signals + heuristics) first, then eligibility/approval gate. Excerpts + links only on ingest. Dry-run safe. Use `files ingest --dry-run --json` for service path.",
    }
    typer.echo(json.dumps(payload, indent=2))
    raise typer.Exit(0)
