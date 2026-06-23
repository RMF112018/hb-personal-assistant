"""Forecast runtime configuration wiring (Implementation Phase 6).

The five forecast UI surfaces (Phases 1-5) resolve their filesystem roots from environment
variables (``HB_FORECAST_*``) that are only ever set transiently in tests/smokes, so the live
app serves no real data. This module adds a persistent app-support JSON settings file as a third
resolution layer **behind** the env vars and provides:

  - per-root resolvers with precedence **explicit arg > env var > settings-file > managed_default >
    None** (env must win so every existing test that ``monkeypatch.setenv(...)`` then constructs a
    service with no args stays green);
  - ``build_runtime_status`` — a **redaction-safe** per-root status payload (booleans + coded
    enums only, never path strings, so it passes ``find_redaction_leaks``);
  - ``read_runtime_config_admin`` — the raw configured paths (admin-only echo; the single
    deliberate carve-out from the "no payload echoes paths" convention);
  - ``save_runtime_config`` — validates each supplied root and, critically, re-checks that the
    write-roots (runs/eval) are not under the **resolved** data root regardless of where the data
    root was resolved from (``resolve_eval_root`` only guards against the *env* data root, so a
    settings-file data root would otherwise be a blind spot), then persists. Fail-closed: it
    writes nothing if any check fails.

Validation here is intentionally **non-mutating** (no ``mkdir`` side effects on a status read);
the authoritative fail-closed enforcement still lives in the services at use-time.
"""

from __future__ import annotations

import contextlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.analytics.forecast_catalog import resolve_package_roots_from_env
from hb_assistant.construction.analytics.forecast_external_ingest import (
    ENV_DB_PATH,
    ENV_EVAL_ROOT,
)
from hb_assistant.construction.analytics.forecast_run_service import (
    ENV_CFR_SRC,
    ENV_DATA_ROOT,
    ENV_RUNS_ROOT,
)

_SURFACE = "analytics.forecast_runtime"
_CONFIG_NAME = "forecast_runtime_config.json"

# Phase E config-edit root. Defined here (the config module owns the resolution layer); the
# config-edit service imports this name so there is exactly one spelling. It is a WRITE root:
# isolated config-edit proposals are written under it, so it must be outside the live data root.
ENV_CONFIG_EDIT_ROOT = "HB_FORECAST_CONFIG_EDIT_ROOT"

# Phase E2 promotion opt-in (default OFF). A boolean flag (NOT a path root) that must be explicitly
# enabled before any config-edit proposal can be promoted to the live config DB.
ENV_PROMOTION_ENABLED = "HB_FORECAST_PROMOTION_ENABLED"

# DB-config-backed generation opt-in (default OFF). A boolean flag (NOT a path root) gating whether the
# Run Center may generate the comprehensive package CONSUMING the live DB config snapshot.
ENV_DB_CONFIG_RUN_ENABLED = "HB_FORECAST_DB_CONFIG_RUN_ENABLED"

# Assumption-consumption opt-in (default OFF). A boolean flag (NOT a path root) gating whether the
# decision-support engine CONSUMES operator/required assumptions (confidence modifiers + required gate).
ENV_ASSUMPTION_CONSUMPTION_ENABLED = "HB_FORECAST_ASSUMPTION_CONSUMPTION_ENABLED"
_TRUTHY = {"1", "true", "yes", "on"}

# Whitelisted keys. An unknown key in the on-disk file can never inject behaviour.
DEFAULT_CONFIG: dict[str, Any] = {
    "package_roots": [],  # list[str]; absolute existing dirs (read-only)
    "data_root": None,  # str|None; absolute, exists, is_dir
    "runs_root": None,  # str|None; absolute, creatable, MUST be outside data_root
    "eval_root": None,  # str|None; absolute, creatable, MUST be outside data_root
    "db_path": None,  # str|None; read-only source-domain DB; not write-guarded
    "cfr_src": None,  # str|None; absolute existing dir; optional (defaults to subrepo path)
    "config_edit_root": None,  # str|None; absolute, creatable, MUST be outside data_root (write)
    "promotion_enabled": False,  # bool flag (NOT a path); gates the Phase E2 live config promotion
    "db_config_run_enabled": False,  # bool flag (NOT a path); gates DB-config-backed comprehensive generation
    "assumption_consumption_enabled": False,  # bool flag (NOT a path); gates decision-support assumption consumption
    "schema_version": 1,  # LOCAL file version only — NOT the DB schema; do not conflate
}

