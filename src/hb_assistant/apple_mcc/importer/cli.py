"""Importer CLI entrypoints (dry-run safe)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="apple-mcc-importer")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--batch", type=Path, default=None)
    p.add_argument("--db", type=Path, default=None)
    args = p.parse_args(argv)
    if args.dry_run:
        print(json.dumps({"dry_run": True, "ok": True}))
        return 0
    if args.batch is None:
        print("batch required without --dry-run", file=sys.stderr)
        return 2
    print(json.dumps({"batch": str(args.batch), "db": str(args.db), "ok": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
