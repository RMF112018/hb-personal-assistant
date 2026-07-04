"""Bounded file readers for NAS MCP root tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hb_assistant.files.parsers.csv import CSVParser
from hb_assistant.files.parsers.docx import DOCXParser
from hb_assistant.files.parsers.pdf import PDFParser
from hb_assistant.files.parsers.txt import TXTParser
from hb_assistant.files.parsers.xlsx import XLSXParser

from .config import NasMcpConfig
from .path_safe import deny_if_blocked, is_probably_binary, resolve_under_root


class FileReadError(Exception):
    """File read denied or unsupported."""


def _ext(path: Path) -> str:
    return path.suffix.lower().lstrip(".")


def read_bounded_file(*, config: NasMcpConfig, root: Path, relative_path: str, max_chars: int | None = None) -> dict[str, Any]:
    target = resolve_under_root(root, relative_path)
    deny_if_blocked(target, denied_patterns=config.denied_name_patterns, denied_dir_segments=config.denied_dir_segments)
    if not target.is_file():
        raise FileReadError("not a file")
    cap = min(max_chars or config.max_excerpt_bytes, config.max_excerpt_bytes)
    ext = _ext(target)
    if ext not in config.read_extensions:
        raise FileReadError(f"unsupported read extension: {ext or '(none)'}")
    if ext in {"txt", "md", "yaml", "yml", "json"}:
        sample = target.read_bytes()[: cap + 1]
        if ext not in {"yaml", "yml", "json"} and is_probably_binary(sample[:4096]):
            raise FileReadError("binary file denied")
        if ext == "json":
            text = sample[:cap].decode("utf-8", errors="replace")
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                raise FileReadError("invalid json") from exc
            return {"file_type": ext, "content": text, "truncated": len(sample) > cap}
        if ext in {"yaml", "yml"}:
            text = sample[:cap].decode("utf-8", errors="replace")
            return {"file_type": ext, "content": text, "truncated": len(sample) > cap}
        parsed = TXTParser().parse(target, max_chars=cap)
        return {"file_type": ext, "content": parsed.get("text_excerpt", ""), "truncated": len(sample) > cap}
    if ext == "csv":
        parsed = CSVParser().parse(target, max_chars=cap)
        return {"file_type": ext, **parsed}
    if ext == "pdf":
        parsed = PDFParser().parse(target, max_chars=cap)
        return {"file_type": ext, **parsed}
    if ext == "docx":
        parsed = DOCXParser().parse(target, max_chars=cap)
        return {"file_type": ext, **parsed}
    if ext in {"xlsx", "xls"}:
        parsed = XLSXParser().parse(target, max_chars=cap)
        return {"file_type": ext, **parsed}
    raise FileReadError(f"unsupported read extension: {ext}")
