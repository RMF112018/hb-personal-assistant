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
        try:
            reader = PdfReader(str(path))
            if reader.is_encrypted:
                return {"text_excerpt": "", "char_count": 0, "error": "encrypted", "failure_code": "encrypted_or_password_protected"}
            text_parts = []
            for page in reader.pages[:5]:  # bounded pages
                t = page.extract_text() or ""
                text_parts.append(t)
                if sum(len(p) for p in text_parts) > max_chars:
                    break
            excerpt = "\n".join(text_parts)[:max_chars]
            meta = {
                "text_excerpt": excerpt,
                "char_count": len(excerpt),
                "page_count": len(reader.pages),
            }
            if not excerpt.strip():
                meta["failure_code"] = "scanned_pdf_no_text"
            return meta
        except Exception as e:
            msg = str(e)[:200]
            fc = "encrypted_or_password_protected" if "encrypt" in msg.lower() or "password" in msg.lower() else "parser_error"
            return {"text_excerpt": "", "char_count": 0, "error": msg, "failure_code": fc}
