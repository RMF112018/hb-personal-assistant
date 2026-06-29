"""Project Schedule Hub API contract tests."""

from __future__ import annotations

import json
import re
import signal
import sqlite3
import time
from datetime import date
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from hb_assistant.construction.analytics import create_app
from hb_assistant.construction.analytics.project_schedule_summary_service import (
    ProjectScheduleSummaryService,
    _comparison_activity_movement,
    _comparison_finish_field,
)
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project

RAW_VERSION_PATTERN = re.compile(r"[A-Za-z0-9_-]+\|[A-Za-z0-9_-]+\|\d{4}-\d{2}-\d{2}")


def _viewer() -> dict[str, str]:
    return {"X-HB-UI-Role": "viewer"}


def _fresh_db(tmp_path: Path) -> Path:
    db = tmp_path / "project-schedule-hub.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    return db


def _table_counts(db: Path) -> dict[str, int]:
    with sqlite3.connect(db) as conn:
        names = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        return {name: int(conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]) for name in names}


def _seed_one_version(db: Path, *, review_required: bool = False) -> None:
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO schedule_file_imports (
              import_id, project_key, source_type, source_format, import_status,
              activity_count, relationship_count, cost_loaded_status,
              schedule_version_key, source_filename_redacted, created_at
            ) VALUES (
              'imp-current', 'tropical', 'xer', 'primavera_xer', 'committed',
              3, 1, 'not_cost_loaded', 'tropical|S1|2026-06-23', 'TWNU19.xer',
              '2026-06-24T10:00:00Z'
            )
            """
        )
        activities = [
            ("A100", "Area A remaining", "2026-06-23", "2026-07-05", None, None, "WBS-A", "2", 0),
            ("A200", "Substantial completion milestone", "2026-07-05", "2026-07-05", None, None, "WBS-A", "0", 1),
            ("A300", "Recently completed", "2026-06-10", "2026-06-20", "2026-06-10", "2026-06-20", "WBS-B", "5", 0),
        ]
        for row in activities:
            conn.execute(
                """
                INSERT INTO procore_ep_schedule_activities (
                  project_key, schedule_id, schedule_version_key, import_id,
                  source_type, source_format, activity_id, activity_name,
                  start_date, finish_date, actual_start, actual_finish,
                  wbs_code, total_float, is_milestone
                ) VALUES ('tropical', 'S1', 'tropical|S1|2026-06-23', 'imp-current',
                  'xer', 'primavera_xer', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row,
            )
        conn.execute(
            """
            INSERT INTO procore_ep_schedule_relationships (
              project_key, schedule_id, schedule_version_key, import_id,
              predecessor_activity_id, successor_activity_id, relationship_type
            ) VALUES (
              'tropical', 'S1', 'tropical|S1|2026-06-23', 'imp-current',
              'A100', 'A200', 'FS'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO schedule_identities (
              schedule_identity_key, project_key, identity_status, latest_import_id,
              latest_schedule_version_key
            ) VALUES ('identity-main', 'tropical', 'active', 'imp-current', 'tropical|S1|2026-06-23')
            """
        )
        conn.execute(
            """
            INSERT INTO schedule_version_identity_matches (
              match_id, schedule_identity_key, schedule_version_key, import_id, project_key,
              source_format, activity_count, relationship_count, wbs_count,
              match_type, match_status, match_rule, confidence_score, requires_review
            ) VALUES (
              'match-current', 'identity-main', 'tropical|S1|2026-06-23', 'imp-current',
              'tropical', 'primavera_xer', 3, 1, 0, 'seed',
              ?, 'seed', '1.00', ?
            )
            """,
            ("requires_review" if review_required else "resolved", 1 if review_required else 0),
        )
        conn.commit()