# Coded blockers — path-free, so every status payload passes find_redaction_leaks.
BLOCKER_NOT_CONFIGURED = "not_configured"
BLOCKER_NOT_ABSOLUTE = "not_absolute"
BLOCKER_MISSING = "missing"
BLOCKER_NOT_A_DIRECTORY = "not_a_directory"
BLOCKER_UNDER_LIVE_DATA_ROOT = "under_live_data_root"
BLOCKER_NOT_CREATABLE = "not_creatable"


class ForecastRuntimeConfigError(RuntimeError):
    """Raised when a runtime-config write is refused. The message is a path-free blocker code."""


# -- settings file (mirrors daily_brief.py) -----------------------------------


_WRITABLE_KEYS = (
    "package_roots",
    "data_root",
    "runs_root",
    "eval_root",
    "db_path",
    "cfr_src",
    "config_edit_root",
)


def _config_path() -> Path:
    pp = PathPolicy()
    path = pp.get_forecast_runtime_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_config() -> dict[str, Any]:
    p = _config_path()
    cfg = dict(DEFAULT_CONFIG)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                # Whitelist-merge: only known keys, only when present.
                cfg.update({k: data[k] for k in cfg if k in data})
        except Exception:
            # Fail closed to defaults; never block resolution on a bad config file.
            pass
    return cfg


def _save_config(cfg: dict[str, Any]) -> None:
    p = _config_path()
    payload = {k: cfg.get(k, DEFAULT_CONFIG[k]) for k in DEFAULT_CONFIG}
    with contextlib.suppress(Exception):
        p.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


# -- helpers ------------------------------------------------------------------


def _first(*values: str | None) -> str | None:
    for v in values:
        if v:
            return v
    return None


def _is_under(child: Path, parent: Path) -> bool:
    try:
        c = child.resolve(strict=False)
        r = parent.resolve(strict=False)
        return c == r or c.is_relative_to(r)
    except OSError:
        return True  # fail closed


# -- managed defaults (app-support layout) --------------------------------------


def managed_forecast_paths() -> dict[str, Any]:
    """Canonical app-managed forecast paths (server-side only; never in status payloads)."""
    pp = PathPolicy()
    return {
        "package_roots": [str(pp.get_forecast_packages_dir())],
        "data_root": str(pp.get_forecast_data_dir()),
        "runs_root": str(pp.get_forecast_runs_dir()),
        "eval_root": str(pp.get_forecast_evaluations_dir()),
        "config_edit_root": str(pp.get_forecast_config_proposals_dir()),
        "db_path": str(pp.get_db_path()),
    }


def build_managed_defaults_payload() -> dict[str, Any]:
    """Settings-file payload for admin reset (path keys only)."""
    managed = managed_forecast_paths()
    return {k: managed[k] for k in _WRITABLE_KEYS if k in managed}


def _managed_package_roots() -> list[str]:
    return list(managed_forecast_paths()["package_roots"])


def _env_set(env_key: str) -> bool:
    val = os.environ.get(env_key)
    return val is not None and str(val).strip() != ""


def seed_runtime_config_if_incomplete() -> list[str]:
    """Persist app-managed defaults for roots missing from env and settings file."""
    cfg = _load_config()
    managed = managed_forecast_paths()
    seeded: list[str] = []

    if not _env_set("HB_FORECAST_PACKAGE_ROOTS"):
        env_roots = resolve_package_roots_from_env()
        if not env_roots and not [x for x in (cfg.get("package_roots") or []) if x]:
            cfg["package_roots"] = managed["package_roots"]
            seeded.append("package_roots")

    env_key_map = (
        (ENV_DATA_ROOT, "data_root"),
        (ENV_RUNS_ROOT, "runs_root"),
        (ENV_EVAL_ROOT, "eval_root"),
        (ENV_DB_PATH, "db_path"),
        (ENV_CONFIG_EDIT_ROOT, "config_edit_root"),
    )
    for env_key, cfg_key in env_key_map:
        if _env_set(env_key):
            continue
        if cfg.get(cfg_key):
            continue
        cfg[cfg_key] = managed[cfg_key]
        seeded.append(cfg_key)

    if seeded:
        cfg["schema_version"] = DEFAULT_CONFIG["schema_version"]
        _save_config(cfg)
    return seeded


