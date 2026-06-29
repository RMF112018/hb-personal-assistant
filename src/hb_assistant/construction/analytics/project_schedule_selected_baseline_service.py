"""Selected-baseline workflow and readiness for Project Schedule Hub."""

from __future__ import annotations

from datetime import date
from typing import Any

from hb_assistant.store.connection import open_connection
from hb_assistant.store.project_schedule_hub_repository import ProjectScheduleHubRepository
from hb_assistant.store.schedule_identity_repository import ScheduleIdentityRepository

from .project_schedule_comparison import label_from_source
from .project_schedule_summary_service import _date_str, _parse_date
from .schedule_trust_service import ScheduleTrustService


class ProjectScheduleSelectedBaselineService:
    """Validate, persist, and describe selected-baseline state without recomputing facts."""

    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._repo = ProjectScheduleHubRepository(db_path=db_path)
        self._identity = ScheduleIdentityRepository(db_path=db_path)
        self._trust = ScheduleTrustService(db_path=db_path)

    def get_state(
        self,
        *,
        project_key: str,
        current_schedule_version_key: str | None = None,
    ) -> dict[str, Any]:
        current = self._version(project_key, current_schedule_version_key) if current_schedule_version_key else self._current_version(project_key)
        if not current:
            return {
                "available": False,
                "project_key": project_key,
                "current_version_key": current_schedule_version_key,
                "selected_baseline_version_key": None,
                "selected_baseline_label": None,
                "selected_baseline_data_date": None,
                "status": "no_current_schedule",
                "readiness": {
                    "ready": False,
                    "blockers": ["no_current_schedule"],
                    "backend_derived": True,
                },
                "recompute_required": False,
                "caveats": ["Selected-baseline comparison remains separate from prior-update comparison."],
                "prior_update_comparison": {"basis": "prior_update", "separate": True},
            }
        current_key = str(current["schedule_version_key"])
        selection = self._repo.get_active_baseline_selection(
            project_key=project_key,
            current_schedule_version_key=current_key,
        )
        if not selection:
            return self._state_envelope(
                project_key=project_key,
                current=current,
                baseline=None,
                selection=None,
                status="no_selection",
                readiness={
                    "ready": False,
                    "blockers": ["selected_baseline_required"],
                    "backend_derived": True,
                },
                recompute_required=False,
            )

        baseline_key = str(selection["selected_baseline_schedule_version_key"])
        baseline = self._version(project_key, baseline_key)
        if not baseline:
            return self._state_envelope(
                project_key=project_key,
                current=current,
                baseline=None,
                selection=selection,
                status="invalid_selection",
                readiness={
                    "ready": False,
                    "blockers": ["invalid_selected_baseline_version"],
                    "backend_derived": True,
                },
                recompute_required=True,
            )

        readiness = self.compression_readiness(
            project_key=project_key,
            current_schedule_version_key=current_key,
            selected_baseline_schedule_version_key=baseline_key,
        )
        status = "ready" if readiness["ready"] else "recompute_required"
        return self._state_envelope(
            project_key=project_key,
            current=current,
            baseline=baseline,
            selection=selection,
            status=status,
            readiness=readiness,
            recompute_required=not bool(readiness["ready"]),
        )

    def select_baseline(
        self,
        *,
        project_key: str,
        current_schedule_version_key: str,
        selected_baseline_schedule_version_key: str,
        selected_by_operator: str | None,
        selection_note: str | None = None,
    ) -> dict[str, Any]:
        if not current_schedule_version_key or not selected_baseline_schedule_version_key:
            raise ValueError("baseline_selection_required")
        if current_schedule_version_key == selected_baseline_schedule_version_key:
            raise ValueError("baseline_must_differ_from_current")

        current = self._version(project_key, current_schedule_version_key)
        if not current:
            raise ValueError("invalid_current_schedule_version")
        baseline = self._version(project_key, selected_baseline_schedule_version_key)
        if not baseline:
            if self._version_any_project(selected_baseline_schedule_version_key):
                raise ValueError("baseline_project_mismatch")
            raise ValueError("invalid_selected_baseline_version")

        current_match = self._identity.get_match_for_version(current_schedule_version_key)
        if not self._trust.is_hub_eligible(
            project_key=project_key,
            version=current,
            identity_match=current_match,
        ):
            raise ValueError("invalid_current_schedule_version")

        current_date = self._data_date(current)
        baseline_date = self._data_date(baseline)
        if current_date and baseline_date and baseline_date > current_date:
            raise ValueError("baseline_must_not_be_future_of_current")

        baseline_match = self._identity.get_match_for_version(selected_baseline_schedule_version_key)
        current_identity = (current_match or {}).get("schedule_identity_key")
        baseline_identity = (baseline_match or {}).get("schedule_identity_key")
        if current_identity and baseline_identity and current_identity != baseline_identity:
            raise ValueError("baseline_identity_mismatch")

        self._repo.set_baseline_selection(
            project_key=project_key,
            current_schedule_version_key=current_schedule_version_key,
            selected_baseline_schedule_version_key=selected_baseline_schedule_version_key,
            selected_by_operator=selected_by_operator,
            selection_note=selection_note,
        )
        return self.get_state(
            project_key=project_key,
            current_schedule_version_key=current_schedule_version_key,
        )

    def compression_payload(
        self,
        *,
        project_key: str,
        current_schedule_version_key: str,
        as_of_date: date,
    ) -> dict[str, Any]:
        state = self.get_state(
            project_key=project_key,
            current_schedule_version_key=current_schedule_version_key,
        )
        if state["status"] == "no_selection":
            raise ValueError("metric_not_trend_ready")
        readiness = dict(state.get("readiness") or {})
        if not readiness.get("ready"):
            return {
                "available": False,
                "reason": "selected_baseline_recompute_required",
                "readiness": readiness,
                "recompute_required": True,
                "selected_baseline": self._selected_baseline_payload(state),
                "points": [],
                "summary": {
                    "prior_update_comparison_separate": True,
                    "backend_derived": True,
                },
                "data_quality_notes": [
                    "Selected-baseline matching or duration facts are incomplete; no compression value was fabricated."
                ],
            }

        ratio = readiness["compression_ratio"]
        return {
            "available": True,
            "reason": None,
            "readiness": readiness,
            "recompute_required": False,
            "selected_baseline": self._selected_baseline_payload(state),
            "points": [
                {
                    "data_date": _date_str(self._data_date(state.get("_current_version"))),
                    "period": as_of_date.isoformat(),
                    "current_version_key": current_schedule_version_key,
                    "selected_baseline_version_key": state.get("selected_baseline_version_key"),
                    "compression_ratio": ratio,
                    "matched_activity_count": readiness["matched_activity_count"],
                    "current_remaining_duration_days": readiness["current_remaining_duration_days"],
                    "baseline_remaining_duration_days": readiness["baseline_remaining_duration_days"],
                    "comparison_basis": "selected_baseline",
                }
            ],
            "summary": {
                "prior_update_comparison_separate": True,
                "backend_derived": True,
                "duration_basis": readiness["duration_basis"],
            },
            "data_quality_notes": ["Compression ratio is backend-derived from selected-baseline matched activity durations."],
        }

    def compression_readiness(
        self,
        *,
        project_key: str,
        current_schedule_version_key: str,
        selected_baseline_schedule_version_key: str,
    ) -> dict[str, Any]:
        del project_key
        rows = self._matched_duration_rows(
            current_schedule_version_key=current_schedule_version_key,
            selected_baseline_schedule_version_key=selected_baseline_schedule_version_key,
        )
        blockers: list[str] = []
        matched = len(rows)
        current_sum = 0.0
        baseline_sum = 0.0
        usable = 0
        for row in rows:
            current_duration = _duration_days(row.get("current_duration_remaining")) or _duration_days(
                row.get("current_duration_original")
            )
            baseline_duration = _duration_days(row.get("baseline_duration_remaining")) or _duration_days(
                row.get("baseline_duration_original")
            )
            if current_duration is None or baseline_duration is None:
                continue
            current_sum += current_duration
            baseline_sum += baseline_duration
            usable += 1

        if matched == 0:
            blockers.append("baseline_matching_unavailable")
        if usable == 0:
            blockers.append("duration_basis_unavailable")
        if current_sum <= 0:
            blockers.append("current_duration_unavailable")
        if baseline_sum <= 0:
            blockers.append("baseline_duration_unavailable")

        ready = not blockers
        ratio = ((baseline_sum / current_sum) - 1) * 100 if ready else None
        return {
            "ready": ready,
            "blockers": blockers,
            "backend_derived": True,
            "matched_activity_count": matched,
            "usable_duration_activity_count": usable,
            "duration_basis": "duration_remaining_then_original",
            "current_remaining_duration_days": round(current_sum, 4) if current_sum else None,
            "baseline_remaining_duration_days": round(baseline_sum, 4) if baseline_sum else None,
            "compression_ratio": round(ratio, 4) if ratio is not None else None,
        }

    def _state_envelope(
        self,
        *,
        project_key: str,
        current: dict[str, Any],
        baseline: dict[str, Any] | None,
        selection: dict[str, Any] | None,
        status: str,
        readiness: dict[str, Any],
        recompute_required: bool,
    ) -> dict[str, Any]:
        return {
            "available": True,
            "project_key": project_key,
            "current_version_key": current.get("schedule_version_key"),
            "current_label": self._label(current),
            "current_data_date": _date_str(self._data_date(current)),
            "selected_baseline_version_key": baseline.get("schedule_version_key") if baseline else (selection or {}).get("selected_baseline_schedule_version_key"),
            "selected_baseline_label": self._label(baseline) if baseline else None,
            "selected_baseline_data_date": _date_str(self._data_date(baseline)) if baseline else None,
            "status": status,
            "readiness": readiness,
            "recompute_required": recompute_required,
            "selection": selection,
            "caveats": [
                "Selected-baseline comparison is a review cue and remains separate from prior-update comparison.",
                "Phase 8A does not trigger import, CPM, or diff recompute.",
            ],
            "prior_update_comparison": {"basis": "prior_update", "separate": True},
            "_current_version": current,
            "_selected_baseline_version": baseline,
        }

    def _current_version(self, project_key: str) -> dict[str, Any] | None:
        with open_connection(self._db_path) as conn:
            rows = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT import_id, project_key, schedule_version_key, source_type,
                           source_format, import_status, activity_count, relationship_count,
                           cost_loaded_status, created_at, source_filename_redacted
                    FROM schedule_file_imports
                    WHERE import_status='committed'
                      AND project_key=?
                      AND schedule_version_key IS NOT NULL
                    ORDER BY created_at DESC, schedule_version_key DESC
                    """,
                    (project_key,),
                ).fetchall()
            ]
        eligible = []
        for version in rows:
            self._hydrate_version(version)
            match = self._identity.get_match_for_version(str(version["schedule_version_key"]))
            if self._trust.is_hub_eligible(project_key=project_key, version=version, identity_match=match):
                eligible.append(version)
        eligible.sort(key=lambda v: (self._data_date(v) or date.min, str(v.get("created_at") or "")), reverse=True)
        return eligible[0] if eligible else None

    def _version(self, project_key: str, schedule_version_key: str | None) -> dict[str, Any] | None:
        if not schedule_version_key:
            return None
        with open_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT import_id, project_key, schedule_version_key, source_type,
                       source_format, import_status, activity_count, relationship_count,
                       cost_loaded_status, created_at, source_filename_redacted
                FROM schedule_file_imports
                WHERE project_key=?
                  AND schedule_version_key=?
                  AND import_status='committed'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (project_key, schedule_version_key),
            ).fetchone()
        version = dict(row) if row else None
        if version:
            self._hydrate_version(version)
        return version

    def _version_any_project(self, schedule_version_key: str) -> dict[str, Any] | None:
        with open_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT project_key, schedule_version_key
                FROM schedule_file_imports
                WHERE schedule_version_key=?
                  AND import_status='committed'
                LIMIT 1
                """,
                (schedule_version_key,),
            ).fetchone()
        return dict(row) if row else None

    def _matched_duration_rows(
        self,
        *,
        current_schedule_version_key: str,
        selected_baseline_schedule_version_key: str,
    ) -> list[dict[str, Any]]:
        with open_connection(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT
                  c.activity_id,
                  c.duration_remaining AS current_duration_remaining,
                  c.duration_original AS current_duration_original,
                  b.duration_remaining AS baseline_duration_remaining,
                  b.duration_original AS baseline_duration_original
                FROM procore_ep_schedule_activities c
                JOIN procore_ep_schedule_activities b
                  ON b.activity_id=c.activity_id
                 AND b.schedule_version_key=?
                WHERE c.schedule_version_key=?
                  AND (c.actual_finish IS NULL OR TRIM(c.actual_finish)='')
                """,
                (selected_baseline_schedule_version_key, current_schedule_version_key),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _hydrate_version(version: dict[str, Any]) -> None:
        version["display_label"] = version.get("source_filename_redacted")
        version["source_filename"] = version.get("source_filename_redacted")
        version["imported_at"] = version.get("created_at")
        version["data_date"] = _date_str(ProjectScheduleSelectedBaselineService._data_date(version))

    @staticmethod
    def _data_date(version: dict[str, Any] | None) -> date | None:
        if not version:
            return None
        return _parse_date(version.get("data_date")) or _parse_date(str(version.get("schedule_version_key") or "").split("|")[-1])

    @staticmethod
    def _label(version: dict[str, Any] | None) -> str | None:
        if not version:
            return None
        label = label_from_source(version.get("source_filename_redacted"))
        if label:
            return label
        data_date = ProjectScheduleSelectedBaselineService._data_date(version)
        if data_date:
            return f"Update {data_date.isoformat()}"
        return str(version.get("schedule_version_key") or "") or None

    @staticmethod
    def _selected_baseline_payload(state: dict[str, Any]) -> dict[str, Any]:
        return {
            "selected_baseline_version_key": state.get("selected_baseline_version_key"),
            "selected_baseline_label": state.get("selected_baseline_label"),
            "selected_baseline_data_date": state.get("selected_baseline_data_date"),
            "status": state.get("status"),
            "readiness": state.get("readiness"),
            "recompute_required": state.get("recompute_required"),
        }


def public_selected_baseline_state(state: dict[str, Any]) -> dict[str, Any]:
    """Strip private helper fields before returning API or hub payloads."""

    return {k: v for k, v in state.items() if not str(k).startswith("_")}


def _duration_days(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        cleaned = text.lower().replace("days", "").replace("day", "").replace("d", "").strip()
        try:
            number = float(cleaned)
        except ValueError:
            return None
    # P6 duration fields are often hours. Large values divisible by 8 are treated as hours.
    if abs(number) > 24:
        return number / 8.0
    return number
