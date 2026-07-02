#!/usr/bin/env python3
"""Capture post-commit repo state for Phase 0 clean-DB evidence."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()


def capture_repo_state(evidence_dir: Path, outfile: str = "32-final-repo-state.txt", *, base_commit: str = "53c5a977") -> Path:
    repo = Path(_run("git", "rev-parse", "--show-toplevel"))
    out = evidence_dir / outfile
    head = _run("git", "rev-parse", "HEAD")
    branch = _run("git", "branch", "--show-current")
    status = _run("git", "status", "--short")
    stat = _run("git", "show", "--stat", "--oneline", "--no-renames", "HEAD")
    log = _run("git", "log", "--oneline", "-20")
    content = (
        f"branch={branch}\n"
        f"head={head}\n"
        f"base_commit={base_commit}\n\n"
        f"status:\n{status}\n\n"
        f"head stat:\n{stat}\n\n"
        f"recent commits:\n{log}\n"
    )
    out.write_text(content, encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence-dir",
        required=True,
        type=Path,
        help="Phase 0 evidence directory",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Exit 1 when head= in the artifact does not match git rev-parse HEAD",
    )
    parser.add_argument(
        "--outfile",
        default="32-final-repo-state.txt",
        help="Output filename inside evidence directory",
    )
    parser.add_argument(
        "--base-commit",
        default="53c5a977",
        help="Base commit hash recorded in the artifact",
    )
    args = parser.parse_args(argv)
    out = capture_repo_state(args.evidence_dir, outfile=args.outfile, base_commit=args.base_commit)
    if args.verify:
        head = _run("git", "rev-parse", "HEAD")
        for line in out.read_text(encoding="utf-8").splitlines():
            if line.startswith("head="):
                if line.split("=", 1)[1] != head:
                    print(f"head mismatch: artifact={line.split('=', 1)[1]} HEAD={head}", file=sys.stderr)
                    return 1
                break
        else:
            print("head= line missing", file=sys.stderr)
            return 1
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