def reset_runtime_config_to_managed_defaults() -> dict[str, Any]:
    """Overwrite settings-file path keys with app-managed defaults (env still wins at runtime)."""
    cfg = _load_config()
    managed = managed_forecast_paths()
    for key in _WRITABLE_KEYS:
        if key == "package_roots":
            cfg[key] = managed["package_roots"]
        elif key in managed:
            cfg[key] = managed[key]
        elif key == "cfr_src":
            cfg[key] = None
    cfg["schema_version"] = DEFAULT_CONFIG["schema_version"]
    _save_config(cfg)
    return build_runtime_status()


# -- resolvers (precedence: explicit > env > settings-file > managed_default) --


def resolve_package_roots(explicit: list[str] | None = None) -> list[str]:
    """Resolve the package roots. Reuses ``resolve_package_roots_from_env`` for the env layer."""
    if explicit:
        return [str(x) for x in explicit]
    env = resolve_package_roots_from_env()
    if env:
        return env
    settings = [str(x) for x in (_load_config().get("package_roots") or []) if x]
    if settings:
        return settings
    return _managed_package_roots()


def resolve_data_root(explicit: str | None = None) -> str | None:
    return _first(
        explicit,
        os.environ.get(ENV_DATA_ROOT),
        _load_config().get("data_root"),
        managed_forecast_paths()["data_root"],
    )


def resolve_runs_root(explicit: str | None = None) -> str | None:
    return _first(
        explicit,
        os.environ.get(ENV_RUNS_ROOT),
        _load_config().get("runs_root"),
        managed_forecast_paths()["runs_root"],
    )


def resolve_eval_root_value(explicit: str | None = None) -> str | None:
    return _first(
        explicit,
        os.environ.get(ENV_EVAL_ROOT),
        _load_config().get("eval_root"),
        managed_forecast_paths()["eval_root"],
    )


def resolve_db_path(explicit: str | None = None) -> str | None:
    return _first(
        explicit,
        os.environ.get(ENV_DB_PATH),
        _load_config().get("db_path"),
        managed_forecast_paths()["db_path"],
    )


def resolve_cfr_src(explicit: str | None = None) -> str | None:
    return _first(explicit, os.environ.get(ENV_CFR_SRC), _load_config().get("cfr_src"))


def resolve_config_edit_root_value(explicit: str | None = None) -> str | None:
    return _first(
        explicit,
        os.environ.get(ENV_CONFIG_EDIT_ROOT),
        _load_config().get("config_edit_root"),
        managed_forecast_paths()["config_edit_root"],
    )


def is_managed_db_path(db_path: str | None) -> bool:
    if not db_path:
        return False
    try:
        return Path(db_path).resolve() == PathPolicy().get_db_path().resolve()
    except OSError:
        return False


def resolve_promotion_enabled(explicit: bool | str | None = None) -> bool:
    """Resolve the Phase E2 promotion opt-in (explicit > env > settings-file > default False)."""
    if explicit is not None:
        return explicit is True or str(explicit).strip().lower() in _TRUTHY
    env = os.environ.get(ENV_PROMOTION_ENABLED)
    if env is not None:
        return env.strip().lower() in _TRUTHY
    return bool(_load_config().get("promotion_enabled"))


def resolve_db_config_run_enabled(explicit: bool | str | None = None) -> bool:
    """Resolve the DB-config-backed generation opt-in (explicit > env > settings-file > default False)."""
    if explicit is not None:
        return explicit is True or str(explicit).strip().lower() in _TRUTHY
    env = os.environ.get(ENV_DB_CONFIG_RUN_ENABLED)
    if env is not None:
        return env.strip().lower() in _TRUTHY
    return bool(_load_config().get("db_config_run_enabled"))


def resolve_assumption_consumption_enabled(explicit: bool | str | None = None) -> bool:
    """Resolve the assumption-consumption opt-in (explicit > env > settings-file > default False)."""
    if explicit is not None:
        return explicit is True or str(explicit).strip().lower() in _TRUTHY
    env = os.environ.get(ENV_ASSUMPTION_CONSUMPTION_ENABLED)
    if env is not None:
        return env.strip().lower() in _TRUTHY
    return bool(_load_config().get("assumption_consumption_enabled"))


# -- non-mutating validation (status + save) ----------------------------------


def _existing_dir_blocker(raw: str | None) -> str | None:
    """Blocker for a read root that must be an absolute, existing directory."""
    if not raw:
        return BLOCKER_NOT_CONFIGURED
    p = Path(raw)
    if not p.is_absolute():
        return BLOCKER_NOT_ABSOLUTE
    if not p.exists():
        return BLOCKER_MISSING
    if not p.is_dir():
        return BLOCKER_NOT_A_DIRECTORY
    return None


