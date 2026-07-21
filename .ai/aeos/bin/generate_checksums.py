#!/usr/bin/env python3
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "CHECKSUMS.txt"


def is_macos_metadata(path: Path) -> bool:
    return (
        path.name == ".DS_Store"
        or path.name.startswith("._")
        or "__MACOSX" in path.parts
    )


def main() -> int:
    metadata = [path for path in ROOT.rglob("*") if is_macos_metadata(path)]
    if metadata:
        print("Checksum generation refused: macOS metadata is present")
        for path in metadata:
            print(f"- {path.relative_to(ROOT)}")
        return 1

    lines: list[str] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path == OUTPUT:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(ROOT).as_posix()}")

    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT} with {len(lines)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
