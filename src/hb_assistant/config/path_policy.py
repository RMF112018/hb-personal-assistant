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
import stat
from pathlib import Path
from typing import Optional

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

    def ensure_dirs(self, *, create_sensitive: bool = True) -> None:
        """Create the standard directory tree.

        Sensitive directories (auth, evidence if it will hold private) get 0o700.
        """
        dirs_700 = [
            self.get_app_support(),
            self.get_auth_dir(),
            self.get_evidence_dir(),  # evidence may contain sanitized + private/ subdir
            self.get_logs_dir(),
        ]
        dirs_755 = [
            self.get_app_support() / "db",
            self.get_app_support() / "cache",
            self.get_cache_dir("files"),
            self.get_cache_dir("extracted-text"),
            self.get_cache_dir("embeddings"),
        ]

        for d in dirs_700:
            d.mkdir(parents=True, exist_ok=True)
            if create_sensitive:
                os.chmod(d, 0o700)

        for d in dirs_755:
            d.mkdir(parents=True, exist_ok=True)
            # default umask usually fine; explicit 0o755 for clarity on non-sensitive
            try:
                os.chmod(d, 0o755)
            except PermissionError:
                pass  # best effort

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
            "evidence": str(self.get_evidence_dir()),
        }
