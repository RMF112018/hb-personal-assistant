"""ParserRouter: dispatch by extension to bounded parsers, failure isolation per 08 codes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from .parsers.csv import CSVParser
from .parsers.docx import DOCXParser
from .parsers.image import ImageParser
from .parsers.pdf import PDFParser
from .parsers.pptx import PPTXParser
from .parsers.txt import TXTParser
from .parsers.xlsx import XLSXParser
from .parsers.zip import ZIPParser


class ParserRouter:
    def parse(self, path: Path, content_type: Optional[str] = None) -> Dict[str, Any]:
        ext = path.suffix.lower()
        try:
            if ext == ".pdf":
                return PDFParser().parse(path)
            if ext == ".docx":
                return DOCXParser().parse(path)
            if ext in {".xlsx", ".xlsm"}:
                return XLSXParser().parse(path)
            if ext == ".pptx":
                return PPTXParser().parse(path)
            if ext == ".csv":
                return CSVParser().parse(path)
            if ext in {".txt", ".md"}:
                return TXTParser().parse(path)
            if ext in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
                return ImageParser().parse(path)
            if ext == ".zip":
                return ZIPParser().parse(path)
            # unsupported
            return {"text_excerpt": "", "char_count": 0, "error": "unsupported_type", "failure_code": "unsupported_type"}
        except Exception as e:  # isolation
            msg = str(e)[:200]
            fc = "parser_error"
            if "encrypt" in msg.lower() or "password" in msg.lower():
                fc = "encrypted_or_password_protected"
            return {"text_excerpt": "", "char_count": 0, "error": msg, "failure_code": fc}
