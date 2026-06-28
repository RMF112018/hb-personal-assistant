"""Autonomous Markdown mutation tools for the UI-managed Obsidian MCP service."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy

from .config import ObsidianMcpConfig
from .tools import ObsidianMcpToolError, ResolvedPath, resolve_safe_path


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _support_dir() -> Path:
    root = PathPolicy().get_app_support() / "analytics" / "obsidian_mcp"
    root.mkdir(parents=True, exist_ok=True)
    return root


def audit_path() -> Path:
    return _support_dir() / "mutations.jsonl"


def backup_root() -> Path:
    root = _support_dir() / "backups"
    root.mkdir(parents=True, exist_ok=True)
    return root


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _event(
    *,
    action: str,
    relative_path: str,
    status: str,
    caller_surface: str,
    error_code: str | None = None,
    old_sha256: str | None = None,
    new_sha256: str | None = None,
    old_bytes: int | None = None,
    new_bytes: int | None = None,
    backup_path: str | None = None,
) -> dict[str, Any]:
    return {
        "timestamp": _now(),
        "action": action,
        "relative_path": relative_path,
        "status": status,
        "error_code": error_code,
        "old_sha256": old_sha256,
        "new_sha256": new_sha256,
        "old_bytes": old_bytes,
        "new_bytes": new_bytes,
        "backup_path": backup_path,
        "caller_surface": caller_surface,
    }


def record_mutation(event: dict[str, Any]) -> dict[str, Any]:
    safe = {k: v for k, v in event.items() if v is not None}
    path = audit_path()
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(safe, sort_keys=True) + "\n")
    with suppress(OSError):
        path.chmod(0o600)
    return safe


def recent_mutations(limit: int = 20) -> list[dict[str, Any]]:
    path = audit_path()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-max(1, limit) :]:
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(raw, dict):
            out.append(raw)
    return out


def _write_policy_enabled(config: ObsidianMcpConfig) -> None:
    if not config.writes_enabled:
        raise ObsidianMcpToolError("writes_disabled")
    if not config.vault_markdown_write_enabled:
        raise ObsidianMcpToolError("markdown_writes_disabled")


def _validate_content(config: ObsidianMcpConfig, content: str) -> int:
    if len(content) > config.max_write_chars:
        raise ObsidianMcpToolError("content_exceeds_write_cap")
    return len(content.encode("utf-8"))


def _is_protected(config: ObsidianMcpConfig, rel: str) -> bool:
    low = rel.lower().strip("/")
    parts = low.split("/") if low else []
    for protected in config.protected_paths:
        target = protected.lower().strip("/")
        if low == target or low.startswith(f"{target}/"):
            return True
    return any(part in {".git", ".obsidian", ".trash"} for part in parts)


def _has_blocked_hidden(config: ObsidianMcpConfig, rel: str) -> bool:
    if not config.blocked_hidden_paths:
        return False
    return any(part.startswith(".") for part in rel.split("/") if part)


def _reject_symlink_components(root: Path, relative: str) -> None:
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise ObsidianMcpToolError("symlink_paths_not_allowed")


def resolve_markdown_write_path(
    config: ObsidianMcpConfig,
    requested: str,
    *,
    must_exist: bool = False,
    parent_must_exist: bool = True,
) -> ResolvedPath:
    resolved = resolve_safe_path(config, requested, must_exist=must_exist)
    if not resolved.relative:
        raise ObsidianMcpToolError("path_required")
    if resolved.path.suffix.lower().lstrip(".") not in config.allowed_write_file_types:
        raise ObsidianMcpToolError("markdown_writes_only")
    if _is_protected(config, resolved.relative):
        raise ObsidianMcpToolError("protected_path_blocked")
    if _has_blocked_hidden(config, resolved.relative):
        raise ObsidianMcpToolError("hidden_path_blocked")
    _reject_symlink_components(resolved.root, resolved.relative)
    parent = resolved.path.parent
    if parent.exists():
        try:
            parent.resolve().relative_to(resolved.root)
        except ValueError as exc:
            raise ObsidianMcpToolError("path_outside_vault_root") from exc
    elif parent_must_exist:
        raise ObsidianMcpToolError("parent_directory_missing")
    return resolved


def _backup_existing(path: Path, relative: str) -> str:
    stamp = _now().replace(":", "").replace("+", "Z")
    dest = backup_root() / stamp / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(path.read_bytes())
    with suppress(OSError):
        dest.chmod(0o600)
    return str(dest)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.hb-mcp-",
            suffix=".tmp",
            delete=False,
        ) as fh:
            tmp_name = fh.name
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    finally:
        if tmp_name:
            with suppress(FileNotFoundError):
                Path(tmp_name).unlink()


def _safe_failure(action: str, path: str, caller_surface: str, exc: ObsidianMcpToolError) -> dict[str, Any]:
    cleaned = path.strip().replace("\\", "/")
    rel = "__invalid_path__" if Path(cleaned).is_absolute() or ".." in Path(cleaned).parts else cleaned.strip("/")
    rel = rel or "__invalid_path__"
    event = record_mutation(
        _event(
            action=action,
            relative_path=rel,
            status="rejected",
            caller_surface=caller_surface,
            error_code=exc.code,
        )
    )
    return {"ok": False, "error_code": exc.code, "event": event}


def create_note(
    config: ObsidianMcpConfig,
    *,
    path: str,
    content: str,
    overwrite: bool = False,
    create_parent_dirs: bool = True,
    expected_sha256: str | None = None,
    caller_surface: str = "mcp",
) -> dict[str, Any]:
    try:
        _write_policy_enabled(config)
        new_bytes = _validate_content(config, content)
        parent_must_exist = not (create_parent_dirs and config.create_parent_dirs_enabled)
        resolved = resolve_markdown_write_path(config, path, parent_must_exist=parent_must_exist)
        if not resolved.path.parent.exists():
            if not create_parent_dirs or not config.create_parent_dirs_enabled:
                raise ObsidianMcpToolError("parent_directory_missing")
            resolved.path.parent.mkdir(parents=True, exist_ok=True)
            _reject_symlink_components(resolved.root, resolved.relative)
        old_sha: str | None = None
        old_bytes: int | None = None
        backup_path: str | None = None
        if resolved.path.exists():
            if not resolved.path.is_file():
                raise ObsidianMcpToolError("path_is_not_file")
            if not overwrite:
                raise ObsidianMcpToolError("note_already_exists")
            if config.write_requires_expected_sha256 and not expected_sha256:
                raise ObsidianMcpToolError("expected_sha256_required")
            old_sha = sha256_file(resolved.path)
            old_bytes = resolved.path.stat().st_size
            if expected_sha256 != old_sha:
                raise ObsidianMcpToolError("sha256_mismatch")
            if config.backup_before_replace:
                backup_path = _backup_existing(resolved.path, resolved.relative)
        _atomic_write(resolved.path, content)
        new_sha = sha256_file(resolved.path)
        event = record_mutation(
            _event(
                action="create_note" if old_sha is None else "create_note_overwrite",
                relative_path=resolved.relative,
                status="applied",
                caller_surface=caller_surface,
                old_sha256=old_sha,
                new_sha256=new_sha,
                old_bytes=old_bytes,
                new_bytes=new_bytes,
                backup_path=backup_path,
            )
        )
        return {
            "path": resolved.relative,
            "created": old_sha is None,
            "overwritten": old_sha is not None,
            "sha256": new_sha,
            "bytes": new_bytes,
            "backup_path": backup_path,
            "event": event,
        }
    except ObsidianMcpToolError as exc:
        failure = _safe_failure("create_note", path, caller_surface, exc)
        raise ObsidianMcpToolError(failure["error_code"]) from exc


def patch_note(
    config: ObsidianMcpConfig,
    *,
    path: str,
    content: str,
    expected_sha256: str,
    caller_surface: str = "mcp",
) -> dict[str, Any]:
    try:
        _write_policy_enabled(config)
        new_bytes = _validate_content(config, content)
        if not expected_sha256:
            raise ObsidianMcpToolError("expected_sha256_required")
        resolved = resolve_markdown_write_path(config, path, must_exist=True)
        if not resolved.path.is_file():
            raise ObsidianMcpToolError("path_is_not_file")
        old_sha = sha256_file(resolved.path)
        old_bytes = resolved.path.stat().st_size
        if expected_sha256 != old_sha:
            raise ObsidianMcpToolError("sha256_mismatch")
        backup_path = _backup_existing(resolved.path, resolved.relative) if config.backup_before_replace else None
        _atomic_write(resolved.path, content)
        new_sha = sha256_file(resolved.path)
        event = record_mutation(
            _event(
                action="patch_note",
                relative_path=resolved.relative,
                status="applied",
                caller_surface=caller_surface,
                old_sha256=old_sha,
                new_sha256=new_sha,
                old_bytes=old_bytes,
                new_bytes=new_bytes,
                backup_path=backup_path,
            )
        )
        return {
            "path": resolved.relative,
            "sha256": new_sha,
            "old_sha256": old_sha,
            "bytes": new_bytes,
            "backup_path": backup_path,
            "event": event,
        }
    except ObsidianMcpToolError as exc:
        _safe_failure("patch_note", path, caller_surface, exc)
        raise


def write_readiness(config: ObsidianMcpConfig) -> dict[str, Any]:
    root = Path(config.vault_root).expanduser().resolve()
    backup = backup_root()
    root_writable = root.exists() and root.is_dir() and os.access(root, os.W_OK)
    backup_writable = backup.exists() and backup.is_dir() and os.access(backup, os.W_OK)
    blockers: list[dict[str, str]] = []
    if not config.writes_enabled:
        blockers.append({"code": "writes_disabled", "detail": "write mode is disabled"})
    if not config.vault_markdown_write_enabled:
        blockers.append({"code": "markdown_writes_disabled", "detail": "Markdown writes are disabled"})
    if not root_writable:
        blockers.append({"code": "vault_not_writable", "detail": "vault root is not writable"})
    if config.backup_before_replace and not backup_writable:
        blockers.append({"code": "backup_root_not_writable", "detail": "backup root is not writable"})
    return {
        "surface": "settings.obsidian_mcp.write_readiness",
        "ok": not blockers,
        "writes_enabled": config.writes_enabled,
        "vault_markdown_write_enabled": config.vault_markdown_write_enabled,
        "allow_full_vault_markdown_writes": config.allow_full_vault_markdown_writes,
        "max_write_chars": config.max_write_chars,
        "protected_paths": config.protected_paths,
        "blocked_hidden_paths": config.blocked_hidden_paths,
        "backup_root": str(backup),
        "vault_writable": root_writable,
        "backup_writable": backup_writable,
        "blocking_issues": blockers,
    }
