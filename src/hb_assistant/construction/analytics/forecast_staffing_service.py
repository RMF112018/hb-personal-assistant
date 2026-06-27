"""Project Staffing API facade (Phase 3).

Thin orchestration layer over the ``construction/forecast/staffing`` subpackage for the FastAPI
surface. Mirrors ForecastOperatorAssumptionsService: instantiated per request with a resolved
``db_path``, returns redaction-safe ``{surface, project_key, ..., guardrails}`` dicts (the repos
already exclude ``raw_json``), and raises ``ForecastStaffingError`` (mapped to HTTP 503 by the
route wrapper) when the managed DB is missing/unreadable or below the required schema version.

Validate-on-write: create/patch ALWAYS persist the row, then resolve template inheritance, run
``validate_row``, and persist the resulting ``validation_status`` + field errors — an invalid row
stays visible with its errors (it is never rejected).
"""

from __future__ import annotations

import functools
import sqlite3
from typing import Any, Callable

from hb_assistant.construction.forecast.staffing import (
    attribution,
    template_resolution,
    validation,
)
from hb_assistant.construction.forecast.staffing._common import StaffingStoreError
from hb_assistant.construction.forecast.staffing.repositories import (
    AbsenceOverrideRepository,
    AttributionReviewRepository,
    AttributionRuleRepository,
    HolidayCalendarRepository,
    StaffingActualsRepository,
    StaffingAssumptionsRepository,
    StaffingConfigRepository,
    StaffingTemplateRepository,
)
from hb_assistant.store.errors import StoreReadinessError

_SURFACE = "analytics.forecast_staffing"


class ForecastStaffingError(RuntimeError):
    """Fail-closed: the staffing store is unavailable (missing/unreadable DB or schema too low)."""


def _guardrails() -> dict[str, Any]:
    return {
        "local_first": True,
        "no_cli_shellout": True,
        "no_live_endpoint_calls": True,
        "no_external_writeback": True,
        "raw_content_never_stored": True,
        "direct_managed_db_write": True,
    }


