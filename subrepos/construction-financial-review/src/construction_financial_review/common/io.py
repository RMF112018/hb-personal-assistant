"""Streaming JSON/JSONL/CSV IO helpers (stdlib only)."""
from __future__ import annotations

import csv
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


def write_csv(path: str | Path, fieldnames: list[str], rows: Iterable[dict]) -> int:
    """Write rows as CSV deterministically: fixed field order, QUOTE_ALL, '\\n' terminator, no BOM.

    Caller is responsible for deterministic row ordering and 2dp Decimal-string money values.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(p, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, quoting=csv.QUOTE_ALL,
                                lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
            n += 1
    return n


def jsonl_parses(path: str | Path) -> bool:
    """True if every non-blank line parses as JSON."""
    try:
        for _ in read_jsonl(path):
            pass
        return True
    except Exception:
        return False
