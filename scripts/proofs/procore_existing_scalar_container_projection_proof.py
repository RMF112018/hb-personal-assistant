#!/usr/bin/env python3
"""Body-free proof for Patch 4 existing scalar container projections.

The utility verifies the Patch 3 object/container design rows whose recommended
future action is to reuse existing scalar decomposition columns. It never maps or
projects whole object/list values into the bare container column.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hb_assistant.procore import projection_registry

EXPECTED_REUSE_TARGETS = 35
RAW_TABLE = "procore_endpoint_raw_payloads"
DEFAULT_INVENTORY = Path(
    "docs/evidence/procore-null-projection-patch3-design/"
    "20260619T074626Z/object-container-field-inventory.json"
)
AFFECTED_ENDPOINTS = (
    "change-events",
    "commitment-change-orders",
    "daily-log-inspections",
    "daily-log-manpower",
    "daily-log-notes",
    "inspections",
    "meetings",
    "observations",
    "prime-change-orders",
    "projects",
    "purchase-order-contracts",
    "rfis",
    "submittals",
)
BODY_FREE_GUARDRAILS = {
    "raw_payload_values_emitted": False,
    "live_calls_disabled": True,
    "writeback": "none",
}


class ProofError(RuntimeError):
    """Patch 4 proof cannot continue safely."""


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_empty(value: Any) -> bool:
    return value in (None, "", [], {})


def _tokens(json_path: str) -> list[tuple[str, bool]]:
    body = json_path[2:] if json_path.startswith("$.") else json_path
    out: list[tuple[str, bool]] = []
    for segment in body.split("."):
        if not segment:
            continue
        out.append((segment[:-2], True) if segment.endswith("[]") else (segment, False))
    return out


def _values_at(node: Any, json_path: str) -> list[Any]:
    values = [node]
    for key, is_array in _tokens(json_path):
        next_values: list[Any] = []
        for value in values:
            if not isinstance(value, dict) or key not in value:
                continue
            child = value[key]
            if is_array:
                if isinstance(child, list):
                    next_values.extend(child)
            else:
                next_values.append(child)
        values = next_values
        if not values:
            break
    return values


def _path_check(payloads: list[dict[str, Any]], json_path: str) -> dict[str, Any]:
    present = 0
    non_empty = 0
    empty = 0
    object_keys: Counter[str] = Counter()
    for payload in payloads:
        values = _values_at(payload, json_path)
        if values:
            present += 1
        if any(not _is_empty(value) for value in values):
            non_empty += 1
        if values and all(_is_empty(value) for value in values):
            empty += 1
        for value in values:
            if isinstance(value, dict):
                object_keys.update(str(key) for key in value)
    return {
        "json_path": json_path,
        "path_present_count": present,
        "path_non_empty_count": non_empty,
        "path_null_or_empty_count": empty,
        "path_missing_count": max(len(payloads) - present, 0),
        "object_keys_present": sorted(object_keys)[:40],
        "raw_payload_values_emitted": False,
    }


def load_patch3_targets(inventory_json: str | Path = DEFAULT_INVENTORY) -> list[dict[str, Any]]:
    path = Path(inventory_json)
    if not path.exists():
        raise ProofError(f"Patch 3 inventory not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    fields = payload.get("fields")
    if not isinstance(fields, list):
        raise ProofError("Patch 3 inventory is malformed: fields must be a list")
    targets = [
        field
        for field in fields
        if field.get("future_recommendation") == "reuse_existing_scalar_decomposition_columns"
    ]
    if len(targets) != EXPECTED_REUSE_TARGETS:
        raise ProofError(
            "Patch 3 inventory target mismatch: expected "
            f"{EXPECTED_REUSE_TARGETS}, found {len(targets)}"
        )
    for field in targets:
        scalars = field.get("existing_scalar_decomposition_columns")
        if not isinstance(field.get("table"), str) or not isinstance(field.get("column"), str):
            raise ProofError("Patch 3 inventory target is missing table/column")
        if not isinstance(scalars, list) or not all(isinstance(c, str) for c in scalars):
            raise ProofError(
                f"Patch 3 inventory target has invalid scalar list: "
                f"{field.get('table')}.{field.get('column')}"
            )
    return sorted(targets, key=lambda r: (r["table"], r["column"]))


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({_quote(table)})")}


def _non_null_count(conn: sqlite3.Connection, table: str, column: str) -> int:
    sql = f"SELECT COUNT(*) FROM {_quote(table)} WHERE {_quote(column)} IS NOT NULL"
    return int(conn.execute(sql).fetchone()[0])


def _row_count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {_quote(table)}").fetchone()[0])


def _endpoint_payloads(conn: sqlite3.Connection, endpoint_key: str) -> list[dict[str, Any]]:
    table_names = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if RAW_TABLE not in table_names:
        return []
    payloads: list[dict[str, Any]] = []
    sql = (
        f"SELECT payload_json FROM {_quote(RAW_TABLE)} "
        "WHERE endpoint_key = ? AND is_current = 1 "
        "AND raw_procore_payload_persisted = 1 AND source_quality = 'live_full_payload'"
    )
    for (payload_json,) in conn.execute(sql, (endpoint_key,)):
        try:
            payload = json.loads(payload_json)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _registry_path_for(plan: Any, column: str) -> str | None:
    for rel_path, destination in getattr(plan, "primary_columns", ()):
        if destination == column:
            return f"$.{rel_path}"
    return None


def collect_inventory(
    *,
    db_path: str | Path,
    inventory_json: str | Path = DEFAULT_INVENTORY,
) -> dict[str, Any]:
    targets = load_patch3_targets(inventory_json)
    plans = projection_registry.load_registry()
    conn = sqlite3.connect(db_path)
    try:
        fields: list[dict[str, Any]] = []
        for target in targets:
            table = target["table"]
            bare_column = target["column"]
            endpoint_key = str(target.get("endpoint_key") or "")
            plan = plans.get(endpoint_key)
            columns = _table_columns(conn, table)
            bare_exists = bare_column in columns
            bare_mapped = bool(plan and _registry_path_for(plan, bare_column))
            payloads = _endpoint_payloads(conn, endpoint_key)
            scalar_records = []
            for scalar_column in target["existing_scalar_decomposition_columns"]:
                registry_json_path = _registry_path_for(plan, scalar_column) if plan else None
                path_check = (
                    _path_check(payloads, registry_json_path)
                    if registry_json_path is not None
                    else {
                        "json_path": None,
                        "path_present_count": 0,
                        "path_non_empty_count": 0,
                        "path_null_or_empty_count": 0,
                        "path_missing_count": len(payloads),
                        "object_keys_present": [],
                        "raw_payload_values_emitted": False,
                    }
                )
                scalar_records.append(
                    {
                        "column": scalar_column,
                        "column_exists": scalar_column in columns,
                        "registry_mapped": registry_json_path is not None,
                        "registry_json_path": registry_json_path,
                        "source_path_check": path_check,
                    }
                )
            fields.append(
                {
                    "table": table,
                    "bare_column": bare_column,
                    "endpoint_key": endpoint_key,
                    "row_count": _row_count(conn, table) if bare_exists else None,
                    "bare_column_exists": bare_exists,
                    "bare_column_registry_mapped": bare_mapped,
                    "bare_column_non_null_count": (
                        _non_null_count(conn, table, bare_column) if bare_exists else None
                    ),
                    "raw_payload_rows_inspected": len(payloads),
                    "scalar_columns": scalar_records,
                    "raw_payload_values_emitted": False,
                }
            )
    finally:
        conn.close()
    return {
        "generated_at_utc": _utc_now(),
        "inventory_json": str(inventory_json),
        "db_path": str(db_path),
        "target_field_count": len(fields),
        "guardrails": BODY_FREE_GUARDRAILS,
        "fields": fields,
    }


def count_targets(db_path: str | Path, inventory: dict[str, Any]) -> dict[str, Any]:
    conn = sqlite3.connect(db_path)
    try:
        fields = []
        for field in inventory["fields"]:
            table = field["table"]
            bare_column = field["bare_column"]
            scalar_counts = []
            for scalar in field["scalar_columns"]:
                column = scalar["column"]
                scalar_counts.append(
                    {
                        "column": column,
                        "non_null_count": _non_null_count(conn, table, column)
                        if scalar["column_exists"]
                        else None,
                    }
                )
            fields.append(
                {
                    "table": table,
                    "bare_column": bare_column,
                    "endpoint_key": field["endpoint_key"],
                    "row_count": _row_count(conn, table) if field["bare_column_exists"] else None,
                    "bare_column_non_null_count": _non_null_count(conn, table, bare_column)
                    if field["bare_column_exists"]
                    else None,
                    "scalar_columns": scalar_counts,
                    "raw_payload_values_emitted": False,
                }
            )
    finally:
        conn.close()
    return {"generated_at_utc": _utc_now(), "guardrails": BODY_FREE_GUARDRAILS, "fields": fields}


def reset_scalar_columns(db_path: str | Path, inventory: dict[str, Any]) -> dict[str, Any]:
    conn = sqlite3.connect(db_path)
    try:
        for field in inventory["fields"]:
            table = field["table"]
            assignments = [
                f"{_quote(scalar['column'])} = NULL"
                for scalar in field["scalar_columns"]
                if scalar["column_exists"]
            ]
            if assignments:
                conn.execute(f"UPDATE {_quote(table)} SET {', '.join(assignments)}")
        conn.commit()
    finally:
        conn.close()
    return count_targets(db_path, inventory)


def run_endpoint_replays(
    *,
    db_path: str | Path,
    endpoints: list[str],
    hb_assistant: str,
    out_dir: str | Path,
) -> dict[str, Any]:
    receipts: dict[str, Any] = {}
    out = Path(out_dir)
    for endpoint in endpoints:
        cmd = [
            hb_assistant,
            "procore",
            "analytics",
            "projection-reprocess",
            "--db",
            str(db_path),
            "--endpoint",
            endpoint,
            "--apply",
            "--json",
        ]
        proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
        receipt_path = out / f"{endpoint}-projection-reprocess-receipt.json"
        receipt_text = proc.stdout or "{}"
        receipt_path.write_text(receipt_text, encoding="utf-8")
        try:
            receipt = json.loads(receipt_text)
        except json.JSONDecodeError:
            receipt = {"ok": False, "parse_error": True, "stdout_empty": not bool(proc.stdout)}
        receipt["returncode"] = proc.returncode
        if proc.stderr:
            receipt["stderr_present"] = True
        receipts[endpoint] = receipt
    return {
        "generated_at_utc": _utc_now(),
        "guardrails": BODY_FREE_GUARDRAILS,
        "receipts": receipts,
    }


def classify_results(
    *,
    inventory: dict[str, Any],
    reset_counts: dict[str, Any],
    post_counts: dict[str, Any],
) -> dict[str, Any]:
    reset_by_field = {
        (field["table"], field["bare_column"]): field for field in reset_counts["fields"]
    }
    post_by_field = {
        (field["table"], field["bare_column"]): field for field in post_counts["fields"]
    }
    field_outcomes = []
    scalar_status_counts: Counter[str] = Counter()
    parent_status_counts: Counter[str] = Counter()
    for field in inventory["fields"]:
        key = (field["table"], field["bare_column"])
        reset_field = reset_by_field[key]
        post_field = post_by_field[key]
        reset_scalars = {s["column"]: s for s in reset_field["scalar_columns"]}
        post_scalars = {s["column"]: s for s in post_field["scalar_columns"]}
        scalar_outcomes = []
        for scalar in field["scalar_columns"]:
            column = scalar["column"]
            source_non_empty = int(
                scalar["source_path_check"].get("path_non_empty_count") or 0
            )
            reset_non_null = reset_scalars[column]["non_null_count"]
            post_non_null = post_scalars[column]["non_null_count"]
            if not scalar["column_exists"]:
                status = "needs_endpoint_specific_review"
            elif source_non_empty == 0:
                status = "source_absent_for_specific_scalar_column"
            elif not scalar["registry_mapped"]:
                status = "registry_mapping_missing_for_existing_scalar_column"
            elif post_non_null is not None and reset_non_null is not None and post_non_null > reset_non_null:
                status = "already_replays_existing_scalar_columns"
            else:
                status = "projection_write_path_missing_for_existing_scalar_column"
            scalar_status_counts[status] += 1
            scalar_outcomes.append(
                {
                    "column": column,
                    "registry_json_path": scalar["registry_json_path"],
                    "source_non_empty_count": source_non_empty,
                    "after_reset_non_null_count": reset_non_null,
                    "after_replay_non_null_count": post_non_null,
                    "status": status,
                }
            )
        statuses = {outcome["status"] for outcome in scalar_outcomes}
        if statuses == {"already_replays_existing_scalar_columns"}:
            parent_status = "covered_by_existing_scalar_decomposition_columns"
        elif statuses <= {
            "already_replays_existing_scalar_columns",
            "source_absent_for_specific_scalar_column",
        } and "already_replays_existing_scalar_columns" in statuses:
            parent_status = "partially_covered_existing_scalar_columns"
        else:
            parent_status = "needs_endpoint_specific_review"
        parent_status_counts[parent_status] += 1
        field_outcomes.append(
            {
                "table": field["table"],
                "bare_column": field["bare_column"],
                "endpoint_key": field["endpoint_key"],
                "bare_column_non_null_after_replay": post_field["bare_column_non_null_count"],
                "post_proof_decision": {
                    "decision_class": parent_status,
                    "decision_status": "no_whole_object_projection",
                    "mapping_candidate": False,
                    "next_action": (
                        "no_action_existing_scalar_decomposition_verified"
                        if parent_status == "covered_by_existing_scalar_decomposition_columns"
                        else "review_scalar_source_coverage_before_schema_decision"
                    ),
                    "evidence_basis": (
                        "Existing scalar destination columns replayed from source-backed registry paths."
                        if parent_status == "covered_by_existing_scalar_decomposition_columns"
                        else "At least one scalar destination lacked source-backed replay proof."
                    ),
                },
                "scalar_columns": scalar_outcomes,
                "raw_payload_values_emitted": False,
            }
        )
    return {
        "generated_at_utc": _utc_now(),
        "guardrails": BODY_FREE_GUARDRAILS,
        "field_count": len(field_outcomes),
        "scalar_status_counts": dict(sorted(scalar_status_counts.items())),
        "parent_status_counts": dict(sorted(parent_status_counts.items())),
        "high_confidence_mapping_candidates": int(
            scalar_status_counts["registry_mapping_missing_for_existing_scalar_column"]
            + scalar_status_counts[
                "projection_write_path_missing_for_existing_scalar_column"
            ]
        ),
        "fields": field_outcomes,
    }


def write_markdown_report(
    *,
    out_path: str | Path,
    starting_commit: str | None,
    inventory: dict[str, Any],
    classifications: dict[str, Any],
    replay_receipts: dict[str, Any],
) -> None:
    lines = [
        "# Patch 4 Existing Scalar Container Projection Evidence",
        "",
        f"Generated at: `{_utc_now()}`",
        "",
        "## Objective",
        "",
        "Verify the 35 Patch 3 bare object/container fields that should be represented "
        "through existing scalar decomposition columns. This proof does not populate "
        "the bare object/container columns.",
        "",
        "## Starting Commit",
        "",
        f"`{starting_commit or 'not recorded'}`",
        "",
        "## Summary",
        "",
        f"- Target bare object/container fields: `{inventory['target_field_count']}`",
        f"- Parent decision counts: `{classifications['parent_status_counts']}`",
        f"- Scalar status counts: `{classifications['scalar_status_counts']}`",
        "- Raw strict findings are not described as fixed; Patch 4 records post-proof "
        "covered/no-action/review dispositions.",
        "- Source-absent scalar leaves are not classified as covered.",
        "- Bare object/container non-null counts, where present, are preexisting/unchanged "
        "counts; Patch 4 does not reset or populate bare object/container columns.",
        "- Raw payload values emitted: `false`",
        "",
        "## Field Outcomes",
        "",
        "| Table | Bare column | Endpoint | Decision | Bare non-null after replay |",
        "| --- | --- | --- | --- | ---: |",
    ]
    for field in classifications["fields"]:
        decision = field["post_proof_decision"]["decision_class"]
        lines.append(
            f"| `{field['table']}` | `{field['bare_column']}` | "
            f"`{field['endpoint_key']}` | `{decision}` | "
            f"{field['bare_column_non_null_after_replay']} |"
        )
    lines.extend(
        [
            "",
            "## Replay Receipts",
            "",
        ]
    )
    for endpoint, receipt in replay_receipts.get("receipts", {}).items():
        lines.append(
            f"- `{endpoint}`: ok=`{receipt.get('ok')}`, "
            f"returncode=`{receipt.get('returncode')}`, "
            f"primary_rows_written=`{receipt.get('primary_rows_written')}`"
        )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Bare object/container columns were not reset or populated by Patch 4.",
            "- Budget Detail was not changed.",
            "- `company_id` was not derived or backfilled.",
            "- No live Procore calls, scheduler runs, SourceRefreshOrchestrator runs, "
            "writeback, production DB mutation, broad refresh, or push were performed.",
        ]
    )
    Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _copy_db(source: str | Path, destination: str | Path) -> None:
    shutil.copy2(source, destination)


def _integrity_check(db_path: str | Path, out_path: str | Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        rows = [
            *(row[0] for row in conn.execute("PRAGMA integrity_check")),
            *(row[0] for row in conn.execute("PRAGMA quick_check")),
        ]
    finally:
        conn.close()
    Path(out_path).write_text("\n".join(map(str, rows)) + "\n", encoding="utf-8")


def run_proof(args: argparse.Namespace) -> dict[str, Any]:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    db_path = Path(args.db_path)
    if args.copy_from:
        _copy_db(args.copy_from, db_path)
    _integrity_check(db_path, out / "copied-db-integrity-check.txt")
    inventory = collect_inventory(db_path=db_path, inventory_json=args.inventory_json)
    (out / "target-field-inventory.json").write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    pre_counts = count_targets(db_path, inventory)
    (out / "pre-replay-scalar-counts.json").write_text(
        json.dumps(pre_counts, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    reset_counts = reset_scalar_columns(db_path, inventory)
    (out / "reset-scalar-counts.json").write_text(
        json.dumps(reset_counts, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    replay_receipts = run_endpoint_replays(
        db_path=db_path,
        endpoints=list(AFFECTED_ENDPOINTS),
        hb_assistant=args.hb_assistant,
        out_dir=out,
    )
    post_counts = count_targets(db_path, inventory)
    (out / "post-replay-scalar-counts.json").write_text(
        json.dumps(post_counts, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    classifications = classify_results(
        inventory=inventory, reset_counts=reset_counts, post_counts=post_counts
    )
    (out / "classification-summary.json").write_text(
        json.dumps(classifications, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out / "replay-receipts-summary.json").write_text(
        json.dumps(replay_receipts, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_markdown_report(
        out_path=out / "patch4-existing-scalar-container-evidence.md",
        starting_commit=args.starting_commit,
        inventory=inventory,
        classifications=classifications,
        replay_receipts=replay_receipts,
    )
    return {
        "ok": classifications["high_confidence_mapping_candidates"] == 0,
        "out": str(out),
        "classification_summary": classifications,
        "raw_payload_values_emitted": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--copy-from")
    parser.add_argument("--inventory-json", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--hb-assistant",
        default="/Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant",
    )
    parser.add_argument("--starting-commit")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = run_proof(args)
    except ProofError as exc:
        payload = {"ok": False, "error": str(exc), "raw_payload_values_emitted": False}
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(str(exc))
        return 2
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
