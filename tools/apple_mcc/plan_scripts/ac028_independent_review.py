#!/usr/bin/env python3
"""AC-028 independent review gate — deferred until PR/reviewer assignment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ev", required=True)
    p.add_argument("--allow-deferred", action="store_true", default=True)
    args = p.parse_args(argv)
    ev = Path(args.ev)
    status = {
        "ac": "AC-028",
        "status": "DEFERRED_OPERATOR_GATE",
        "reason": "independent_review_requires_pr_and_reviewer_assignment",
    }
    (ev / "ac028-status.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print("AC028_DEFERRED")
    return 0 if args.allow_deferred else 2


if __name__ == "__main__":
    raise SystemExit(main())
