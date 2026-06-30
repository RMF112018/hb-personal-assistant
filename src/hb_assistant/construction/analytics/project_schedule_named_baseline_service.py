"""Project-level named baseline slot selection for Schedule Controls."""

from __future__ import annotations

from datetime import date
from typing import Any

from hb_assistant.store.connection import open_connection
from hb_assistant.store.project_schedule_named_baseline_repository import (
    ProjectScheduleNamedBaselineRepository,
)
from hb_assistant.store.schedule_identity_repository import ScheduleIdentityRepository

from .project_schedule_baseline_vocabulary import (
    BASELINE_SLOT_KEYS,
    BASELINE_SLOT_ORDER,
    label_for_slot,
)
from .project_schedule_comparison import label_from_source
from .project_schedule_summary_service import ProjectScheduleSummaryService, _date_str, _parse_date
from .schedule_trust_service import ScheduleTrustService


class ProjectScheduleNamedBaselineService:
  """Read and persist named baseline anchors independent of legacy V90 selection."""

  def __init__(self, *, db_path: str) -> None:
    self._db_path = db_path
    self._repo = ProjectScheduleNamedBaselineRepository(db_path=db_path)
    self._summary = ProjectScheduleSummaryService(db_path=db_path)
    self._identity = ScheduleIdentityRepository(db_path=db_path)
    self._trust = ScheduleTrustService(db_path=db_path)

  def get_baselines_state(self, project_key: str, *, as_of: date | None = None) -> dict[str, Any]:
    context = self._summary.build_schedule_hub_context(project_key, as_of=as_of)
    if not context:
      return {"available": False, "reason": "no_schedule", "project_key": project_key}

    current_key = str(context.get("schedule_version_key") or "")
    current_data_date = str(context.get("schedule_data_date") or "") or None
    as_of_date = context.get("as_of_date")
    as_of_str = as_of_date.isoformat() if isinstance(as_of_date, date) else str(as_of_date or "")

    active_by_slot = {row["slot_key"]: row for row in self._repo.list_active_slots(project_key=project_key)}
    slots: list[dict[str, Any]] = []
    for slot_key in BASELINE_SLOT_ORDER:
      row = active_by_slot.get(slot_key)
      slot_payload = self._slot_payload(
        project_key=project_key,
        slot_key=slot_key,
        row=row,
        current_key=current_key,
        current_data_date=current_data_date,
      )
      slots.append(slot_payload)

    return {
      "available": True,
      "project_key": project_key,
      "as_of_date": as_of_str or None,
      "current_schedule_version_key": current_key,
      "current_schedule_data_date": current_data_date,
      "slots": slots,
      "available_versions": self._available_versions(
        project_key=project_key,
        current_key=current_key,
        current_data_date=current_data_date,
      ),
    }

  def update_baselines(
    self,
    project_key: str,
    *,
    selections: dict[str, Any],
    as_of: date | None = None,
    selected_by: str | None,
  ) -> dict[str, Any]:
    if not isinstance(selections, dict):
      raise ValueError("invalid_selections_payload")

    context = self._summary.build_schedule_hub_context(project_key, as_of=as_of)
    if not context:
      raise ValueError("no_schedule")
    current_key = str(context.get("schedule_version_key") or "")
    current_data_date = str(context.get("schedule_data_date") or "") or None

    for slot_key in selections:
      if slot_key not in BASELINE_SLOT_KEYS:
        raise ValueError("unknown_slot_key")

    active_by_slot = {row["slot_key"]: row for row in self._repo.list_active_slots(project_key=project_key)}
    final_versions: dict[str, str] = {}
    for slot_key in BASELINE_SLOT_ORDER:
      if slot_key in selections:
        value = selections[slot_key]
        if value is None:
          continue
        if not isinstance(value, dict):
          raise ValueError("invalid_slot_selection")
        version_key = str(value.get("schedule_version_key") or "")
        if not version_key:
          raise ValueError("schedule_version_key_required")
        self._validate_version_for_slot(
          project_key=project_key,
          slot_key=slot_key,
          schedule_version_key=version_key,
          current_key=current_key,
          current_data_date=current_data_date,
        )
        final_versions[slot_key] = version_key
      elif slot_key in active_by_slot:
        final_versions[slot_key] = str(active_by_slot[slot_key]["schedule_version_key"])

    version_values = list(final_versions.values())
    if len(version_values) != len(set(version_values)):
      raise ValueError("duplicate_schedule_version_across_slots")

    for slot_key in BASELINE_SLOT_ORDER:
      if slot_key not in selections:
        continue
      value = selections[slot_key]
      if value is None:
        self._repo.clear_slot(project_key=project_key, slot_key=slot_key)
        continue
      version_key = str(value.get("schedule_version_key") or "")
      display_name = str(value.get("display_name") or "").strip() or None
      notes = str(value.get("notes") or "").strip() or None
      self._repo.set_slot_selection(
        project_key=project_key,
        slot_key=slot_key,
        schedule_version_key=version_key,
        display_name=display_name,
        notes=notes,
        selected_by=selected_by,
      )

    return self.get_baselines_state(project_key, as_of=as_of)

  def resolve_slot_for_controls(
    self,
    project_key: str,
    *,
    slot_key: str,
    as_of: date | None = None,
  ) -> dict[str, Any]:
    context = self._summary.build_schedule_hub_context(project_key, as_of=as_of)
    if not context:
      return {"selection_status": "invalid", "reason": "no_schedule"}

    current_key = str(context.get("schedule_version_key") or "")
    current_data_date = str(context.get("schedule_data_date") or "") or None
    row = self._repo.get_active_slot(project_key=project_key, slot_key=slot_key)
    if not row:
      return {
        "selection_status": "missing",
        "slot_key": slot_key,
        "slot_label": label_for_slot(slot_key),
      }

    version_key = str(row.get("schedule_version_key") or "")
    try:
      self._validate_version_for_slot(
        project_key=project_key,
        slot_key=slot_key,
        schedule_version_key=version_key,
        current_key=current_key,
        current_data_date=current_data_date,
      )
    except ValueError as exc:
      return {
        "selection_status": "invalid",
        "slot_key": slot_key,
        "slot_label": label_for_slot(slot_key),
        "reason": str(exc),
        "schedule_version_key": version_key,
      }

    version = self._version_row(project_key, version_key)
    return {
      "selection_status": "selected",
      "slot_key": slot_key,
      "slot_label": label_for_slot(slot_key),
      "schedule_version_key": version_key,
      "schedule_data_date": _date_str(self._summary._data_date(version)) if version else None,
      "display_name": row.get("display_name") or self._friendly_label(version, version_key),
      "selected_at": row.get("selected_at"),
      "selected_by": row.get("selected_by"),
      "notes": row.get("notes"),
    }

  def _slot_payload(
    self,
    *,
    project_key: str,
    slot_key: str,
    row: dict[str, Any] | None,
    current_key: str,
    current_data_date: str | None,
  ) -> dict[str, Any]:
    base = {
      "slot_key": slot_key,
      "slot_label": label_for_slot(slot_key),
      "selection": None,
      "status": "missing",
    }
    if not row:
      return base

    version_key = str(row.get("schedule_version_key") or "")
    try:
      self._validate_version_for_slot(
        project_key=project_key,
        slot_key=slot_key,
        schedule_version_key=version_key,
        current_key=current_key,
        current_data_date=current_data_date,
      )
      status = "selected"
    except ValueError:
      status = "invalid"

    version = self._version_row(project_key, version_key)
    base["status"] = status
    base["selection"] = {
      "schedule_version_key": version_key,
      "schedule_data_date": _date_str(self._summary._data_date(version)) if version else None,
      "display_name": row.get("display_name") or self._friendly_label(version, version_key),
      "selected_at": row.get("selected_at"),
      "selected_by": row.get("selected_by"),
      "notes": row.get("notes"),
    }
    return base

  def _available_versions(
    self,
    *,
    project_key: str,
    current_key: str,
    current_data_date: str | None,
  ) -> list[dict[str, Any]]:
    versions = self._summary._hub_project_versions(project_key)
    current_parsed = _parse_date(current_data_date)
    out: list[dict[str, Any]] = []
    for version in versions:
      version_key = str(version.get("schedule_version_key") or "")
      data_date = _date_str(self._summary._data_date(version))
      ineligible_reason = None
      eligible = True
      if version_key == current_key:
        eligible = False
        ineligible_reason = "cannot_select_current_schedule_version"
      else:
        version_date = _parse_date(data_date)
        if current_parsed and version_date and version_date > current_parsed:
          eligible = False
          ineligible_reason = "schedule_version_after_current_as_of"
        match = self._identity.get_match_for_version(version_key)
        if not self._trust.is_hub_eligible(project_key=project_key, version=version, identity_match=match):
          eligible = False
          ineligible_reason = ineligible_reason or "not_hub_eligible"
      out.append(
        {
          "schedule_version_key": version_key,
          "schedule_data_date": data_date,
          "display_name": self._friendly_label(version, version_key),
          "source_label": version.get("source_filename_redacted") or version.get("display_label"),
          "import_id": version.get("import_id"),
          "package_id": version.get("package_id"),
          "is_current_as_of": version_key == current_key,
          "eligible_baseline": eligible,
          "ineligibility_reason": ineligible_reason,
        }
      )
    out.sort(key=lambda row: (row.get("schedule_data_date") or "", row.get("display_name") or ""), reverse=True)
    return out

  def _validate_version_for_slot(
    self,
    *,
    project_key: str,
    slot_key: str,
    schedule_version_key: str,
    current_key: str,
    current_data_date: str | None,
  ) -> None:
    del slot_key
    if schedule_version_key == current_key:
      raise ValueError("baseline_cannot_equal_current_schedule_version")
    version = self._version_row(project_key, schedule_version_key)
    if not version:
      if self._version_any_project(schedule_version_key):
        raise ValueError("baseline_project_mismatch")
      raise ValueError("invalid_schedule_version_key")

    current_parsed = _parse_date(current_data_date)
    baseline_date = self._summary._data_date(version)
    if current_parsed and baseline_date and baseline_date > current_parsed:
      raise ValueError("baseline_must_not_be_future_of_current")

    current_match = self._identity.get_match_for_version(current_key)
    baseline_match = self._identity.get_match_for_version(schedule_version_key)
    current_identity = (current_match or {}).get("schedule_identity_key")
    baseline_identity = (baseline_match or {}).get("schedule_identity_key")
    if current_identity and baseline_identity and current_identity != baseline_identity:
      raise ValueError("baseline_identity_mismatch")

  def _version_row(self, project_key: str, schedule_version_key: str) -> dict[str, Any] | None:
    return self._summary._version_row(project_key, schedule_version_key)

  def _version_any_project(self, schedule_version_key: str) -> dict[str, Any] | None:
    with open_connection(self._db_path) as conn:
      row = conn.execute(
        """
        SELECT project_key, schedule_version_key
        FROM schedule_file_imports
        WHERE schedule_version_key=? AND import_status='committed'
        LIMIT 1
        """,
        (schedule_version_key,),
      ).fetchone()
    return dict(row) if row else None

  @staticmethod
  def _friendly_label(version: dict[str, Any] | None, version_key: str) -> str:
    if version:
      return str(version.get("display_label") or version.get("source_filename_redacted") or label_from_source(version_key))
    return label_from_source(version_key)
