#!/usr/bin/env python3
"""Schema-driven schedule table inventory for clean-DB validation."""

from __future__ import annotations

import argparse
import json
import sys

from hb_assistant.construction.schedule_clean_db.schema_audit import (
    build_schema_audit_report,
    write_schema_audit_outputs,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--project-key", required=True)
    parser.add_argument("--read-only-live", action="store_true")
    parser.add_argument("--json-out")
    parser.add_argument("--md-out")
    args = parser.parse_args(argv)
    try:
        report = build_schema_audit_report(
            args.db_path,
            project_key=args.project_key,
            read_only_live=args.read_only_live,
        )
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    write_schema_audit_outputs(report, json_out=args.json_out, md_out=args.md_out)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