def _write_root_blocker(raw: str | None, data_root_raw: str | None) -> str | None:
    """Blocker for a write root: absolute, outside data_root, and creatable (no mkdir here)."""
    if not raw:
        return BLOCKER_NOT_CONFIGURED
    p = Path(raw)
    if not p.is_absolute():
        return BLOCKER_NOT_ABSOLUTE
    if data_root_raw and _is_under(p, Path(data_root_raw)):
        return BLOCKER_UNDER_LIVE_DATA_ROOT
    if p.exists():
        return None if p.is_dir() else BLOCKER_NOT_A_DIRECTORY
    # Not existing: creatable iff the nearest EXISTING ancestor is a writable directory. Walk up the
    # chain so a write root with missing-but-creatable parents (e.g. an auto-default under app-support
    # whose container does not exist yet) is correctly creatable — this mirrors mkdir(parents=True).
    ancestor = p.parent
    while not ancestor.exists() and ancestor.parent != ancestor:
        ancestor = ancestor.parent
    if ancestor.exists() and ancestor.is_dir() and os.access(ancestor, os.W_OK):
        return None
    return BLOCKER_NOT_CREATABLE


def _db_blocker(raw: str | None) -> str | None:
    if not raw:
        return BLOCKER_NOT_CONFIGURED
    return None if Path(raw).exists() else BLOCKER_MISSING


