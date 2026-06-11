"""hb-assistant email-calendar — local email/calendar raw→structured projection surfaces.

SQLite-only, read-or-local-write. No Microsoft Graph calls. `projection-reprocess` defaults
to a dry run; `--apply` requires an explicit `--db` so it can never implicitly mutate the
production DB. All commands emit counts / field names / source-quality only — never raw bodies.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import typer

app = typer.Typer(
    help="Local email/calendar raw→structured projection surfaces (SQLite only; no Graph calls)."
)
raw_app = typer.Typer(
    help="Email/calendar structured projection (dry-run default; --apply requires --db)."
)
app.add_typer(raw_app, name="raw")


def _emit(payload: dict[str, Any], *, json_out: bool, exit_code: int = 0) -> None:
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(exit_code)


@raw_app.command("projection-inventory")
def projection_inventory(
    db: Optional[str] = typer.Option(
        None, "--db", help="Explicit SQLite DB path (use a /tmp copy)."
    ),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Mechanical field inventory + projection matrix rows (names/paths + destinations only)."""
    from hb_assistant.construction.email_calendar import projection_engine as eng

    _emit(eng.inventory(db_path=db), json_out=json_out)


@raw_app.command("projection-coverage")
def projection_coverage(
    db: Optional[str] = typer.Option(
        None, "--db", help="Explicit SQLite DB path (use a /tmp copy)."
    ),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Completeness coverage (zero unmapped primary/nested business fields). Exit 3 on unmapped."""
    from hb_assistant.construction.email_calendar import projection_engine as eng

    payload = eng.coverage(db_path=db)
    _emit(payload, json_out=json_out, exit_code=0 if payload["ok"] else 3)


@raw_app.command("projection-reprocess")
def projection_reprocess(
    db: Optional[str] = typer.Option(
        None, "--db", help="Explicit SQLite DB path (required for --apply)."
    ),
    family: Optional[str] = typer.Option(
        None, "--family", help="email_message | email_thread | calendar_event"
    ),
    dry_run: bool = typer.Option(
        True, "--dry-run/--no-dry-run", help="Default: preview only; zero writes."
    ),
    apply: bool = typer.Option(
        False, "--apply", help="Persist structured projection rows to the supplied --db."
    ),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Project raw rows into the structured tables. Dry-run default; --apply needs an explicit --db."""
    from hb_assistant.construction.email_calendar import projection_engine as eng

    if apply and not db:
        _emit(
            {
                "command": "hb-assistant email-calendar raw projection-reprocess",
                "ok": False,
                "status": "refused_apply_without_db",
                "hint": "pass an explicit --db (use a /tmp copy); --apply never targets the prod DB implicitly",
            },
            json_out=json_out,
            exit_code=2,
        )
    payload = eng.reprocess(
        db_path=db, apply=apply and not dry_run, family=family, mode=eng.MODE_ENFORCE
    )
    _emit(payload, json_out=json_out, exit_code=0 if payload["ok"] else 3)


@raw_app.command("status")
def status(
    db: Optional[str] = typer.Option(None, "--db", help="Explicit SQLite DB path."),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Raw + structured row counts and source-quality distribution (counts only)."""
    from hb_assistant.construction.email_calendar import projection_engine as eng

    _emit(eng.status(db_path=db), json_out=json_out)


@raw_app.command("no-raw-leak-scan")
def no_raw_leak_scan_cmd(
    path: list[str] = typer.Option(..., "--path", help="File or directory to scan (repeatable)."),
    sentinel: list[str] = typer.Option([], "--sentinel", help="Extra body/agenda sentinel string."),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Scan evidence/output for email/calendar raw / secret / join-URL leakage. Exit 3 on finding."""
    from hb_assistant.construction.email_calendar.redaction import no_raw_leak_scan

    payload = no_raw_leak_scan(path, sentinels=sentinel)
    _emit(payload, json_out=json_out, exit_code=0 if payload["ok"] else 3)
