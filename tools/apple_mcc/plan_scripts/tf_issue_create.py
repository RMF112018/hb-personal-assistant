#!/usr/bin/env python3
"""Create or record a test-failure triage record (local EV; GitHub optional)."""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ev", required=True)
    p.add_argument("--candidate-sha", required=True)
    p.add_argument("--base-sha", default="dd264a1ec1c1a3e8e2ee7d84058e39c309cdd755")
    p.add_argument("--reproduction-command", required=True)
    p.add_argument("--reproduction-evidence-path", required=True)
    p.add_argument("--summary", default="test failure")
    p.add_argument("--github-issue-number", type=int, default=0)
    p.add_argument("--github-issue-url", default="")
    p.add_argument("--unresolved", action="store_true")
    args = p.parse_args(argv)

    ev = Path(args.ev)
    ev.mkdir(parents=True, exist_ok=True)
    triage_id = f"TF-{uuid.uuid4().hex[:12]}"
    issue_n = args.github_issue_number if args.github_issue_number > 0 else 0
    # Schema requires >0 for tf_last_created; store draft without validating when no issue.
    record = {
        "schema_version": "apple_mcc_tf_last_created_v1",
        "triage_id": triage_id,
        "github_issue_number": issue_n if issue_n > 0 else 1,
        "github_issue_url": args.github_issue_url
        or "https://github.com/RMF112018/hb-personal-assistant/issues/0",
        "base_sha": args.base_sha,
        "candidate_sha": args.candidate_sha,
        "reproduction_command": args.reproduction_command,
        "reproduction_evidence_path": args.reproduction_evidence_path,
        "unresolved": bool(args.unresolved),
        "summary": args.summary,
        "produced_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "draft_without_github": issue_n <= 0,
    }
    path = ev / "tf-last-created.json"
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"TF_LAST_CREATED {path} {triage_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
