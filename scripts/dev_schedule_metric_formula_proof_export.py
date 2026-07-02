#!/usr/bin/env python3
"""Export schedule metric formula proof evidence from a copied schedule database."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hb_assistant.config.db_path_guard import assert_not_live_db
from hb_assistant.construction.analytics.schedule_metric_formula_proof import (
    ScheduleMetricFormulaProofExporter,
)
from hb_assistant.construction.schedule_clean_db.guards import (
    assert_clean_copy_path,
    require_confirm_clean_copy,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path")
    parser.add_argument("--project-key", default="tropical")
    parser.add_argument("--schedule-version-key")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--comparison-basis", default="prior_update")
    parser.add_argument("--weighting-basis", default="duration_weighted")
    parser.add_argument("--tolerance", type=float, default=1e-4)
    parser.add_argument("--confirm-clean-copy", action="store_true")
    parser.add_argument("--allow-custom-copy-path", action="store_true")
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--allow-mismatches", action="store_true")
    args = parser.parse_args(argv)

    if args.fixture:
        return _fixture_export(args)

    if not args.db_path or not args.schedule_version_key:
        print("--db-path and --schedule-version-key required unless --fixture", file=sys.stderr)
        return 2
    try:
        assert_not_live_db(args.db_path, context="metric formula proof export")
        if not args.allow_custom_copy_path:
            require_confirm_clean_copy(args.confirm_clean_copy)
            assert_clean_copy_path(args.db_path, allow_custom_copy_path=args.allow_custom_copy_path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    exporter = ScheduleMetricFormulaProofExporter(db_path=args.db_path)
    try:
        _pkg, code = exporter.export(
            project_key=args.project_key,
            schedule_version_key=args.schedule_version_key,
            out_dir=args.out_dir,
            comparison_basis=args.comparison_basis,
            weighting_basis=args.weighting_basis,
            tolerance=args.tolerance,
        )
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 4
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 4
    if code and args.allow_mismatches:
        return 0
    return code


def _fixture_export(args: argparse.Namespace) -> int:
    import sys

    repo = Path(__file__).resolve().parents[1]
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    from fastapi.testclient import TestClient
    from hb_assistant.construction.analytics.api import create_app
    from hb_assistant.store.migrator import SQLiteMigrator
    from tests.schedule_project_test_helpers import seed_procore_ep_project

    xer = repo / "tests/fixtures/schedules/xer/minimal.xer"
    db = args.out_dir.parent / "_fixture_db.sqlite"
    if db.exists():
        db.unlink()
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    client = TestClient(create_app(db_path=str(db)))
    preview = client.post(
        "/api/projects/tropical/schedule/import-preview",
        headers={"X-HB-UI-Role": "operator"},
        files={"file": ("minimal.xer", xer.read_bytes(), "application/xml")},
    )
    assert preview.status_code == 200, preview.text
    commit = client.post(
        "/api/projects/tropical/schedule/import-commit",
        headers={"X-HB-UI-Role": "operator"},
        json={"import_id": preview.json()["import_id"], "project_key": "tropical", "confirm": True},
    )
    assert commit.status_code == 200, commit.text
    vk = commit.json()["schedule_version_key"]
    exporter = ScheduleMetricFormulaProofExporter(db_path=str(db))
    _pkg, code = exporter.export(
        project_key="tropical",
        schedule_version_key=vk,
        out_dir=args.out_dir,
        comparison_basis=args.comparison_basis,
        weighting_basis=args.weighting_basis,
        tolerance=args.tolerance,
    )
    if db.exists():
        db.unlink()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
