"""PDFParser: bounded text extraction (pypdf)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None  # will be handled at runtime

class PDFParser:
    def parse(self, path: Path, max_chars: int = 8000) -> Dict[str, Any]:
        if PdfReader is None:
            raise RuntimeError("pypdf not installed")
        reader = PdfReader(str(path))
        text_parts = []
        for page in reader.pages[:5]:  # bounded
            t = page.extract_text() or ""
            text_parts.append(t)
            if sum(len(p) for p in text_parts) > max_chars:
                break
        excerpt = "\n".join(text_parts)[:max_chars]
        return {
            "text_excerpt": excerpt,
            "char_count": len(excerpt),
            "page_count": len(reader.pages),
        }
