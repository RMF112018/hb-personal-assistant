#!/usr/bin/env python3
"""Validate a WP receipt (types, ancestry, base_sha)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from schemas import PredicateFail, SchemaError, validate


def _is_ancestor(start: str, end: str) -> bool:
    try:
        subprocess.check_call(
            ["git", "merge-base", "--is-ancestor", start, end],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        return start == end


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ev", required=True)
    p.add_argument("--nn", required=True)
    p.add_argument("--base-sha", default="dd264a1ec1c1a3e8e2ee7d84058e39c309cdd755")
    args = p.parse_args(argv)

    path = Path(args.ev) / f"wp{args.nn}-receipt.json"
    if args.nn == "reg":
        path = Path(args.ev) / "reg-receipt.json"
    if not path.is_file():
        print(f"MISSING {path}", file=sys.stderr)
        return 2
    obj = json.loads(path.read_text(encoding="utf-8"))
    try:
        if args.nn == "reg":
            validate("reg_receipt", obj)
        else:
            validate("wp_receipt", obj)
    except SchemaError as exc:
        print(f"SCHEMA_FAIL {exc}", file=sys.stderr)
        return 2
    except PredicateFail as exc:
        print(f"PREDICATE_FAIL {exc}", file=sys.stderr)
        return 3

    if obj.get("base_sha") != args.base_sha:
        print("BASE_SHA_MISMATCH", file=sys.stderr)
        return 3
    if not _is_ancestor(obj["start_sha"], obj["end_sha"]):
        print("ANCESTRY_FAIL", file=sys.stderr)
        return 3
    if obj.get("tests_exit_code") != 0:
        print("TESTS_NOT_GREEN", file=sys.stderr)
        return 3
    print(f"WP_RECEIPT_VALID {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
