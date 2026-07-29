#!/usr/bin/env python3
"""Produce a WP receipt JSON under $EV."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ev", required=True)
    p.add_argument("--wp", required=True)
    p.add_argument("--nn", required=True)
    p.add_argument("--start-sha", required=True)
    p.add_argument("--end-sha", required=True)
    p.add_argument("--base-sha", default="dd264a1ec1c1a3e8e2ee7d84058e39c309cdd755")
    p.add_argument("--tests-argv-json", required=True)
    p.add_argument("--tests-exit-code", type=int, default=0)
    p.add_argument("--files-json", required=True)
    args = p.parse_args(argv)

    ev = Path(args.ev)
    ev.mkdir(parents=True, exist_ok=True)
    tests_argv = json.loads(args.tests_argv_json)
    files = json.loads(args.files_json)
    if not isinstance(tests_argv, list) or not isinstance(files, list):
        raise SystemExit("tests_argv and files must be JSON arrays")

    # Measure touched via git if possible
    touched = list(files)
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", f"{args.start_sha}..{args.end_sha}"],
            text=True,
        )
        git_touched = [ln.strip() for ln in out.splitlines() if ln.strip()]
        if git_touched:
            touched = git_touched
    except Exception:
        pass

    receipt = {
        "schema_version": "apple_mcc_wp_receipt_v1",
        "wp": args.wp,
        "nn": args.nn,
        "start_sha": args.start_sha,
        "end_sha": args.end_sha,
        "base_sha": args.base_sha,
        "tests_argv": tests_argv,
        "tests_exit_code": int(args.tests_exit_code),
        "files_declared": files,
        "files_touched": touched,
        "receipt_git_commit": None,
        "produced_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out_path = ev / f"wp{args.nn}-receipt.json"
    out_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"WP_RECEIPT_OK {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
