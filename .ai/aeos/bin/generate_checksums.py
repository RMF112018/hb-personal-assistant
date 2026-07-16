#!/usr/bin/env python3
from __future__ import annotations
import hashlib
from pathlib import Path

root = Path(__file__).resolve().parents[2]
output = root / "CHECKSUMS.txt"
lines = []
for path in sorted(root.rglob("*")):
    if not path.is_file() or path == output or ".DS_Store" in path.parts:
        continue
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    lines.append(f"{digest}  {path.relative_to(root).as_posix()}")
output.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote {output} with {len(lines)} entries")
