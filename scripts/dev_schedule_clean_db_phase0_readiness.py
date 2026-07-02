#!/usr/bin/env python3
"""Phase 0 readiness gate before full clean-DB workflow validation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.schedule_clean_db.purge import run_tropical_purge
from hb_assistant.construction.schedule_clean_db.schema_audit import build_schema_audit_report
from hb_assistant.store.migrator import SQLiteMigrator


def _seed_project(db: Path) -> None:
    import sqlite3

    SQLiteMigrator(db_path=str(db)).apply()
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO procore_ep_projects (
              record_key, endpoint_key, project_key, project_id, display_name, project_number,
              record_id, source_quality, is_current, created_utc, updated_utc,
              external_writeback_performed, raw_payload_emitted_to_read_model,
              raw_payload_emitted_to_evidence
            ) VALUES ('rk-tropical', 'projects', 'tropical', '9001', 'Tropical Wind', NULL,
              '9001', 'ok', 1, '2026-06-22T00:00:00Z', '2026-06-22T00:00:00Z', 0, 0, 0)
            """
        )
        conn.commit()


def _check(ok: bool, detail: str) -> dict:
    return {"ok": ok, "detail": detail}


def run_readiness_checks(evidence_dir: Path | None = None) -> dict:
    repo = PathPolicy().resolve_repo_root()
    checks: list[dict] = []

    gitignore = (repo / ".gitignore").read_text(encoding="utf-8")
    checks.append(
        {
            "id": "gitignore_local_sensitive",
            **_check("/local-sensitive/" in gitignore, "root local-sensitive gitignored"),
        }
    )

    script_names = [
        "dev_schedule_clean_db_backend.py",
        "dev_schedule_clean_db_schema_audit.py",
        "dev_clean_tropical_schedule_db.py",
        "dev_schedule_import_preview_mutation_probe.py",
        "dev_schedule_import_package_manifest.py",
        "dev_schedule_evidence_artifact_scan.py",
        "dev_schedule_live_db_unchanged_probe.py",
    ]
    for name in script_names:
        path = repo / "scripts" / name
        checks.append({"id": f"script_{name}", **_check(path.is_file(), str(path))})

    helper = repo / "frontend" / "e2e" / "helpers" / "scheduleLoadedState.ts"
    checks.append(
        {"id": "loaded_state_helper", **_check(helper.is_file(), str(helper))}
    )

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "fixture.db"
        _seed_project(db)
        try:
            audit = build_schema_audit_report(db, project_key="tropical")
            checks.append(
                {
                    "id": "schema_audit_fixture",
                    **_check("discovered_by_heuristic" in audit, "schema audit runs"),
                }
            )
            purge = run_tropical_purge(str(db), project_key="tropical", dry_run=True, apply=False)
            checks.append(
                {
                    "id": "purge_dry_run",
                    **_check(purge.get("dry_run") is True, "purge dry-run supported"),
                }
            )
        except Exception as exc:
            checks.append({"id": "fixture_tools", **_check(False, str(exc))})

        proof = subprocess.run(
            [
                sys.executable,
                str(repo / "scripts" / "dev_schedule_clean_db_backend.py"),
                "--db-path",
                str(db),
                "--port",
                "18099",
                "--confirm-clean-copy",
                "--allow-custom-copy-path",
                "--print-proof-only",
            ],
            capture_output=True,
            text=True,
            cwd=repo,
            check=False,
        )
        checks.append(
            {
                "id": "backend_runner_proof",
                **_check(proof.returncode == 0, proof.stdout.strip()[:200] or proof.stderr.strip()),
            }
        )

    if evidence_dir and evidence_dir.is_dir():
        required = [
            "00-repo-state.txt",
            "27-phase0-summary.md",
        ]
        for name in required:
            checks.append(
                {
                    "id": f"evidence_{name}",
                    **_check((evidence_dir / name).is_file(), name),
                }
            )

    ready = all(c.get("ok") for c in checks)
    return {"ready_for_full_clean_db_validation": ready, "checks": checks}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir")
    parser.add_argument("--json-out")
    args = parser.parse_args(argv)
    evidence = Path(args.evidence_dir) if args.evidence_dir else None
    report = run_readiness_checks(evidence)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report.get("ready_for_full_clean_db_validation") else 1


if __name__ == "__main__":
    raise SystemExit(main())
