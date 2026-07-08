"""Top-level NAS MCP CLI commands."""

from __future__ import annotations

import json

import typer

mcp_app = typer.Typer(
    name="mcp",
    help="NAS read-only MCP bridge — dedicated loopback HTTP (Phase N7).",
)


@mcp_app.command("serve")
def serve(
    nas_readonly: bool = typer.Option(
        False,
        "--nas-readonly",
        help="Required: enable NAS readonly MCP mode (fail-closed guards).",
    ),
    streamable_http: bool = typer.Option(
        False,
        "--streamable-http",
        help="Serve MCP streamable HTTP (required for NAS tunnel access).",
    ),
    host: str = typer.Option("0.0.0.0", "--host", help="Bind host inside container namespace."),
    port: int = typer.Option(8765, "--port", help="MCP listen port (container)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Report readiness without listening."),
) -> None:
    """Start the dedicated NAS readonly MCP HTTP server."""
    if not nas_readonly or not streamable_http:
        typer.echo(
            json.dumps(
                {
                    "ok": False,
                    "error": "Both --nas-readonly and --streamable-http are required.",
                },
                indent=2,
            )
        )
        raise typer.Exit(code=2)

    from hb_assistant.nas_mcp.server import serve_nas_readonly_streamable_http

    payload = serve_nas_readonly_streamable_http(host=host, port=port, dry_run=dry_run)
    if dry_run:
        typer.echo(json.dumps(payload, indent=2, default=str))
        raise typer.Exit(code=0 if payload.get("ready") else 1)
    typer.echo(json.dumps(payload, indent=2, default=str))


@mcp_app.command("exposure-audit")
def exposure_audit(
    db_path: str = typer.Option(
        None,
        "--db-path",
        help="Optional DB to audit read-only; default builds a fresh migrated temp DB (never prod).",
    ),
    out_json: str = typer.Option(None, "--out-json", help="Write the machine-readable JSON artifact here."),
    out_md: str = typer.Option(None, "--out-md", help="Write the human-readable markdown summary here."),
    as_json: bool = typer.Option(True, "--json/--no-json", help="Echo the JSON artifact to stdout."),
) -> None:
    """N8C-22 client-exposure parity audit: prove whether all 78 canonical assistant tools are actually
    exposed as callable client tools (not merely advertised in status). Read-only; no prod mutation."""
    from pathlib import Path

    from hb_assistant.nas_mcp.exposure_audit import build_exposure_audit, render_markdown

    audit = build_exposure_audit(db_path=db_path)
    if out_json:
        Path(out_json).write_text(json.dumps(audit, indent=2), encoding="utf-8")
    if out_md:
        Path(out_md).write_text(render_markdown(audit), encoding="utf-8")
    if as_json:
        typer.echo(json.dumps(audit, indent=2))
    gap = audit["summary"]["missing_from_client_manifest"] > 0 or audit["summary"]["not_callable"] > 0
    raise typer.Exit(code=1 if gap else 0)
