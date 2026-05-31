"""Phase 07B calendar/email JSON contract loaders.

Loads the read-only matching/summary/candidate contracts shipped under
``hb_assistant.resources.json``:

- ``calendar_project_match_contract.json``
- ``email_thread_summary_contract.json``
- ``meeting_email_relationship_candidate_contract.json``

These contracts govern candidate typing, confidence classes, review routing, and
forbidden-persistence lists for the later 07B matching/summary prompts. Each
loader validates required keys and asserts auto-promotion is disabled.

Resolution mirrors the data-quality resources: importlib package resource first,
filesystem fallback for dev/test. Read-only; no external calls; no raw content.
"""

from __future__ import annotations

import json
from importlib import resources as importlib_resources
from pathlib import Path
from typing import Any

_RESOURCE_PKG = "hb_assistant.resources.json"
_CALENDAR_PROJECT_MATCH = "calendar_project_match_contract.json"
_EMAIL_THREAD_SUMMARY = "email_thread_summary_contract.json"
_MEETING_EMAIL_CANDIDATE = "meeting_email_relationship_candidate_contract.json"


class CalendarContractError(RuntimeError):
    """Raised when a calendar/email contract cannot be loaded or is malformed."""


def _load_json_resource(filename: str) -> dict[str, Any]:
    try:
        if hasattr(importlib_resources, "files"):
            text = (importlib_resources.files(_RESOURCE_PKG) / filename).read_text(encoding="utf-8")
        else:  # pragma: no cover - legacy importlib path
            text = importlib_resources.read_text(_RESOURCE_PKG, filename, encoding="utf-8")
    except Exception:
        candidate = (
            Path(__file__).resolve().parents[3] / "resources" / "json" / filename
        )
        if not candidate.exists():
            raise CalendarContractError(f"Contract resource not found: {filename}") from None
        text = candidate.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise CalendarContractError(f"Contract {filename} must be a JSON object")
    return data


def _require_keys(data: dict[str, Any], keys: list[str], filename: str) -> None:
    missing = [k for k in keys if k not in data]
    if missing:
        raise CalendarContractError(f"Contract {filename} missing keys: {missing}")


def load_calendar_project_match_contract() -> dict[str, Any]:
    data = _load_json_resource(_CALENDAR_PROJECT_MATCH)
    _require_keys(
        data,
        ["version", "candidate_types", "confidence_classes", "review_required_when",
         "forbidden_persistence"],
        _CALENDAR_PROJECT_MATCH,
    )
    if data.get("auto_promotion_allowed") is not False:
        raise CalendarContractError("calendar project-match contract must disable auto-promotion")
    return data


def load_email_thread_summary_contract() -> dict[str, Any]:
    data = _load_json_resource(_EMAIL_THREAD_SUMMARY)
    _require_keys(
        data,
        ["version", "summary_modes", "default_mode", "persisted_fields",
         "forbidden_persistence", "review_required_when"],
        _EMAIL_THREAD_SUMMARY,
    )
    return data


def load_meeting_email_relationship_candidate_contract() -> dict[str, Any]:
    data = _load_json_resource(_MEETING_EMAIL_CANDIDATE)
    _require_keys(
        data,
        ["version", "signals", "candidate_classes", "review_required_classes", "required_fields"],
        _MEETING_EMAIL_CANDIDATE,
    )
    if data.get("auto_promotion_allowed") is not False:
        raise CalendarContractError("meeting/email candidate contract must disable auto-promotion")
    return data
