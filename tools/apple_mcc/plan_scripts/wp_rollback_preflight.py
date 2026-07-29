#!/usr/bin/env python3
"""Require a clean porcelain worktree before package rollback."""

from __future__ import annotations

import argparse
import subprocess
import sys


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ev", required=True)
    p.add_argument("--nn", required=True)
    args = p.parse_args(argv)
    out = subprocess.check_output(["git", "status", "--porcelain"], text=True)
    dirty = [ln for ln in out.splitlines() if ln.strip()]
    if dirty:
        print("ROLLBACK_PREFLIGHT_DIRTY", file=sys.stderr)
        for ln in dirty[:50]:
            print(ln, file=sys.stderr)
        return 2
    print(f"ROLLBACK_PREFLIGHT_OK nn={args.nn}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
