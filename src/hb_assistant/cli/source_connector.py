"""`hb-assistant source-connector` — read-only NAS source-root file discovery (N8C-12).

Search / list / inspect / bounded-read indexed NAS source-root FILES (PDFs, contracts, invoices, drawings,
proposals, spreadsheets) as first-class, root-aware, cursor-paged objects — distinct from Obsidian vault
notes and generated source cards. Every command is read-only: nothing here scans a root, reindexes, generates
a card, or mutates anything. ``read`` opens exactly one configured file (bounded, extension-gated) and falls
back to the indexed excerpt when a live read is not permitted.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import typer

app = typer.Typer(help="Read-only NAS source-root file discovery (indexed source files, not vault notes).")


def _emit(payload: dict[str, Any], *, json_out: bool, exit_code: int = 0) -> None:
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(exit_code)


def _db_path(db: Optional[str]) -> str:
    if db:
        return db
    from hb_assistant.config.path_policy import PathPolicy

    return str(PathPolicy().get_db_path())


def _ctx(db: Optional[str]) -> Any:
    from hb_assistant.obsidian_mcp.config import load_config
    from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository

    return SourceIndexRepository(_db_path(db)), load_config()


@app.command("status")
def status(db: Optional[str] = typer.Option(None, "--db"),
           json_out: bool = typer.Option(True, "--json")) -> None:
    """Read-only source-index status + configured source-root summary (no absolute paths)."""
    from hb_assistant.obsidian_mcp import source_connector_service as svc

    repo, config = _ctx(db)
    _emit(svc.source_status(repo, config), json_out=json_out)


@app.command("roots")
def roots(db: Optional[str] = typer.Option(None, "--db"),
          json_out: bool = typer.Option(True, "--json")) -> None:
    """Read-only list of configured source roots (key/enabled/sensitive + indexed file counts)."""
    from hb_assistant.obsidian_mcp import source_connector_service as svc

    repo, config = _ctx(db)
    _emit(svc.list_source_roots(repo, config), json_out=json_out)


@app.command("search")
def search(
    query: str = typer.Option(..., "--query", help="Full-text query over indexed source-file content."),
    root_key: Optional[str] = typer.Option(None, "--root-key", help="Scope to one source_root_key."),
    ext: Optional[str] = typer.Option(None, "--ext", help="Filter by file extension, e.g. pdf."),
    limit: int = typer.Option(25, "--limit"),
    cursor: Optional[str] = typer.Option(None, "--cursor", help="Opaque next-page cursor."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Root-aware full-text search over indexed source files (deterministic cursor windows)."""
    from hb_assistant.obsidian_mcp import source_connector_service as svc
    from hb_assistant.obsidian_mcp.source_connector_models import SourceConnectorValidationError

    repo, config = _ctx(db)
    try:
        _emit(svc.search_source_files(repo, config, query=query, source_root_key=root_key,
                                      file_ext=ext, limit=limit, cursor=cursor), json_out=json_out)
    except SourceConnectorValidationError as e:
        _emit({"error": str(e)}, json_out=json_out, exit_code=1)


@app.command("list")
def list_files(
    root_key: str = typer.Option(..., "--root-key", help="source_root_key to list under."),
    prefix: Optional[str] = typer.Option(None, "--prefix", help="rel_path prefix (folder)."),
    limit: int = typer.Option(25, "--limit"),
    cursor: Optional[str] = typer.Option(None, "--cursor"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Index-backed listing of source files under a root/prefix (keyset-paged; never a filesystem scan)."""
    from hb_assistant.obsidian_mcp import source_connector_service as svc
    from hb_assistant.obsidian_mcp.source_connector_models import SourceConnectorValidationError

    repo, config = _ctx(db)
    try:
        _emit(svc.list_source_files(repo, config, source_root_key=root_key, prefix=prefix,
                                    limit=limit, cursor=cursor), json_out=json_out)
    except SourceConnectorValidationError as e:
        _emit({"error": str(e)}, json_out=json_out, exit_code=1)


@app.command("metadata")
def metadata(
    source_id: Optional[str] = typer.Option(None, "--source-id"),
    source_ref: Optional[str] = typer.Option(None, "--source-ref"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Metadata for one source file (distinguishes original file vs supplemental generated card)."""
    from hb_assistant.obsidian_mcp import source_connector_service as svc
    from hb_assistant.obsidian_mcp.source_connector_models import SourceConnectorValidationError

    repo, config = _ctx(db)
    try:
        _emit(svc.source_file_metadata(repo, config, source_id=source_id, source_ref=source_ref),
              json_out=json_out)
    except SourceConnectorValidationError as e:
        _emit({"error": str(e)}, json_out=json_out, exit_code=1)


@app.command("read")
def read(
    source_id: Optional[str] = typer.Option(None, "--source-id"),
    source_ref: Optional[str] = typer.Option(None, "--source-ref"),
    max_chars: int = typer.Option(4000, "--max-chars"),
    prefer_live: bool = typer.Option(True, "--prefer-live/--indexed",
        help="Default attempts a bounded live read; --indexed forces the indexed excerpt."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Bounded, extension-gated read of one source file (indexed_excerpt_fallback when not live-readable)."""
    from hb_assistant.obsidian_mcp import source_connector_service as svc
    from hb_assistant.obsidian_mcp.source_connector_models import SourceConnectorValidationError

    repo, config = _ctx(db)
    try:
        _emit(svc.read_source_file(repo, config, source_id=source_id, source_ref=source_ref,
                                   max_chars=max_chars, prefer_live=prefer_live), json_out=json_out)
    except SourceConnectorValidationError as e:
        _emit({"error": str(e)}, json_out=json_out, exit_code=1)
