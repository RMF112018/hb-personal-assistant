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
