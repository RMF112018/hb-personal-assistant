#!/usr/bin/env python3
"""Print candidate SHA (git HEAD) for green orchestration."""

from __future__ import annotations

import argparse
import subprocess


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--format", choices=("plain", "json"), default="plain")
    args = p.parse_args(argv)
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if args.format == "json":
        print(f'{{"candidate_sha":"{sha}"}}')
    else:
        print(sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
