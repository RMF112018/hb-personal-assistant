#!/usr/bin/env python3
"""Schedule Intelligence V62 live DB cutover orchestrator.

Read-only preflight, sqlite3.backup-based backup, copied-live-DB rehearsal, and
operator-gated live apply. Does not auto-migrate schedule routes; migration is explicit.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from hb_assistant.config.path_policy import PathPolicy  # noqa: E402
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks  # noqa: E402
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator  # noqa: E402
from hb_assistant.store.schedule_tables import V62_TABLES  # noqa: E402

GMA_FIXTURE = REPO / "tests/fixtures/schedules/xml/gma_sample.xml"
EXPECTED_TABLE_COUNT = 412
REHEARSAL_PASS_MARKER = "copied_live_rehearsal_proof.json"
SCHEDULE_TESTS = [
    "tests/test_schedule_schema_migration.py",
    "tests/test_schedule_activity_repository.py",
    "tests/test_procore_schedule_activity_projection.py",
    "tests/test_schedule_xml_parser.py",
    "tests/test_schedule_import_api.py",
    "tests/test_schedule_cost_mapping_controls.py",
    "tests/test_schedule_dto_redaction.py",
    "tests/test_data_quality_table_inventory.py",
]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_info() -> dict[str, str]:
    def _run(args: list[str]) -> str:
        cp = subprocess.run(args, cwd=REPO, capture_output=True, text=True, check=False)
        return (cp.stdout or "").strip()

    return {
        "branch": _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "commit_sha": _run(["git", "rev-parse", "HEAD"]),
    }


def live_db_path() -> Path:
    return PathPolicy().get_db_path()


def fingerprint_db_files(db: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for label, suffix in (("main", ""), ("shm", "-shm"), ("wal", "-wal")):
        p = Path(f"{db}{suffix}")
        entry: dict[str, Any] = {"path": str(p), "exists": p.exists()}
        if p.exists():
            st = p.stat()
            entry["size_bytes"] = st.st_size
            entry["mtime_ns"] = st.st_mtime_ns
            entry["sha256"] = sha256_file(p)
        out[label] = entry
    return out


def ro_conn(db: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)


def table_count(conn: sqlite3.Connection) -> int:
    """Match table_inventory: user tables + views (lifecycle contract includes views)."""
    row = conn.execute(
        """
        SELECT COUNT(*) FROM sqlite_master
        WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'
        """
    ).fetchone()
    return int(row[0]) if row else 0


def schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    return int(row[0] or 0)


def db_audit(db: Path) -> dict[str, Any]:
    conn = ro_conn(db)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        missing_v62 = [
            t
            for t in V62_TABLES
            if not conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (t,)
            ).fetchone()
        ]
        return {
            "db_path": str(db),
            "schema_version": schema_version(conn),
            "table_count": table_count(conn),
            "procore_ep_schedules_count": int(
                conn.execute("SELECT COUNT(*) FROM procore_ep_schedules").fetchone()[0]
            ),
            "journal_mode": conn.execute("PRAGMA journal_mode").fetchone()[0],
            "integrity_check": conn.execute("PRAGMA integrity_check").fetchone()[0],
            "foreign_key_check": [
                f"{r[0]}.{r[1]}.{r[2]}"
                for r in conn.execute("PRAGMA foreign_key_check").fetchall()
            ],
            "missing_v62_tables": missing_v62,
        }
    finally:
        conn.close()


def backup_db(*, source: Path, dest: Path) -> dict[str, Any]:
    if dest.exists():
        raise RuntimeError(f"backup already exists (refusing overwrite): {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(str(dest))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    conn = ro_conn(dest)
    try:
        verified_schema = schema_version(conn)
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()
    return {
        "source_db": str(source),
        "backup_path": str(dest),
        "size_bytes": dest.stat().st_size,
        "sha256": sha256_file(dest),
        "verified_schema_version": verified_schema,
        "integrity_check": integrity,
    }


def _gma_import_smoke(db: Path) -> dict[str, Any]:
    from fastapi.testclient import TestClient

    from hb_assistant.construction.analytics import create_app

    if not GMA_FIXTURE.exists():
        raise RuntimeError(f"GMA fixture missing: {GMA_FIXTURE}")

    client = TestClient(create_app(db_path=str(db)))
    headers = {"X-HB-UI-Role": "operator"}
    preview = client.post(
        "/api/schedules/import-preview",
        headers=headers,
        files={"file": ("gma_sample.xml", GMA_FIXTURE.read_bytes(), "application/xml")},
        data={"project_key": "tropical"},
    )
    if preview.status_code != 200:
        raise RuntimeError(f"import-preview failed: {preview.status_code} {preview.text}")
    preview_body = preview.json()
    if find_redaction_leaks(preview_body):
        raise RuntimeError(f"preview redaction leaks: {find_redaction_leaks(preview_body)}")

    import_id = preview_body["import_id"]
    commit = client.post(
        "/api/schedules/import-commit",
        headers=headers,
        json={"import_id": import_id, "project_key": "tropical", "confirm": True},
    )
    if commit.status_code != 200:
        raise RuntimeError(f"import-commit failed: {commit.status_code} {commit.text}")
    commit_body = commit.json()
    if find_redaction_leaks(commit_body):
        raise RuntimeError(f"commit redaction leaks: {find_redaction_leaks(commit_body)}")

    svk = commit_body["schedule_version_key"]
    acts = client.get(f"/api/schedules/versions/{svk}/activities")
    rels = client.get(f"/api/schedules/versions/{svk}/relationships")
    if acts.status_code != 200 or rels.status_code != 200:
        raise RuntimeError("activities/relationships fetch failed")
    act_body = acts.json()
    rel_body = rels.json()
    for body in (act_body, rel_body, preview_body, commit_body):
        if find_redaction_leaks(body):
            raise RuntimeError(f"response redaction leak: {find_redaction_leaks(body)}")

    activity_count = len(act_body["activities"])
    relationship_count = len(rel_body["relationships"])

    conn = ro_conn(db)
    try:
        null_linkage = conn.execute(
            """
            SELECT COUNT(*) FROM procore_ep_schedule_activities
            WHERE schedule_version_key=? AND schedule_table_id IS NULL
            """,
            (svk,),
        ).fetchone()[0]
        schedule_keys = {
            r[0]
            for r in conn.execute(
                """
                SELECT DISTINCT schedule_table_id FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                """,
                (svk,),
            ).fetchall()
        }
    finally:
        conn.close()

    run = client.post(
        "/api/schedules/cost-mapping/runs",
        headers=headers,
        json={
            "project_key": "tropical",
            "schedule_version_key": svk,
            "operator_objective": "association_only",
        },
    )
    if run.status_code != 200:
        raise RuntimeError(f"cost-mapping run failed: {run.status_code}")
    run_id = run.json()["mapping_run_id"]
    weight_before = client.get("/api/schedules/cost-weighting/tropical")
    weight_after_unapproved = weight_before.json()["weighting_results"]

    cands = client.get(f"/api/schedules/cost-mapping/runs/{run_id}/candidates").json()["candidates"]
    for c in cands:
        client.post(
            f"/api/schedules/cost-mapping/candidates/{c['id']}/review",
            headers=headers,
            json={"operator_status": "approved"},
        )
    client.post(f"/api/schedules/cost-mapping/runs/{run_id}/approve", headers=headers)
    weight_after = client.get("/api/schedules/cost-weighting/tropical").json()["weighting_results"]

    return {
        "schedule_version_key": svk,
        "activity_count": activity_count,
        "relationship_count": relationship_count,
        "null_schedule_table_id_count": int(null_linkage),
        "distinct_schedule_table_ids": sorted(schedule_keys),
        "cost_weighting_before_approval": len(weight_after_unapproved),
        "cost_weighting_after_approval": len(weight_after),
        "redaction_leaks": [],
    }


def migrate_and_verify(db: Path) -> dict[str, Any]:
    before = SQLiteMigrator(db_path=str(db)).current_version()
    after = SQLiteMigrator(db_path=str(db)).apply()
    conn = ro_conn(db)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        missing = [
            t
            for t in V62_TABLES
            if not conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (t,)
            ).fetchone()
        ]
        fk_violations = [
            f"{r[0]}.{r[1]}.{r[2]}"
            for r in conn.execute("PRAGMA foreign_key_check").fetchall()
        ]
        audit = {
            "schema_before": before,
            "schema_after": after,
            "table_count": table_count(conn),
            "integrity_check": conn.execute("PRAGMA integrity_check").fetchone()[0],
            "foreign_key_check": fk_violations,
            "missing_v62_tables": missing,
        }
    finally:
        conn.close()
    return audit


def _schema_after(mig: dict[str, Any]) -> int:
    return int(mig.get("schema_after") or mig.get("schema_version") or 0)


def stop_conditions(proof: dict[str, Any], *, require_gma: bool = True) -> list[str]:
    failures: list[str] = []
    mig = proof.get("migration", {})
    smoke = proof.get("gma_smoke", {})

    if _schema_after(mig) != LATEST_SCHEMA_VERSION:
        failures.append(f"schema_after != {LATEST_SCHEMA_VERSION}")
    if mig.get("table_count") != EXPECTED_TABLE_COUNT:
        failures.append(f"table_count != {EXPECTED_TABLE_COUNT}")
    if mig.get("integrity_check") != "ok":
        failures.append("integrity_check failed")
    if mig.get("foreign_key_check"):
        failures.append("foreign_key_check violations")
    if mig.get("missing_v62_tables"):
        failures.append(f"missing V62 tables: {mig['missing_v62_tables']}")
    if not require_gma:
        return failures
    if smoke.get("activity_count") != 189:
        failures.append("GMA activity_count != 189")
    if smoke.get("relationship_count") != 282:
        failures.append("GMA relationship_count != 282")
    if smoke.get("null_schedule_table_id_count", 1) != 0:
        failures.append("committed activities have null schedule_table_id")
    if len(smoke.get("distinct_schedule_table_ids") or []) != 1:
        failures.append("activities do not tie to exactly one schedule_table_id")
    if smoke.get("cost_weighting_before_approval", 1) != 0:
        failures.append("weighting populated before approval")
    if smoke.get("cost_weighting_after_approval", 0) < 1:
        failures.append("weighting empty after approval")
    if smoke.get("redaction_leaks"):
        failures.append("redaction leaks in smoke responses")
    return failures


def run_pytest(out_dir: Path) -> dict[str, Any]:
    cmd = [str(REPO / ".venv/bin/pytest"), "-q", *SCHEDULE_TESTS]
    if not cmd[0].endswith("pytest") or not Path(cmd[0]).exists():
        cmd = ["pytest", "-q", *SCHEDULE_TESTS]
    cp = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, check=False)
    log = out_dir / "schedule_tests.log"
    log.write_text((cp.stdout or "") + "\n--- STDERR ---\n" + (cp.stderr or ""), encoding="utf-8")
    return {"exit_code": cp.returncode, "log": str(log)}


def cmd_preflight(args: argparse.Namespace) -> int:
    out = Path(args.out_dir)
    live = live_db_path()
    proof = {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "live_preflight",
        **git_info(),
        "latest_schema_version_expected": LATEST_SCHEMA_VERSION,
        "live_db_fingerprints": fingerprint_db_files(live),
        "live_db_audit": db_audit(live) if live.exists() else {"error": "live_db_missing"},
    }
    write_json(out / "live_preflight.json", proof)
    print(json.dumps(proof, indent=2))
    return 0 if live.exists() else 1


def cmd_backup(args: argparse.Namespace) -> int:
    out = Path(args.out_dir)
    live = live_db_path()
    if not live.exists():
        print("live DB missing", file=sys.stderr)
        return 1
    dest = out / "backups" / "hb-personal-assistant-pre-v62.sqlite"
    receipt = backup_db(source=live, dest=dest)
    write_json(out / "backup_receipt.json", receipt)
    print(json.dumps(receipt, indent=2))
    return 0


def cmd_rehearse(args: argparse.Namespace) -> int:
    out = Path(args.out_dir)
    backup_path = out / "backups" / "hb-personal-assistant-pre-v62.sqlite"
    if not backup_path.exists():
        print("backup missing; run backup first", file=sys.stderr)
        return 1

    copy_path = out / "work" / "rehearsal-copy.sqlite"
    if copy_path.exists():
        copy_path.unlink()
    backup_db(source=backup_path, dest=copy_path)

    migration = migrate_and_verify(copy_path)
    gma_smoke = _gma_import_smoke(copy_path)
    failures = stop_conditions({"migration": migration, "gma_smoke": gma_smoke})
    proof = {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "copied_live_rehearsal",
        **git_info(),
        "copy_db": str(copy_path),
        "migration": migration,
        "gma_smoke": gma_smoke,
        "stop_condition_failures": failures,
        "status": "pass" if not failures else "fail",
    }
    write_json(out / REHEARSAL_PASS_MARKER, proof)
    print(json.dumps(proof, indent=2))
    return 0 if not failures else 2


def cmd_apply_live(args: argparse.Namespace) -> int:
    out = Path(args.out_dir)
    marker = out / REHEARSAL_PASS_MARKER
    if not marker.exists():
        print("rehearsal proof missing; run rehearse first", file=sys.stderr)
        return 1
    proof = json.loads(marker.read_text(encoding="utf-8"))
    if proof.get("status") != "pass":
        print("rehearsal did not pass; refusing live apply", file=sys.stderr)
        return 2
    if not args.confirm:
        print("live apply requires --confirm", file=sys.stderr)
        return 3

    live = live_db_path()
    before_audit = db_audit(live)
    conn = sqlite3.connect(str(live))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()

    migration = migrate_and_verify(live)
    after_audit = db_audit(live)
    failures = stop_conditions({"migration": migration, "gma_smoke": {}}, require_gma=False)

    receipt = {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "live_apply",
        **git_info(),
        "before": before_audit,
        "migration": migration,
        "after": after_audit,
        "stop_condition_failures": failures,
        "status": "pass" if not failures else "fail",
    }
    write_json(out / "live_apply_receipt.json", receipt)
    write_json(out / "final_live_db.json", fingerprint_db_files(live))
    print(json.dumps(receipt, indent=2))
    return 0 if not failures else 2


def cmd_certify(args: argparse.Namespace) -> int:
    out = Path(args.out_dir)
    live = live_db_path()
    audit = db_audit(live)
    if audit["schema_version"] < LATEST_SCHEMA_VERSION:
        print("live DB not migrated; run apply-live first", file=sys.stderr)
        return 1
    gma_smoke = _gma_import_smoke(live)
    failures = stop_conditions({"migration": audit, "gma_smoke": gma_smoke})
    pytest_result = run_pytest(out)
    if pytest_result["exit_code"] != 0:
        failures.append("schedule pytest suite failed")

    proof = {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "post_migration_certification",
        **git_info(),
        "live_db_audit": audit,
        "gma_smoke": gma_smoke,
        "pytest": pytest_result,
        "stop_condition_failures": failures,
        "status": "pass" if not failures else "fail",
    }
    write_json(out / "post_migration_certification.json", proof)
    write_json(out / "final_live_db.json", fingerprint_db_files(live))

    readme = out / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# Schedule Intelligence V62 Live Cutover Evidence",
                "",
                f"- captured: `{proof['captured_utc']}`",
                f"- branch: `{proof.get('branch', '')}`",
                f"- commit: `{proof.get('commit_sha', '')}`",
                f"- status: **{proof['status']}**",
                f"- schema version: `{audit.get('schema_version')}` (expected `{LATEST_SCHEMA_VERSION}`)",
                f"- table count: `{audit.get('table_count')}` (expected `{EXPECTED_TABLE_COUNT}`)",
                "",
                "## Artifacts",
                "",
                "- `live_preflight.json` — pre-migration read-only audit",
                "- `backup_receipt.json` + `backups/hb-personal-assistant-pre-v62.sqlite`",
                "- `copied_live_rehearsal_proof.json` — migration + GMA smoke on copy",
                "- `live_apply_receipt.json` — live migration receipt (if applied)",
                "- `post_migration_certification.json` — post-apply certification",
                "- `schedule_tests.log` — pytest output",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof, indent=2))
    return 0 if not failures else 2


def cmd_freeze(args: argparse.Namespace) -> int:
    out = Path(args.out_dir)
    pytest_result = run_pytest(out)
    baseline = {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "freeze_baseline",
        **git_info(),
        "latest_schema_version": LATEST_SCHEMA_VERSION,
        "expected_table_count": EXPECTED_TABLE_COUNT,
        "v62_table_count": len(V62_TABLES),
        "pytest": pytest_result,
        "status": "pass" if pytest_result["exit_code"] == 0 else "fail",
    }
    write_json(out / "freeze_baseline.json", baseline)
    print(json.dumps(baseline, indent=2))
    return 0 if baseline["status"] == "pass" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Schedule Intelligence V62 live cutover")
    parser.add_argument(
        "--out-dir",
        default=str(REPO / "docs/evidence/schedule-intelligence-v62-live-cutover" / utc_stamp()),
        help="Evidence output directory",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name, fn in (
        ("freeze", cmd_freeze),
        ("preflight", cmd_preflight),
        ("backup", cmd_backup),
        ("rehearse", cmd_rehearse),
        ("apply-live", cmd_apply_live),
        ("certify", cmd_certify),
    ):
        p = sub.add_parser(name)
        if name == "apply-live":
            p.add_argument("--confirm", action="store_true", help="Confirm live DB migration")
        p.set_defaults(func=fn)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())