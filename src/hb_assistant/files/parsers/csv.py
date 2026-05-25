"""CSVParser: bounded row extraction with dialect handling (stdlib csv)."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict


class CSVParser:
    MAX_ROWS = 100

    def parse(self, path: Path, max_chars: int = 4000) -> Dict[str, Any]:
        try:
            # sniff dialect, fallback
            with path.open("rb") as fb:
                raw = fb.read(4096)
            try:
                dialect = csv.Sniffer().sniff(raw.decode("utf-8", errors="replace"))
            except Exception:
                dialect = csv.excel
            parts: list[str] = []
            total = 0
            rows = 0
            with path.open(newline="", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f, dialect)
                for row in reader:
                    line = " | ".join(str(c) for c in row).strip()
                    if line:
                        parts.append(line)
                        total += len(line) + 1
                        rows += 1
                        if rows >= self.MAX_ROWS or total > max_chars:
                            break
            excerpt = "\n".join(parts)[:max_chars]
            return {
                "text_excerpt": excerpt,
                "char_count": len(excerpt),
                "rows_sampled": rows,
            }
        except Exception as e:
            msg = str(e)[:200]
            return {"text_excerpt": "", "char_count": 0, "error": msg, "failure_code": "parser_error"}
