#!/usr/bin/env python3
"""Run one acceptance check; always write AC log + exit file."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ev", required=True)
    p.add_argument("--id", required=True)
    p.add_argument("--argv-json", default="")
    p.add_argument("--shell", default="")
    args = p.parse_args(argv)

    ac_dir = Path(args.ev) / "ac"
    ac_dir.mkdir(parents=True, exist_ok=True)
    log_path = ac_dir / f"{args.id}.log"
    exit_path = ac_dir / f"{args.id}.exit"

    if args.argv_json:
        cmd = json.loads(args.argv_json)
        if not isinstance(cmd, list) or not all(isinstance(x, str) for x in cmd):
            raise SystemExit("--argv-json must be a JSON string array")
        proc = subprocess.run(cmd, capture_output=True, text=True)
    elif args.shell:
        proc = subprocess.run(args.shell, shell=True, capture_output=True, text=True)
    else:
        raise SystemExit("provide --argv-json or --shell")

    body = []
    body.append(f"AC_ID={args.id}")
    body.append(f"CMD={shlex.join(proc.args) if isinstance(proc.args, list) else proc.args}")
    if proc.stdout:
        body.append("--- stdout ---")
        body.append(proc.stdout.rstrip("\n"))
    if proc.stderr:
        body.append("--- stderr ---")
        body.append(proc.stderr.rstrip("\n"))
    rc = int(proc.returncode)
    result = "PASS" if rc == 0 else "FAIL"
    body.append(f"AC_RESULT={result} exit={rc}")
    log_path.write_text("\n".join(body) + "\n", encoding="utf-8")
    exit_path.write_text(str(rc) + "\n", encoding="utf-8")
    print(body[-1])
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
