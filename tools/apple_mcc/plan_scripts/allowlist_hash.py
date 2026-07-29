#!/usr/bin/env python3
"""Hash an allowlist file (newline-terminated UTF-8 paths)."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--path", required=True)
    p.add_argument("--expect", default="")
    args = p.parse_args(argv)
    data = Path(args.path).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    print(digest)
    if args.expect and args.expect != digest:
        print(f"ALLOWLIST_HASH_MISMATCH expected={args.expect}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