def _seed_persisted_diff(db: Path) -> int:
    with sqlite3.connect(db) as conn:
        cur = conn.execute(
            """
            INSERT INTO schedule_version_diffs (
              project_key, from_schedule_version_key, to_schedule_version_key,
              diff_type, activity_changed_count, finish_drift_days
            ) VALUES (
              'tropical', 'tropical|S1|2026-06-01', 'tropical|S1|2026-07-01',
              'identity_safe_default', 2, '15'
            )
            """
        )
        diff_id = int(cur.lastrowid)
        conn.execute(
            """
            INSERT INTO schedule_version_diff_facts (
              diff_fact_id, diff_id, project_key, from_schedule_version_key,
              to_schedule_version_key, metric_key, metric_value, status, basis
            ) VALUES (
              'fact-default-diff', ?, 'tropical', 'tropical|S1|2026-06-01',
              'tropical|S1|2026-07-01', 'activity_changed_count', '2',
              'available', 'seeded_test_diff'
            )
            """,
            (diff_id,),
        )
        for detail_id, activity_id, name, field, old, new, delta in (
            ("detail-a100", "A100", "Area A start", "finish_date", "2026-06-05", "2026-06-17", 12),
            ("detail-a200", "A200", "Substantial completion milestone", "finish_date", "2026-06-10", "2026-06-25", 15),
        ):
            conn.execute(
                """
                INSERT INTO schedule_version_diff_detail_facts (
                  detail_id, diff_id, project_key, from_schedule_version_key,
                  to_schedule_version_key, schedule_identity_key, identity_safe,
                  comparison_type, change_domain, change_type, entity_key,
                  entity_label, wbs_code, activity_id, activity_name, field_name,
                  from_value, to_value, day_delta, severity,
                  is_critical_path_related, requires_attention
                ) VALUES (
                  ?, ?, 'tropical', 'tropical|S1|2026-06-01',
                  'tropical|S1|2026-07-01', 'identity-main', 1,
                  'identity_safe_default', 'activity', 'date_drift', ?,
                  ?, 'WBS-A', ?, ?, ?, ?, ?, ?, 'critical', 1, 1
                )
                """,
                (detail_id, diff_id, activity_id, name, activity_id, name, field, old, new, delta),
            )
        conn.execute(
            """
            INSERT INTO schedule_version_diff_impact_rollups (
              rollup_id, diff_id, project_key, from_schedule_version_key,
              to_schedule_version_key, schedule_identity_key, comparison_type,
              identity_safe, rollup_type, rollup_key, rollup_label, wbs_code,
              activity_count, change_count, critical_count, date_drift_count,
              requires_attention_count, max_day_delta, net_day_delta,
              max_later_day_delta, impact_score, impact_level, requires_attention
            ) VALUES (
              'rollup-summary', ?, 'tropical', 'tropical|S1|2026-06-01',
              'tropical|S1|2026-07-01', 'identity-main', 'identity_safe_default',
              1, 'summary', 'summary', 'Summary', NULL, 2, 2, 2, 2, 2,
              15, 27, 15, '90', 'critical', 1
            )
            """,
            (diff_id,),
        )
        conn.commit()
    return diff_id


