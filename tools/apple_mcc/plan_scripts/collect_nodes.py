#!/usr/bin/env python3
"""Collect process/node inventory for candidate evidence."""

from __future__ import annotations

import argparse
import hashlib
import platform
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ev", required=True)
    p.add_argument("--candidate", required=True)
    args = p.parse_args(argv)
    out_dir = Path(args.ev) / "candidate" / args.candidate
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"python={sys.version.split()[0]}",
        f"platform={platform.platform()}",
        f"executable={sys.executable}",
        f"candidate={args.candidate}",
    ]
    text = "\n".join(lines) + "\n"
    nodes = out_dir / "collected-nodes.txt"
    nodes.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(nodes.read_bytes()).hexdigest()
    (out_dir / "collected-nodes.sha256").write_text(digest + "\n", encoding="utf-8")
    print(f"COLLECT_NODES_OK {nodes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
