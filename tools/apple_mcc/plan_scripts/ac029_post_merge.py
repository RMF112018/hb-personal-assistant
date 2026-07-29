#!/usr/bin/env python3
"""AC-029 post-merge gate — not applicable pre-merge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ev", required=True)
    args = p.parse_args(argv)
    status = {
        "ac": "AC-029",
        "status": "DEFERRED_OPERATOR_GATE",
        "reason": "post_merge_not_applicable_pre_merge",
    }
    Path(args.ev).mkdir(parents=True, exist_ok=True)
    (Path(args.ev) / "ac029-status.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8"
    )
    print("AC029_DEFERRED_PRE_MERGE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