def _seed_comparable_versions(db: Path) -> None:
    with sqlite3.connect(db) as conn:
        for import_id, version_key, filename, activities, relationships in (
            (
                "imp-prior",
                "tropical|S1|2026-06-01",
                "TWNU18.xer",
                [
                    ("A100", "Area A start", "2026-06-01", "2026-06-05", None, None, "WBS-A", "5", 0),
                    ("A200", "Substantial completion milestone", "2026-06-06", "2026-06-10", None, None, "WBS-A", "0", 1),
                ],
                [("A100", "A200", "FS")],
            ),
            (
                "imp-current",
                "tropical|S1|2026-07-01",
                "TWNU19.xer",
                [
                    ("A100", "Area A start", "2026-06-01", "2026-06-17", "2026-06-01", "", "WBS-A", "-2", 0),
                    ("A200", "Substantial completion milestone", "2026-06-18", "2026-06-25", None, None, "WBS-A", "0", 1),
                    ("A300", "Closeout work", "2026-06-26", "2026-07-03", None, None, "WBS-B", "3", 0),
                ],
                [("A100", "A200", "FS"), ("A200", "A300", "FS")],
            ),
        ):
            conn.execute(
                """
                INSERT INTO schedule_file_imports (
                  import_id, project_key, source_type, source_format, import_status,
                  activity_count, relationship_count, cost_loaded_status,
                  schedule_version_key, source_filename_redacted, created_at
                ) VALUES (?, 'tropical', 'xer', 'primavera_xer', 'committed',
                  ?, ?, 'not_cost_loaded', ?, ?, ?)
                """,
                (import_id, len(activities), len(relationships), version_key, filename, version_key.split("|")[-1]),
            )
            for row in activities:
                conn.execute(
                    """
                    INSERT INTO procore_ep_schedule_activities (
                      project_key, schedule_id, schedule_version_key, import_id,
                      source_type, source_format, activity_id, activity_name,
                      start_date, finish_date, actual_start, actual_finish,
                      wbs_code, total_float, is_milestone
                    ) VALUES ('tropical', 'S1', ?, ?, 'xer', 'primavera_xer',
                      ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (version_key, import_id, *row),
                )
            for pred, succ, rel_type in relationships:
                conn.execute(
                    """
                    INSERT INTO procore_ep_schedule_relationships (
                      project_key, schedule_id, schedule_version_key, import_id,
                      predecessor_activity_id, successor_activity_id, relationship_type
                    ) VALUES ('tropical', 'S1', ?, ?, ?, ?, ?)
                    """,
                    (version_key, import_id, pred, succ, rel_type),
                )
            conn.execute(
                """
                INSERT OR IGNORE INTO schedule_identities (
                  schedule_identity_key, project_key, identity_status, latest_import_id,
                  latest_schedule_version_key
                ) VALUES ('identity-main', 'tropical', 'active', ?, ?)
                """,
                (import_id, version_key),
            )
            conn.execute(
                """
                INSERT INTO schedule_version_identity_matches (
                  match_id, schedule_identity_key, schedule_version_key, import_id, project_key,
                  source_format, activity_count, relationship_count, wbs_count,
                  match_type, match_status, match_rule, confidence_score, requires_review
                ) VALUES (?, 'identity-main', ?, ?, 'tropical', 'primavera_xer',
                  ?, ?, 0, 'seed', 'resolved', 'seed', '1.00', 0)
                """,
                (f"match-{import_id}", version_key, import_id, len(activities), len(relationships)),
            )
        conn.commit()


def _seed_unrelated_future_version(db: Path) -> None:
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO schedule_file_imports (
              import_id, project_key, source_type, source_format, import_status,
              activity_count, relationship_count, cost_loaded_status,
              schedule_version_key, source_filename_redacted, created_at
            ) VALUES (
              'imp-future-unrelated', 'tropical', 'xer', 'primavera_xer', 'committed',
              1, 0, 'not_cost_loaded', 'tropical|S2|2026-08-01',
              'UnrelatedFuture.xer', '2026-07-04T09:00:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO procore_ep_schedule_activities (
              project_key, schedule_id, schedule_version_key, import_id,
              source_type, source_format, activity_id, activity_name,
              start_date, finish_date, actual_start, actual_finish,
              wbs_code, total_float, is_milestone
            ) VALUES (
              'tropical', 'S2', 'tropical|S2|2026-08-01', 'imp-future-unrelated',
              'xer', 'primavera_xer', 'F100', 'Future unrelated work',
              '2026-08-01', '2026-08-10', NULL, NULL, 'WBS-F', '0', 0
            )
            """
        )
        conn.execute(
            """
            INSERT INTO schedule_identities (
              schedule_identity_key, project_key, identity_status, latest_import_id,
              latest_schedule_version_key
            ) VALUES (
              'identity-future-unrelated', 'tropical', 'active',
              'imp-future-unrelated', 'tropical|S2|2026-08-01'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO schedule_version_identity_matches (
              match_id, schedule_identity_key, schedule_version_key, import_id, project_key,
              source_format, activity_count, relationship_count, wbs_count,
              match_type, match_status, match_rule, confidence_score, requires_review
            ) VALUES (
              'match-future-unrelated', 'identity-future-unrelated',
              'tropical|S2|2026-08-01', 'imp-future-unrelated',
              'tropical', 'primavera_xer', 1, 0, 0, 'seed',
              'resolved', 'seed', '1.00', 0
            )
            """
        )
        conn.commit()


