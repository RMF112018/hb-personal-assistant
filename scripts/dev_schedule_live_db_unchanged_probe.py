#!/usr/bin/env python3
"""Live DB unchanged probe — read-only snapshot and compare."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hb_assistant.construction.schedule_clean_db.live_db_probe import (
    compare_snapshots,
    load_snapshot,
    snapshot_live_db,
    write_snapshot,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-db-path", required=True)
    parser.add_argument("--project-key", default="tropical")
    parser.add_argument("--read-only-live", action="store_true")
    parser.add_argument("--snapshot-out")
    parser.add_argument("--compare-before")
    parser.add_argument("--json-out")
    parser.add_argument("--md-out")
    args = parser.parse_args(argv)

    if args.compare_before:
        before = load_snapshot(args.compare_before)
        after = snapshot_live_db(
            args.live_db_path,
            project_key=args.project_key,
            read_only_live=args.read_only_live,
        )
        result = compare_snapshots(before, after)
        if args.json_out:
            Path(args.json_out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        if args.md_out:
            Path(args.md_out).write_text(
                "# Live DB compare\n\n```json\n" + json.dumps(result, indent=2) + "\n```\n",
                encoding="utf-8",
            )
        print(json.dumps(result, indent=2))
        return 0 if result.get("passed") else 1

    snap = snapshot_live_db(
        args.live_db_path,
        project_key=args.project_key,
        read_only_live=args.read_only_live,
    )
    if args.snapshot_out:
        write_snapshot(snap, args.snapshot_out)
    print(json.dumps(snap, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
