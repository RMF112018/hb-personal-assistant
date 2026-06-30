"""Prove canonical XER/XML package merge behavior in an isolated SQLite DB."""

from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from hb_assistant.construction.analytics.schedule_import_service import ScheduleImportService
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.schedule_activity_repository import ScheduleActivityRepository

COUNT_SOURCES: dict[str, str] = {
    "committed_imports": (
        "SELECT COUNT(*) FROM schedule_file_imports "
        "WHERE schedule_version_key=? AND import_status='committed'"
    ),
    "activities": (
        "SELECT COUNT(*) FROM procore_ep_schedule_activities WHERE schedule_version_key=?"
    ),
    "relationships": (
        "SELECT COUNT(*) FROM procore_ep_schedule_relationships WHERE schedule_version_key=?"
    ),
    "activity_codes": (
        "SELECT COUNT(*) FROM procore_ep_schedule_activity_code_assignments "
        "WHERE schedule_version_key=?"
    ),
    "udfs": "SELECT COUNT(*) FROM procore_ep_schedule_udf_values WHERE schedule_version_key=?",
    "baselines": (
        "SELECT baseline_project_id, activity_count, relationship_count "
        "FROM schedule_baseline_projects WHERE current_schedule_version_key=? "
        "ORDER BY baseline_project_id"
    ),
    "cpm_computed_activity_count": (
        "commit response field computed_activity_count from ScheduleImportService.commit"
    ),
}


def _seed_project(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO procore_ep_projects (
              record_key, endpoint_key, project_key, project_id, display_name,
              project_number, record_id, source_quality, is_current,
              created_utc, updated_utc, external_writeback_performed,
              raw_payload_emitted_to_read_model, raw_payload_emitted_to_evidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "rk-tropical-9001",
                "projects",
                "tropical",
                "9001",
                "Tropical Wind",
                "TWNU",
                "9001",
                "ok",
                1,
                "2026-06-30T00:00:00Z",
                "2026-06-30T00:00:00Z",
                0,
                0,
                0,
            ),
        )


