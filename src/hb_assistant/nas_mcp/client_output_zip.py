"""N8C-24 — ZIP payload validation for the generated-output workspace.

ZIP is higher-risk than plain documents: it can carry traversal/absolute member paths, symlinks,
encrypted members, denied filenames, or decompression bombs. This module validates a ZIP byte payload
BEFORE it is written and NEVER extracts it. Extraction is not exposed anywhere in N8C-24.
"""

from __future__ import annotations

import io
import zipfile
from typing import Any

from .config import NasMcpConfig


class ZipValidationError(Exception):
    """A ZIP payload failed a safety check and must not be written."""


# Directory segments / filename fragments that must never appear in a member path.
_DENIED_MEMBER_FRAGMENTS = (
    "..", "\\", ".git/", ".obsidian/", "__macosx", ".ssh/", ".pem", ".p12", ".enc", ".key",
)
_DENIED_MEMBER_EXTENSIONS = (
    ".sh", ".command", ".app", ".exe", ".dmg", ".pkg", ".bat", ".ps1", ".jar", ".dylib",
)
# ZIP symlink detection: external_attr high 16 bits carry unix mode; S_IFLNK == 0o120000.
_S_IFLNK = 0o120000


def validate_zip_payload(config: NasMcpConfig, data: bytes) -> dict[str, Any]:
    """Validate a ZIP byte payload. Returns a bounded validation summary (member list, sizes, warnings).
    Raises ZipValidationError on any hard failure. Never extracts."""
    if not data:
        raise ZipValidationError("empty zip payload")
    if len(data) > config.max_client_output_file_bytes:
        raise ZipValidationError("zip payload exceeds max_client_output_file_bytes")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ZipValidationError(f"not a valid zip: {exc}") from exc

    infos = zf.infolist()
    if len(infos) > config.max_client_output_zip_members:
        raise ZipValidationError(
            f"zip member count {len(infos)} exceeds max_client_output_zip_members")

    warnings: list[str] = []
    total_uncompressed = 0
    member_preview: list[dict[str, Any]] = []
    for info in infos:
        name = info.filename
        low = name.lower().replace("\\", "/")
        if name.startswith("/") or (len(name) > 1 and name[1] == ":"):
            raise ZipValidationError(f"absolute member path: {name}")
        if any(frag in low for frag in _DENIED_MEMBER_FRAGMENTS):
            raise ZipValidationError(f"denied member path/segment: {name}")
        if not info.is_dir() and any(low.endswith(ext) for ext in _DENIED_MEMBER_EXTENSIONS):
            raise ZipValidationError(f"denied member extension: {name}")
        if (info.flag_bits & 0x1):  # encryption flag
            raise ZipValidationError(f"encrypted member: {name}")
        if (info.external_attr >> 16) & _S_IFLNK == _S_IFLNK:
            raise ZipValidationError(f"symlink member: {name}")
        total_uncompressed += int(info.file_size)
        if total_uncompressed > config.max_client_output_zip_uncompressed_bytes:
            raise ZipValidationError("zip uncompressed size exceeds max_client_output_zip_uncompressed_bytes")
        if len(member_preview) < config.max_client_output_zip_members:
            member_preview.append({
                "name": name,
                "file_size": int(info.file_size),
                "compress_size": int(info.compress_size),
                "is_dir": info.is_dir(),
            })

    compressed = sum(int(i.compress_size) for i in infos)
    return {
        "zip_validation_passed": True,
        "member_count": len(infos),
        "compressed_bytes": compressed,
        "declared_uncompressed_bytes": total_uncompressed,
        "member_preview": member_preview,
        "zip_validation_warnings": warnings,
    }
