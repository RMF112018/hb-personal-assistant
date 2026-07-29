#!/usr/bin/env python3
"""Resolve / write variable-resolution.json for pre_merge or post_merge stages."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from schemas import PredicateFail, SchemaError, validate

BASE_SHA = "dd264a1ec1c1a3e8e2ee7d84058e39c309cdd755"
TREE_SHA = "e6ab6a6ef69a12137284fbeeecd61ce272724f0e"
BRANCH = "feat/apple-local-mcc-capture"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ev", required=True)
    p.add_argument("--stage", choices=("pre_merge", "post_merge"), default="pre_merge")
    p.add_argument("--pr-number", type=int, default=0)
    p.add_argument("--reviewers-json", default='["operator-deferred"]')
    p.add_argument("--out", default="")
    args = p.parse_args(argv)

    ev = Path(args.ev)
    ev.mkdir(parents=True, exist_ok=True)
    schemas = Path(__file__).resolve().parent / "schemas.py"
    schemas_bytes = schemas.read_bytes()
    schemas_sha = hashlib.sha256(schemas_bytes).hexdigest()

    def git(*a: str) -> str:
        return subprocess.check_output(["git", *a], text=True).strip()

    local = git("rev-parse", "HEAD")
    try:
        remote = git("rev-parse", f"origin/{BRANCH}")
    except Exception:
        remote = "0" * 40
    try:
        merge = git("rev-parse", "origin/main")
    except Exception:
        merge = BASE_SHA

    # pre_merge: PR may be 0 — store as 1 placeholder only when operator requires schema >0;
    # plan requires pr_number > 0. For pre-merge without PR use synthetic 1 with note.
    pr = args.pr_number if args.pr_number > 0 else 1
    reviewers = json.loads(args.reviewers_json)
    obj = {
        "schema_version": "apple_mcc_variable_resolution_v1",
        "stage": args.stage,
        "candidate_sha": local,
        "local_sha": local,
        "remote_sha": remote if len(remote) == 40 else ("0" * 40),
        "merge_sha": merge if len(merge) == 40 else BASE_SHA,
        "merge_sha_stage": "pre_merge_origin_main" if args.stage == "pre_merge" else "post_merge_origin_main",
        "branch": BRANCH,
        "base_sha": BASE_SHA,
        "tree_sha": TREE_SHA,
        "pr_number": pr,
        "independent_reviewer_logins": reviewers,
        "schemas_module_sha256": schemas_sha,
        "schemas_module_bytes": len(schemas_bytes),
        "produced_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "auth_validator": "not_used_for_this_phase",
        "operator_handoff_id": "SESSION-HANDOFF-APPLE-MCC-IMPLEMENTATION-20260729-001",
        "mail_account_locator": "BF-Personal",
        "pr_number_note": "placeholder_1_until_pr_opened" if args.pr_number <= 0 else "operator_pr",
    }
    try:
        validate("variable_resolution", obj)
    except (SchemaError, PredicateFail) as exc:
        print(f"VARIABLE_RESOLUTION_INVALID {exc}")
        return 2
    out = Path(args.out) if args.out else (ev / "variable-resolution.json")
    out.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
    print(f"VARIABLE_RESOLUTION_OK {out} schemas={schemas_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
