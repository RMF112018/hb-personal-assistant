"""ParserRouter: dispatch by extension, failure isolation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from .parsers.pdf import PDFParser

class ParserRouter:
    def parse(self, path: Path, content_type: Optional[str] = None) -> Dict[str, Any]:
        ext = path.suffix.lower()
        if ext == ".pdf":
            return PDFParser().parse(path)
        # Add other parsers...
        return {"text_excerpt": "", "char_count": 0, "error": "unsupported_type"}
