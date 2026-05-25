"""TokenCacheManager: MSAL serializable cache persistence for delegated + app-only.

Exact files per 04 spec:
  ~/Library/Application Support/HB Personal Assistant/auth/msal-token-cache.bin
  ~/Library/Application Support/HB Personal Assistant/auth/msal-token-cache-app.bin

Permissions: 700 on auth dir (via PathPolicy), 600 on cache files.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any, Dict, List, Optional

import msal  # type: ignore

from hb_assistant.config.path_policy import PathPolicy

from .exceptions import TokenCacheError


class TokenCacheManager:
    """Manages two isolated MSAL SerializableTokenCache files with strict perms."""

    DELEGATED_CACHE = "msal-token-cache.bin"
    APPONLY_CACHE = "msal-token-cache-app.bin"

    def __init__(self, path_policy: Optional[PathPolicy] = None) -> None:
        self._pp = path_policy or PathPolicy()
        self._auth_dir = self._pp.get_auth_dir()
        self._pp.ensure_dirs(create_sensitive=True)

    def _cache_path(self, app_only: bool = False) -> Path:
        name = self.APPONLY_CACHE if app_only else self.DELEGATED_CACHE
        return self._auth_dir / name

    def _enforce_file_perms(self, path: Path) -> None:
        if path.exists():
            try:
                os.chmod(path, 0o600)
            except OSError as e:
                raise TokenCacheError(f"Failed to chmod 600 {path}: {e}") from e

    def load_cache(self, app_only: bool = False) -> msal.SerializableTokenCache:
        """Load (or create empty) a SerializableTokenCache for the given mode."""
        cache = msal.SerializableTokenCache()
        p = self._cache_path(app_only)
        if p.exists():
            try:
                with p.open("r", encoding="utf-8") as f:
                    cache.deserialize(f.read())
            except Exception as e:
                raise TokenCacheError(f"Failed to load cache {p}: {e}") from e
        return cache

    def save_cache(self, cache: msal.SerializableTokenCache, app_only: bool = False) -> None:
        """Persist if dirty, then enforce 600."""
        if not cache.has_state_changed:
            return
        p = self._cache_path(app_only)
        try:
            with p.open("w", encoding="utf-8") as f:
                f.write(cache.serialize())
            self._enforce_file_perms(p)
        except Exception as e:
            raise TokenCacheError(f"Failed to save cache {p}: {e}") from e

    def clear_cache(self, app_only: Optional[bool] = None) -> List[str]:
        """Delete cache file(s). Returns list of deleted paths (for status/evidence)."""
        deleted: List[str] = []
        targets = [self._cache_path(False), self._cache_path(True)] if app_only is None else [self._cache_path(app_only)]
        for p in targets:
            if p.exists():
                try:
                    p.unlink()
                    deleted.append(str(p))
                except Exception as e:
                    raise TokenCacheError(f"Failed to clear {p}: {e}") from e
        return deleted

    def get_accounts(self, app_only: bool = False) -> List[Dict[str, Any]]:
        """Return list of accounts known to the cache (safe fields only)."""
        cache = self.load_cache(app_only)
        # MSAL exposes accounts via the cache state; we avoid loading full app here.
        # Parse minimally from serialized if needed, but for Phase 2 we return empty or basic.
        # Real account listing is done via the provider after acquire.
        return []

    def check_permissions(self) -> Dict[str, Any]:
        """Return permission status for the two cache files (used by diagnostics)."""
        info: Dict[str, Any] = {}
        for name, app_only in [(self.DELEGATED_CACHE, False), (self.APPONLY_CACHE, True)]:
            p = self._cache_path(app_only)
            exists = p.exists()
            mode = None
            ok = False
            if exists:
                try:
                    st = os.stat(p)
                    mode = oct(stat.S_IMODE(st.st_mode))
                    ok = (stat.S_IMODE(st.st_mode) & 0o777) == 0o600
                except Exception:
                    pass
            info[name] = {"exists": exists, "mode": mode, "perms_ok": ok, "path": str(p)}
        return info
