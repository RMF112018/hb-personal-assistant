#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "CHECKSUMS.txt"


def is_macos_metadata(path: Path) -> bool:
    return path.name == ".DS_Store" or path.name.startswith("._") or "__MACOSX" in path.parts


def expected_lines() -> list[str]:
    metadata = [p for p in ROOT.rglob("*") if is_macos_metadata(p)]
    if metadata:
        raise RuntimeError("macOS metadata present: " + ", ".join(str(p.relative_to(ROOT)) for p in metadata))
    lines=[]
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path == OUTPUT or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(ROOT).as_posix()}")
    return lines


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args=parser.parse_args()
    try:
        text="\n".join(expected_lines())+"\n"
    except RuntimeError as exc:
        print(f"Checksum generation refused: {exc}")
        return 1
    if args.check:
        if not OUTPUT.is_file():
            print("CHECKSUMS.txt missing")
            return 1
        if OUTPUT.read_text(encoding="utf-8") != text:
            print("CHECKSUMS.txt is stale")
            return 1
        print(f"CHECKSUMS.txt current with {len(text.splitlines())} entries")
        return 0
    OUTPUT.write_text(text, encoding="utf-8")
    print(f"Wrote {OUTPUT} with {len(text.splitlines())} entries")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
