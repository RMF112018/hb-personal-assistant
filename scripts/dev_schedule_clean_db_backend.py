#!/usr/bin/env python3
"""Safe local backend runner for schedule clean-DB validation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from hb_assistant.construction.analytics.api import create_app
from hb_assistant.construction.schedule_clean_db.diagnostics import evidence_disable_background_workers
from hb_assistant.construction.schedule_clean_db.guards import (
    assert_clean_copy_path,
    is_live_db_path,
    require_confirm_clean_copy,
)
from hb_assistant.store.migrator import SQLiteMigrator


def _repo_head() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, timeout=5
        )
        return out.decode().strip()
    except Exception:
        return "unknown"


def build_startup_proof(
    *,
    db_path: str,
    port: int,
    confirm_clean_copy: bool,
    allow_custom_copy_path: bool,
) -> dict:
    require_confirm_clean_copy(confirm_clean_copy)
    guard = assert_clean_copy_path(
        db_path, allow_custom_copy_path=allow_custom_copy_path
    )
    schema_version = 0
    try:
        schema_version = int(SQLiteMigrator(db_path=db_path).current_version())
    except Exception:
        pass
    worker_mode = "disabled" if evidence_disable_background_workers() else "enabled"
    return {
        "mode": "schedule_clean_db_backend",
        "db_path": guard["db_path"],
        "db_path_is_live_db": guard["db_path_is_live_db"],
        "clean_copy_guard_passed": guard["clean_copy_guard_passed"],
        "schema_version": schema_version,
        "repo_head": _repo_head(),
        "port": port,
        "background_worker_mode": worker_mode,
        "background_workers_disabled_by_env": evidence_disable_background_workers(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--confirm-clean-copy", action="store_true")
    parser.add_argument("--allow-custom-copy-path", action="store_true")
    parser.add_argument("--print-proof-only", action="store_true")
    parser.add_argument("--no-start", action="store_true")
    args = parser.parse_args(argv)

    try:
        proof = build_startup_proof(
            db_path=args.db_path,
            port=args.port,
            confirm_clean_copy=args.confirm_clean_copy,
            allow_custom_copy_path=args.allow_custom_copy_path,
        )
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2

    if is_live_db_path(args.db_path):
        print(json.dumps({"error": "live database path rejected"}), file=sys.stderr)
        return 2

    app = create_app(db_path=str(Path(args.db_path).expanduser().resolve()))
    if app.state.db_path != str(Path(args.db_path).expanduser().resolve()):
        proof["app_state_db_path_warning"] = app.state.db_path

    print(json.dumps(proof, indent=2))
    if args.print_proof_only or args.no_start:
        return 0

    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
