#!/usr/bin/env python3
"""Write env-identity.json and env-identity.sha256 (never env-identity.json.sha256)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ev", required=True)
    p.add_argument("--candidate", required=True)
    args = p.parse_args(argv)

    out_dir = Path(args.ev) / "candidate" / args.candidate
    out_dir.mkdir(parents=True, exist_ok=True)

    def _git(*a: str) -> str:
        try:
            return subprocess.check_output(["git", *a], text=True).strip()
        except Exception:
            return ""

    identity = {
        "schema_version": "apple_mcc_env_identity_v1",
        "produced_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "cwd": os.getcwd(),
        "git_head": _git("rev-parse", "HEAD"),
        "git_branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "candidate_sha": args.candidate,
        "uid": os.getuid() if hasattr(os, "getuid") else None,
    }
    json_path = out_dir / "env-identity.json"
    payload = json.dumps(identity, indent=2, sort_keys=True) + "\n"
    json_path.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(json_path.read_bytes()).hexdigest()
    sha_path = out_dir / "env-identity.sha256"
    sha_path.write_text(digest + "\n", encoding="utf-8")
    # Guard against mistaken double-extension artifact
    bad = out_dir / "env-identity.json.sha256"
    if bad.exists():
        bad.unlink()
    print(f"ENV_IDENTITY_OK {json_path} {sha_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
