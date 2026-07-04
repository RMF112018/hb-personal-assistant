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
