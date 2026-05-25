"""PathPolicy: canonical resolution of all local filesystem locations.

Responsibilities (Phase 1 foundation):
- Resolve repo root (best-effort via this file or git)
- Resolve Application Support root + all standard subdirectories
- Resolve Obsidian vault (from config or sensible default)
- Ensure directories exist with correct permissions (700 for auth-containing dirs)
- Basic permission checks (fail closed on weak auth dir perms in production paths)
- Provide stable Path objects for DB, caches, logs, evidence, etc.

This module must NEVER log tokens, keys, or full paths that could leak in evidence.
"""

from __future__ import annotations

import os
import pwd
import sqlite3
import stat
from pathlib import Path
from typing import Any, Optional

from .loader import load_config
from .models import AppConfig


class PathPolicy:
    """Central path resolver for HB Personal Assistant."""

    # Fixed app name for Application Support (matches architecture decisions)
    APP_NAME = "HB Personal Assistant"

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self._config = config or load_config()
        self._repo_root: Optional[Path] = None
        self._app_support: Optional[Path] = None

    # --- Repo root ---

    def resolve_repo_root(self) -> Path:
        """Best-effort discovery of the git repo root containing this package."""
        if self._repo_root is not None:
            return self._repo_root

        # Start from this file and walk up until we see .git or pyproject.toml
        here = Path(__file__).resolve()
        for parent in [here] + list(here.parents):
            if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
                self._repo_root = parent
                return parent
        # Fallback: cwd (dev convenience)
        self._repo_root = Path.cwd()
        return self._repo_root

    # --- Application Support (primary local state) ---

    def get_app_support(self) -> Path:
        if self._app_support is not None:
            return self._app_support

        configured = self._config.paths.application_support_root
        p = Path(configured).expanduser()
        if not p.is_absolute():
            # Make absolute relative to home if relative
            p = Path.home() / p.relative_to(p.anchor) if p.anchor else Path.home() / p
        self._app_support = p
        return p

    def get_auth_dir(self) -> Path:
        return self.get_app_support() / "auth"

    def get_db_path(self) -> Path:
        return self.get_app_support() / "db" / "hb-personal-assistant.sqlite"

    def get_cache_dir(self, sub: str = "files") -> Path:
        return self.get_app_support() / "cache" / sub

    def get_logs_dir(self) -> Path:
        return self.get_app_support() / "logs"

    def get_evidence_dir(self) -> Path:
        return self.get_app_support() / "evidence"

    # --- Obsidian Vault ---

    def get_vault_root(self) -> Path:
        return Path(self._config.paths.obsidian_vault).expanduser()

    def get_daily_notes_dir(self) -> Path:
        return self.get_vault_root() / self._config.paths.daily_notes_folder

    def get_ai_outputs_dir(self) -> Path:
        return self.get_vault_root() / self._config.paths.ai_outputs_folder

    # --- Ensure + Permissions ---

    def _owner_for_path(self, path: Path) -> str | None:
        try:
            uid = path.stat().st_uid
            return pwd.getpwuid(uid).pw_name
        except Exception:
            return None

    def _mode_for_path(self, path: Path) -> str | None:
        try:
            return oct(stat.S_IMODE(path.stat().st_mode))
        except Exception:
            return None

    def _build_path_status(
        self,
        path: Path,
        *,
        kind: str,
        chmod_attempted: bool,
        chmod_ok: bool,
        error: str | None,
    ) -> dict[str, Any]:
        exists = path.exists()
        writable = os.access(path, os.W_OK) if exists else False
        return {
            "path": str(path),
            "kind": kind,
            "exists": exists,
            "writable": writable,
            "mode": self._mode_for_path(path) if exists else None,
            "owner": self._owner_for_path(path) if exists else None,
            "chmod_attempted": chmod_attempted,
            "chmod_ok": chmod_ok,
            "error": error,
        }

    def ensure_dirs(
        self,
        *,
        create_sensitive: bool = True,
        strict_sensitive: bool = False,
        return_report: bool = False,
    ) -> None | dict[str, Any]:
        """Create standard app-support directories with bounded permission handling.

        - Non-sensitive path chmod failures are best-effort warnings.
        - Auth path chmod failure can fail only when strict_sensitive=True.
        """

        specs: list[tuple[Path, str, int | None, bool]] = [
            (self.get_app_support(), "app_support_root", 0o755, False),
            (self.get_auth_dir(), "auth_dir", 0o700 if create_sensitive else None, True),
            (self.get_app_support() / "db", "db_dir", 0o755, False),
            (self.get_app_support() / "cache", "cache_root", 0o755, False),
            (self.get_cache_dir("files"), "cache_files", 0o755, False),
            (self.get_cache_dir("extracted-text"), "cache_extracted_text", 0o755, False),
            (self.get_cache_dir("embeddings"), "cache_embeddings", 0o755, False),
            (self.get_logs_dir(), "logs_root", 0o755, False),
            (self.get_logs_dir() / "run-logs", "logs_run", 0o755, False),
            (self.get_logs_dir() / "error-logs", "logs_error", 0o755, False),
            (self.get_evidence_dir(), "evidence_dir", 0o755, False),
        ]

        report_paths: list[dict[str, Any]] = []
        warnings: list[str] = []
        failures: list[str] = []

        for path, kind, chmod_mode, sensitive in specs:
            chmod_attempted = False
            chmod_ok = False
            error: str | None = None

            try:
                path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                error = f"mkdir_failed: {e}"
                failures.append(f"{kind}: {e}")
                report_paths.append(
                    self._build_path_status(
                        path,
                        kind=kind,
                        chmod_attempted=chmod_attempted,
                        chmod_ok=chmod_ok,
                        error=error,
                    )
                )
                if sensitive and strict_sensitive:
                    raise PermissionError(f"Failed to create sensitive dir {path}: {e}") from e
                continue

            if chmod_mode is not None:
                chmod_attempted = True
                try:
                    os.chmod(path, chmod_mode)
                    chmod_ok = True
                except Exception as e:
                    error = f"chmod_failed: {e}"
                    target = failures if sensitive and strict_sensitive else warnings
                    target.append(f"{kind}: {e}")
                    if sensitive and strict_sensitive:
                        report_paths.append(
                            self._build_path_status(
                                path,
                                kind=kind,
                                chmod_attempted=chmod_attempted,
                                chmod_ok=chmod_ok,
                                error=error,
                            )
                        )
                        raise PermissionError(
                            f"Failed to chmod sensitive dir {path} to {oct(chmod_mode)}: {e}"
                        ) from e

            report_paths.append(
                self._build_path_status(
                    path,
                    kind=kind,
                    chmod_attempted=chmod_attempted,
                    chmod_ok=chmod_ok,
                    error=error,
                )
            )

        report: dict[str, Any] = {
            "ok": len(failures) == 0,
            "warnings": warnings,
            "failures": failures,
            "paths": report_paths,
        }

        if return_report:
            return report
        return None

    def check_perms(self, strict: bool = False) -> dict[str, bool]:
        """Return a dict of permission checks.

        strict=True will raise on auth dir problems (for early fail in production runs).
        """
        results: dict[str, bool] = {}
        auth_dir = self.get_auth_dir()

        if auth_dir.exists():
            mode = stat.S_IMODE(os.stat(auth_dir).st_mode)
            results["auth_dir_700"] = (mode & 0o777) == 0o700
            if strict and not results["auth_dir_700"]:
                raise PermissionError(
                    f"Auth directory {auth_dir} has mode {oct(mode)}; expected 0o700"
                )
        else:
            results["auth_dir_700"] = False

        # Token cache files (if present) should be 0o600
        for name in ("msal-token-cache.bin", "msal-token-cache-app.bin"):
            f = auth_dir / name
            if f.exists():
                mode = stat.S_IMODE(os.stat(f).st_mode)
                results[f"{name}_600"] = (mode & 0o777) == 0o600
            else:
                results[f"{name}_600"] = True  # absent is ok

        return results

    # --- Convenience for diagnostics ---

    def summary(self) -> dict[str, str]:
        """Return a safe (no secrets) summary for diagnostics env --json."""
        return {
            "repo_root": str(self.resolve_repo_root()),
            "app_support": str(self.get_app_support()),
            "auth_dir": str(self.get_auth_dir()),
            "db_path": str(self.get_db_path()),
            "vault_root": str(self.get_vault_root()),
            "daily_notes": str(self.get_daily_notes_dir()),
            "ai_outputs": str(self.get_ai_outputs_dir()),
            "logs": str(self.get_logs_dir()),
            "logs_run": str(self.get_logs_dir() / "run-logs"),
            "logs_error": str(self.get_logs_dir() / "error-logs"),
            "evidence": str(self.get_evidence_dir()),
        }

    def ensure_db_ready(self, *, return_report: bool = False) -> None | dict[str, Any]:
        """Validate SQLite DB path readiness with actionable diagnostics."""
        app_support = self.get_app_support()
        db_path = self.get_db_path()
        db_parent = db_path.parent

        checks: dict[str, Any] = {
            "app_support_exists": app_support.exists(),
            "db_parent_exists": db_parent.exists(),
            "db_parent_is_dir": db_parent.is_dir() if db_parent.exists() else False,
            "db_parent_writable": os.access(db_parent, os.W_OK) if db_parent.exists() else False,
            "sqlite_openable": False,
            "wal_mode": None,
        }
        report: dict[str, Any] = {
            "ok": False,
            "status": "blocked_db_unavailable",
            "db_path": str(db_path),
            "db_parent": str(db_parent),
            "checks": checks,
            "repair_guidance": [
                f'mkdir -p "{db_parent}"',
                f'chmod u+rwx "{db_parent}"',
                f'# If ownership is wrong and local chmod fails: sudo chown -R $(whoami) "{app_support}"',
            ],
            "error": None,
        }

        if not checks["app_support_exists"]:
            report["error"] = "app_support_missing"
            return report if return_report else None

        if not checks["db_parent_exists"]:
            report["error"] = "db_parent_missing"
            return report if return_report else None

        if not checks["db_parent_is_dir"]:
            report["error"] = "db_parent_not_directory"
            return report if return_report else None

        if not checks["db_parent_writable"]:
            report["error"] = "db_parent_not_writable"
            return report if return_report else None

        conn = None
        try:
            conn = sqlite3.connect(str(db_path), timeout=5)
            checks["sqlite_openable"] = True
            try:
                wal = conn.execute("PRAGMA journal_mode = WAL").fetchone()
                wal_mode = str(wal[0]).lower() if wal and wal[0] is not None else "unknown"
                checks["wal_mode"] = wal_mode
            except Exception:
                checks["wal_mode"] = "degraded"
        except Exception as e:
            report["error"] = f"sqlite_open_failed: {e}"
            return report if return_report else None
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

        report["ok"] = True
        report["status"] = "ok"
        report["error"] = None
        return report if return_report else None
