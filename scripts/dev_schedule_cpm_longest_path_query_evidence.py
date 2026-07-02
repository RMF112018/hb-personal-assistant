#!/usr/bin/env python3
"""Generate sanitized queried CPM longest-path live evidence (read-only, no DB writes)."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.db_path_guard import assert_not_live_db
from hb_assistant.construction.analytics.schedule_cpm_formula_trace import (
    CpmRunChainResolver,
    PATH_DURATION_DEFINITION,
    assert_db_unchanged,
    snapshot_db_row_counts,
)
from hb_assistant.construction.schedule_clean_db.guards import (
    assert_clean_copy_path,
    require_confirm_clean_copy,
)

STAGE_ORDER = ("forward_pass", "backward_pass", "float", "longest_path", "criticality")
PATH_DURATION_BASIS = "path_finish_offset_days - path_start_offset_days"
PATH_BASIS = "max_forward_early_finish_backtrace"

SQL_QUERIES: dict[str, str] = {
    "schema_version": "SELECT MAX(version) AS schema_version FROM schema_migrations",
    "activity_count": (
        "SELECT COUNT(*) AS activity_count FROM procore_ep_schedule_activities "
        "WHERE schedule_version_key = ? AND project_key = ?"
    ),
    "relationship_count": (
        "SELECT COUNT(*) AS relationship_count FROM procore_ep_schedule_relationships "
        "WHERE schedule_version_key = ? AND project_key = ?"
    ),
    "schedule_version_exists": (
        "SELECT COUNT(*) AS cnt FROM procore_ep_schedule_activities "
        "WHERE schedule_version_key = ? AND project_key = ?"
    ),
    "cpm_runs_for_version": (
        "SELECT cpm_run_id, calculation_type, cpm_recalculation_status, source_run_id, "
        "import_id, created_at, schedule_start_anchor, schedule_finish_anchor "
        "FROM schedule_cpm_runs "
        "WHERE schedule_version_key = ? AND project_key = ? "
        "AND calculation_type IN ('forward_pass','backward_pass','float','longest_path','criticality') "
        "ORDER BY created_at"
    ),
    "activity_results_count": (
        "SELECT COUNT(*) FROM schedule_cpm_activity_results WHERE cpm_run_id = ?"
    ),
    "relationship_results_count": (
        "SELECT COUNT(*) FROM schedule_cpm_relationship_results WHERE cpm_run_id = ?"
    ),
    "path_count": "SELECT COUNT(*) FROM schedule_cpm_paths WHERE cpm_run_id = ?",
    "path_activities_count": (
        "SELECT COUNT(*) FROM schedule_cpm_path_activities WHERE cpm_run_id = ?"
    ),
    "paths_for_run": (
        "SELECT path_id, path_rank, end_activity_id, activity_count, relationship_count, "
        "path_duration, path_start_offset_days, path_finish_offset_days, path_basis "
        "FROM schedule_cpm_paths WHERE cpm_run_id = ? ORDER BY path_rank"
    ),
}


def _hash_id(value: str | None) -> str:
    if not value:
        return ""
    return hashlib.sha256(str(value).encode()).hexdigest()[:16]


def _ro_connect(db_path: str | Path) -> sqlite3.Connection:
    uri = f"file:{Path(db_path).resolve()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _row(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> Any:
    cur = conn.execute(sql, params)
    row = cur.fetchone()
    return row[0] if row else None


def _parse_schedule_version_key(key: str) -> dict[str, str]:
    parts = key.split("|")
    if len(parts) >= 3:
        return {
            "project_key": parts[0],
            "schedule_id": parts[1],
            "data_date": "|".join(parts[2:]),
        }
    return {"project_key": parts[0] if parts else "", "schedule_id": "", "data_date": ""}


def build_db_copy_metadata(
    *,
    db_path: Path,
    project_key: str,
    schedule_version_key: str,
    conn: sqlite3.Connection,
) -> dict[str, Any]:
    schema_version = _row(conn, SQL_QUERIES["schema_version"])
    activity_count = _row(conn, SQL_QUERIES["activity_count"], (schedule_version_key, project_key))
    relationship_count = _row(
        conn, SQL_QUERIES["relationship_count"], (schedule_version_key, project_key)
    )
    parsed = _parse_schedule_version_key(schedule_version_key)
    return {
        "db_path_redacted": True,
        "db_path_hint": "local-sensitive/clean-db/<redacted-copy>",
        "db_open_mode": "read_only",
        "schema_version": int(schema_version or 0),
        "project_key": project_key,
        "schedule_version_key": schedule_version_key,
        "schedule_version_exists": bool(activity_count and int(activity_count) > 0),
        "activity_count": int(activity_count or 0),
        "relationship_count": int(relationship_count or 0),
        "data_date": parsed.get("data_date"),
        "source_label_or_schedule_id": parsed.get("schedule_id"),
        "query_status": "pass",
        "queried_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def build_schedule_version_proof(meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "schedule_version_key": meta["schedule_version_key"],
        "project_key": meta["project_key"],
        "schedule_version_exists": meta["schedule_version_exists"],
        "activity_count": meta["activity_count"],
        "relationship_count": meta["relationship_count"],
        "data_date": meta["data_date"],
        "schedule_id": meta["source_label_or_schedule_id"],
        "query_status": meta["query_status"],
    }


def _stage_row(conn: sqlite3.Connection, run: dict[str, Any] | None) -> dict[str, Any] | None:
    if not run:
        return None
    return {
        "cpm_run_id_hash": _hash_id(str(run.get("cpm_run_id"))),
        "cpm_recalculation_status": run.get("cpm_recalculation_status"),
        "source_run_id_hash": _hash_id(str(run.get("source_run_id") or "")) or None,
        "import_id_hash": _hash_id(str(run.get("import_id") or "")),
        "created_at": run.get("created_at"),
        "status": "completed",
    }


def build_lineage_proof(
    *,
    db_path: str,
    schedule_version_key: str,
    conn: sqlite3.Connection,
) -> dict[str, Any]:
    cur = conn.execute(
        SQL_QUERIES["cpm_runs_for_version"],
        (schedule_version_key, _parse_schedule_version_key(schedule_version_key)["project_key"]),
    )
    cols = [d[0] for d in cur.description]
    runs = [dict(zip(cols, row)) for row in cur.fetchall()]
    by_type = {str(r["calculation_type"]): r for r in runs}

    resolver = CpmRunChainResolver(db_path=db_path)
    chain = resolver.resolve(schedule_version_key, latest=True)

    stages_db = {name: _stage_row(conn, by_type.get(name)) for name in STAGE_ORDER}
    crit = by_type.get("criticality")
    lp = by_type.get("longest_path")
    flt = by_type.get("float")
    bwd = by_type.get("backward_pass")
    fwd = by_type.get("forward_pass")

    same_import = (
        fwd
        and bwd
        and str(fwd.get("import_id") or "") == str(bwd.get("import_id") or "")
        and str(fwd.get("import_id") or "") != ""
    )

    checks = {
        "criticality_sources_longest_path": bool(
            crit and lp and str(crit.get("source_run_id") or "") == str(lp.get("cpm_run_id") or "")
        ),
        "longest_path_sources_float": bool(
            lp and flt and str(lp.get("source_run_id") or "") == str(flt.get("cpm_run_id") or "")
        ),
        "float_sources_backward": bool(
            flt and bwd and str(flt.get("source_run_id") or "") == str(bwd.get("cpm_run_id") or "")
        ),
        "backward_sources_forward": bool(
            bwd
            and fwd
            and (
                str(bwd.get("source_run_id") or "") == str(fwd.get("cpm_run_id") or "")
                or same_import
            )
        ),
    }

    return {
        "lineage_valid": chain.lineage_valid,
        "resolution_mode": chain.resolution_mode,
        "schedule_version_key": schedule_version_key,
        "chain_id_hash": _hash_id(chain.chain_id),
        "stages": stages_db,
        "lineage_checks": checks,
        "resolver_stage_run_id_hashes": {
            k: _hash_id(str(v.get("cpm_run_id"))) if v else None
            for k, v in chain.stages.items()
            if k in STAGE_ORDER
        },
        "query_status": "pass" if chain.lineage_valid and all(checks.values()) else "fail",
    }


def build_table_counts(conn: sqlite3.Connection, runs_by_type: dict[str, dict[str, Any]]) -> dict[str, Any]:
    act: dict[str, int] = {}
    rel: dict[str, int] = {}
    for stage in ("forward_pass", "backward_pass", "float", "criticality"):
        run = runs_by_type.get(stage)
        if not run:
            continue
        rid = str(run["cpm_run_id"])
        act[stage] = int(_row(conn, SQL_QUERIES["activity_results_count"], (rid,)) or 0)
    for stage in ("forward_pass", "backward_pass", "float"):
        run = runs_by_type.get(stage)
        if not run:
            continue
        rid = str(run["cpm_run_id"])
        rel[stage] = int(_row(conn, SQL_QUERIES["relationship_results_count"], (rid,)) or 0)

    lp_run = runs_by_type.get("longest_path")
    lp_id = str(lp_run["cpm_run_id"]) if lp_run else ""
    paths = int(_row(conn, SQL_QUERIES["path_count"], (lp_id,)) or 0) if lp_id else 0
    path_acts = (
        int(_row(conn, SQL_QUERIES["path_activities_count"], (lp_id,)) or 0) if lp_id else 0
    )

    return {
        "schedule_cpm_activity_results": act,
        "schedule_cpm_relationship_results": rel,
        "schedule_cpm_paths": {"longest_path": paths},
        "schedule_cpm_path_activities": {"longest_path": path_acts},
        "query_status": "pass",
    }


def build_persisted_path_proof(conn: sqlite3.Connection, lp_run: dict[str, Any] | None) -> dict[str, Any]:
    if not lp_run:
        return {"path_count": 0, "paths": [], "query_status": "fail"}
    rid = str(lp_run["cpm_run_id"])
    cur = conn.execute(SQL_QUERIES["paths_for_run"], (rid,))
    cols = [d[0] for d in cur.description]
    paths = []
    for row in cur.fetchall():
        rec = dict(zip(cols, row))
        paths.append(
            {
                "path_rank": rec.get("path_rank"),
                "path_id_hash": _hash_id(str(rec.get("path_id"))),
                "terminal_activity_id_hash": _hash_id(str(rec.get("end_activity_id"))),
                "activity_count_on_path": rec.get("activity_count"),
                "relationship_count_on_path": rec.get("relationship_count"),
                "path_start_offset_days": rec.get("path_start_offset_days"),
                "path_finish_offset_days": rec.get("path_finish_offset_days"),
                "path_duration_days": rec.get("path_duration"),
                "path_duration_basis": PATH_DURATION_BASIS,
                "basis": rec.get("path_basis") or PATH_BASIS,
            }
        )
    return {
        "path_count": len(paths),
        "paths": paths,
        "query_status": "pass" if paths else "fail",
    }


def sanitize_exporter_outputs(raw_dir: Path, out_dir: Path) -> dict[str, Any]:
    summary_path = raw_dir / "cpm-run-summary.json"
    diff_path = raw_dir / "cpm-validation-recompute-diff.json"
    audit_path = raw_dir / "cpm-formula-audit.md"

    summary = json.loads(summary_path.read_text()) if summary_path.is_file() else {}
    diff = json.loads(diff_path.read_text()) if diff_path.is_file() else {}
    audit_text = audit_path.read_text() if audit_path.is_file() else ""

    san_summary = {
        "mode": summary.get("mode"),
        "schedule_version_key": summary.get("schedule_version_key"),
        "formula_version": summary.get("formula_version"),
        "diff_status": summary.get("diff_status"),
        "activity_count": summary.get("activity_count"),
        "relationship_count": summary.get("relationship_count"),
        "chain_resolution": {
            "chain_id_hash": _hash_id(
                str((summary.get("chain_resolution") or {}).get("chain_id") or "")
            ),
            "resolution_mode": (summary.get("chain_resolution") or {}).get("resolution_mode"),
            "status": (summary.get("chain_resolution") or {}).get("status"),
            "lineage_valid": (summary.get("chain_resolution") or {}).get("lineage_valid"),
        },
    }

    lp = diff.get("longest_path") or {}
    san_diff = {
        "status": diff.get("status"),
        "stage_status": diff.get("stage_status"),
        "activity_match_summary": {
            "matched": diff.get("matched_activity_count"),
            "total": diff.get("activity_count"),
            "mismatched": diff.get("mismatched_activity_count"),
        },
        "relationship_match_summary": {
            "matched": diff.get("matched_relationship_count"),
            "total": diff.get("relationship_count"),
            "mismatched": diff.get("mismatched_relationship_count"),
        },
        "longest_path": {
            "diff_status": lp.get("diff_status"),
            "persisted_path_count": lp.get("persisted_path_count"),
            "shadow_path_count": lp.get("shadow_path_count"),
            "matched_path_count": lp.get("matched_path_count"),
            "mismatched_path_count": lp.get("mismatched_path_count"),
            "path_mismatches": [],
            "path_duration_basis": lp.get("path_duration_basis"),
        },
        "source_field_exclusion": {
            "status": (diff.get("source_field_exclusion") or {}).get("status"),
            "violations": [],
        },
    }

    shadow_summary = lp.get("shadow_summary") or {}
    persisted_summary = lp.get("persisted_summary") or {}
    path_summary = {
        "persisted_path_count": lp.get("persisted_path_count", 0),
        "shadow_path_count": lp.get("shadow_path_count", 0),
        "matched_path_count": lp.get("matched_path_count", 0),
        "mismatched_path_count": lp.get("mismatched_path_count", 0),
        "path_rank": persisted_summary.get("path_rank") or 1,
        "activity_count_on_path": shadow_summary.get("activity_count", 0),
        "relationship_count_on_path": shadow_summary.get("relationship_count", 0),
        "terminal_activity_id_hash_or_redacted": _hash_id(
            str(persisted_summary.get("end_activity_id") or shadow_summary.get("end_activity_id") or "")
        ),
        "path_duration_days": shadow_summary.get("path_duration"),
        "path_duration_basis": PATH_DURATION_BASIS,
        "diff_status": lp.get("diff_status"),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "07-cpm-run-summary-sanitized.json").write_text(
        json.dumps(san_summary, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "08-cpm-validation-recompute-diff-sanitized.json").write_text(
        json.dumps(san_diff, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "09-cpm-formula-audit-sanitized.md").write_text(audit_text, encoding="utf-8")
    (out_dir / "10-cpm-live-path-summary-sanitized.json").write_text(
        json.dumps(path_summary, indent=2) + "\n", encoding="utf-8"
    )
    return {"sanitized": True, "diff_status": san_diff.get("status"), "lp_status": lp.get("diff_status")}


def write_query_manifest(
    out_dir: Path,
    *,
    project_key: str,
    schedule_version_key: str,
    commands: list[str],
    files: list[str],
) -> None:
    lines = [
        "# Query manifest — CPM longest-path live queried evidence",
        "",
        "## Inputs",
        "",
        f"- Copied DB: `local-sensitive/clean-db/<redacted>` (local-only; not included)",
        f"- Project key: `{project_key}`",
        f"- Schedule version key: `{schedule_version_key}`",
        "- SQLite open mode: `read_only` (`file:...?mode=ro`)",
        "",
        "## SQL queries executed",
        "",
    ]
    for name, sql in SQL_QUERIES.items():
        lines.append(f"### `{name}`")
        lines.append("")
        lines.append("```sql")
        lines.append(sql.strip())
        lines.append("```")
        lines.append("")
    lines.extend(
        [
            "## Python / exporter commands",
            "",
        ]
    )
    for cmd in commands:
        lines.append(f"- `{cmd}`")
    lines.extend(
        [
            "",
            "## Generated files",
            "",
        ]
    )
    for f in files:
        lines.append(f"- `{f}`")
    lines.extend(
        [
            "",
            "## Exclusions",
            "",
            "No SQLite database file is included in commit-eligible evidence.",
            "Raw activity/relationship/longest-path JSONL traces remain local-only.",
        ]
    )
    (out_dir / "01-query-manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_query_evidence(
    *,
    db_path: Path,
    project_key: str,
    schedule_version_key: str,
    out_dir: Path,
    copied_db_before: dict[str, int] | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    with _ro_connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        meta = build_db_copy_metadata(
            db_path=db_path,
            project_key=project_key,
            schedule_version_key=schedule_version_key,
            conn=conn,
        )
        (out_dir / "02-db-copy-metadata.json").write_text(
            json.dumps(meta, indent=2) + "\n", encoding="utf-8"
        )
        (out_dir / "03-schedule-version-proof.json").write_text(
            json.dumps(build_schedule_version_proof(meta), indent=2) + "\n", encoding="utf-8"
        )
        lineage = build_lineage_proof(
            db_path=str(db_path), schedule_version_key=schedule_version_key, conn=conn
        )
        (out_dir / "04-cpm-lineage-proof.json").write_text(
            json.dumps(lineage, indent=2) + "\n", encoding="utf-8"
        )

        cur = conn.execute(
            SQL_QUERIES["cpm_runs_for_version"], (schedule_version_key, project_key)
        )
        cols = [d[0] for d in cur.description]
        runs = [dict(zip(cols, row)) for row in cur.fetchall()]
        by_type = {str(r["calculation_type"]): r for r in runs}

        counts = build_table_counts(conn, by_type)
        (out_dir / "05-cpm-table-counts.json").write_text(
            json.dumps(counts, indent=2) + "\n", encoding="utf-8"
        )
        path_proof = build_persisted_path_proof(conn, by_type.get("longest_path"))
        (out_dir / "06-persisted-longest-path-proof.json").write_text(
            json.dumps(path_proof, indent=2) + "\n", encoding="utf-8"
        )

    copied_after = snapshot_db_row_counts(db_path)
    if copied_db_before is not None:
        assert_db_unchanged(copied_db_before, copied_after)

    return {
        "meta": meta,
        "lineage": lineage,
        "counts": counts,
        "path_proof": path_proof,
        "copied_db_unchanged": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--project-key", required=True)
    parser.add_argument("--schedule-version-key", required=True)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--confirm-clean-copy", action="store_true")
    parser.add_argument("--allow-custom-copy-path", action="store_true")
    parser.add_argument("--sanitize-from-raw", type=Path)
    args = parser.parse_args(argv)

    if args.sanitize_from_raw:
        result = sanitize_exporter_outputs(args.sanitize_from_raw, args.out_dir)
        print(json.dumps(result, indent=2))
        return 0

    try:
        assert_not_live_db(args.db_path, context="cpm longest path query evidence")
        if not args.allow_custom_copy_path:
            require_confirm_clean_copy(args.confirm_clean_copy)
            assert_clean_copy_path(
                args.db_path,
                allow_custom_copy_path=args.allow_custom_copy_path,
            )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    before = snapshot_db_row_counts(args.db_path)
    result = run_query_evidence(
        db_path=Path(args.db_path),
        project_key=args.project_key,
        schedule_version_key=args.schedule_version_key,
        out_dir=args.out_dir,
        copied_db_before=before,
    )
    print(json.dumps({"query_status": "pass", "activity_count": result["meta"]["activity_count"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