def _seed_large_tropical_schedule(db: Path, *, activity_count: int = 1800) -> None:
    prior_key = "tropical|S1|2026-06-01"
    current_key = "tropical|S1|2026-07-01"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO schedule_identities (
              schedule_identity_key, project_key, identity_status, latest_import_id,
              latest_schedule_version_key
            ) VALUES ('identity-main', 'tropical', 'active', 'imp-current-large', ?)
            """,
            (current_key,),
        )
        for import_id, version_key, created_at in (
            ("imp-prior-large", prior_key, "2026-06-02T08:00:00Z"),
            ("imp-current-large", current_key, "2026-07-02T08:00:00Z"),
        ):
            conn.execute(
                """
                INSERT INTO schedule_file_imports (
                  import_id, project_key, source_type, source_format, import_status,
                  activity_count, relationship_count, cost_loaded_status,
                  schedule_version_key, source_filename_redacted, created_at
                ) VALUES (?, 'tropical', 'xer', 'primavera_xer', 'committed',
                  ?, ?, 'not_cost_loaded', ?, ?, ?)
                """,
                (import_id, activity_count, activity_count - 1, version_key, f"{import_id}.xer", created_at),
            )
            conn.execute(
                """
                INSERT INTO schedule_version_identity_matches (
                  match_id, schedule_identity_key, schedule_version_key, import_id, project_key,
                  source_format, activity_count, relationship_count, wbs_count,
                  match_type, match_status, match_rule, confidence_score, requires_review
                ) VALUES (?, 'identity-main', ?, ?, 'tropical', 'primavera_xer',
                  ?, ?, 0, 'seed', 'resolved', 'seed', '1.00', 0)
                """,
                (f"match-{import_id}", version_key, import_id, activity_count, activity_count - 1),
            )

        prior_rows = []
        current_rows = []
        rel_rows = []
        for i in range(activity_count):
            aid = f"A{i:05d}"
            wbs = f"WBS-{i % 12:02d}"
            prior_finish = f"2026-06-{(i % 28) + 1:02d}"
            current_finish = f"2026-07-{(i % 28) + 1:02d}"
            is_milestone = 1 if i % 100 == 0 else 0
            prior_rows.append((prior_key, "imp-prior-large", aid, f"Activity {i:05d}", prior_finish, prior_finish, None, None, wbs, "5", is_milestone))
            actual_start = "2026-06-20" if i % 9 == 0 else None
            actual_finish = "2026-06-25" if i % 11 == 0 else None
            float_value = "-2" if i % 37 == 0 else ("0" if i % 29 == 0 else "6")
            current_rows.append((current_key, "imp-current-large", aid, f"Activity {i:05d}", current_finish, current_finish, actual_start, actual_finish, wbs, float_value, is_milestone))
            if i:
                rel_rows.append((current_key, "imp-current-large", f"A{i - 1:05d}", aid, "FS"))

        conn.executemany(
            """
            INSERT INTO procore_ep_schedule_activities (
              project_key, schedule_id, schedule_version_key, import_id,
              source_type, source_format, activity_id, activity_name,
              start_date, finish_date, actual_start, actual_finish,
              wbs_code, total_float, is_milestone
            ) VALUES ('tropical', 'S1', ?, ?, 'xer', 'primavera_xer', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            prior_rows + current_rows,
        )
        conn.executemany(
            """
            INSERT INTO procore_ep_schedule_relationships (
              project_key, schedule_id, schedule_version_key, import_id,
              predecessor_activity_id, successor_activity_id, relationship_type
            ) VALUES ('tropical', 'S1', ?, ?, ?, ?, ?)
            """,
            rel_rows,
        )
        cur = conn.execute(
            """
            INSERT INTO schedule_version_diffs (
              project_key, from_schedule_version_key, to_schedule_version_key,
              diff_type, activity_changed_count, finish_drift_days
            ) VALUES ('tropical', ?, ?, 'identity_safe_default', 50, '30')
            """,
            (prior_key, current_key),
        )
        diff_id = int(cur.lastrowid)
        detail_rows = [
            (
                f"large-detail-{i}", diff_id, f"A{i:05d}", f"Activity {i:05d}",
                "2026-06-15", "2026-07-15", 30, 1 if i < 20 else 0,
            )
            for i in range(50)
        ]
        conn.executemany(
            """
            INSERT INTO schedule_version_diff_detail_facts (
              detail_id, diff_id, project_key, from_schedule_version_key,
              to_schedule_version_key, schedule_identity_key, identity_safe,
              comparison_type, change_domain, change_type, entity_key,
              entity_label, wbs_code, activity_id, activity_name, field_name,
              from_value, to_value, day_delta, severity,
              is_critical_path_related, requires_attention
            ) VALUES (?, ?, 'tropical', ?, ?, 'identity-main', 1,
              'identity_safe_default', 'activity', 'date_drift', ?,
              ?, 'WBS-00', ?, ?, 'finish_date', ?, ?, ?, 'critical', ?, 1)
            """,
            [
                (detail_id, did, prior_key, current_key, aid, name, aid, name, old, new, delta, crit)
                for detail_id, did, aid, name, old, new, delta, crit in detail_rows
            ],
        )
        for calc in ("graph_diagnostics", "forward_pass", "backward_pass", "float", "longest_path", "criticality"):
            conn.execute(
                """
                INSERT INTO schedule_cpm_runs (
                  cpm_run_id, project_key, schedule_version_key, import_id,
                  node_count, edge_count, is_acyclic, diagnostic_count,
                  analysis_scope, cpm_recalculation_status, calculation_type,
                  computed_activity_count, blocked_activity_count, created_at
                ) VALUES (?, 'tropical', ?, 'imp-current-large', ?, ?, 1, 0,
                  'test_fixture', 'persisted', ?, ?, 0, '2026-07-02T09:00:00Z')
                """,
                (f"cpm-{calc}", current_key, activity_count, activity_count - 1, calc, activity_count),
            )
        cpm_rows = [
            (
                "cpm-criticality", current_key, "tropical", f"A{i:05d}", f"Activity {i:05d}",
                i, 1 if i < 10 else 0, 1 if 10 <= i < 25 else 0, "computed",
            )
            for i in range(activity_count)
        ]
        conn.executemany(
            """
            INSERT INTO schedule_cpm_activity_results (
              cpm_run_id, schedule_version_key, project_key, activity_id,
              activity_name, topological_index, forward_pass_status,
              predecessor_count, successor_count, computed_critical_flag,
              computed_near_critical_flag, computed_criticality_status
            ) VALUES (?, ?, ?, ?, ?, ?, 'computed', 1, 1, ?, ?, ?)
            """,
            cpm_rows,
        )
        conn.execute(
            """
            INSERT INTO schedule_cpm_paths (
              path_id, cpm_run_id, schedule_version_key, project_key, path_type,
              path_rank, start_activity_id, end_activity_id, activity_count,
              relationship_count, path_duration, path_status, path_basis
            ) VALUES ('path-main', 'cpm-longest_path', ?, 'tropical', 'longest_path',
              1, 'A00000', 'A00049', 50, 49, 50, 'available', 'test_fixture')
            """,
            (current_key,),
        )
        conn.executemany(
            """
            INSERT INTO schedule_cpm_path_activities (
              path_id, cpm_run_id, schedule_version_key, project_key, path_type,
              path_rank, path_sequence, activity_id, activity_name,
              computed_early_start, computed_early_finish, computed_total_float
            ) VALUES ('path-main', 'cpm-longest_path', ?, 'tropical', 'longest_path',
              1, ?, ?, ?, '2026-07-01', '2026-07-02', 0)
            """,
            [(current_key, i, f"A{i:05d}", f"Activity {i:05d}") for i in range(50)],
        )
        conn.commit()


