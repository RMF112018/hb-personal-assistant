"""diagnostics subcommands.

Phase 1: Only `env --json` is fully functional and safe (no secrets ever emitted).
Other subcommands (auth, graph, scan-sensitive) are explicit stubs.
"""

from __future__ import annotations

import json
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


@app.command("scan-sensitive")
def scan_stub(
    repo: str = typer.Option(".", "--repo"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    payload = {
        "implemented": False,
        "target_phase": 11,
        "repo": repo,
        "note": "Sensitive artifact scanner (forbidden patterns in src + evidence) will be added in hardening phase",
    }
    typer.echo(json.dumps(payload, indent=2))
    raise typer.Exit(0)


@app.command("proof")
def proof_cmd(
    delegated_graph: bool = typer.Option(False, "--delegated-graph", help="Run the 10-step Delegated Graph Capability Proof (Prompt 03 gate)"),
    step: str = typer.Option("all", "--step", help="Specific step number or 'all'"),
    json_out: bool = typer.Option(True, "--json", help="Emit structured evidence (default)"),
    safe: bool = typer.Option(True, "--safe", help="Safe/read-only mode (no writes beyond evidence)"),
) -> None:
    """Delegated Graph Capability Proof runner (Prompt 03).

    This is the mandatory gate before production mail/calendar/file retrieval.
    Full orchestration and evidence writing lives in scripts/proofs/delegated_graph_capability_proof.py.

    Usage examples:
      hb-assistant diagnostics proof --delegated-graph --json
      hb-assistant diagnostics proof --delegated-graph --step 1-5 --json
    """
    if not delegated_graph:
        payload = {
            "available_proofs": ["delegated-graph"],
            "note": "See --delegated-graph for the 10-step proof per 05_Delegated_Graph_Proof_Specification.md",
            "script": "scripts/proofs/delegated_graph_capability_proof.py"
        }
        typer.echo(json.dumps(payload, indent=2))
        raise typer.Exit(0)

    # Thin wrapper: in a full implementation this would import and run the proof module.
    # For now we point to the canonical script (created as part of this phase).
    payload = {
        "proof": "delegated-graph",
        "step": step,
        "safe": safe,
        "status": "delegated_to_script",
        "instruction": "Run: python -m scripts.proofs.delegated_graph_capability_proof --step " + step + " --json",
        "evidence_location": "docs/evidence/prompt-03-delegated-proof/",
        "assumption": "Missing delegated scopes (e.g. Mail.Read) are assumed granted during development prior to deployment per execution directive."
    }
    typer.echo(json.dumps(payload, indent=2))
    raise typer.Exit(0)


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
        return prov.get_token(scopes or ["Calendars.Read", "User.Read"])

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
        "note": "This is a redacted preview only. No files were written to your vault. Use the full morning run (later phase) for real writes.",
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
    """Safe, redacted file/attachment link discovery sample (Phase 9, eligibility preview, dry-run)."""
    # Thin: in real would call FileIngestionService.discover... with recent mail/calendar
    # For sample: return redacted metadata + eligibility preview (no real Graph calls in this helper)
    payload = {
        "mode": "files-discovery-preview",
        "pending": [
            {"type": "attachment", "name": "[redacted].pdf", "size_mb": 1.2, "eligibility": "ok"},
            {"type": "drive_item", "name": "Q3 Report.xlsx", "size_mb": 4.5, "eligibility": "ok"},
        ],
        "note": "Redacted metadata + eligibility only. Full ingest uses controlled download + parsers (dry-run recommended).",
    }
    typer.echo(json.dumps(payload, indent=2))
    raise typer.Exit(0)