def _count_one(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> int:
    return int(conn.execute(sql, params).fetchone()[0])


def _duplicate_buckets(conn: sqlite3.Connection, schedule_version_key: str) -> dict[str, int]:
    return {
        "activities": _count_one(
            conn,
            """
            SELECT COUNT(*) FROM (
              SELECT activity_id FROM procore_ep_schedule_activities
              WHERE schedule_version_key=?
              GROUP BY schedule_version_key, activity_id HAVING COUNT(*) > 1
            )
            """,
            (schedule_version_key,),
        ),
        "relationships": _count_one(
            conn,
            """
            SELECT COUNT(*) FROM (
              SELECT predecessor_activity_id, successor_activity_id, relationship_type, lag_value
              FROM procore_ep_schedule_relationships
              WHERE schedule_version_key=?
              GROUP BY schedule_version_key, predecessor_activity_id, successor_activity_id,
                       relationship_type, lag_value
              HAVING COUNT(*) > 1
            )
            """,
            (schedule_version_key,),
        ),
        "activity_codes": _count_one(
            conn,
            """
            SELECT COUNT(*) FROM (
              SELECT activity_id, code_type, code_value
              FROM procore_ep_schedule_activity_code_assignments
              WHERE schedule_version_key=?
              GROUP BY schedule_version_key, activity_id, code_type, code_value
              HAVING COUNT(*) > 1
            )
            """,
            (schedule_version_key,),
        ),
        "udfs": _count_one(
            conn,
            """
            SELECT COUNT(*) FROM (
              SELECT activity_id, udf_type_name, udf_value
              FROM procore_ep_schedule_udf_values
              WHERE schedule_version_key=?
              GROUP BY schedule_version_key, activity_id, udf_type_name, udf_value
              HAVING COUNT(*) > 1
            )
            """,
            (schedule_version_key,),
        ),
    }


def _db_counts(db_path: Path, schedule_version_key: str) -> dict[str, Any]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        sample = conn.execute(
            """
            SELECT activity_id FROM procore_ep_schedule_activities
            WHERE schedule_version_key=?
            ORDER BY activity_id
            LIMIT 1
            """,
            (schedule_version_key,),
        ).fetchone()
        baseline_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT baseline_project_id, activity_count, relationship_count
                FROM schedule_baseline_projects
                WHERE current_schedule_version_key=?
                ORDER BY baseline_project_id
                """,
                (schedule_version_key,),
            ).fetchall()
        ]
        return {
            "count_sources": COUNT_SOURCES,
            "committed_imports": _count_one(
                conn,
                "SELECT COUNT(*) FROM schedule_file_imports WHERE schedule_version_key=? AND import_status='committed'",
                (schedule_version_key,),
            ),
            "activities": _count_one(
                conn,
                "SELECT COUNT(*) FROM procore_ep_schedule_activities WHERE schedule_version_key=?",
                (schedule_version_key,),
            ),
            "relationships": _count_one(
                conn,
                "SELECT COUNT(*) FROM procore_ep_schedule_relationships WHERE schedule_version_key=?",
                (schedule_version_key,),
            ),
            "activity_codes": _count_one(
                conn,
                "SELECT COUNT(*) FROM procore_ep_schedule_activity_code_assignments WHERE schedule_version_key=?",
                (schedule_version_key,),
            ),
            "udfs": _count_one(
                conn,
                "SELECT COUNT(*) FROM procore_ep_schedule_udf_values WHERE schedule_version_key=?",
                (schedule_version_key,),
            ),
            "baselines": baseline_rows,
            "duplicate_buckets": _duplicate_buckets(conn, schedule_version_key),
            "sample_activity_id": sample["activity_id"] if sample else None,
        }


def _import_twice(service: ScheduleImportService, path: Path) -> dict[str, Any]:
    commits = []
    previews = []
    for _ in range(2):
        preview = service.preview_bytes(
            filename=path.name,
            data=path.read_bytes(),
            project_key="tropical",
        )
        commit = service.commit(
            import_id=preview["import_id"],
            project_key="tropical",
            confirm=True,
        )
        previews.append(preview)
        commits.append(commit)
    return {"previews": previews, "commits": commits}


def run(fixtures_dir: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="schedule-canonical-merge-") as tmp:
        db_path = Path(tmp) / "proof.sqlite"
        SQLiteMigrator(db_path=str(db_path)).apply()
        _seed_project(db_path)
        service = ScheduleImportService(db_path=str(db_path))
        results = []
        for path in sorted(fixtures_dir.glob("TWNU*.zip")):
            imported = _import_twice(service, path)
            final_commit = imported["commits"][-1]
            schedule_version_key = final_commit["schedule_version_key"]
            counts = _db_counts(db_path, schedule_version_key)
            lineage = None
            if counts["sample_activity_id"]:
                lineage = ScheduleActivityRepository(db_path=str(db_path)).get_activity_merge_lineage(
                    schedule_version_key=schedule_version_key,
                    activity_id=counts["sample_activity_id"],
                )
            results.append(
                {
                    "package": path.name,
                    "detected_source_files": [
                        {
                            "filename": file["filename"],
                            "source_format": file["source_format"],
                            "detected_activities": file["detected_activities"],
                            "detected_relationships": file["detected_relationships"],
                            "detected_baseline_projects": file["detected_baseline_projects"],
                        }
                        for file in imported["previews"][-1]["files"]
                    ],
                    "ignored_files": "macOS metadata omitted from parsed file manifest",
                    "equivalence_status": imported["previews"][-1]["equivalence_report"]["status"],
                    "schedule_version_key": schedule_version_key,
                    "first_import_id": imported["commits"][0]["import_id"],
                    "second_import_id": imported["commits"][1]["import_id"],
                    "superseded_import_id": imported["commits"][1].get("superseded_import_id"),
                    "canonical_counts": counts,
                    "cpm": {
                        "triggered": final_commit.get("cpm_recompute_triggered"),
                        "status": final_commit.get("cpm_recompute_status"),
                        "computed_activity_count": final_commit.get("computed_activity_count"),
                        "computed_activity_count_source": COUNT_SOURCES[
                            "cpm_computed_activity_count"
                        ],
                        "canonical_relationship_input_count": counts["relationships"],
                        "canonical_relationship_input_source": COUNT_SOURCES["relationships"],
                    },
                    "lineage_probe": lineage,
                }
            )
        return {"db_path": str(db_path), "packages": results}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=Path("tests/fixtures/project_schedule_import_packages"),
    )
    args = parser.parse_args()
    print(json.dumps(run(args.fixtures_dir), indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
