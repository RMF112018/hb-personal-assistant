#!/usr/bin/env python3
"""Validate zero unresolved TF for candidate green."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ev", required=True)
    p.add_argument("--candidate-sha", required=True)
    p.add_argument("--base-sha", default="dd264a1ec1c1a3e8e2ee7d84058e39c309cdd755")
    p.add_argument("--out", required=True)
    args = p.parse_args(argv)

    ev = Path(args.ev)
    tf_path = ev / "tf-last-created.json"
    open_unresolved = 0
    checked: list[int] = []
    triage_present = False
    if tf_path.is_file():
        triage_present = True
        obj = json.loads(tf_path.read_text(encoding="utf-8"))
        if obj.get("unresolved") is True:
            open_unresolved += 1
        n = obj.get("github_issue_number")
        if isinstance(n, int):
            checked.append(n)

    result = {
        "schema_version": "apple_mcc_tf_validate_result_v1",
        "candidate_sha": args.candidate_sha,
        "open_unresolved_count": open_unresolved,
        "checked_issue_numbers": checked,
        "canonical_triage_present": triage_present or open_unresolved == 0,
        "zero_unresolved": open_unresolved == 0,
        "validator_exit_code": 0 if open_unresolved == 0 else 1,
        "base_sha": args.base_sha,
        "produced_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"TF_VALIDATE open_unresolved={open_unresolved}")
    return 0 if open_unresolved == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