def _fail_closed(fn: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except (StaffingStoreError, StoreReadinessError, sqlite3.Error) as exc:
            raise ForecastStaffingError(str(exc)) from exc

    return wrapper


class ForecastStaffingService:
    """Project-scoped staffing reads + operator writes over the V76/V81 staffing tables."""

    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path

    # -- repository accessors -------------------------------------------------

    def _config(self) -> StaffingConfigRepository:
        return StaffingConfigRepository(db_path=self._db_path)

    def _assumptions(self) -> StaffingAssumptionsRepository:
        return StaffingAssumptionsRepository(db_path=self._db_path)

    def _absences(self) -> AbsenceOverrideRepository:
        return AbsenceOverrideRepository(db_path=self._db_path)

    def _templates(self) -> StaffingTemplateRepository:
        return StaffingTemplateRepository(db_path=self._db_path)

    def _holidays(self) -> HolidayCalendarRepository:
        return HolidayCalendarRepository(db_path=self._db_path)

    def _rules(self) -> AttributionRuleRepository:
        return AttributionRuleRepository(db_path=self._db_path)

    def _reviews(self) -> AttributionReviewRepository:
        return AttributionReviewRepository(db_path=self._db_path)

    def _actuals(self) -> StaffingActualsRepository:
        return StaffingActualsRepository(db_path=self._db_path)

    def _envelope(self, project_key: str, **extra: Any) -> dict[str, Any]:
        return {"surface": _SURFACE, "project_key": project_key, **extra, "guardrails": _guardrails()}

    # -- validate-on-write helper --------------------------------------------

    def _validate_config_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Resolve template inheritance + validate a config row; persist + return its status."""
        template_version = None
        if row.get("template_id"):
            template_version = self._templates().get_current_version(row["template_id"])
        try:
            effective, _inherited, _overridden = template_resolution.resolve_effective_row(
                row, template_version
            )
            errors = validation.validate_row(effective)
        except template_resolution.TemplateResolutionError as exc:
            errors = [{"field": "template", "code": "template_resolution_failed", "message": str(exc)}]
        result = validation.validation_result(errors)
        persisted = self._config().set_validation(
            row["staffing_config_id"], status=result["status"], errors=result["errors"]
        )
        return persisted if persisted is not None else row

    # -- config ---------------------------------------------------------------

    @_fail_closed
    def list_config(self, project_key: str) -> dict[str, Any]:
        return self._envelope(project_key, rows=self._config().list(project_key, active_only=True))

    @_fail_closed
    def create_config(self, project_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = self._config().create({**payload, "project_key": project_key})
        validated = self._validate_config_row(row)
        return self._envelope(project_key, ok=True, kind="staffing_config_created", row=validated)

    @_fail_closed
    def patch_config(self, project_key: str, config_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        row = self._config().patch(config_id, fields)
        if row is None:
            return self._envelope(project_key, ok=False, kind="staffing_config_not_found")
        validated = self._validate_config_row(row)
        return self._envelope(project_key, ok=True, kind="staffing_config_updated", row=validated)

    @_fail_closed
    def deactivate_config(self, project_key: str, config_id: str) -> dict[str, Any]:
        row = self._config().deactivate(config_id)
        ok = row is not None
        return self._envelope(project_key, ok=ok, kind="staffing_config_deactivated", row=row)

    # -- assumptions ----------------------------------------------------------

    @_fail_closed
    def get_assumptions(self, project_key: str) -> dict[str, Any]:
        return self._envelope(project_key, assumptions=self._assumptions().get(project_key))

    @_fail_closed
    def patch_assumptions(self, project_key: str, fields: dict[str, Any]) -> dict[str, Any]:
        clean = {k: v for k, v in fields.items() if v is not None}
        calendar_id = clean.get("holiday_calendar_id")
        if calendar_id is not None and calendar_id not in self._holidays().calendar_ids():
            return self._envelope(
                project_key,
                ok=False,
                kind="staffing_assumptions_invalid",
                errors=[{"field": "holiday_calendar_id", "code": "holiday_calendar_invalid",
                         "message": "Unknown holiday calendar."}],
            )
        saved = self._assumptions().upsert(project_key, **clean)
        return self._envelope(project_key, ok=True, kind="staffing_assumptions_updated",
                              assumptions=saved)

    # -- absence overrides ----------------------------------------------------

    @_fail_closed
    def list_absences(self, project_key: str) -> dict[str, Any]:
        return self._envelope(project_key, rows=self._absences().list(project_key, active_only=True))

    @_fail_closed
    def create_absence(self, project_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        errors = validation.validate_absence({**payload, "project_key": project_key})
        if errors:
            return self._envelope(project_key, ok=False, kind="staffing_absence_invalid",
                                 errors=errors)
        row = self._absences().create({**payload, "project_key": project_key})
        return self._envelope(project_key, ok=True, kind="staffing_absence_created", row=row)

    @_fail_closed
    def patch_absence(self, project_key: str, absence_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        row = self._absences().patch(absence_id, fields)
        ok = row is not None
        return self._envelope(project_key, ok=ok, kind="staffing_absence_updated", row=row)

    @_fail_closed
    def deactivate_absence(self, project_key: str, absence_id: str) -> dict[str, Any]:
        row = self._absences().deactivate(absence_id)
        ok = row is not None
        return self._envelope(project_key, ok=ok, kind="staffing_absence_deactivated", row=row)

    # -- readiness ------------------------------------------------------------

    @_fail_closed
    def readiness(self, project_key: str) -> dict[str, Any]:
        rows = self._config().list(project_key, active_only=True)
        absences = self._absences().list(project_key, active_only=True)
        assumptions = self._assumptions().get(project_key)
        calendar_ids = self._holidays().calendar_ids()
        templates = self._templates()

        effective_rows: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for row in rows:
            template_version = None
            if row.get("template_id"):
                template_version = templates.get_current_version(row["template_id"])
            try:
                effective, _i, _o = template_resolution.resolve_effective_row(row, template_version)
            except template_resolution.TemplateResolutionError as exc:
                effective_rows.append(row)
                errors.append({"field": "template", "code": "template_resolution_failed",
                               "message": str(exc),
                               "staffing_config_id": row.get("staffing_config_id")})
                continue
            effective_rows.append(effective)
            errors.extend(validation.validate_row(effective))
        errors.extend(validation.validate_project(effective_rows, absences))
        errors.extend(validation.validate_assumptions(assumptions, valid_calendar_ids=calendar_ids))

        unmatched = self._reviews().list(project_key, status="unmatched")
        if errors:
            status = "blocked"
        elif not rows or unmatched:
            status = "degraded"
        else:
            status = "ready"
        reasons = sorted({e["code"] for e in errors})
        if not rows:
            reasons.append("no_active_staffing_rows")
        if unmatched:
            reasons.append("unmatched_actuals_pending")
        return self._envelope(
            project_key,
            readiness_status=status,
            readiness_reasons=reasons,
            validation_errors=errors,
            active_row_count=len(rows),
            unmatched_review_count=len(unmatched),
        )

    # -- attribution ----------------------------------------------------------

    @_fail_closed
    def list_rules(self, project_key: str) -> dict[str, Any]:
        return self._envelope(project_key, rules=self._rules().list(project_key, active_only=True))

    @_fail_closed
    def create_rule(self, project_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        rule = self._rules().upsert_rule(
            project_key=project_key,
            cost_code=payload["cost_code"],
            category=payload["category"],
            staffing_config_id=payload["staffing_config_id"],
            created_by_role=payload.get("created_by_role"),
        )
        attribution.refresh_attribution(self._db_path, project_key)
        return self._envelope(project_key, ok=True, kind="staffing_rule_created", rule=rule)

    @_fail_closed
    def deactivate_rule(self, project_key: str, rule_id: str) -> dict[str, Any]:
        rule = self._rules().deactivate(rule_id)
        attribution.refresh_attribution(self._db_path, project_key)
        ok = rule is not None
        return self._envelope(project_key, ok=ok, kind="staffing_rule_deactivated", rule=rule)

    @_fail_closed
    def list_unmatched(self, project_key: str) -> dict[str, Any]:
        return self._envelope(
            project_key, review_items=attribution.list_unmatched_actuals(self._db_path, project_key)
        )

    @_fail_closed
    def resolve_review_item(
        self, project_key: str, review_item_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        result = attribution.resolve_review_item(
            self._db_path,
            review_item_id,
            staffing_config_id=payload["staffing_config_id"],
            resolved_by_role=payload.get("resolved_by_role"),
        )
        return self._envelope(
            project_key, ok=True, kind="staffing_review_resolved",
            resolved=result.get("resolved"),
        )

    @_fail_closed
    def mat_summary(self, project_key: str) -> dict[str, Any]:
        return self._envelope(project_key, materials=self._actuals().mat_summary(project_key))

    @_fail_closed
    def rebuild_actuals(self, project_key: str) -> dict[str, Any]:
        counts = attribution.rebuild(self._db_path, project_key)
        return self._envelope(project_key, ok=True, kind="staffing_actuals_rebuilt", **counts)
