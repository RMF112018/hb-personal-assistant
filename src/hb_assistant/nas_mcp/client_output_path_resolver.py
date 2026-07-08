"""N8C-24 — controlled path resolution for the connected-client generated-output workspace.

Generated files land under the governed ``outputs`` root in a small, fixed folder structure. This
resolver refuses any path outside that structure (no new top-level folder, no traversal/absolute/symlink)
and never writes — it only computes + validates destinations. Self-contained within ``nas_mcp`` (no
``obsidian_mcp`` imports), consistent with ``path_safe``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .config import NasMcpConfig
from .path_safe import (
    PathAccessError,
    deny_if_blocked,
    resolve_under_root,
    validate_relative_under_root,
)
from .root_policy import assert_write

OUTPUT_ROOT_KEY = "outputs"
PENDING_FOLDER = "00 Pending"
FINAL_FOLDER = "01 Final"
ARCHIVE_FOLDER = "90 Archive"
RECEIPTS_FOLDER = "99 Receipts"
MANIFESTS_FOLDER = "99 Manifests"
CONTROLLED_TOP_LEVEL: frozenset[str] = frozenset(
    {PENDING_FOLDER, FINAL_FOLDER, ARCHIVE_FOLDER, RECEIPTS_FOLDER, MANIFESTS_FOLDER}
)

MANIFEST_BASENAME = "client-output-manifest"


class OutputPathError(PathAccessError):
    """Invalid or disallowed generated-output destination."""


def sanitize_output_title(title: str, *, cap: int = 80) -> str:
    """Filesystem-safe, organization-neutral filename stem (no control chars, no path separators)."""
    cleaned = re.sub(r"[^A-Za-z0-9 _.\-]+", " ", str(title or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return (cleaned or "untitled")[:cap].strip(" .") or "untitled"


def validate_output_extension(config: NasMcpConfig, file_type: str) -> str:
    ext = str(file_type or "").strip().lower().lstrip(".")
    if ext in config.denied_output_extensions:
        raise OutputPathError(f"denied output extension: {ext}")
    if ext not in config.client_output_extensions:
        raise OutputPathError(f"unsupported output extension: {ext or '(none)'}")
    return ext


def _date_parts(now: str) -> tuple[str, str, str]:
    # now is an ISO-8601 timestamp; derive YYYY/MM/DD for date-partitioning.
    d = str(now)[:10].split("-")
    if len(d) != 3 or not all(d):
        raise OutputPathError("invalid timestamp for date partition")
    return d[0], d[1], d[2]


def resolve_output_relative_path(
    *, output_id: str, title: str, file_type: str, destination_state: str, now: str,
    config: NasMcpConfig,
) -> dict[str, Any]:
    """Compute the controlled relative path for a generated output. Pure (no IO)."""
    ext = validate_output_extension(config, file_type)
    state = str(destination_state or "pending").strip().lower()
    if state not in ("pending", "final"):
        raise OutputPathError(f"invalid destination_state: {state}")
    top = FINAL_FOLDER if state == "final" else PENDING_FOLDER
    yyyy, mm, dd = _date_parts(now)
    filename = f"{output_id} - {sanitize_output_title(title)}.{ext}"
    rel = f"{top}/{yyyy}/{mm}/{dd}/{filename}"
    return {
        "resolved_relative_path": rel,
        "filename": filename,
        "file_type": ext,
        "top_level": top,
        "destination_state": state,
        "path_display": f"{OUTPUT_ROOT_KEY}/{rel}",
    }


def receipt_relative_path(*, output_id: str) -> str:
    return f"{RECEIPTS_FOLDER}/{sanitize_output_title(output_id)} - Output File Receipt.md"


def manifest_relative_paths() -> tuple[str, str]:
    return (f"{MANIFESTS_FOLDER}/{MANIFEST_BASENAME}.md", f"{MANIFESTS_FOLDER}/{MANIFEST_BASENAME}.json")


def archive_relative_path(*, current_relative_path: str, now: str) -> str:
    """Move a committed file's relative path under 90 Archive, preserving its date/name tail."""
    tail = str(current_relative_path).split("/", 1)[-1] if "/" in str(current_relative_path) else current_relative_path
    return f"{ARCHIVE_FOLDER}/{tail}"


def _assert_controlled_top_level(relative_path: str) -> None:
    top = str(relative_path).replace("\\", "/").split("/", 1)[0]
    if top not in CONTROLLED_TOP_LEVEL:
        raise OutputPathError(f"destination outside controlled output folders: {top!r}")


def resolve_output_write_path(config: NasMcpConfig, relative_path: str) -> dict[str, Any]:
    """Validate a controlled relative path against the LIVE outputs root (traversal/absolute/symlink/hidden/
    new-top-level all rejected). Returns the resolved absolute target + display. Never writes."""
    spec = assert_write(config, OUTPUT_ROOT_KEY)
    _assert_controlled_top_level(relative_path)
    # structural check first (cheap), then symlink-aware resolution against the real root.
    validate_relative_under_root(spec.mount, relative_path, kind="output")
    target = resolve_under_root(spec.mount, relative_path)
    deny_if_blocked(
        target, denied_patterns=config.denied_name_patterns, denied_dir_segments=config.denied_dir_segments)
    return {
        "root_key": OUTPUT_ROOT_KEY,
        "absolute_path": str(target),
        "relative_path": str(relative_path),
        "path_display": f"{OUTPUT_ROOT_KEY}/{relative_path}",
        "destination_exists": Path(target).exists(),
    }
