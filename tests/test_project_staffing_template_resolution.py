"""Phase 2a template-inheritance / effective-row resolution tests."""

from __future__ import annotations

import pytest

from hb_assistant.construction.forecast.staffing.template_resolution import (
    INHERITABLE_FIELDS,
    TemplateResolutionError,
    resolve_effective_row,
)

_VERSION = {
    "default_role_title": "Superintendent",
    "default_employment_type": "Full Time",
    "default_rate_unit": "weekly",
    "cost_code": "01-100",
    "cost_code_description": "Field Supervision",
    "default_lab_rate": "2500.00",
    "default_lbn_rate": "0.00",
    "default_mat_rate": None,
}


def _config(**over: object) -> dict:
    row = {
        "staffing_config_id": "cfg1",
        "project_key": "tropical",
        "template_id": "tpl1",
        "person_name": "Jane Doe",
        "start_date": "2026-07-01",
        "finish_date": "2026-12-31",
        "role_title": "OWN-ROLE",
        "lab_rate": "9999.00",
        "override_fields": [],
    }
    row.update(over)
    return row


def test_inherits_all_when_no_overrides() -> None:
    effective, inherited, overridden = resolve_effective_row(_config(), _VERSION)
    assert effective["role_title"] == "Superintendent"  # from template, not OWN-ROLE
    assert effective["lab_rate"] == "2500.00"
    assert effective["cost_code"] == "01-100"
    assert overridden == []
    assert set(inherited) == set(INHERITABLE_FIELDS)
    # identity fields always passthrough
    assert effective["person_name"] == "Jane Doe"


def test_override_keeps_config_value() -> None:
    effective, inherited, overridden = resolve_effective_row(
        _config(override_fields=["lab_rate", "role_title"]), _VERSION
    )
    assert effective["lab_rate"] == "9999.00"  # overridden -> config value
    assert effective["role_title"] == "OWN-ROLE"
    assert effective["employment_type"] == "Full Time"  # still inherited
    assert overridden == ["lab_rate", "role_title"]
    assert "lab_rate" not in inherited


def test_no_template_passthrough() -> None:
    effective, inherited, overridden = resolve_effective_row(
        _config(template_id=None, role_title="Standalone"), None
    )
    assert effective["role_title"] == "Standalone"
    assert effective["lab_rate"] == "9999.00"
    assert inherited == []
    assert overridden == []


def test_missing_version_raises() -> None:
    with pytest.raises(TemplateResolutionError):
        resolve_effective_row(_config(), None)


def test_override_fields_json_string_form() -> None:
    # repository may hand back the raw JSON string instead of a decoded list
    effective, inherited, overridden = resolve_effective_row(
        _config(override_fields=None, override_fields_json='["cost_code"]', cost_code="OWN-CODE"),
        _VERSION,
    )
    assert effective["cost_code"] == "OWN-CODE"  # overridden -> config value, not template
    assert overridden == ["cost_code"]
    assert "cost_code" not in inherited