def _db_advisory(raw: str | None) -> dict[str, Any]:
    """Non-blocking, read-only advisory for a configured db_path.

    Returns INTEGERS ONLY (schema_version + config_snapshot_count) — never a path or snapshot name —
    so the status payload stays redaction-safe. Opens ``mode=ro`` and returns ``{}`` on ANY error
    (missing/locked/old-schema/config-tables-absent) so a bad DB never breaks the status read. Mirrors
    the proven probe in forecast_config_catalog (schema_migrations MAX(version) + config snapshot
    count) without importing the heavier catalog service.
    """
    if not raw:
        return {}
    p = Path(raw)
    if not p.exists():
        return {}
    try:
        conn = sqlite3.connect(f"{p.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error:
        return {}
    try:
        out: dict[str, Any] = {}
        try:
            row = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
        except sqlite3.Error:
            return {}  # not a recognizable HB DB → no advisory at all
        if row is not None and row[0] is not None:
            out["schema_version"] = int(row[0])
        with contextlib.suppress(sqlite3.Error):
            # config table may be absent on an older DB; omit the count rather than fail.
            crow = conn.execute("SELECT COUNT(*) FROM forecast_config_snapshots").fetchone()
            out["config_snapshot_count"] = int(crow[0]) if crow and crow[0] is not None else 0
        return out
    finally:
        conn.close()


def _source(
    env_val: Any,
    settings_val: Any,
    *,
    default: bool = False,
    managed: bool = False,
) -> str | None:
    if env_val:
        return "env"
    if settings_val:
        return "settings_file"
    if managed:
        return "managed_default"
    if default:
        return "default"
    return None


def _package_settings_nonempty(settings: list[str]) -> bool:
    return bool(settings)


def _settings_match_managed() -> dict[str, bool]:
    """Whether persisted settings-file values equal the canonical managed paths."""
    cfg = _load_config()
    managed = managed_forecast_paths()
    pkg = [str(x) for x in (cfg.get("package_roots") or []) if x]
    return {
        "package_roots": pkg == managed["package_roots"],
        "data_root": cfg.get("data_root") == managed["data_root"],
        "runs_root": cfg.get("runs_root") == managed["runs_root"],
        "eval_root": cfg.get("eval_root") == managed["eval_root"],
        "db_path": cfg.get("db_path") == managed["db_path"],
        "config_edit_root": cfg.get("config_edit_root") == managed["config_edit_root"],
    }


def _storage_mode(roots: dict[str, Any]) -> str:
    path_keys = (
        "package_roots",
        "data_root",
        "runs_root",
        "eval_root",
        "db_path",
        "config_edit_root",
    )
    managed_match = _settings_match_managed()

    def _is_app_managed(key: str) -> bool:
        source = roots.get(key, {}).get("source")
        if source == "managed_default":
            return True
        return source == "settings_file" and managed_match.get(key, False)

    if all(_is_app_managed(k) for k in path_keys):
        return "app_managed"
    if any(roots.get(k, {}).get("source") == "env" for k in path_keys):
        return "custom"
    if any(
        roots.get(k, {}).get("source") == "settings_file" and not managed_match.get(k, False)
        for k in path_keys
    ):
        return "custom"
    return "app_managed"


# -- status (redaction-safe) --------------------------------------------------


def build_runtime_status() -> dict[str, Any]:
    """Per-root resolved/valid/blocker booleans + coded enums. Never emits a path string."""
    cfg = _load_config()

    pkg_env = resolve_package_roots_from_env()
    pkg_settings = [str(x) for x in (cfg.get("package_roots") or []) if x]
    pkg_managed = _managed_package_roots()
    pkg_raw = pkg_env or pkg_settings or pkg_managed
    pkg_blocker = (
        BLOCKER_NOT_CONFIGURED
        if not pkg_raw
        else next((b for b in (_existing_dir_blocker(r) for r in pkg_raw) if b), None)
    )
    pkg_using_managed = not pkg_env and not _package_settings_nonempty(pkg_settings)

    data_env, data_settings = os.environ.get(ENV_DATA_ROOT), cfg.get("data_root")
    data_raw = resolve_data_root()
    runs_env, runs_settings = os.environ.get(ENV_RUNS_ROOT), cfg.get("runs_root")
    runs_raw = resolve_runs_root()
    eval_env, eval_settings = os.environ.get(ENV_EVAL_ROOT), cfg.get("eval_root")
    eval_raw = resolve_eval_root_value()
    db_env, db_settings = os.environ.get(ENV_DB_PATH), cfg.get("db_path")
    db_raw = resolve_db_path()
    cfr_env, cfr_settings = os.environ.get(ENV_CFR_SRC), cfg.get("cfr_src")
    cfr_raw = _first(cfr_env, cfr_settings)
    cedit_env, cedit_settings = os.environ.get(ENV_CONFIG_EDIT_ROOT), cfg.get("config_edit_root")
    cedit_raw = resolve_config_edit_root_value()

    data_blocker = _existing_dir_blocker(data_raw)
    runs_blocker = _write_root_blocker(runs_raw, data_raw)
    eval_blocker = _write_root_blocker(eval_raw, data_raw)
    db_blocker = _db_blocker(db_raw)
    # cfr_src is optional: unset means "use the bundled subrepo default" (valid).
    cfr_blocker = _existing_dir_blocker(cfr_raw) if cfr_raw else None
    config_edit_blocker = _write_root_blocker(cedit_raw, data_raw)

    def _root(blocker: str | None, source: str | None, **extra: Any) -> dict[str, Any]:
        return {
            "configured": source is not None,
            "valid": blocker is None,
            "source": source,
            "blocker": blocker,
            **extra,
        }

    roots = {
        "package_roots": _root(
            pkg_blocker,
            _source(pkg_env, pkg_settings, managed=pkg_using_managed),
            count=len(pkg_raw),
        ),
        "data_root": _root(
            data_blocker,
            _source(data_env, data_settings, managed=not data_env and not data_settings),
        ),
        "runs_root": _root(
            runs_blocker,
            _source(runs_env, runs_settings, managed=not runs_env and not runs_settings),
        ),
        "eval_root": _root(
            eval_blocker,
            _source(eval_env, eval_settings, managed=not eval_env and not eval_settings),
        ),
        # db_path carries a redaction-safe advisory (ints only) so onboarding can confirm the DB
        # actually holds config content, not just that the file exists.
        "db_path": _root(
            db_blocker,
            _source(db_env, db_settings, managed=not db_env and not db_settings),
            **_db_advisory(db_raw),
        ),
        "cfr_src": _root(cfr_blocker, _source(cfr_env, cfr_settings, default=True)),
        "config_edit_root": _root(
            config_edit_blocker,
            _source(cedit_env, cedit_settings, managed=not cedit_env and not cedit_settings),
        ),
    }

    surfaces_ready = {
        "catalog": pkg_blocker is None,
        "config": db_blocker is None,
        "run_center": data_blocker is None and runs_blocker is None and cfr_blocker is None,
        "external_eval": (
            pkg_blocker is None and eval_blocker is None and db_blocker is None
        ),
        # Config-edit proposals seed from the live DB (db_path) and write under config_edit_root.
        "config_edit": config_edit_blocker is None and db_blocker is None,
        # Config promotion (Phase E2) additionally requires the explicit opt-in (default OFF).
        "config_promotion": (
            config_edit_blocker is None and db_blocker is None and resolve_promotion_enabled()
        ),
        # DB-config-backed generation: comprehensive consumes the live config snapshot (held in the
        # live app DB, not the runtime db_path). Needs the data root (predecessor packages) + engine
        # valid AND the explicit opt-in (default OFF).
        "db_config_run": (
            data_blocker is None and cfr_blocker is None and resolve_db_config_run_enabled()
        ),
    }

    return {
        "surface": _SURFACE,
        "storage_mode": _storage_mode(roots),
        "roots": roots,
        "surfaces_ready": surfaces_ready,
        "promotion": {"enabled": resolve_promotion_enabled()},
        "db_config_run": {"enabled": resolve_db_config_run_enabled()},
        "guardrails": {
            "read_only": True,
            "local_first": True,
            "no_path_strings_in_status": True,
            "settings_layer_behind_env": True,
            "managed_defaults_available": True,
        },
    }


# -- admin echo (carve-out: DOES return raw paths) ----------------------------


def read_runtime_config_admin() -> dict[str, Any]:
    """Return the raw configured paths so an admin can read/edit current values.

    This is the single deliberate exception to the "no payload echoes paths" convention and is
    why the route is admin-gated.
    """
    cfg = _load_config()
    return {
        "surface": _SURFACE,
        "config": {k: cfg.get(k, DEFAULT_CONFIG[k]) for k in DEFAULT_CONFIG},
        "config_file_present": _config_path().exists(),
    }


# -- write (fail-closed) ------------------------------------------------------


def save_runtime_config(updates: dict[str, Any]) -> dict[str, Any]:
    """Validate the supplied roots, re-check write-roots vs the resolved data root, then persist.

    Raises ``ForecastRuntimeConfigError`` (path-free blocker code) and writes nothing on any
    failure. Returns the redaction-safe status on success (never echoes the submitted paths).
    """
    cfg = _load_config()
    # Overlay only whitelisted, supplied keys.
    for key in _WRITABLE_KEYS:
        if key in updates and updates[key] is not None:
            cfg[key] = updates[key]
    # Boolean flags (not path roots → no path validation). Phase E2 promotion opt-in.
    if "promotion_enabled" in updates and updates["promotion_enabled"] is not None:
        cfg["promotion_enabled"] = bool(
            updates["promotion_enabled"] is True
            or str(updates["promotion_enabled"]).strip().lower() in _TRUTHY
        )
    if "db_config_run_enabled" in updates and updates["db_config_run_enabled"] is not None:
        cfg["db_config_run_enabled"] = bool(
            updates["db_config_run_enabled"] is True
            or str(updates["db_config_run_enabled"]).strip().lower() in _TRUTHY
        )
    if (
        "assumption_consumption_enabled" in updates
        and updates["assumption_consumption_enabled"] is not None
    ):
        cfg["assumption_consumption_enabled"] = bool(
            updates["assumption_consumption_enabled"] is True
            or str(updates["assumption_consumption_enabled"]).strip().lower() in _TRUTHY
        )

    # Effective data root for the write-root cross-check (settings value, since this is the
    # persisted config; env is a per-process override that must not weaken the persisted guard).
    data_raw = cfg.get("data_root")

    def _refuse(root: str, blocker: str | None) -> None:
        if blocker is not None:
            raise ForecastRuntimeConfigError(f"{root}:{blocker}")

    pkg = [str(x) for x in (cfg.get("package_roots") or []) if x]
    for r in pkg:
        _refuse("package_roots", _existing_dir_blocker(r))
    if cfg.get("data_root"):
        _refuse("data_root", _existing_dir_blocker(cfg.get("data_root")))
    if cfg.get("runs_root"):
        # The critical cross-check: refuse a runs root under the resolved data root regardless of
        # where data_root came from (closes the resolve_eval_root env-only blind spot).
        _refuse("runs_root", _write_root_blocker(cfg.get("runs_root"), data_raw))
    if cfg.get("eval_root"):
        _refuse("eval_root", _write_root_blocker(cfg.get("eval_root"), data_raw))
    if cfg.get("config_edit_root"):
        # Same write-root cross-check: a config-edit root must not sit under the data root.
        _refuse("config_edit_root", _write_root_blocker(cfg.get("config_edit_root"), data_raw))
    if cfg.get("db_path"):
        _refuse("db_path", _db_blocker(cfg.get("db_path")))
    if cfg.get("cfr_src"):
        _refuse("cfr_src", _existing_dir_blocker(cfg.get("cfr_src")))

    cfg["schema_version"] = DEFAULT_CONFIG["schema_version"]
    _save_config(cfg)
    return build_runtime_status()
