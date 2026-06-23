"""P4b — project-config loader + tropical byte-parity anchor.

The loader (common/project_config.py) is the single source of every project-specific value the
generators previously hardcoded. These tests assert that the tropical config reproduces the EXACT
former literals (so identical config => byte-identical tropical output) and that it fails closed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from construction_financial_review.common.project_config import (
    ProjectConfigError,
    load_project_config,
    resolve_project_key,
)

# Exact former hardcoded literals from the generators (byte-parity anchor).
_TROPICAL = {
    "project_name": "Tropical World Nursery Senior Living Facility",
    "project_display_name": "Tropical World Nursery",
    "job_reference": "23-435-01",
    "forecast_period": "2026-June",
    "procore_export_folder": "cost_forecast_agent_db_json_export_tropical_20260614_080344",
    "june_cutoff": "2026-06-01",
    "july_cutoff": "2026-07-01",
}
_TROPICAL_ROWCOUNTS = {
    "canonical/budget_codes.jsonl": 127,
    "canonical/cost_entries.jsonl": 6324,
    "canonical/monthly_actuals_by_budget_code.jsonl": 1081,
    "canonical/owner_pay_app_line_items_mapped.jsonl": 1657,
    "canonical/owner_pay_app_totals.jsonl": 63,
    "canonical/procore_subcontractor_payment_app_headers.jsonl": 219,
    "canonical/procore_subcontractor_payment_app_line_items_mapped.jsonl": 13088,
    "canonical/procore_commitments.jsonl": 73,
}
_XW_AUTHORITATIVE_NAME = "owner_sov_scope_crosswalk_tropical_authoritative_20260614_final"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("CFR_PROJECT_KEY", raising=False)
    monkeypatch.delenv("HB_FORECAST_EVAL_PROJECT_ALLOWLIST", raising=False)


def test_resolve_project_key_default_and_env(monkeypatch):
    assert resolve_project_key() == "tropical"
    monkeypatch.setenv("CFR_PROJECT_KEY", "fixtureproj")
    assert resolve_project_key() == "fixtureproj"


def test_tropical_config_reproduces_former_literals():
    cfg = load_project_config("tropical")
    for key, value in _TROPICAL.items():
        assert cfg[key] == value, key
    assert cfg["row_count_expectations"] == _TROPICAL_ROWCOUNTS
    # the owner-SOV crosswalk DIR name derives from the config path stem == former XW_AUTHORITATIVE_NAME
    assert Path(cfg["owner_sov_scope_crosswalk"]).stem == _XW_AUTHORITATIVE_NAME


def test_missing_project_fails_closed():
    with pytest.raises(ProjectConfigError):
        load_project_config("nope-not-a-real-project")


def test_ineligible_project_fails_closed():
    # "other" is not in the default allowlist -> refused before any file access
    with pytest.raises(ProjectConfigError):
        load_project_config("other")


def test_fixtureproj_loads_with_required_fields():
    cfg = load_project_config("fixtureproj")
    assert cfg["project_key"] == "fixtureproj"
    for key in (
        "project_name",
        "project_display_name",
        "job_reference",
        "forecast_period",
        "procore_export_folder",
        "june_cutoff",
        "july_cutoff",
        "row_count_expectations",
        "owner_sov_scope_crosswalk",
        "default_data_root",
    ):
        assert key in cfg, key
