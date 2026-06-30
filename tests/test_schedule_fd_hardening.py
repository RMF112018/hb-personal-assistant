"""File-descriptor hardening for schedule repositories and quality evaluation."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from hb_assistant.construction.analytics.schedule_import_service import ScheduleImportService
from hb_assistant.construction.analytics.schedule_quality_service import ScheduleQualityService
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.schedule_activity_repository import ScheduleActivityRepository
from hb_assistant.store.schedule_mapping_repository import ScheduleMappingRepository
from hb_assistant.store.schedule_quality_repository import ScheduleQualityRepository
from tests.schedule_project_test_helpers import seed_procore_ep_project

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "schedules" / "xml" / "minimal_schedule.xml"


def _open_fds() -> int | None:
    for path in ("/dev/fd", f"/proc/{os.getpid()}/fd"):
        try:
            return len(os.listdir(path))
        except OSError:
            continue
    return None


def _db(tmp_path: Path) -> str:
    db = tmp_path / "schedule-fd.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    return str(db)


def _seed_version(db: str) -> tuple[str, str | None]:
    imp = ScheduleImportService(db_path=db)
    preview = imp.preview_bytes(
        filename=FIXTURE.name,
        data=FIXTURE.read_bytes(),
        project_key="tropical",
    )
    commit = imp.commit(import_id=preview["import_id"], project_key="tropical", confirm=True)
    return commit["schedule_version_key"], commit.get("evaluation_run_id")


def _exercise_schedule_read_paths(
    db: str, *, version_key: str, evaluation_run_id: str | None
) -> None:
    activity_repo = ScheduleActivityRepository(db_path=db)
    mapping_repo = ScheduleMappingRepository(db_path=db)
    quality_repo = ScheduleQualityRepository(db_path=db)
    quality_svc = ScheduleQualityService(db_path=db)

    activity_repo.count_activities(version_key)
    activity_repo.list_activities(version_key, limit=500, offset=0)
    activity_repo.list_relationships(version_key)
    activity_repo.get_version_summary(version_key)
    mapping_repo.list_quality_findings(version_key)
    quality_repo.get_latest_run(version_key)
    quality_repo.list_findings(version_key, limit=20)
    if evaluation_run_id:
        quality_repo.list_metrics(evaluation_run_id)
    quality_svc.get_quality_summary(version_key)
    quality_svc.list_evaluations(project_key="tropical")


def test_schedule_repository_paths_do_not_leak_fds(tmp_path: Path) -> None:
    db = _db(tmp_path)
    baseline = _open_fds()
    if baseline is None:
        pytest.skip("no /dev/fd or /proc/self/fd on this platform")

    version_key, evaluation_run_id = _seed_version(db)
    for _ in range(40):
        _exercise_schedule_read_paths(
            db, version_key=version_key, evaluation_run_id=evaluation_run_id
        )

    after = _open_fds()
    assert after is not None
    assert after - baseline <= 8, f"open FDs grew materially: {baseline} -> {after}"


def test_schedule_suite_paths_succeed_under_constrained_fd_budget(tmp_path: Path) -> None:
    resource = pytest.importorskip("resource")
    db = _db(tmp_path)
    baseline = _open_fds()
    if baseline is None:
        pytest.skip("no /dev/fd or /proc/self/fd on this platform")

    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    ceiling = baseline + 96
    if hard != resource.RLIM_INFINITY and hard < ceiling:
        pytest.skip("hard FD limit too low to exercise safely")
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (ceiling, hard))
        version_key, evaluation_run_id = _seed_version(db)
        for _ in range(25):
            _exercise_schedule_read_paths(
                db, version_key=version_key, evaluation_run_id=evaluation_run_id
            )
    finally:
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))