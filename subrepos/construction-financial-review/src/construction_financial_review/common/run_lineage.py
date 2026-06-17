"""Full-fresh-run lineage state for the core analysis/crosswalk chain.

A full fresh run mints a run-specific state file (`.cfr_run_state/full_fresh_<project>_<run_id>.json`)
and exports its path as `CFR_RUN_LINEAGE_STATE`. Each early stage (run-analysis / run-mapping-workpaper /
run-crosswalk-v2) resolves its upstream packages from that state at RUNTIME (never at import) so the
analysis chain automatically carries the fresh upstream lineage without any manual stamp arguments.

Strict rule while a run state is active: consume upstream ONLY from the state (or an explicit debug
override); a missing required upstream fails closed — never fall back to latest-glob, never to the stale
named packages in config, never to hardcoded package paths.
"""
from __future__ import annotations

import os
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .io import read_json, write_json

ENV_STATE = "CFR_RUN_LINEAGE_STATE"
STATE_DIR_NAME = ".cfr_run_state"

# package-type -> (exact-prefix builder, extra exclude substring for the glob, optional required marker file)
_PTYPES = ("context", "analysis", "mapping_workpaper", "crosswalk_v2")


def _prefix(ptype: str, project_key: str) -> str:
    if ptype == "context":
        return f"forecast_context_package_{project_key}_"
    if ptype == "analysis":
        return f"forecast_analysis_package_{project_key}_"
    if ptype == "mapping_workpaper":
        return f"mapping_discrepancy_workpaper_{project_key}_"
    if ptype == "crosswalk_v2":
        return f"forecast_analysis_package_{project_key}_crosswalk_v2_"
    raise ValueError(f"unknown package type: {ptype}")


def _matches(ptype: str, name: str, project_key: str) -> bool:
    """A dir name belongs to ptype. `analysis` excludes the crosswalk_v2 variant (shared prefix)."""
    if not name.startswith(_prefix(ptype, project_key)):
        return False
    if ptype == "analysis" and "_crosswalk_v2_" in name:
        return False
    return True


def stamp_of(pkg: Path) -> Optional[str]:
    parts = pkg.name.split("_")
    return "_".join(parts[-2:]) if len(parts) >= 2 else None


def _latest_of(data_root: Path, ptype: str, project_key: str) -> Optional[Path]:
    cands = sorted(p for p in Path(data_root).glob(_prefix(ptype, project_key) + "*")
                   if p.is_dir() and _matches(ptype, p.name, project_key))
    return cands[-1] if cands else None


# --------------------------------------------------------------------------- state file lifecycle

def state_dir(subproject_root) -> Path:
    return Path(subproject_root) / STATE_DIR_NAME


def new_run_state_path(subproject_root, project_key: str, run_id: str) -> Path:
    return state_dir(subproject_root) / f"full_fresh_{project_key}_{run_id}.json"