def _run_with_timeout(seconds: float, fn):
    def _handle_timeout(signum, frame):
        del signum, frame
        raise TimeoutError(f"operation exceeded {seconds} seconds")

    previous = signal.signal(signal.SIGALRM, _handle_timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return fn()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _assert_default_pm_fields_have_no_raw_identifiers(body: dict[str, Any]) -> None:
    default = {
        key: value
        for key, value in body.items()
        if key not in {"technical_links", "technical_evidence"}
    }
    payload = json.dumps(default, sort_keys=True)
    forbidden = (
        "schedule_version_key",
        "schedule_identity_key",
        "computed_cpm_health",
        "identity_safe",
        "source_export_proxy",
    )
    for token in forbidden:
        assert token not in payload
    assert RAW_VERSION_PATTERN.search(payload) is None


def _assert_default_lists_are_capped(body: dict[str, Any]) -> None:
    assert len(body["actions"]["preview"]) <= 5
    assert len(body["actions"]["all_items"]) <= 25
    assert len(body["change_impact"]["direct_remaining_changes"]["items"]) <= 10
    assert len(body["change_impact"]["direct_remaining_changes"]["top_impacted_activities"]) <= 10
    assert len(body["change_impact"]["upstream_remaining_impact"]["items"]) <= 10
    assert len(body["recent_progress"]["completed_items"]) <= 10
    assert len(body["recent_progress"]["started_items"]) <= 10
    assert len(body["critical_path"]["items"]) <= 20
    assert len(body["milestones"]["items"]) <= 20
    assert len(body["trend_summary"]["series"]) <= 12


def _assert_no_full_raw_datasets(body: dict[str, Any]) -> None:
    payload = json.dumps(body, sort_keys=True)
    for forbidden_key in (
        '"activities"',
        '"relationships"',
        '"diagnostics"',
        '"detail_rows"',
        '"cpm_activity_results"',
        '"diff_detail_facts"',
    ):
        assert forbidden_key not in payload


def test_project_schedule_no_schedule_contract_and_prefilled_import_link(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    body = ProjectScheduleSummaryService(db_path=str(db)).build_summary(
        "tropical", as_of=date(2026, 6, 28)
    )

    assert body["status"] == "no_schedule"
    assert body["readiness"]["no_schedule"]["required"] is True
    assert body["technical_links"]["schedule_import_url"] == "/projects/tropical/schedule/import"
    assert body["schedule_story"]["headline"] == "No schedule update is imported for this project."


def test_project_schedule_one_update_no_prior_and_cpm_unavailable(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_one_version(db)

    body = ProjectScheduleSummaryService(db_path=str(db)).build_summary(
        "tropical", as_of=date(2026, 6, 28)
    )

    assert body["current_schedule"]["friendly_label"] == "TWNU19"
    assert body["current_schedule"]["data_date"] == "2026-06-23"
    assert body["previous_update"]["available"] is False
    assert body["readiness"]["no_prior_update"]["required"] is True
    assert body["readiness"]["cpm_unavailable"]["required"] is True
    assert body["readiness"]["diff_unavailable"]["required"] is True
    assert body["recent_progress"]["window_basis"] == "last_14_calendar_days"
    assert body["command_summary"]["remaining_activity_count"] == 2


def _seed_xer_change_impact_comparison(db: Path) -> None:
    with sqlite3.connect(db) as conn:
        for import_id, version_key, filename, created_at in (
            ("imp-prior-xer", "tropical|S1|2026-06-01", "TWNU18.xer", "2026-06-01T10:00:00Z"),
            ("imp-current-xer", "tropical|S1|2026-07-01", "TWNU19.xer", "2026-07-01T10:00:00Z"),
        ):
            conn.execute(
                """
                INSERT INTO schedule_file_imports (
                  import_id, project_key, source_type, source_format, import_status,
                  activity_count, relationship_count, cost_loaded_status,
                  schedule_version_key, source_filename_redacted, created_at
                ) VALUES (?, 'tropical', 'xer', 'primavera_xer', 'committed',
                  6, 0, 'not_cost_loaded', ?, ?, ?)
                """,
                (import_id, version_key, filename, created_at),
            )
        activities = [
            (
                "tropical|S1|2026-06-01",
                "imp-prior-xer",
                "FILTER-OUT-20",
                "ENVELOPE COMPLETION",
                "2026-07-01",
                "2026-07-30 16:00",
                None,
                None,
                None,
                "2026-07-30 16:00",
                "WBS-A",
                "-360",
                0,
            ),
            (
                "tropical|S1|2026-07-01",
                "imp-current-xer",
                "FILTER-OUT-20",
                "ENVELOPE COMPLETION",
                "2026-08-01",
                "2026-08-25 16:00",
                None,
                None,
                None,
                "2026-07-30 16:00",
                "WBS-A",
                "-408",
                0,
            ),
            (
                "tropical|S1|2026-06-01",
                "imp-prior-xer",
                "U13-P3-FIN-100",
                "OWNER ACCEPTANCE",
                "2026-09-10",
                "2026-09-17 16:00",
                None,
                None,
                None,
                "2026-09-17 16:00",
                "WBS-B",
                "-360",
                0,
            ),
            (
                "tropical|S1|2026-07-01",
                "imp-current-xer",
                "U13-P3-FIN-100",
                "OWNER ACCEPTANCE",
                "2026-09-18",
                "2026-09-25 16:00",
                None,
                None,
                None,
                "2026-09-17 16:00",
                "WBS-B",
                "-408",
                0,
            ),
            (
                "tropical|S1|2026-06-01",
                "imp-prior-xer",
                "U13-2NDFLELECRM-40",
                "FLOAT WORSENED ONLY",
                "2026-07-01",
                "2026-07-09 16:00",
                None,
                None,
                None,
                "2026-07-09 16:00",
                "WBS-C",
                "-1000",
                0,
            ),
            (
                "tropical|S1|2026-07-01",
                "imp-current-xer",
                "U13-2NDFLELECRM-40",
                "FLOAT WORSENED ONLY",
                "2026-06-20",
                "2026-06-26 16:00",
                None,
                None,
                None,
                "2026-07-09 16:00",
                "WBS-C",
                "-1072",
                0,
            ),
            (
                "tropical|S1|2026-06-01",
                "imp-prior-xer",
                "MS-SUB",
                "Substantial completion milestone",
                "2026-08-01",
                "2026-08-05 16:00",
                None,
                None,
                None,
                "2026-08-05 16:00",
                "WBS-M",
                "0",
                1,
            ),
            (
                "tropical|S1|2026-07-01",
                "imp-current-xer",
                "MS-SUB",
                "Substantial completion milestone",
                "2026-08-06",
                "2026-08-12 16:00",
                None,
                None,
                None,
                "2026-08-05 16:00",
                "WBS-M",
                "0",
                1,
            ),
            (
                "tropical|S1|2026-07-01",
                "imp-current-xer",
                "NEW-REM-1",
                "New remaining scope",
                "2026-09-01",
                "2026-09-30 16:00",
                None,
                None,
                None,
                "2026-09-30 16:00",
                "WBS-N",
                "-10",
                0,
            ),
        ]
        for row in activities:
            conn.execute(
                """
                INSERT INTO procore_ep_schedule_activities (
                  project_key, schedule_id, schedule_version_key, import_id,
                  source_type, source_format, activity_id, activity_name,
                  start_date, finish_date, actual_start, actual_finish,
                  remaining_finish, remaining_early_finish,
                  wbs_code, total_float, is_milestone
                ) VALUES (
                  'tropical', 'S1', ?, ?, 'xer', 'primavera_xer',
                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                row,
            )
        conn.execute(
            """
            INSERT OR IGNORE INTO schedule_identities (
              schedule_identity_key, project_key, identity_status, latest_import_id,
              latest_schedule_version_key
            ) VALUES ('identity-main', 'tropical', 'active', 'imp-current-xer', 'tropical|S1|2026-07-01')
            """
        )
        for import_id, version_key in (
            ("imp-prior-xer", "tropical|S1|2026-06-01"),
            ("imp-current-xer", "tropical|S1|2026-07-01"),
        ):
            conn.execute(
                """
                INSERT INTO schedule_version_identity_matches (
                  match_id, schedule_identity_key, schedule_version_key, import_id, project_key,
                  source_format, activity_count, relationship_count, wbs_count,
                  match_type, match_status, match_rule, confidence_score, requires_review
                ) VALUES (?, 'identity-main', ?, ?, 'tropical', 'primavera_xer',
                  6, 0, 0, 'seed', 'resolved', 'seed', '1.00', 0)
                """,
                (f"match-{import_id}", version_key, import_id),
            )
        conn.commit()


def test_comparison_finish_field_prefers_remaining_finish_then_finish_date() -> None:
    assert _comparison_finish_field({"remaining_finish": "2026-08-01", "finish_date": "2026-09-01"}) == "2026-08-01"
    assert _comparison_finish_field({"finish_date": "2026-08-25 16:00", "remaining_early_finish": "2026-07-30 16:00"}) == "2026-08-25 16:00"
    assert _comparison_finish_field({"remaining_early_finish": "2026-07-30 16:00"}) == "2026-07-30 16:00"


def test_comparison_activity_movement_uses_finish_date_when_remaining_finish_blank() -> None:
    previous = {
        "finish_date": "2026-07-30 16:00",
        "remaining_finish": None,
        "remaining_early_finish": "2026-07-30 16:00",
        "total_float": "-360",
    }
    current = {
        "finish_date": "2026-08-25 16:00",
        "remaining_finish": None,
        "remaining_early_finish": "2026-07-30 16:00",
        "total_float": "-408",
    }
    movement = _comparison_activity_movement(current, previous)
    assert movement["finish_delta_days"] == 26
    assert movement["float_delta_days"] == -48.0


def test_change_impact_uses_finish_date_when_remaining_finish_blank(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_xer_change_impact_comparison(db)

    body = ProjectScheduleSummaryService(db_path=str(db)).build_summary(
        "tropical", as_of=date(2026, 7, 3)
    )

    summary = body["change_impact"]["direct_remaining_changes"]["summary"]
    assert body["change_impact"]["comparison_basis"] == "resolved_finish_date"
    assert summary["finish_moved_later_count"] >= 2
    assert summary["finish_changed_count"] >= 3
    assert summary["finish_moved_earlier_count"] >= 1
    assert summary["new_remaining_activities"] == 1
    assert summary["worsened_float_count"] >= 1
    assert summary["improved_float_count"] == 0
    assert summary["moved_remaining_milestones_count"] == 1
    assert summary["common_remaining_activities"] == 4
    story = body["schedule_story"]
    driver_text = story.get("primary_driver_narrative") or story["primary_change_driver"]
    assert "moved" in driver_text.lower() or "appears connected" in driver_text.lower()
    assert body.get("change_driver_analysis", {}).get("available") is True
    assert summary["finish_moved_later_count"] > 0


def test_project_schedule_populated_comparison_actions_and_no_mutation(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    assert _seed_persisted_diff(db) > 0
    before = _table_counts(db)

    body = ProjectScheduleSummaryService(db_path=str(db)).build_summary(
        "tropical", as_of=date(2026, 7, 3)
    )

    after = _table_counts(db)
    assert before == after
    assert body["status"] in {"ready", "partial"}
    assert body["previous_update"]["available"] is True
    assert body["readiness"]["diff_unavailable"]["required"] is False
    assert body["change_impact"]["available"] is True
    assert "direct_remaining_changes" in body["change_impact"]
    assert "upstream_remaining_impact" in body["change_impact"]
    assert body["actions"]["preview_limit"] == 5
    assert len(body["actions"]["preview"]) <= 5
    _assert_default_lists_are_capped(body)
    _assert_default_pm_fields_have_no_raw_identifiers(body)
    _assert_no_full_raw_datasets(body)
    expected_caveat = "This summary identifies schedule movement and review priorities. It does not determine delay causation, responsibility, entitlement, or compensability."
    assert expected_caveat in body["schedule_story"]["caveats"]
    assert not any("it does not determine delay causation, responsibility, schedule movement, or schedule movement" in caveat.lower() for caveat in body["schedule_story"]["caveats"])
    story = " ".join(str(v) for v in body["schedule_story"].values())
    for forbidden in ("caused the delay", "responsible for the delay", "claim impact"):
        assert forbidden not in story.lower()


def test_project_schedule_current_selection_ignores_unrelated_future_dated_import(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    _seed_unrelated_future_version(db)

    body = ProjectScheduleSummaryService(db_path=str(db)).build_summary(
        "tropical", as_of=date(2026, 7, 3)
    )

    assert body["current_schedule"]["friendly_label"] == "TWNU19"
    assert body["current_schedule"]["data_date"] == "2026-07-01"
    assert body["technical_evidence"]["schedule_version_key"] == "tropical|S1|2026-07-01"
    assert body["technical_evidence"]["schedule_version_key"] != "tropical|S2|2026-08-01"


def test_project_schedule_read_does_not_passively_recompute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hb_assistant.construction.analytics.schedule_cpm_service import ScheduleCpmGraphService
    from hb_assistant.construction.analytics.schedule_import_service import ScheduleImportService

    db = _fresh_db(tmp_path)
    _seed_large_tropical_schedule(db, activity_count=300)

    def fail_if_called(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise AssertionError("Project Schedule Hub read attempted a passive compute/write path")

    monkeypatch.setattr(ScheduleImportService, "_compute_default_version_diff_best_effort", fail_if_called)
    for method_name in (
        "run_graph_diagnostics",
        "run_forward_pass",
        "run_backward_pass",
        "run_float_calculation",
        "run_longest_path",
        "run_criticality_classification",
    ):
        monkeypatch.setattr(ScheduleCpmGraphService, method_name, fail_if_called)

    before = _table_counts(db)
    body = ProjectScheduleSummaryService(db_path=str(db)).build_summary(
        "tropical", as_of=date(2026, 7, 3)
    )
    after = _table_counts(db)

    assert before == after
    assert body["computed_cpm"]["available"] is True
    _assert_default_lists_are_capped(body)
    _assert_no_full_raw_datasets(body)


def test_project_schedule_large_fixture_performance_under_two_seconds(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_large_tropical_schedule(db, activity_count=1800)
    service = ProjectScheduleSummaryService(db_path=str(db))

    started = time.perf_counter()
    body = _run_with_timeout(
        2.0,
        lambda: service.build_summary("tropical", as_of=date(2026, 7, 3)),
    )
    elapsed = time.perf_counter() - started

    assert elapsed < 2.0
    assert body["current_schedule"]["activity_count"] == 1800
    assert body["remaining_health"]["remaining_activity_count"] > 1000
    assert body["computed_cpm"]["available"] is True
    assert body["critical_path"]["activity_count"] == 50
    assert body["critical_path"]["default_limit"] == 20
    _assert_default_lists_are_capped(body)
    _assert_default_pm_fields_have_no_raw_identifiers(body)
    _assert_no_full_raw_datasets(body)
    stage_names = {entry["stage"] for entry in body["technical_evidence"]["performance_stage_timings"]}
    assert "version_resolution" in stage_names
    assert "current_activity_summary" in stage_names


def test_project_schedule_version_resolution_explain_is_bounded(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_large_tropical_schedule(db, activity_count=100)
    explain = ProjectScheduleSummaryService(db_path=str(db)).explain_version_resolution_queries("tropical")

    before_details = " ".join(row["detail"] for row in explain["before"])
    after_details = " ".join(row["detail"] for row in explain["after"])

    assert "idx_schedule_activities_import" in before_details
    assert "idx_schedule_relationships" in before_details or "SEARCH r " in before_details
    assert "USE TEMP B-TREE" in before_details
    assert "schedule_file_imports" in after_details
    assert "procore_ep_schedule_activities" not in after_details
    assert "procore_ep_schedule_relationships" not in after_details


def test_project_schedule_identity_review_required(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_one_version(db, review_required=True)

    body = ProjectScheduleSummaryService(db_path=str(db)).build_summary(
        "tropical", as_of=date(2026, 6, 28)
    )

    assert body["readiness"]["identity_review_required"]["required"] is True
    assert body["status"] in {"partial", "review_required"}
    if body["status"] == "partial":
        assert any(item["code"] == "identity_review" for item in body["actions"]["all_items"])


def test_project_schedule_fixture_states_are_representative(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    no_schedule = ProjectScheduleSummaryService(db_path=str(db)).build_summary(
        "tropical", as_of=date(2026, 6, 28)
    )
    assert no_schedule["status"] == "no_schedule"

    _seed_one_version(db)
    one_update = ProjectScheduleSummaryService(db_path=str(db)).build_summary("tropical")
    assert one_update["previous_update"]["available"] is False
    assert one_update["computed_cpm"]["available"] is False


def test_project_schedule_route_is_registered(tmp_path: Path) -> None:
    pytest.importorskip("multipart")
    db = _fresh_db(tmp_path)
    app = create_app(db_path=str(db))
    paths = {getattr(route, "path", "") for route in getattr(app, "routes", [])}
    assert "/api/projects/{project_key}/schedule" in paths
