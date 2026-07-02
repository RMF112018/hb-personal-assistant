#!/usr/bin/env python3
"""Manifest tool for schedule import packages."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hb_assistant.construction.schedule_clean_db.package_manifest import (
    build_package_manifest,
    write_package_manifest_outputs,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-path", required=True)
    parser.add_argument("--json-out")
    parser.add_argument("--md-out")
    args = parser.parse_args(argv)
    try:
        manifest = build_package_manifest(args.package_path)
    except FileNotFoundError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    write_package_manifest_outputs(manifest, json_out=args.json_out, md_out=args.md_out)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
