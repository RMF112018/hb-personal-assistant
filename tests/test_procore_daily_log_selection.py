"""Phase 04 Prompt 08 — Procore daily log selection scope loader tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from hb_assistant.procore.daily_log_selection import (
    DAILY_LOG_SELECTION_ENV_VAR,
    DailyLogSelectionError,
    ProcoreDailyLogSelection,
    load_daily_log_selection,
)


def test_load_daily_log_selection_from_seed() -> None:
    selection = load_daily_log_selection()
    assert isinstance(selection, ProcoreDailyLogSelection)
    assert selection.version == 1
    assert len(selection.selected_sections) == 5
    assert len(selection.review_only_sections) == 1
    assert len(selection.routed_to_review_sections) == 4
    selected_ids = {s.id for s in selection.selected_sections}
    assert selected_ids == {"counts", "weather", "manpower", "dcr", "delivery"}
    review_ids = {s.id for s in selection.review_only_sections}
    assert review_ids == {"notes"}
    routed_ids = {s.id for s in selection.routed_to_review_sections}
    assert routed_ids == {"accident", "injury", "delay", "safety"}


def test_daily_log_selection_payload_keys_helper_returns_bucket_map() -> None:
    selection = load_daily_log_selection()
    mapping = selection.payload_keys()
    # Spot-check that each section's payload_key resolves to the expected bucket.
    assert mapping["counts"] == "selected"
    assert mapping["weather_logs"] == "selected"
    assert mapping["manpower_logs"] == "selected"
    assert mapping["dcr_logs"] == "selected"
    assert mapping["delivery_logs"] == "selected"
    assert mapping["notes_logs"] == "review_only"
    assert mapping["accident_logs"] == "routed_to_review"
    assert mapping["injury_logs"] == "routed_to_review"
    assert mapping["delay_logs"] == "routed_to_review"
    assert mapping["safety_violation_logs"] == "routed_to_review"


def test_daily_log_selection_rejects_duplicate_section_ids_across_buckets() -> None:
    bad = {
        "version": 1,
        "selected_sections": [
            {"id": "x", "payload_key": "xs", "category": "x_selected"},
        ],
        "review_only_sections": [
            {"id": "x", "payload_key": "xs2", "category": "x_review"},
        ],
        "routed_to_review_sections": [
            {"id": "y", "payload_key": "ys", "category": "y_routed"},
        ],
    }
    with pytest.raises(ValueError):
        ProcoreDailyLogSelection.model_validate(bad)


def test_daily_log_selection_rejects_duplicate_categories() -> None:
    bad = {
        "version": 1,
        "selected_sections": [
            {"id": "a", "payload_key": "as_", "category": "shared_category"},
        ],
        "review_only_sections": [
            {"id": "b", "payload_key": "bs_", "category": "shared_category"},
        ],
        "routed_to_review_sections": [
            {"id": "c", "payload_key": "cs_", "category": "c_routed"},
        ],
    }
    with pytest.raises(ValueError):
        ProcoreDailyLogSelection.model_validate(bad)


def test_daily_log_selection_rejects_empty_scope() -> None:
    bad = {
        "version": 1,
        "selected_sections": [],
        "review_only_sections": [],
        "routed_to_review_sections": [],
    }
    with pytest.raises(ValueError):
        ProcoreDailyLogSelection.model_validate(bad)


def test_load_daily_log_selection_env_override(tmp_path: Path) -> None:
    custom = {
        "version": 2,
        "selected_sections": [
            {
                "id": "custom",
                "payload_key": "custom_logs",
                "category": "custom_category",
                "canonical_field_keys": ["id"],
            }
        ],
        "review_only_sections": [
            {"id": "rev", "payload_key": "rev_logs", "category": "rev_category"}
        ],
        "routed_to_review_sections": [
            {"id": "rt", "payload_key": "rt_logs", "category": "rt_category"}
        ],
    }
    path = tmp_path / "custom.seed.yaml"
    path.write_text(yaml.safe_dump(custom))
    os.environ[DAILY_LOG_SELECTION_ENV_VAR] = str(path)
    try:
        selection = load_daily_log_selection()
    finally:
        os.environ.pop(DAILY_LOG_SELECTION_ENV_VAR, None)
    assert selection.version == 2
    assert selection.selected_sections[0].id == "custom"


def test_load_daily_log_selection_invalid_yaml_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.seed.yaml"
    bad.write_text("- this is a list, not a mapping\n")
    with pytest.raises(DailyLogSelectionError):
        load_daily_log_selection(override_path=bad)
