"""DB path resolution diagnostics for schedule evidence runs."""

from __future__ import annotations

import os
from typing import Any

from hb_assistant.config.path_policy import PathPolicy


def evidence_disable_background_workers() -> bool:
    return os.environ.get("HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS", "").strip() == "1"


def evidence_diagnostics_enabled(role: dict[str, str] | None = None) -> bool:
    if os.environ.get("HB_EVIDENCE_DIAGNOSTICS", "").strip() == "1":
        return True
    if role and role.get("role") in {"operator", "admin"}:
        return True
    return False


def resolve_schedule_db_paths(app_state_db_path: str | None) -> dict[str, Any]:
    policy_path = str(PathPolicy().get_db_path())
    if app_state_db_path:
        resolution = "app_state"
        resolved = str(app_state_db_path)
    else:
        resolution = "path_policy"
        resolved = policy_path
    return {
        "resolved_db_path": resolved,
        "app_state_db_path": app_state_db_path,
        "path_policy_db_path": policy_path,
        "schedule_route_db_resolution": resolution,
    }


def build_db_diagnostics(
    app_state_db_path: str | None,
    *,
    requested_clean_copy: str | None = None,
    role: dict[str, str] | None = None,
    background_worker_mode: str = "enabled",
    background_workers_disabled_by_env: bool = False,
    background_workers: dict[str, bool] | None = None,
) -> dict[str, Any]:
    paths = resolve_schedule_db_paths(app_state_db_path)
    out: dict[str, Any] = {
        **paths,
        "background_worker_mode": background_worker_mode,
        "background_workers_disabled_by_env": background_workers_disabled_by_env,
    }
    if background_workers is not None:
        out["background_workers"] = background_workers
    if requested_clean_copy is not None:
        try:
            out["db_path_matches_requested_clean_copy"] = (
                str(Path(requested_clean_copy).expanduser().resolve())
                == str(paths["resolved_db_path"])
            )
        except Exception:
            out["db_path_matches_requested_clean_copy"] = False
    if not evidence_diagnostics_enabled(role):
        # PM-safe default: omit path fields unless diagnostics enabled.
        return {
            "background_worker_mode": background_worker_mode,
            "background_workers_disabled_by_env": background_workers_disabled_by_env,
            **({"background_workers": background_workers} if background_workers else {}),
        }
    if requested_clean_copy is not None and "db_path_matches_requested_clean_copy" not in out:
        out["db_path_matches_requested_clean_copy"] = False
    return out
