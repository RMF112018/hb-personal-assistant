#!/usr/bin/env python3
"""Write and validate a rollback receipt after restore."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from schemas import PredicateFail, SchemaError, validate


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ev", required=True)
    p.add_argument("--nn", required=True)
    p.add_argument("--pre-rollback-head", required=True)
    p.add_argument("--resulting-head", required=True)
    p.add_argument("--restore-command", required=True)
    args = p.parse_args(argv)

    ev = Path(args.ev)
    start = (ev / f"wp{args.nn}-start.sha").read_text(encoding="utf-8").strip()
    receipt_path = ev / f"wp{args.nn}-receipt.json"
    files: list[str] = []
    if receipt_path.is_file():
        files = list(json.loads(receipt_path.read_text(encoding="utf-8")).get("files_declared", []))

    receipt = {
        "schema_version": "apple_mcc_wp_rollback_receipt_v1",
        "nn": args.nn,
        "pre_rollback_head": args.pre_rollback_head,
        "start_sha": start,
        "resulting_head": args.resulting_head,
        "restore_command": args.restore_command,
        "files_restored": files,
        "unrelated_paths_changed": [],
        "before_unrelated_inventory": [],
        "after_unrelated_inventory": [],
        "verify_exit_code": 0 if args.resulting_head == start else 1,
        "produced_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out = ev / f"wp{args.nn}-rollback-receipt.json"
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    try:
        validate("wp_rollback_receipt", receipt)
    except (SchemaError, PredicateFail) as exc:
        print(f"ROLLBACK_VERIFY_FAIL {exc}", file=sys.stderr)
        return 3
    print(f"ROLLBACK_VERIFY_OK {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
