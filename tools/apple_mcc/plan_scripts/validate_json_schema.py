#!/usr/bin/env python3
"""Validate a JSON document against a bound schemas.py schema name."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from schemas import PredicateFail, SchemaError, validate

# Bound after WP-00; may be overridden by env APPLE_MCC_SCHEMAS_SHA256
_SCHEMAS_PATH = Path(__file__).resolve().parent / "schemas.py"


def _measured_sha() -> str:
    return hashlib.sha256(_SCHEMAS_PATH.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--schema", required=True)
    p.add_argument("--path", required=True)
    p.add_argument("--expect-schemas-sha256", default=os.environ.get("APPLE_MCC_SCHEMAS_SHA256", ""))
    args = p.parse_args(argv)

    measured = _measured_sha()
    if args.expect_schemas_sha256 and args.expect_schemas_sha256 != measured:
        print(f"SCHEMAS_DIGEST_MISMATCH expected={args.expect_schemas_sha256} measured={measured}", file=sys.stderr)
        return 4

    path = Path(args.path)
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"JSON_LOAD_FAIL {exc}", file=sys.stderr)
        return 2

    try:
        validate(args.schema, obj)
    except SchemaError as exc:
        print(f"SCHEMA_FAIL {exc}", file=sys.stderr)
        return 2
    except PredicateFail as exc:
        print(f"PREDICATE_FAIL {exc}", file=sys.stderr)
        return 3

    print(f"SCHEMA_OK {args.schema} {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
