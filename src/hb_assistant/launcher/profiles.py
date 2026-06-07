"""Environment profiles (dev / production) with strict path isolation.

Production uses the configured app-support root. Dev uses a SEPARATE root named
``<root> (Dev)`` with its own DB / logs / evidence / cache / scheduler-state /
launcher-state. A collision guard raises if dev and production ever resolve to the
same DB or app-support path.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from hb_assistant.config.loader import load_config
from hb_assistant.config.models import AppConfig, LauncherEnvConfig, SchedulerConfig
from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.launcher.models import Environment
from hb_assistant.source_refresh.orchestrator import _safe_git_sha
from hb_assistant.store.migrator import SQLiteMigrator

DEFAULT_FRONTEND_URL = "http://127.0.0.1:5173"


class ProfileCollisionError(ValueError):
    """Raised when dev and production resolve to the same DB / app-support path."""


@dataclass(frozen=True)
class Profile:
    """Resolved per-environment paths, modes, and live-read policy."""

    environment: Environment
    app_support_root: Path
    db_path: Path
    log_path: Path
    evidence_path: Path
    cache_path: Path
    scheduler_state_path: Path
    launcher_session_path: Path
    frontend_mode: str
    backend_mode: str
    source_refresh_mode: str
    mcp_mode: str
    scheduler_enabled: bool
    scheduler: SchedulerConfig
    path_policy: PathPolicy
    frontend_url: str = "http://127.0.0.1:5173"
    frontend_url_source: str = "fallback"
    frontend_open_timeout_seconds: int = 30
    frontend_display_name: str = "HB Assistant"
    frontend_alias_url: str | None = None

    @property
    def mock_data(self) -> bool:
        """Dev always runs source refresh in local/mock mode."""
        return self.environment == "dev"

    def summary(self) -> dict[str, Any]:
        return {
            "environment": self.environment,
            "app_support_root": _redact(self.app_support_root),
            "db_path": _redact(self.db_path),
            "log_path": _redact(self.log_path),
            "evidence_path": _redact(self.evidence_path),
            "scheduler_state_path": _redact(self.scheduler_state_path),
            "launcher_session_path": _redact(self.launcher_session_path),
            "frontend_mode": self.frontend_mode,
            "backend_mode": self.backend_mode,
            "source_refresh_mode": self.source_refresh_mode,
            "mcp_mode": self.mcp_mode,
            "scheduler_enabled": self.scheduler_enabled,
            "frontend_url": self.frontend_url,
            "frontend_url_source": self.frontend_url_source,
            "frontend_open_timeout_seconds": self.frontend_open_timeout_seconds,
            "frontend_display_name": self.frontend_display_name,
            "frontend_alias_url": self.frontend_alias_url,
        }


def _redact(p: Path) -> str:
    text = str(p)
    home = str(Path.home())
    return text.replace(home, "~") if text.startswith(home) else text


def _dev_root(prod_root: Path) -> Path:
    return prod_root.parent / f"{prod_root.name} (Dev)"


def _resolve_frontend_url(launcher_env: LauncherEnvConfig) -> tuple[str, str]:
    """Resolve (frontend_url, source) for an environment from launcher config.

    Returns the configured URL with source ``"config"`` when set, else the
    Vite/static default with source ``"fallback"``. A CLI ``--frontend-url`` override
    (source ``"cli"``) is applied later in the launcher service, not here.
    """
    if launcher_env.frontend_url:
        return launcher_env.frontend_url, "config"
    return DEFAULT_FRONTEND_URL, "fallback"


def _build_profile(
    environment: Environment,
    pp: PathPolicy,
    scheduler: SchedulerConfig,
    launcher_env: LauncherEnvConfig,
) -> Profile:
    root = pp.get_app_support()
    frontend_url, frontend_url_source = _resolve_frontend_url(launcher_env)
    display_name = launcher_env.frontend_display_name or (
        "HB Assistant (Dev)" if environment == "dev" else "HB Assistant"
    )
    return Profile(
        environment=environment,
        app_support_root=root,
        db_path=pp.get_db_path(),
        log_path=pp.get_logs_dir(),
        evidence_path=pp.get_evidence_dir(),
        cache_path=pp.get_cache_dir("launcher"),
        scheduler_state_path=root / "scheduler-state" / "daily-source-refresh.json",
        launcher_session_path=root / "launcher-state" / f"session-{environment}.json",
        frontend_mode="npm_dev" if environment == "dev" else "static_dist",
        backend_mode=f"uvicorn_factory_{environment}",
        source_refresh_mode="mock_data" if environment == "dev" else "local_or_gated_live",
        mcp_mode="stdio",
        scheduler_enabled=scheduler.enabled,
        scheduler=scheduler,
        path_policy=pp,
        frontend_url=frontend_url,
        frontend_url_source=frontend_url_source,
        frontend_open_timeout_seconds=launcher_env.frontend_open_timeout_seconds,
        frontend_display_name=display_name,
        frontend_alias_url=launcher_env.frontend_alias_url,
    )


def resolve_profile(environment: Environment, *, config: Optional[AppConfig] = None) -> Profile:
    """Resolve a Profile, enforcing strict dev/production isolation."""
    cfg = config or load_config()
    prod_pp = PathPolicy(config=cfg)
    prod_root = prod_pp.get_app_support()
    dev_root = _dev_root(prod_root)

    # Strict isolation guard — dev and production must never share a root/DB.
    if dev_root == prod_root:
        raise ProfileCollisionError(f"dev/production app-support collision: {prod_root}")

    if environment == "production":
        pp = prod_pp
    else:
        dev_cfg = cfg.model_copy(deep=True)
        dev_cfg.paths.application_support_root = str(dev_root)
        pp = PathPolicy(config=dev_cfg)
        if pp.get_db_path() == prod_pp.get_db_path():
            raise ProfileCollisionError("dev/production DB path collision")

    launcher_env = cfg.launcher.dev if environment == "dev" else cfg.launcher.production
    return _build_profile(environment, pp, cfg.automation.scheduler, launcher_env)


def _open_ro_count(conn: sqlite3.Connection, table: str) -> int:
    try:
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()  # noqa: S608 — fixed table
        return int(row[0]) if row else 0
    except sqlite3.Error:
        return 0


def snapshot_source_db(
    dev_profile: Profile, *, source_db: Path, confirm: bool, tables: Optional[list[str]] = None
) -> dict[str, Any]:
    """Copy the current source SQLite into the Dev profile DB (never mutating source).

    Requires ``confirm`` to overwrite an existing Dev DB. Emits a metadata-only
    snapshot receipt (no row data). Refuses to run against a non-dev profile.
    """
    if dev_profile.environment != "dev":
        raise ProfileCollisionError("snapshot_source_db only targets the dev profile")
    source_db = Path(source_db)
    dest = dev_profile.db_path
    if not source_db.exists():
        return {"status": "source_missing", "source_db": _redact(source_db)}
    if dest.exists() and not confirm:
        return {
            "status": "confirmation_required",
            "dev_db": _redact(dest),
            "exists": True,
            "hint": "re-run with --confirm to overwrite the existing Dev DB",
        }

    dest.parent.mkdir(parents=True, exist_ok=True)
    # Read-only source URI + SQLite backup API ⇒ the source file is never written.
    src = sqlite3.connect(f"file:{source_db}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(str(dest))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    counts: dict[str, int] = {}
    if tables:
        ro = sqlite3.connect(f"file:{dest}?mode=ro", uri=True)
        try:
            counts = {t: _open_ro_count(ro, t) for t in tables}
        finally:
            ro.close()

    receipt: dict[str, Any] = {
        "command": "launcher snapshot-dev-db",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "repo_sha": _safe_git_sha(),
        "status": "ok",
        "source_db_path": _redact(source_db),
        "dev_db_path": _redact(dest),
        "source_size_bytes": source_db.stat().st_size,
        "dev_size_bytes": dest.stat().st_size,
        "source_schema_version": _schema_version(source_db),
        "dev_schema_version": _schema_version(dest),
        "table_row_counts": counts,
        "source_mutated": False,
        "metadata_only": True,
    }
    out_dir = dev_profile.evidence_path / "snapshot"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "snapshot-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True))
    return receipt


def _schema_version(db: Path) -> int:
    try:
        return int(SQLiteMigrator(db).current_version())
    except Exception:
        return 0