def start_run_state(project_key: str, data_root, run_id: str, *, path: Path) -> Path:
    """Write a fresh run-specific state file (and a `current_<project>` visibility pointer)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    state = OrderedDict([
        ("project_key", project_key),
        ("run_started_at_utc", datetime.now(timezone.utc).isoformat()),
        ("run_id", run_id),
        ("data_root", str(data_root)),
        ("packages", OrderedDict()),
    ])
    write_json(path, state)
    # visibility pointer only — NOT the authoritative active source (env var points at the run file)
    write_json(path.parent / f"current_{project_key}.json",
               OrderedDict([("active_run_state", str(path)), ("run_id", run_id)]))
    return path


def load_state(path) -> Optional[dict]:
    path = Path(path)
    return read_json(path) if path.exists() else None


def active_state_path() -> Optional[Path]:
    v = os.environ.get(ENV_STATE)
    return Path(v) if v else None


def active_state() -> Optional[dict]:
    p = active_state_path()
    return load_state(p) if p else None


def active_data_root(default) -> Path:
    """Data root from the active run state when present, else the provided default (no FS access)."""
    st = active_state()
    if st and st.get("data_root"):
        return Path(st["data_root"])
    return Path(default)


def record_latest(path, ptype: str, *, project_key: str) -> "OrderedDict":
    """Detect the newest package of `ptype` under the state's data root, VALIDATE it, and record it.

    Fail closed (SystemExit) unless: it exists, the name matches the ptype prefix, its stamp is >= the
    run's run_id (rejects pre-run/stale packages), it carries a validation_report.json, and it is under
    the state's configured data_root.
    """
    if ptype not in _PTYPES:
        raise SystemExit(f"ERROR: unknown lineage package type: {ptype}")
    state = load_state(path)
    if state is None:
        raise SystemExit(f"ERROR: run lineage state not found: {path}")
    data_root = Path(state["data_root"])
    run_id = state["run_id"]
    pkg = _latest_of(data_root, ptype, project_key)
    if pkg is None or not pkg.is_dir():
        raise SystemExit(f"ERROR: no {ptype} package found under {data_root} to record")
    if not _matches(ptype, pkg.name, project_key):
        raise SystemExit(f"ERROR: detected package {pkg.name} does not match {ptype} prefix")
    try:
        pkg.resolve().relative_to(data_root.resolve())
    except ValueError:
        raise SystemExit(f"ERROR: {pkg} is not under the run data root {data_root}")
    stamp = stamp_of(pkg)
    if stamp is None or stamp < run_id:
        raise SystemExit(
            f"ERROR: {ptype} package {pkg.name} (stamp {stamp}) predates run {run_id} — refusing stale record")
    if not (pkg / "validation_report.json").exists():
        raise SystemExit(f"ERROR: {ptype} package {pkg.name} missing validation_report.json")
    state.setdefault("packages", OrderedDict())[ptype] = OrderedDict([
        ("path", str(pkg)), ("stamp", stamp)])
    write_json(Path(path), state)
    return state["packages"][ptype]


# --------------------------------------------------------------------------- upstream resolution

def resolve_upstream(ptype: str, *, data_root, project_key: str, override_stamp: Optional[str] = None,
                     required: bool = True):
    """Return (package_path, lineage_meta). Pure given args — only touches the filesystem when called.

    Precedence: (1) explicit override stamp [debug/dev], (2) active run state, (3) latest-glob (only when
    no active state). Fails closed on a strict miss; never falls back to config names or hardcoded paths.
    """
    if ptype not in _PTYPES:
        raise SystemExit(f"ERROR: unknown lineage package type: {ptype}")

    def _meta(pkg: Optional[Path], source: str) -> "OrderedDict":
        return OrderedDict([
            ("package_type", ptype),
            ("consumed_package", pkg.name if pkg else None),
            ("consumed_stamp", stamp_of(pkg) if pkg else None),
            ("consumed_path", str(pkg) if pkg else None),
            ("lineage_source", source),
        ])

    # (1) explicit override — debug/developer only
    if override_stamp:
        pinned = Path(data_root) / f"{_prefix(ptype, project_key)}{override_stamp}"
        if pinned.is_dir():
            return pinned, _meta(pinned, "explicit_override")
        raise SystemExit(f"ERROR: pinned {ptype} package not found: {pinned.name} under {data_root}")

    # (2) active full-fresh run state — strict, no fallback
    st = active_state()
    if st is not None:
        rec = (st.get("packages") or {}).get(ptype)
        if rec and rec.get("path") and Path(rec["path"]).is_dir():
            return Path(rec["path"]), _meta(Path(rec["path"]), "full_fresh_run_state")
        if required:
            raise SystemExit(
                f"ERROR: active full-fresh run state has no recorded {ptype} package "
                f"(state={active_state_path()}); refusing latest-glob/stale fallback")
        return None, _meta(None, "full_fresh_run_state")

    # (3) no active state — backwards-compatible latest-glob
    pkg = _latest_of(Path(data_root), ptype, project_key)
    if pkg is None and required:
        raise SystemExit(f"ERROR: no {ptype} package found under {data_root}")
    return pkg, _meta(pkg, "latest_glob")


def lineage_consistent(metas: list) -> bool:
    """True when every consumed package was resolved from the active run state (or no state is active —
    standalone/latest-glob runs are not-applicable, reported true)."""
    if active_state() is None:
        return True
    return all(m.get("lineage_source") in ("full_fresh_run_state", "explicit_override") for m in metas)
