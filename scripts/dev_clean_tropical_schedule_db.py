#!/usr/bin/env python3
"""Purge Tropical schedule records from a copied clean database only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hb_assistant.construction.schedule_clean_db.guards import (
    assert_clean_copy_path,
    require_confirm_clean_copy,
)
from hb_assistant.construction.schedule_clean_db.purge import run_tropical_purge


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--project-key", default="tropical")
    parser.add_argument("--confirm-clean-copy", action="store_true")
    parser.add_argument("--allow-custom-copy-path", action="store_true")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json-out")
    args = parser.parse_args(argv)

    if args.apply:
        require_confirm_clean_copy(args.confirm_clean_copy)
        try:
            assert_clean_copy_path(
                args.db_path, allow_custom_copy_path=args.allow_custom_copy_path
            )
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}), file=sys.stderr)
            return 2

    result = run_tropical_purge(
        str(Path(args.db_path).expanduser().resolve()),
        project_key=args.project_key,
        dry_run=not args.apply,
        apply=args.apply,
    )
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
