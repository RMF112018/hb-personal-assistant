"""Read CFR run-lineage state (``.cfr_run_state``) as plain JSON.

A full-fresh forecast run mints ``.cfr_run_state/full_fresh_<project>_<run_id>.json``
and a ``.cfr_run_state/current_<project>.json`` visibility pointer. This module reads
those files without importing the construction-financial-review package, so the
projection layer stays decoupled from the subrepo.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def state_dir(subproject_root: Path) -> Path:
    """Return the ``.cfr_run_state`` directory under a CFR subproject root."""
    return Path(subproject_root) / ".cfr_run_state"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"run-state file is not a JSON object: {path}")
    return data


def active_run_state_path(subproject_root: Path, project_key: str) -> Path | None:
    """Resolve the active full-fresh run-state path via the ``current_<project>`` pointer.

    Returns ``None`` when no pointer exists. Raises if the pointer is present but
    references a missing run-state file (a corrupt/stale lineage pointer is a real error).
    """
    pointer = state_dir(subproject_root) / f"current_{project_key}.json"
    if not pointer.exists():
        return None
    active = _load_json(pointer).get("active_run_state")
    if not active:
        return None
    path = Path(active)
    if not path.exists():
        raise FileNotFoundError(
            f"current_{project_key}.json points to a missing run-state file: {path}"
        )
    return path


def read_run_state(path: Path) -> dict[str, Any]:
    """Load a specific ``full_fresh_<project>_<run_id>.json`` state file.

    Returns a normalized dict: ``run_id``, ``project_key``, ``run_started_at_utc``,
    ``data_root``, and ``packages`` (mapping ptype -> ``{"path", "stamp"}``).
    """
    raw = _load_json(path)
    packages_raw = raw.get("packages") or {}
    packages: dict[str, dict[str, Any]] = {}
    for ptype, rec in packages_raw.items():
        if isinstance(rec, dict) and rec.get("path"):
            packages[str(ptype)] = {"path": str(rec["path"]), "stamp": rec.get("stamp")}
    return {
        "run_id": raw.get("run_id"),
        "project_key": raw.get("project_key"),
        "run_started_at_utc": raw.get("run_started_at_utc"),
        "data_root": raw.get("data_root"),
        "packages": packages,
        "state_path": str(path),
    }


def resolve_run_state(
    *,
    subproject_root: Path | None = None,
    project_key: str | None = None,
    run_state_path: Path | None = None,
) -> dict[str, Any] | None:
    """Resolve a run-state from an explicit path or the active pointer.

    Precedence: explicit ``run_state_path`` wins; otherwise the active
    ``current_<project>`` pointer under ``subproject_root``. Returns ``None`` when
    neither is available.
    """
    if run_state_path is not None:
        return read_run_state(Path(run_state_path))
    if subproject_root is not None and project_key:
        active = active_run_state_path(Path(subproject_root), project_key)
        if active is not None:
            return read_run_state(active)
    return None
