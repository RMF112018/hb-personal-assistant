"""TXT/MDParser: bounded text read with encoding fallback."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


class TXTParser:
    def parse(self, path: Path, max_chars: int = 8000) -> Dict[str, Any]:
        try:
            # try utf8, fallback latin1
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = path.read_text(encoding="latin-1", errors="replace")
            excerpt = text[:max_chars]
            return {
                "text_excerpt": excerpt,
                "char_count": len(excerpt),
            }
        except Exception as e:
            msg = str(e)[:200]
            return {"text_excerpt": "", "char_count": 0, "error": msg, "failure_code": "parser_error"}
