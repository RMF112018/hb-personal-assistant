"""Bounded file writers for NAS MCP output sandbox."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from .config import NasMcpConfig
from .path_safe import deny_if_blocked, resolve_under_root


class FileWriteError(Exception):
    """File write denied or invalid."""


def _ext(path: Path) -> str:
    return path.suffix.lower().lstrip(".")


def _sha_prefix(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def write_output_file(
    *,
    config: NasMcpConfig,
    root: Path,
    relative_path: str,
    content: str,
    overwrite: bool = False,
) -> dict[str, Any]:
    target = resolve_under_root(root, relative_path)
    deny_if_blocked(target, denied_patterns=config.denied_name_patterns, denied_dir_segments=config.denied_dir_segments)
    ext = _ext(target)
    if ext not in config.output_write_extensions:
        raise FileWriteError(f"unsupported write extension: {ext or '(none)'}")
    raw = content.encode("utf-8")
    if len(raw) > config.max_output_file_bytes:
        raise FileWriteError("content exceeds max_output_file_bytes")
    if target.exists() and not overwrite:
        raise FileWriteError("file exists; set overwrite=true to replace")
    target.parent.mkdir(parents=True, exist_ok=True)
    if ext == "csv":
        # content is CSV text
        target.write_bytes(raw)
    elif ext == "json":
        json.loads(content)
        target.write_bytes(raw)
    elif ext == "docx":
        from docx import Document  # noqa: PLC0415

        doc = Document()
        for line in content.splitlines():
            doc.add_paragraph(line)
        doc.save(str(target))
        raw = target.read_bytes()
    elif ext == "xlsx":
        from openpyxl import Workbook  # noqa: PLC0415

        wb = Workbook()
        ws = wb.active
        reader = csv.reader(io.StringIO(content))
        for row_idx, row in enumerate(reader, start=1):
            for col_idx, value in enumerate(row, start=1):
                ws.cell(row=row_idx, column=col_idx, value=value)
        wb.save(str(target))
        raw = target.read_bytes()
    else:
        target.write_bytes(raw)
    return {
        "bytes_written": len(raw),
        "sha256_prefix": _sha_prefix(raw),
        "overwrite_applied": bool(target.exists() and overwrite),
        "created": True,
    }


def create_output_dir(*, config: NasMcpConfig, root: Path, relative_path: str) -> dict[str, Any]:
    target = resolve_under_root(root, relative_path)
    deny_if_blocked(target, denied_patterns=config.denied_name_patterns, denied_dir_segments=config.denied_dir_segments)
    created = not target.exists()
    target.mkdir(parents=True, exist_ok=True)
    if not target.is_dir():
        raise FileWriteError("not a directory")
    return {"created": created}
