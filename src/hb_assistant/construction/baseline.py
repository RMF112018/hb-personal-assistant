"""Baseline comparison primitive for construction-agent sources.

A baseline comparison reads the historic counts recorded on a source's
``baseline`` block (populated by the Phase 02 canonical seed) and compares them
to the live counts in SQLite (V2 ``construction_drive_item_inventory``). The
result is a structured :class:`BaselineComparison` receipt that operators can
read to detect drift between expected and observed inventory size — without
ever copying source documents or contacting Microsoft Graph.

Guardrails:
- Pure metadata read; no Graph HTTP, no source-document copies.
- Tolerance defaults to ±5% before drift is flagged.
- A source without a ``baseline`` block returns ``status="no_baseline_recorded"``.
- A source with a baseline block but empty inventory returns
  ``status="never_crawled"``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel

from hb_assistant.construction.config import SourceLocation
from hb_assistant.construction.store import ConstructionStore

BaselineComparisonStatus = Literal[
    "matches",
    "within_tolerance",
    "drift_detected",
    "never_crawled",
    "no_baseline_recorded",
]

_METRIC_KEYS = (
    "unique_item_count",
    "file_count",
    "folder_count",
    "file_size_gb",
)

_BASELINE_GUARDRAILS: dict[str, bool | str] = {
    "external_systems": "read_only",
    "writeback": "none",
    "metadata_only": True,
    "compares_counts_only": True,
    "source_documents_copied": False,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BaselineComparison(BaseModel):
    """Historic vs current count comparison for a construction source."""

    source_key: str
    project_key: Optional[str]
    scope: Optional[str]
    status: BaselineComparisonStatus
    historic: dict[str, Optional[float]]
    current: dict[str, Optional[float]]
    drift: dict[str, Optional[float]]
    drift_pct: dict[str, Optional[float]]
    tolerance_pct: float = 5.0
    generated_at: str
    guardrails: dict[str, bool | str] = {}

    model_config = {"extra": "forbid"}


def _historic_dict(source: SourceLocation) -> dict[str, Optional[float]]:
    snap = source.baseline
    if snap is None:
        return dict.fromkeys(_METRIC_KEYS)
    return {
        "unique_item_count": snap.baseline_unique_item_count,
        "file_count": snap.baseline_file_count,
        "folder_count": snap.baseline_folder_count,
        "file_size_gb": snap.baseline_file_size_gb,
    }


def _current_dict(source: SourceLocation, store: ConstructionStore) -> dict[str, Optional[float]]:
    status_counts = store.count_inventory(source.source_key)
    active = status_counts.get("active", 0)
    kind_counts = store.count_inventory_by_kind(source.source_key)
    total_size_bytes = kind_counts.get("total_size_bytes")
    file_size_gb: Optional[float] = (
        None if total_size_bytes is None else round(total_size_bytes / 1_000_000_000, 2)
    )
    return {
        "unique_item_count": active,
        "file_count": kind_counts.get("file_count", 0),
        "folder_count": kind_counts.get("folder_count", 0),
        "file_size_gb": file_size_gb,
    }


def _compute_drift(
    historic: dict[str, Optional[float]],
    current: dict[str, Optional[float]],
) -> tuple[dict[str, Optional[float]], dict[str, Optional[float]]]:
    drift: dict[str, Optional[float]] = {}
    drift_pct: dict[str, Optional[float]] = {}
    for key in _METRIC_KEYS:
        h = historic.get(key)
        c = current.get(key)
        if h is None or c is None:
            drift[key] = None
            drift_pct[key] = None
            continue
        d = c - h
        drift[key] = d
        if h == 0:
            drift_pct[key] = None
        else:
            drift_pct[key] = round((d / h) * 100, 2)
    return drift, drift_pct


def _classify(
    historic: dict[str, Optional[float]],
    current: dict[str, Optional[float]],
    drift_pct: dict[str, Optional[float]],
    tolerance_pct: float,
) -> BaselineComparisonStatus:
    historic_present = any(v is not None for v in historic.values())
    if not historic_present:
        return "no_baseline_recorded"

    current_active = current.get("unique_item_count") or 0
    current_files = current.get("file_count") or 0
    current_folders = current.get("folder_count") or 0
    if current_active == 0 and current_files == 0 and current_folders == 0:
        return "never_crawled"

    all_match = True
    all_within_tolerance = True
    for key in _METRIC_KEYS:
        h = historic.get(key)
        c = current.get(key)
        if h is None or c is None:
            continue
        if c != h:
            all_match = False
        pct = drift_pct.get(key)
        if pct is None:
            continue
        if abs(pct) > tolerance_pct:
            all_within_tolerance = False

    if all_match:
        return "matches"
    if all_within_tolerance:
        return "within_tolerance"
    return "drift_detected"


def compute_baseline_comparison(
    source: SourceLocation,
    store: ConstructionStore,
    *,
    tolerance_pct: float = 5.0,
) -> BaselineComparison:
    """Compare a source's historic baseline counts to its live inventory."""

    historic = _historic_dict(source)
    current = _current_dict(source, store)
    drift, drift_pct = _compute_drift(historic, current)
    status = _classify(historic, current, drift_pct, tolerance_pct)

    return BaselineComparison(
        source_key=source.source_key,
        project_key=source.project_key,
        scope=source.kind,
        status=status,
        historic=historic,
        current=current,
        drift=drift,
        drift_pct=drift_pct,
        tolerance_pct=tolerance_pct,
        generated_at=_utc_now(),
        guardrails=dict(_BASELINE_GUARDRAILS),
    )
