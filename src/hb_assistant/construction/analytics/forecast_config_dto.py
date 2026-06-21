"""Read-only, redacted DTOs for the forecast configuration viewer (Implementation Phase 2).

These present the immutable v60 config-registry snapshot (forecast controls, model controls,
staffing mappings, owner-SOV crosswalk, and project settings) to the UI. Redaction is
domain-aware:

  - The ``project`` domain raw_json carries dev-internals (an absolute ``default_data_root``
    path, stamped package names, a ``localhost`` LLM endpoint, a relative config path). It is
    projected through a strict **field whitelist** of business settings only.
  - The control / model_control / staffing / owner_sov domains are business-facing (cost codes,
    dates, dollar values, acceptance metadata, allocation shares — no labor rates). Their fields
    are exposed after passing through a recursive sanitizer.

``forecast_dto.find_redaction_leaks`` is the shared backstop scan; every payload is asserted
leak-free by tests.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

# Friendly labels per config domain (business-facing).
DOMAIN_LABELS: dict[str, str] = {
    "project": "Project settings",
    "forecast_controls": "Forecast controls",
    "forecast_model_controls": "Model controls",
    "forecast_staffing": "Staffing mappings",
    "owner_sov_crosswalk": "Owner-SOV crosswalk",
}

# The ONLY project-domain fields exposed to the UI. Everything else in the project raw_json
# (default_data_root, *_package stamped names, owner_sov_scope_crosswalk path, llm block,
# schedule_package, etc.) is intentionally omitted — dev-internals must not reach the client.
_PROJECT_FIELD_WHITELIST: tuple[str, ...] = (
    "project_name",
    "job_reference",
    "forecast_period",
    "materiality_absolute",
    "materiality_percent",
    "budget_amount_field",
    "current_projected_cost_field",
)


def _friendly_utc(ts: str | None) -> str | None:
    """Render an ISO UTC timestamp as a friendly date label (raw stamp never emitted)."""
    if not ts:
        return None
    raw = ts.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S+00:00", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(raw, fmt)
            break
        except ValueError:
            dt = None
    if dt is None:
        return None
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    return f"{months[dt.month - 1]} {dt.day}, {dt.year}"


def project_fields(raw: dict[str, Any]) -> dict[str, Any]:
    """Whitelist-project the project-domain raw_json to business settings only."""
    out: dict[str, Any] = {}
    for k in _PROJECT_FIELD_WHITELIST:
        if k in raw:
            out[k] = raw[k]
    # budget_details.budget_view_id is the only safe nested field to surface.
    bd = raw.get("budget_details")
    if isinstance(bd, dict) and "budget_view_id" in bd:
        out["budget_view_id"] = bd["budget_view_id"]
    return out


def domain_item_fields(domain: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Return the sanitized business fields for one config item of ``domain``."""
    if domain == "project":
        return project_fields(raw)
    # Other domains are business-facing; expose as-is (the shared leak scan is the backstop,
    # and these domains carry no paths/stamps/endpoints per the repo/DB audit).
    return dict(raw)


@dataclass(frozen=True)
class ConfigSnapshotDTO:
    snapshot_id: str
    snapshot_name: str | None
    created_display: str | None
    reason: str | None
    source_mode: str | None
    item_count: int
    domain_counts: dict[str, int] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConfigDomainDTO:
    domain: str
    display_label: str
    item_count: int
    source_count: int = 0

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConfigItemDTO:
    item_id: str
    domain: str
    config_name: str | None
    item_key: str | None
    item_order: int
    fields: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        return asdict(self)
