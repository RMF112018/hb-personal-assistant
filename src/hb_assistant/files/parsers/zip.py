"""ZIPParser: archive metadata only (no extraction, no exec)."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any, Dict


class ZIPParser:
    MAX_NAMES = 20

    def parse(self, path: Path, max_chars: int = 1000) -> Dict[str, Any]:
        try:
            with zipfile.ZipFile(str(path), "r") as z:
                names = z.namelist()
                count = len(names)
                total_size = sum(i.file_size for i in z.infolist())
                sample = names[: self.MAX_NAMES]
                excerpt = f"zip: {count} entries, total_size~{total_size}B. sample: {sample}"
                excerpt = excerpt[:max_chars]
                return {
                    "text_excerpt": excerpt,
                    "char_count": len(excerpt),
                    "entry_count": count,
                    "metadata_only": True,
                }
        except Exception as e:
            msg = str(e)[:200]
            fc = "encrypted_or_password_protected" if "password" in str(e).lower() else "parser_error"
            return {"text_excerpt": "", "char_count": 0, "error": msg, "failure_code": fc}
