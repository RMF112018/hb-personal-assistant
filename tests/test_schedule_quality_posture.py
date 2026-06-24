"""Schedule quality posture helper tests."""

from __future__ import annotations

import json

from hb_assistant.construction.analytics.schedule_quality_engine import EvaluationContext
from hb_assistant.construction.analytics.schedule_quality_posture import (
    evaluate_schedule_category,
    resolve_scorecard_metric_status,
)
from hb_assistant.construction.analytics.schedule_quality_profiles import get_profile


def _ctx(**kwargs: object) -> EvaluationContext:
    defaults = {
        "project_key": "tropical",
        "schedule_version_key": "tropical|1|2026-01-10",
        "schedule_table_id": None,
        "import_id": "imp-posture",
        "evaluation_run_id": "sq-posture",
        "assessment_profile": get_profile(),
        "data_date": "2026-01-10",
    }
    defaults.update(kwargs)
    return EvaluationContext(**defaults)


def test_gao_categories_do_not_default_pass_without_evidence() -> None:
    summary = evaluate_schedule_category(
        _ctx(activities=[], import_meta=None), "capturing_all_activities"
    )

    assert summary["posture"] == "fail"
    assert summary["reason"] == "no activities in canonical store"
    assert summary["missing_prerequisites"] == ["activities_present", "import_metadata_present"]
    assert isinstance(summary["evidence"], dict)
    assert not str(summary["reason"]).startswith("{")


def test_schedule_risk_readiness_activities_alone_is_not_pass() -> None:
    summary = evaluate_schedule_category(
        _ctx(
            activities=[{"activity_id": "A1"}],
            relationships=[],
            data_date=None,
            schedule_version_key="tropical|1|not-a-date",
            import_meta={"source_format": "ms_project_xml"},
        ),
        "schedule_risk_readiness",
    )

    assert summary["posture"] in {"warn", "partial"}
    assert summary["posture"] != "pass"
    assert "relationships_present" in summary["missing_prerequisites"]
    assert "risk_uncertainty_inputs" in summary["missing_prerequisites"]
    assert summary["evidence"]["risk_uncertainty_model_present"] is False


def test_baseline_maintenance_true_baseline_vs_target_planned_only() -> None:
    true_baseline = evaluate_schedule_category(
        _ctx(
            activities=[{"activity_id": "A1", "baseline_finish": "2026-01-01"}],
            import_meta={"source_format": "ms_project_xml", "baseline_source": "msp_baseline"},
        ),
        "baseline_maintenance",
    )
    target_only = evaluate_schedule_category(
        _ctx(
            activities=[
                {
                    "activity_id": "A1",
                    "target_finish": "2026-01-01",
                    "planned_finish": "2026-01-01",
                }
            ],
            import_meta={"source_format": "primavera_pmxml"},
        ),
        "baseline_maintenance",
    )

    assert true_baseline["posture"] == "pass"
    assert true_baseline["evidence"]["baseline_finish_count"] == 1
    assert target_only["posture"] == "partial"
    assert target_only["source_evidence_class"] == "proxy_only"
    assert target_only["evidence"]["non_baseline_date_fields"]["used_as_baseline_proxy"] is False


def test_aace_category_is_explicitly_limited() -> None:
    summary = evaluate_schedule_category(
        _ctx(activities=[{"activity_id": "A1"}], import_meta={"source_format": "ms_project_xml"}),
        "source_validation",
        aace=True,
    )

    assert summary["posture"] == "partial"
    assert "not a full AACE compliance assessment" in " ".join(summary["caveats"])


def test_critical_path_non_cpm_evidence_never_passes() -> None:
    cases = [
        _ctx(
            activities=[{"activity_id": "A1", "source_critical_flag": True}],
            import_meta={"source_format": "ms_project_xml"},
        ),
        _ctx(
            activities=[{"activity_id": "A1", "derived_float_basis": "remaining_finish"}],
            import_meta={"source_format": "primavera_pmxml"},
            schedule_options={"calculate_float_based_on_finish_date": True},
        ),
        _ctx(
            activities=[{"activity_id": "A1", "source_driving_path_flag": True}],
            import_meta={"source_format": "primavera_pmxml"},
        ),
    ]

    for ctx in cases:
        summary = evaluate_schedule_category(ctx, "critical_path_validity")
        assert summary["posture"] in {"partial", "not_measurable"}
        assert summary["posture"] != "pass"
        assert summary["evidence"]["cpm_recalculation_performed"] is False
        assert summary["evidence"]["critical_path_requires_cpm_recalculation"] is True


def test_scorecard_resolver_unwraps_only_scorable_dcma_thresholds() -> None:
    derived = {
        "metric_code": "dcma_high_float",
        "metric_family": "dcma",
        "status": "measured_from_derived_finish_float",
        "evidence_json": json.dumps({"threshold_status": "warning_threshold"}),
    }
    source_export = {
        "metric_code": "source_msp_critical_slack_available",
        "metric_family": "source_export",
        "status": "measured_from_msp_critical_flag",
        "evidence_json": json.dumps({"threshold_status": "passed_threshold"}),
    }

    assert resolve_scorecard_metric_status(derived) == {
        "metric_code": "dcma_high_float",
        "metric_family": "dcma",
        "raw_status": "measured_from_derived_finish_float",
        "resolved_status": "warning_threshold",
        "included": True,
        "exclusion_reason": None,
    }
    excluded = resolve_scorecard_metric_status(source_export)
    assert excluded["included"] is False
    assert excluded["resolved_status"] is None
    assert excluded["exclusion_reason"] == "non_dcma_advisory_metric"
