"""Baseline-dependent schedule quality helper tests."""

from __future__ import annotations

from hb_assistant.construction.analytics.schedule_baseline_quality import (
    compute_baseline_quality_evidence,
    resolve_status_date,
)


def test_baseline_quality_counts_true_baseline_and_non_baseline_dates() -> None:
    evidence = compute_baseline_quality_evidence(
        activities=[
            {
                "activity_id": "A1",
                "baseline_start": "2026-01-01",
                "baseline_finish": "2026-01-05",
                "target_start": "2026-01-02",
                "target_finish": "2026-01-06",
                "planned_finish": "2026-01-07",
                "activity_status": "TK_Complete",
                "actual_finish": "2026-01-04",
            },
            {
                "activity_id": "A2",
                "target_finish": "2026-01-08",
                "planned_finish": "2026-01-09",
            },
            {
                "activity_id": "MS",
                "baseline_finish": "2026-01-05",
                "is_milestone": True,
            },
            {
                "activity_id": "LOE",
                "baseline_finish": "2026-01-05",
                "activity_type": "LOE",
            },
        ],
        ctx_data_date="2026-01-10",
        import_meta={"baseline_source": "msp_baseline"},
        schedule_version_key="tropical|1|2026-01-01",
    )

    assert evidence["total_activity_count"] == 4
    assert evidence["eligible_activity_count"] == 2
    assert evidence["excluded_activity_count"] == 2
    assert evidence["exclusion_reasons"]["milestone"] == 1
    assert evidence["exclusion_reasons"]["summary_or_loe"] == 1
    assert evidence["baseline_start_count"] == 1
    assert evidence["baseline_finish_count"] == 1
    assert evidence["target_finish_count"] == 2
    assert evidence["planned_finish_count"] == 2
    assert evidence["non_baseline_date_fields"]["used_as_baseline_proxy"] is False
    assert evidence["baseline_source"] == "msp_baseline"
    assert evidence["true_baseline_finish_dates_available"] is True


def test_status_date_resolution_order_and_invalid_reporting() -> None:
    resolved = resolve_status_date(
        ctx_data_date="not-a-date",
        import_meta={"status_date": "2026-02-03"},
        schedule_version_key="tropical|1|2026-01-01",
    )
    assert resolved["status_date"] == "2026-02-03"
    assert resolved["status_date_source"] == "import_meta.status_date"
    assert resolved["status_date_parse_success"] is True
    assert resolved["invalid_status_date_candidates"] == [
        {"source": "ctx.data_date", "raw": "not-a-date", "reason": "invalid"}
    ]

    missing = resolve_status_date(
        ctx_data_date=None,
        import_meta={},
        schedule_version_key="tropical|1|not-a-date",
    )
    assert missing["status_date_parse_success"] is False
    assert missing["status_date_missing_reason"] == "invalid_status_date"


def test_baseline_quality_reports_missing_prerequisites() -> None:
    evidence = compute_baseline_quality_evidence(
        activities=[
            {
                "activity_id": "A1",
                "target_finish": "2026-01-05",
                "planned_finish": "2026-01-06",
            }
        ],
        ctx_data_date=None,
        import_meta={},
        schedule_version_key="tropical|1|not-a-date",
    )

    assert evidence["only_target_or_planned_dates_available"] is True
    assert "invalid_status_date" in evidence["missing_prerequisites"]
    assert "missing baseline finish dates" in evidence["missing_prerequisites"]
    assert evidence["missed_tasks_measurable"] is False
    assert evidence["bei_measurable"] is False
