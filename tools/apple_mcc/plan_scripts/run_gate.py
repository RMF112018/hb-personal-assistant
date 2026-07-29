#!/usr/bin/env python3
"""Run a candidate gate command; always write log + exit under candidate/$CAND/."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ev", required=True)
    p.add_argument("--candidate", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--argv-json", required=True)
    args = p.parse_args(argv)

    out_dir = Path(args.ev) / "candidate" / args.candidate
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / f"{args.name}.log"
    exit_path = out_dir / f"{args.name}.exit"
    cmd = json.loads(args.argv_json)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    text = ""
    if proc.stdout:
        text += proc.stdout
    if proc.stderr:
        text += ("\n" if text else "") + proc.stderr
    log_path.write_text(text, encoding="utf-8")
    rc = int(proc.returncode)
    exit_path.write_text(str(rc) + "\n", encoding="utf-8")
    print(f"GATE {args.name} exit={rc}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
