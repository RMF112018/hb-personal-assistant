"""Shared helpers for schedule project association tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def seed_procore_ep_project_row(
    db_path: str | Path,
    *,
    project_key: str,
    display_name: str,
    project_number: str | None = None,
    project_id: str = "9001",
    record_key: str | None = None,
    is_current: int = 1,
    updated_utc: str = "2026-06-22T00:00:00Z",
) -> str:
    resolved_record_key = record_key or f"rk-{project_key}-{project_id}"
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO procore_ep_projects (
              record_key, endpoint_key, project_key, project_id, display_name, project_number,
              record_id, source_quality, is_current, created_utc, updated_utc,
              external_writeback_performed, raw_payload_emitted_to_read_model,
              raw_payload_emitted_to_evidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_record_key,
                "projects",
                project_key,
                project_id,
                display_name,
                project_number,
                project_id,
                "ok",
                is_current,
                updated_utc,
                updated_utc,
                0,
                0,
                0,
            ),
        )
        conn.commit()
    return resolved_record_key


def seed_procore_ep_project(
    db_path: str | Path,
    *,
    project_key: str,
    display_name: str,
    project_number: str | None = None,
    project_id: str = "9001",
) -> None:
    seed_procore_ep_project_row(
        db_path,
        project_key=project_key,
        display_name=display_name,
        project_number=project_number,
        project_id=project_id,
    )


def seed_named_schedule_udfs(
    db_path: str | Path,
    *,
    project_key: str,
    schedule_version_key: str,
    import_id: str,
    schedule_id: str = "S1",
    activity_ids: list[str] | None = None,
) -> None:
    """Seed Phase 8B named UDF rows for schedule-controls normalization tests."""
    targets = activity_ids or ["A100", "A200", "A300"]
    udf_rows: list[tuple[str, str, str, str]] = [
        ("OLD ID", "Text", "OLD-100"),
        ("PHASE", "Text", "Phase 1"),
        ("FLOOR", "Text", "Level 2"),
        ("SECTOR / AREA", "Text", "North Wing"),
        ("SUBCONTRACTOR", "Text", "ABC Electric"),
        ("Cost Code", "Text", "26-100"),
        ("Filter Out", "Text", "N"),
        ("Start (Previous Status)", "Text", "Planned"),
        ("Finish (Previous Status)", "Text", "Planned"),
        ("Update Notes", "Text", "Awaiting inspection"),
        ("Update Notes - 1", "Text", "Note one"),
        ("Update Notes - 2", "Text", "Note two"),
        ("Schedule Review Comments", "Text", "Review next week"),
    ]
    with sqlite3.connect(str(db_path)) as conn:
        for activity_id in targets:
            for udf_type_name, udf_data_type, udf_value in udf_rows:
                if activity_id == "A300" and udf_type_name == "Filter Out":
                    udf_value = "MAYBE"
                conn.execute(
                    """
                    INSERT INTO procore_ep_schedule_udf_values (
                      project_key, schedule_table_id, schedule_id, schedule_version_key,
                      import_id, activity_id, udf_type_name, udf_data_type, udf_value,
                      source_object_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_key,
                        schedule_id,
                        schedule_id,
                        schedule_version_key,
                        import_id,
                        activity_id,
                        udf_type_name,
                        udf_data_type,
                        udf_value,
                        f"obj-{udf_type_name}",
                    ),
                )
        conn.commit()


def seed_schedule_quality_findings(
    db_path: str | Path,
    *,
    project_key: str,
    schedule_version_key: str,
    import_id: str,
    evaluation_run_id: str = "quality-run-latest",
    activity_id: str = "A100",
    finding_code: str = "missing_predecessor",
) -> None:
    """Seed latest quality evaluation run + finding for review cue tests."""
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO schedule_quality_evaluation_runs (
              evaluation_run_id, project_key, schedule_version_key, import_id,
              assessment_profile, assessment_profile_version, method_source,
              trigger_source, idempotency_key, status, is_latest,
              completed_at, engine_version, checker_version
            ) VALUES (?, ?, ?, ?, 'default', '1', 'test', 'manual_rerun', ?, 'completed', 1,
              '2026-07-01T10:00:00Z', 'test', 'test')
            """,
            (evaluation_run_id, project_key, schedule_version_key, import_id, f"{evaluation_run_id}-key"),
        )
        conn.execute(
            """
            INSERT INTO schedule_quality_findings (
              project_key, schedule_version_key, import_id, evaluation_run_id,
              finding_type, severity, category, activity_id, finding_code, finding_summary
            ) VALUES (?, ?, ?, ?, 'logic_quality', 'high', 'logic_quality', ?, ?, ?)
            """,
            (
                project_key,
                schedule_version_key,
                import_id,
                evaluation_run_id,
                activity_id,
                finding_code,
                f"Quality finding {finding_code} on {activity_id}",
            ),
        )
        conn.commit()