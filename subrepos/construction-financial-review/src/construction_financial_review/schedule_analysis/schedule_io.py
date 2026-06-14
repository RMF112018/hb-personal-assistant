"""Schedule package discovery, streaming readers, and field normalization.

The schedule package is a P6/XER-derived JSON export. Activities carry a pre-normalized
``activity_codes.cost_code`` (e.g. ``"15-16-110"``) plus a raw integer ``cost_code_raw``
(e.g. ``1516110``). All values here are read-only evidence — nothing is mutated.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator, Optional

from ..common.dates import normalize_date
from ..common.io import read_json, read_jsonl

# ---------------------------------------------------------------------------
# Package discovery
# ---------------------------------------------------------------------------

SCHEDULE_PACKAGE_DEFAULT = "project_schedule_json_package"
CONTEXT_GLOB = "forecast_context_package_tropical_*"
ANALYSIS_V2_GLOB = "forecast_analysis_package_tropical_crosswalk_v2_*"
MAPPING_WORKPAPER_GLOB = "mapping_discrepancy_workpaper_tropical_*"


def _latest_dir(data_root: Path, pattern: str) -> Optional[Path]:
    """Latest matching directory by lexical name (timestamps sort correctly)."""
    matches = sorted(p for p in data_root.glob(pattern) if p.is_dir())
    return matches[-1] if matches else None


def discover_packages(data_root: Path, cfg: dict) -> dict:
    """Locate the schedule package plus the latest context / analysis-v2 / workpaper packages.

    Config-named packages are preferred; otherwise the latest-by-name match is used. Returns a
    dict of resolved ``Path`` objects (``None`` for absent optional packages) and a
    ``selection`` list of human-readable notes describing how each was chosen.
    """
    data_root = Path(data_root)
    selection: list[str] = []

    def _prefer(name_key: str, glob: str, required: bool, label: str) -> Optional[Path]:
        named = cfg.get(name_key)
        if named:
            cand = data_root / named
            if cand.is_dir():
                selection.append(f"{label}: config-named '{named}'")
                return cand
            selection.append(f"{label}: config-named '{named}' MISSING; falling back to latest match")
        latest = _latest_dir(data_root, glob)
        if latest is not None:
            selection.append(f"{label}: latest '{latest.name}'")
        elif required:
            selection.append(f"{label}: NONE FOUND (required)")
        else:
            selection.append(f"{label}: none found (optional)")
        return latest

    schedule_name = cfg.get("schedule_package", SCHEDULE_PACKAGE_DEFAULT)
    schedule_pkg = data_root / schedule_name
    if schedule_pkg.is_dir():
        selection.append(f"schedule: '{schedule_name}'")
    else:
        selection.append(f"schedule: '{schedule_name}' MISSING (required)")

    context_pkg = _prefer("forecast_context_package", CONTEXT_GLOB, True, "context")
    analysis_pkg = _prefer("forecast_analysis_package_crosswalk_v2", ANALYSIS_V2_GLOB, True, "analysis_v2")
    workpaper_pkg = _prefer("mapping_discrepancy_workpaper", MAPPING_WORKPAPER_GLOB, False, "mapping_workpaper")

    return {
        "data_root": data_root,
        "schedule_package": schedule_pkg if schedule_pkg.is_dir() else None,
        "context_package": context_pkg,
        "analysis_v2_package": analysis_pkg,
        "mapping_workpaper_package": workpaper_pkg,
        "selection": selection,
    }


# ---------------------------------------------------------------------------
# Schedule readers
# ---------------------------------------------------------------------------

def read_schedule_manifest(schedule_pkg: Path) -> dict:
    return read_json(Path(schedule_pkg) / "schedule_project_manifest.json")


def read_schedule_validation(schedule_pkg: Path) -> dict:
    p = Path(schedule_pkg) / "schedule_validation_report.json"
    return read_json(p) if p.exists() else {}


def iter_activities(schedule_pkg: Path) -> Iterator[dict]:
    yield from read_jsonl(Path(schedule_pkg) / "schedule_activities.jsonl")


def iter_relationships(schedule_pkg: Path) -> Iterator[dict]:
    yield from read_jsonl(Path(schedule_pkg) / "schedule_relationships.jsonl")


# ---------------------------------------------------------------------------
# Field normalization (pure, unit-tested)
# ---------------------------------------------------------------------------

MILESTONE_TYPES = ("Start Milestone", "Finish Milestone")
LOE_SUMMARY_TYPES = ("Level of Effort", "WBS Summary")


def normalize_status(status) -> dict:
    """Return canonical status flags. P6 status is one of Completed/In Progress/Not Started."""
    s = (status or "").strip().lower()
    return {
        "status": status,
        "is_completed": s == "completed",
        "is_in_progress": s == "in progress",
        "is_not_started": s == "not started",
    }


def is_open(status) -> bool:
    """Open = not completed (In Progress or Not Started)."""
    f = normalize_status(status)
    return not f["is_completed"]


def is_milestone(activity_type) -> bool:
    return activity_type in MILESTONE_TYPES


def is_loe_or_summary(activity_type) -> bool:
    return activity_type in LOE_SUMMARY_TYPES


def normalize_cost_code(raw) -> Optional[str]:
    """Normalize a raw 7-digit cost code to ``NN-NN-NNN``.

    Accepts an int (``1516110``) or a pre-normalized string (``"15-16-110"``). Returns None if
    the value is missing or cannot be expressed as a 7-digit code. No fuzzy matching.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        s = raw.strip()
        if s == "":
            return None
        # Already normalized NN-NN-NNN
        if "-" in s:
            parts = s.split("-")
            if len(parts) == 3 and all(parts):
                return s
            return None
        digits = s
    else:
        digits = str(raw)
    if not digits.isdigit():
        return None
    digits = digits.zfill(7)
    if len(digits) != 7:
        return None
    return f"{digits[0:2]}-{digits[2:4]}-{digits[4:7]}"


def activity_cost_code(activity: dict) -> Optional[str]:
    """Deterministic cost code for an activity: prefer the extractor's normalized value, else
    derive from ``cost_code_raw``. (Both are source-provided; this is not a mapping decision.)"""
    codes = activity.get("activity_codes") or {}
    cc = codes.get("cost_code")
    if isinstance(cc, str) and cc.strip():
        norm = normalize_cost_code(cc)
        if norm:
            return norm
    return normalize_cost_code(codes.get("cost_code_raw"))


def _dates(activity: dict) -> dict:
    return activity.get("dates") or {}


def _durations(activity: dict) -> dict:
    return activity.get("durations") or {}


def _float(activity: dict) -> dict:
    return activity.get("float") or {}


def remaining_start(activity: dict) -> Optional[str]:
    """YYYY-MM-DD remaining early start; falls back to early start for not-started work."""
    d = _dates(activity)
    return normalize_date(d.get("remaining_early_start") or d.get("start"))


def remaining_finish(activity: dict) -> Optional[str]:
    d = _dates(activity)
    return normalize_date(d.get("remaining_early_finish") or d.get("finish"))


def total_float_days(activity: dict):
    """Total float in 8h-days (float kept as-is for comparison only; never money)."""
    return _float(activity).get("total_float_days_8h")


def remaining_duration_days(activity: dict):
    return _durations(activity).get("remaining_duration_days_8h")


def predecessor_count(activity: dict) -> int:
    return len(activity.get("predecessors") or [])


def successor_count(activity: dict) -> int:
    return len(activity.get("successors") or [])
