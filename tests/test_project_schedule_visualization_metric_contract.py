"""Phase 5 visualization metric formula contract tests."""

from __future__ import annotations

import inspect
from pathlib import Path

from hb_assistant.construction.analytics import project_schedule_visualization_metric_contract as contract_module
from hb_assistant.construction.analytics.project_schedule_visualization_metric_contract import (
    APPROVED_BASIS_LABELS,
    APPROVED_READINESS_STATUSES,
    NON_CAUSATION_CAVEAT,
    REQUIRED_METRIC_KEYS,
    REQUIRED_NAMED_UDFS,
    ProjectScheduleVisualizationMetricContractService,
    get_visualization_metric_contracts,
    get_visualization_metric_readiness_matrix,
)
from hb_assistant.store.migrator import SQLiteMigrator


def _contracts() -> dict[str, dict]:
    return {contract["metric_key"]: contract for contract in get_visualization_metric_contracts()}


def test_registry_contains_exact_required_neutral_metric_keys() -> None:
    contracts = _contracts()
    assert tuple(contracts) == REQUIRED_METRIC_KEYS
    assert set(contracts) == set(REQUIRED_METRIC_KEYS)
    forbidden = ("smartpm", "smart_pm", "smart-pm", "twnu07")
    for key in contracts:
        lowered = key.lower()
        assert all(term not in lowered for term in forbidden)


def test_every_metric_contract_has_required_phase5_fields() -> None:
    required_fields = {
        "metric_key",
        "display_name",
        "category",
        "pm_facing_purpose",
        "formula_summary",
        "formula_detail",
        "source_tables",
        "source_columns",
        "udf_dependencies",
        "comparison_basis",
        "weighting_basis",
        "default_weighting_basis",
        "configurable_thresholds",
        "configurable_weights",
        "readiness_status",
        "blockers",
        "caveats",
        "future_api_payload_shape",
        "required_tests",
        "notes",
        "basis_labels",
    }
    for contract in get_visualization_metric_contracts():
        assert required_fields <= set(contract)
        for field in (
            "pm_facing_purpose",
            "formula_summary",
            "formula_detail",
            "source_tables",
            "source_columns",
            "comparison_basis",
            "weighting_basis",
            "default_weighting_basis",
            "readiness_status",
            "caveats",
            "future_api_payload_shape",
            "required_tests",
            "basis_labels",
        ):
            assert contract[field], f"{contract['metric_key']} missing {field}"
        assert contract["readiness_status"] in APPROVED_READINESS_STATUSES
        assert set(contract["basis_labels"]) <= set(APPROVED_BASIS_LABELS)


def test_schema_mapped_sources_exist_in_migrated_sqlite_schema(tmp_path: Path) -> None:
    db = tmp_path / "phase5-schema.db"
    SQLiteMigrator(db_path=str(db)).apply()
    service = ProjectScheduleVisualizationMetricContractService(db_path=str(db))

    validation = service.column_mapping_summary()["validation"]
    assert validation
    missing = {
        table: result["missing_columns"]
        for table, result in validation.items()
        if result["missing_columns"] or not result["present"]
    }
    assert missing == {}

    table_names = {row["table_name"] for row in service.table_inventory()}
    for contract in get_visualization_metric_contracts():
        assert set(contract["source_tables"]) <= table_names


def test_readiness_matrix_and_dependency_map_are_complete() -> None:
    service = ProjectScheduleVisualizationMetricContractService()
    matrix = service.readiness_matrix()
    dependency_map = service.dependency_map()
    assert [row["metric_key"] for row in matrix] == list(REQUIRED_METRIC_KEYS)
    assert [row["metric_key"] for row in dependency_map] == list(REQUIRED_METRIC_KEYS)
    for row in matrix + dependency_map:
        assert row["readiness_status"] in APPROVED_READINESS_STATUSES
        assert set(row["basis_labels"]) <= set(APPROVED_BASIS_LABELS)
        assert isinstance(row["blockers"], list)


def test_duration_weighted_progress_and_spi_are_defaults_and_cost_weighted_is_blocked() -> None:
    contracts = _contracts()
    for key in ("planned_vs_actual_percent_complete", "schedule_performance_ratio"):
        metric = contracts[key]
        assert metric["default_weighting_basis"] == "duration_weighted"
        assert "duration_weighted" in metric["weighting_basis"]
        assert "cost_weighted_deferred" in metric["weighting_basis"]
        assert any("cost" in blocker.lower() for blocker in metric["blockers"])
        assert metric["readiness_status"] != "ready_now"


def test_configurable_thresholds_and_weights_are_declared() -> None:
    contracts = _contracts()
    assert "critical_float_threshold_days" in contracts["critical_path_length_index"]["configurable_thresholds"]
    assert "critical_float_threshold_days" in contracts["should_have_finished_status"]["configurable_thresholds"]
    assert contracts["schedule_compression_ratio"]["configurable_thresholds"] == {
        "green_max_percent": 14,
        "yellow_max_percent": 25,
        "red_min_percent": 26,
    }
    health_weights = contracts["project_schedule_health_index"]["configurable_weights"]
    assert {"logic_density", "float", "critical_duration", "constraints", "update_quality", "compression"} <= set(
        health_weights
    )
    assert abs(sum(health_weights.values()) - 1.0) < 0.0001


def test_udf_dependent_metrics_are_not_ready_now_without_normalization(tmp_path: Path) -> None:
    db = tmp_path / "phase5-udf.db"
    SQLiteMigrator(db_path=str(db)).apply()
    service = ProjectScheduleVisualizationMetricContractService(db_path=str(db))
    udf_summary = service.udf_availability_summary()
    assert udf_summary["generic_udf_table_present"] is True
    assert tuple(udf_summary["required_named_udfs"]) == REQUIRED_NAMED_UDFS
    assert udf_summary["stable_named_udf_normalization_proven"] is True

    for metric in get_visualization_metric_contracts():
        if metric["udf_dependencies"]:
            assert metric["readiness_status"] != "ready_now"
            assert metric["readiness_status"] == "ready_after_udf_normalization"
            assert "udf_derived" in metric["basis_labels"]


def test_delay_driver_recovery_and_critical_issue_metrics_have_non_causation_caveat() -> None:
    contracts = _contracts()
    for key in ("schedule_delay_over_time", "delay_analysis", "required_recovery_days", "critical_issues_category_model"):
        assert NON_CAUSATION_CAVEAT in contracts[key]["caveats"]


def test_baseline_and_float_basis_are_not_conflated() -> None:
    contracts = _contracts()
    assert {"baseline", "selected_baseline", "prior_update"} <= set(contracts["schedule_compression_ratio"]["basis_labels"])
    assert {"source_export", "computed_cpm"} <= set(contracts["total_float_consumption_index"]["basis_labels"])
    assert any("must remain separate" in caveat.lower() for caveat in contracts["total_float_consumption_index"]["caveats"])


def test_phase5_module_is_contract_only_and_scope_bounded() -> None:
    source = inspect.getsource(contract_module)
    forbidden_tokens = (
        "FastAPI",
        "@router",
        "APIRouter",
        "React",
        "Chart",
        "INSERT INTO",
        "UPDATE ",
        "DELETE FROM",
        "CREATE TABLE",
    )
    for token in forbidden_tokens:
        assert token not in source
    assert "project_schedule_import_pipeline" not in source
    assert "baseline override" not in source.lower()
