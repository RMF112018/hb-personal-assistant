#!/usr/bin/env python3
"""PM-safe scanner for schedule evidence artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hb_assistant.construction.schedule_clean_db.artifact_scan import (
    render_scan_markdown,
    scan_evidence_dir,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--allowlist-path")
    parser.add_argument("--json-out")
    parser.add_argument("--md-out")
    args = parser.parse_args(argv)
    report = scan_evidence_dir(args.evidence_dir, allowlist_path=args.allowlist_path)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.md_out:
        Path(args.md_out).write_text(render_scan_markdown(report), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
