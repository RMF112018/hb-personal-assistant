"""Read/write tools for MCP output sandbox."""

from __future__ import annotations

from typing import Any

from .config import NasMcpConfig
from .file_readers import FileReadError, read_bounded_file
from .file_writers import FileWriteError, create_output_dir, write_output_file
from .fs_tools import FsToolError, hb_secure_list, hb_secure_stat
from .path_safe import path_display
from .root_policy import assert_read, assert_write


def _outputs_root(config: NasMcpConfig):
    return assert_write(config, "outputs").mount


def _norm(relative_path: str, payload: dict[str, Any]) -> dict[str, Any]:
    rel = payload.get("relative_path", relative_path)
    out = dict(payload)
    out["root_key"] = "outputs"
    out.setdefault("path_display", path_display("outputs", str(rel)))
    return out


def hb_output_list(*, config: NasMcpConfig, relative_path: str = ".", max_entries: int | None = None) -> dict[str, Any]:
    assert_read(config, "outputs")
    result = hb_secure_list(config=config, root_key="outputs", relative_path=relative_path, max_entries=max_entries)
    return _norm(relative_path, result)


def hb_output_stat(*, config: NasMcpConfig, relative_path: str) -> dict[str, Any]:
    assert_read(config, "outputs")
    result = hb_secure_stat(config=config, root_key="outputs", relative_path=relative_path)
    return _norm(relative_path, result)


def hb_output_read(*, config: NasMcpConfig, relative_path: str, max_chars: int | None = None) -> dict[str, Any]:
    assert_read(config, "outputs")
    root = _outputs_root(config)
    try:
        payload = read_bounded_file(config=config, root=root, relative_path=relative_path, max_chars=max_chars)
    except FileReadError as exc:
        raise FsToolError(str(exc)) from exc
    rel = relative_path.strip().replace("\\", "/") or "."
    return {"root_key": "outputs", "relative_path": rel, "path_display": path_display("outputs", rel), **payload}


def hb_output_write_file(
    *,
    config: NasMcpConfig,
    relative_path: str,
    content: str,
    overwrite: bool = False,
) -> dict[str, Any]:
    root = _outputs_root(config)
    try:
        result = write_output_file(
            config=config, root=root, relative_path=relative_path, content=content, overwrite=overwrite
        )
    except FileWriteError as exc:
        raise FsToolError(str(exc)) from exc
    rel = relative_path.strip().replace("\\", "/")
    return {
        "root_key": "outputs",
        "relative_path": rel,
        "path_display": path_display("outputs", rel),
        "overwrite_requested": overwrite,
        **result,
    }


def hb_output_create_dir(*, config: NasMcpConfig, relative_path: str) -> dict[str, Any]:
    root = _outputs_root(config)
    try:
        result = create_output_dir(config=config, root=root, relative_path=relative_path)
    except FileWriteError as exc:
        raise FsToolError(str(exc)) from exc
    rel = relative_path.strip().replace("\\", "/")
    return {
        "root_key": "outputs",
        "relative_path": rel,
        "path_display": path_display("outputs", rel),
        **result,
    }
