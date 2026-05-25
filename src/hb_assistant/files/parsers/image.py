"""ImageParser: metadata only (no OCR, no pixel data)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


class ImageParser:
    def parse(self, path: Path, max_chars: int = 500) -> Dict[str, Any]:
        try:
            ext = path.suffix.lower()
            size = path.stat().st_size if path.exists() else 0
            size_mb = round(size / (1024 * 1024), 2)
            # no PIL: dims unknown without extra dep or format parsing
            excerpt = f"image:{ext} size:{size_mb}MB (metadata only; no OCR/dims in v1.0)"
            excerpt = excerpt[:max_chars]
            return {
                "text_excerpt": excerpt,
                "char_count": len(excerpt),
                "metadata_only": True,
            }
        except Exception as e:
            msg = str(e)[:200]
            return {"text_excerpt": "", "char_count": 0, "error": msg, "failure_code": "parser_error"}
