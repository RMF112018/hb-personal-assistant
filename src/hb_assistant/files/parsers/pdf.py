"""PDFParser: bounded high-fidelity text + table extraction.

Primary engine is ``pdfplumber`` (local, offline) for layout-aware text plus
structured table extraction (schedules, reports, construction design docs). It
falls back to ``pypdf`` whenever pdfplumber is unavailable or raises unexpectedly,
preserving the original behavior exactly. Both engines stay strictly local — no
upload, no network, no API key — and both return the same bounded ``dict`` contract
(``text_excerpt`` / ``char_count`` / ``failure_code`` / ``page_count``) that the
ingestion service and controlled extractor already consume; ``table_count`` and
``extraction_engine`` are additive metadata only. Output is always a bounded
excerpt (first pages, capped chars), never the full document.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None  # will be handled at runtime

try:
    import pdfplumber as _pdfplumber
except ImportError:
    _pdfplumber = None  # primary engine optional; pypdf fallback always available

_MAX_PAGES = 5  # bounded: never the whole document
_MAX_TABLE_ROWS = 50  # bounded rows serialized per detected table


class PDFParser:
    def parse(self, path: Path, max_chars: int = 8000) -> Dict[str, Any]:
        # Primary: pdfplumber (layout-aware text + tables). On an unexpected
        # failure it returns None to signal a fallback to the pypdf path.
        if _pdfplumber is not None:
            result = self._parse_pdfplumber(path, max_chars)
            if result is not None:
                return result
        return self._parse_pypdf(path, max_chars)

    def _parse_pdfplumber(self, path: Path, max_chars: int) -> Optional[Dict[str, Any]]:
        assert _pdfplumber is not None  # guarded by caller
        try:
            text_parts: list[str] = []
            table_count = 0
            total = 0
            with _pdfplumber.open(str(path)) as pdf:
                page_count = len(pdf.pages)
                for page in pdf.pages[:_MAX_PAGES]:
                    prose = page.extract_text() or ""
                    if prose:
                        text_parts.append(prose)
                        total += len(prose)
                    for table in page.extract_tables() or []:
                        rows = self._serialize_table(table)
                        if rows:
                            table_count += 1
                            block = "[table]\n" + "\n".join(rows)
                            text_parts.append(block)
                            total += len(block)
                    if total > max_chars:
                        break
            excerpt = "\n".join(text_parts)[:max_chars]
            meta: Dict[str, Any] = {
                "text_excerpt": excerpt,
                "char_count": len(excerpt),
                "page_count": page_count,
                "table_count": table_count,
                "extraction_engine": "pdfplumber",
            }
            if not excerpt.strip():
                meta["failure_code"] = "scanned_pdf_no_text"
            return meta
        except Exception as e:
            msg = str(e)[:200]
            low = msg.lower()
            if "encrypt" in low or "password" in low:
                # A genuine encryption block is a definitive result, not a reason
                # to retry with pypdf.
                return {
                    "text_excerpt": "",
                    "char_count": 0,
                    "error": msg,
                    "failure_code": "encrypted_or_password_protected",
                    "extraction_engine": "pdfplumber",
                }
            # Unexpected parse error: defer to the pypdf fallback.
            return None

    @staticmethod
    def _serialize_table(table: list[list[Optional[str]]]) -> list[str]:
        """Render a detected table to bounded, single-line pipe-delimited rows."""
        rows: list[str] = []
        for row in table[:_MAX_TABLE_ROWS]:
            cells = [(c if c is not None else "").replace("\n", " ").strip() for c in row]
            line = " | ".join(cells).strip(" |")
            if line:
                rows.append(line)
        return rows

    def _parse_pypdf(self, path: Path, max_chars: int) -> Dict[str, Any]:
        if PdfReader is None:
            raise RuntimeError("pypdf not installed")
        try:
            reader = PdfReader(str(path))
            if reader.is_encrypted:
                return {
                    "text_excerpt": "",
                    "char_count": 0,
                    "error": "encrypted",
                    "failure_code": "encrypted_or_password_protected",
                    "extraction_engine": "pypdf_fallback",
                }
            text_parts = []
            for page in reader.pages[:_MAX_PAGES]:  # bounded pages
                t = page.extract_text() or ""
                text_parts.append(t)
                if sum(len(p) for p in text_parts) > max_chars:
                    break
            excerpt = "\n".join(text_parts)[:max_chars]
            meta = {
                "text_excerpt": excerpt,
                "char_count": len(excerpt),
                "page_count": len(reader.pages),
                "extraction_engine": "pypdf_fallback",
            }
            if not excerpt.strip():
                meta["failure_code"] = "scanned_pdf_no_text"
            return meta
        except Exception as e:
            msg = str(e)[:200]
            fc = (
                "encrypted_or_password_protected"
                if "encrypt" in msg.lower() or "password" in msg.lower()
                else "parser_error"
            )
            return {
                "text_excerpt": "",
                "char_count": 0,
                "error": msg,
                "failure_code": fc,
                "extraction_engine": "pypdf_fallback",
            }
