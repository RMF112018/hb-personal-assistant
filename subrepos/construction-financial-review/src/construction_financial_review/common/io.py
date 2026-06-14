"""Streaming JSON/JSONL IO helpers (stdlib only)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Iterator


def read_jsonl(path: str | Path) -> Iterator[dict]:
    """Yield one parsed object per non-blank line."""
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def read_json(path: str | Path) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_jsonl(path: str | Path, rows: Iterable[dict]) -> int:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(p, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def write_json(path: str | Path, obj: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def jsonl_parses(path: str | Path) -> bool:
    """True if every non-blank line parses as JSON."""
    try:
        for _ in read_jsonl(path):
            pass
        return True
    except Exception:
        return False
