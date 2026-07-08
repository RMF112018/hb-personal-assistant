"""`hb-assistant output` — local operator control of the N8C-24 generated-output workspace.

Lets the operator stage/commit/list/inspect/archive generated files under the configured ``outputs`` root
WITHOUT going through the remote MCP surface. Mirrors the same repository (server-minted approval +
idempotency + receipts + manifest); ``validate-root`` confirms the outputs root is configured read_write.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import typer

app = typer.Typer(help="Local operator control of the generated-output workspace (N8C-24).")


def _emit(payload: dict[str, Any], *, json_out: bool, exit_code: int = 0) -> None:
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(exit_code)


def _config() -> Any:
    from hb_assistant.nas_mcp.config import NasMcpConfig

    return NasMcpConfig.from_env()


def _repo() -> Any:
    from hb_assistant.nas_mcp.client_output_workspace import ClientOutputWorkspaceRepository

    return ClientOutputWorkspaceRepository(_config())


@app.command("status")
def status(json_out: bool = typer.Option(False, "--json")) -> None:
    from hb_assistant.nas_mcp.client_output_tools import client_output_status

    _emit(client_output_status(_config()), json_out=json_out)


@app.command("validate-root")
def validate_root(json_out: bool = typer.Option(False, "--json")) -> None:
    cfg = _config()
    root = cfg.roots.get("outputs") if cfg.roots else None
    ok = root is not None and root.mode == "read_write"
    _emit({"outputs_root_configured": ok, "root_key": "outputs",
           "mount": str(root.mount) if root else None, "mode": root.mode if root else None},
          json_out=json_out, exit_code=0 if ok else 1)


@app.command("list")
def list_outputs(status: Optional[str] = typer.Option(None, "--status"),
                 file_type: Optional[str] = typer.Option(None, "--file-type"),
                 limit: int = typer.Option(50, "--limit"),
                 json_out: bool = typer.Option(False, "--json")) -> None:
    _emit(_repo().list_output_files(status=status, file_type=file_type, limit=limit), json_out=json_out)


@app.command("stage")
def stage(title: str = typer.Option(..., "--title"), file_type: str = typer.Option(..., "--file-type"),
          content_mode: str = typer.Option("text", "--content-mode"),
          content: Optional[str] = typer.Option(None, "--content"),
          content_file: Optional[str] = typer.Option(None, "--content-file"),
          destination_state: str = typer.Option("pending", "--destination-state"),
          json_out: bool = typer.Option(False, "--json")) -> None:
    body = content
    if content_file:
        from pathlib import Path
        body = Path(content_file).read_text(encoding="utf-8")
    _emit(_repo().stage_output_file({
        "title": title, "file_type": file_type, "content_mode": content_mode,
        "content_text": body, "destination_state": destination_state}), json_out=json_out)


@app.command("commit")
def commit(output_id: str = typer.Option(..., "--output-id"),
           operator_approval_id: str = typer.Option(..., "--operator-approval-id"),
           idempotency_key: Optional[str] = typer.Option(None, "--idempotency-key"),
           json_out: bool = typer.Option(False, "--json")) -> None:
    _emit(_repo().commit_output_file(output_id=output_id, operator_approval_id=operator_approval_id,
                                     idempotency_key=idempotency_key), json_out=json_out)


@app.command("receipt")
def receipt(receipt_id: str = typer.Option(..., "--receipt-id"),
            json_out: bool = typer.Option(False, "--json")) -> None:
    r = _repo().get_output_receipt(receipt_id)
    _emit(r or {"error": "receipt_not_found"}, json_out=json_out, exit_code=0 if r else 1)


@app.command("manifest")
def manifest(json_out: bool = typer.Option(False, "--json")) -> None:
    _emit(_repo().get_output_manifest(), json_out=json_out)


@app.command("archive-plan")
def archive_plan(output_id: str = typer.Option(..., "--output-id"),
                 json_out: bool = typer.Option(False, "--json")) -> None:
    _emit(_repo().plan_archive_output(output_id), json_out=json_out)


@app.command("archive-commit")
def archive_commit(output_id: str = typer.Option(..., "--output-id"),
                   operator_approval_id: str = typer.Option(..., "--operator-approval-id"),
                   json_out: bool = typer.Option(False, "--json")) -> None:
    _emit(_repo().commit_archive_output(output_id=output_id, operator_approval_id=operator_approval_id),
          json_out=json_out)
