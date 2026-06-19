#!/usr/bin/env python3
"""Body-free proof for Patch 5 purchase-order custom-field containers."""

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

RAW_TABLE = "procore_endpoint_raw_payloads"
ENDPOINT = "purchase-order-contracts"
TABLE = "procore_ep_purchase_order_contracts"
DEFAULT_INVENTORY = Path(
    "docs/evidence/procore-null-projection-patch3-design/"
    "20260619T074626Z/object-container-field-inventory.json"
)
TARGET_SCALARS = {
    "custom_fields_custom_field_214072_value": [
        "custom_fields_custom_field_214072_value_id",
    ],
    "custom_fields_custom_field_214078_value": [
        "custom_fields_custom_field_214078_value_company_name",
        "custom_fields_custom_field_214078_value_id",
    ],
    "custom_fields_custom_field_214087_value": [
        "custom_fields_custom_field_214087_value_id",
    ],
}
EXPECTED_TARGET_COUNT = 3
EXPECTED_SCALAR_COUNT = 4
BODY_FREE_GUARDRAILS = {
    "raw_payload_values_emitted": False,
    "live_calls_disabled": True,
    "writeback": "none",
}
ALLOWED_CLASSIFICATIONS = {
    "covered_by_existing_scalar_decomposition_columns",
    "partially_covered_existing_scalar_columns",
    "source_absent_for_custom_field_container",
    "source_absent_for_specific_scalar_column",
    "requires_generic_custom_field_value_table",
    "custom_field_metadata_missing",
    "needs_endpoint_specific_review",
}


class ProofError(RuntimeError):
    """Patch 5 proof cannot continue safely."""


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_empty(value: Any) -> bool:
    return value in (None, "", [], {})


def _shape(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return "string"


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
    shape_counts: Counter[str] = Counter()
    for payload in payloads:
        values = _values_at(payload, json_path)
        if values:
            present += 1
        if any(not _is_empty(value) for value in values):
            non_empty += 1
        if values and all(_is_empty(value) for value in values):
            empty += 1
        for value in values:
            shape_counts[_shape(value)] += 1
            if isinstance(value, dict):
                object_keys.update(str(key) for key in value)
    return {
        "json_path": json_path,
        "path_present_count": present,
        "path_non_empty_count": non_empty,
        "path_null_or_empty_count": empty,
        "path_missing_count": max(len(payloads) - present, 0),
        "shape_counts": dict(sorted(shape_counts.items())),
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
    custom_field_candidates = [
        field
        for field in fields
        if field.get("table") == TABLE
        and field.get("future_recommendation") == "needs_additional_source_sample"
        and str(field.get("column", "")).startswith("custom_fields_custom_field_")
    ]
    candidate_columns = {str(field.get("column")) for field in custom_field_candidates}
    if candidate_columns != set(TARGET_SCALARS):
        raise ProofError(
            "Patch 5 target set mismatch: "
            f"expected {sorted(TARGET_SCALARS)}, found {sorted(candidate_columns)}"
        )
    targets = [field for field in custom_field_candidates if field.get("column") in TARGET_SCALARS]
    if len(targets) != EXPECTED_TARGET_COUNT:
        raise ProofError(
            f"Patch 5 target mismatch: expected {EXPECTED_TARGET_COUNT}, found {len(targets)}"
        )
    target_columns = {field["column"] for field in targets}
    if target_columns != set(TARGET_SCALARS):
        raise ProofError(f"Patch 5 target set mismatch: {sorted(target_columns)}")
    for field in targets:
        scalars = field.get("existing_scalar_decomposition_columns")
        expected = TARGET_SCALARS[field["column"]]
        if scalars != expected:
            raise ProofError(
                f"Patch 5 scalar target mismatch for {field['column']}: {scalars}"
            )
    return sorted(targets, key=lambda row: row["column"])


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({_quote(table)})")}


def _non_null_count(conn: sqlite3.Connection, table: str, column: str) -> int:
    return int(
        conn.execute(
            f"SELECT COUNT(*) FROM {_quote(table)} WHERE {_quote(column)} IS NOT NULL"
        ).fetchone()[0]
    )


def _row_count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {_quote(table)}").fetchone()[0])


def _endpoint_payloads(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    tables = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if RAW_TABLE not in tables:
        return []
    payloads: list[dict[str, Any]] = []
    sql = (
        f"SELECT payload_json FROM {_quote(RAW_TABLE)} "
        "WHERE endpoint_key = ? AND is_current = 1 "
        "AND raw_procore_payload_persisted = 1 AND source_quality = 'live_full_payload'"
    )
    for (payload_json,) in conn.execute(sql, (ENDPOINT,)):
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


def _comparative_siblings(plan: Any, target_scalars: list[str], bare_column: str) -> list[dict[str, Any]]:
    prefix = f"{bare_column}_"
    rows = []
    for rel_path, destination in getattr(plan, "primary_columns", ()):
        if destination.startswith(prefix) and destination not in target_scalars:
            rows.append(
                {
                    "column": destination,
                    "registry_json_path": f"$.{rel_path}",
                    "scope": "out_of_scope_comparative_metadata",
                }
            )
    return sorted(rows, key=lambda row: row["column"])


def collect_inventory(
    *,
    db_path: str | Path,
    inventory_json: str | Path = DEFAULT_INVENTORY,
) -> dict[str, Any]:
    targets = load_patch3_targets(inventory_json)
    plan = projection_registry.plan_for(ENDPOINT)
    conn = sqlite3.connect(db_path)
    try:
        columns = _table_columns(conn, TABLE)
        payloads = _endpoint_payloads(conn)
        fields = []
        for target in targets:
            bare_column = target["column"]
            container_path = f"$.custom_fields.custom_field_{bare_column.split('_')[4]}.value"
            scalar_rows = []
            for scalar_column in TARGET_SCALARS[bare_column]:
                registry_json_path = _registry_path_for(plan, scalar_column) if plan else None
                scalar_rows.append(
                    {
                        "column": scalar_column,
                        "column_exists": scalar_column in columns,
                        "registry_mapped": registry_json_path is not None,
                        "registry_json_path": registry_json_path,
                        "source_path_check": _path_check(payloads, registry_json_path)
                        if registry_json_path
                        else {
                            "json_path": None,
                            "path_present_count": 0,
                            "path_non_empty_count": 0,
                            "path_null_or_empty_count": 0,
                            "path_missing_count": len(payloads),
                            "shape_counts": {},
                            "object_keys_present": [],
                            "raw_payload_values_emitted": False,
                        },
                    }
                )
            fields.append(
                {
                    "table": TABLE,
                    "bare_column": bare_column,
                    "endpoint_key": ENDPOINT,
                    "row_count": _row_count(conn, TABLE),
                    "bare_column_exists": bare_column in columns,
                    "bare_column_registry_mapped": bool(
                        plan and _registry_path_for(plan, bare_column)
                    ),
                    "bare_column_non_null_count": _non_null_count(conn, TABLE, bare_column)
                    if bare_column in columns
                    else None,
                    "container_path_check": _path_check(payloads, container_path),
                    "scalar_columns": scalar_rows,
                    "comparative_sibling_columns": _comparative_siblings(
                        plan, TARGET_SCALARS[bare_column], bare_column
                    )
                    if plan
                    else [],
                    "raw_payload_rows_inspected": len(payloads),
                    "raw_payload_values_emitted": False,
                }
            )
    finally:
        conn.close()
    total_scalars = sum(len(field["scalar_columns"]) for field in fields)
    if len(fields) != EXPECTED_TARGET_COUNT or total_scalars != EXPECTED_SCALAR_COUNT:
        raise ProofError(
            f"Patch 5 output target mismatch: fields={len(fields)} scalars={total_scalars}"
        )
    return {
        "generated_at_utc": _utc_now(),
        "inventory_json": str(inventory_json),
        "db_path": str(db_path),
        "target_container_count": len(fields),
        "target_scalar_count": total_scalars,
        "guardrails": BODY_FREE_GUARDRAILS,
        "fields": fields,
    }


def source_shape_summary(inventory: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_at_utc": _utc_now(),
        "guardrails": BODY_FREE_GUARDRAILS,
        "fields": [
            {
                "table": field["table"],
                "bare_column": field["bare_column"],
                "endpoint_key": field["endpoint_key"],
                "container_path_check": field["container_path_check"],
                "scalar_path_checks": [
                    {
                        "column": scalar["column"],
                        "source_path_check": scalar["source_path_check"],
                    }
                    for scalar in field["scalar_columns"]
                ],
                "comparative_sibling_columns": field["comparative_sibling_columns"],
                "raw_payload_values_emitted": False,
            }
            for field in inventory["fields"]
        ],
    }


def count_targets(db_path: str | Path, inventory: dict[str, Any]) -> dict[str, Any]:
    conn = sqlite3.connect(db_path)
    try:
        fields = []
        for field in inventory["fields"]:
            scalar_counts = []
            for scalar in field["scalar_columns"]:
                scalar_counts.append(
                    {
                        "column": scalar["column"],
                        "non_null_count": _non_null_count(conn, TABLE, scalar["column"])
                        if scalar["column_exists"]
                        else None,
                    }
                )
            fields.append(
                {
                    "table": TABLE,
                    "bare_column": field["bare_column"],
                    "endpoint_key": ENDPOINT,
                    "row_count": _row_count(conn, TABLE),
                    "bare_column_non_null_count": _non_null_count(
                        conn, TABLE, field["bare_column"]
                    )
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
        assignments = [
            f"{_quote(scalar['column'])} = NULL"
            for field in inventory["fields"]
            for scalar in field["scalar_columns"]
            if scalar["column_exists"]
        ]
        if assignments:
            conn.execute(f"UPDATE {_quote(TABLE)} SET {', '.join(assignments)}")
        conn.commit()
    finally:
        conn.close()
    return count_targets(db_path, inventory)


def run_replay(*, db_path: str | Path, hb_assistant: str, out_dir: str | Path) -> dict[str, Any]:
    cmd = [
        hb_assistant,
        "procore",
        "analytics",
        "projection-reprocess",
        "--db",
        str(db_path),
        "--endpoint",
        ENDPOINT,
        "--apply",
        "--json",
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    receipt_text = proc.stdout or "{}"
    Path(out_dir, "purchase-order-contracts-projection-reprocess-receipt.json").write_text(
        receipt_text, encoding="utf-8"
    )
    try:
        receipt = json.loads(receipt_text)
    except json.JSONDecodeError:
        receipt = {"ok": False, "parse_error": True}
    receipt["returncode"] = proc.returncode
    if proc.stderr:
        receipt["stderr_present"] = True
    return {"generated_at_utc": _utc_now(), "guardrails": BODY_FREE_GUARDRAILS, "receipt": receipt}


def classify_results(
    *,
    inventory: dict[str, Any],
    reset_counts: dict[str, Any],
    post_counts: dict[str, Any],
) -> dict[str, Any]:
    reset_by = {field["bare_column"]: field for field in reset_counts["fields"]}
    post_by = {field["bare_column"]: field for field in post_counts["fields"]}
    field_rows = []
    scalar_status_counts: Counter[str] = Counter()
    parent_counts: Counter[str] = Counter()
    for field in inventory["fields"]:
        bare_column = field["bare_column"]
        reset_scalars = {s["column"]: s for s in reset_by[bare_column]["scalar_columns"]}
        post_scalars = {s["column"]: s for s in post_by[bare_column]["scalar_columns"]}
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
                status = "needs_endpoint_specific_review"
            elif post_non_null is not None and reset_non_null is not None and post_non_null > reset_non_null:
                status = "already_replays_existing_scalar_columns"
            else:
                status = "needs_endpoint_specific_review"
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
        statuses = {row["status"] for row in scalar_outcomes}
        container_non_empty = int(
            field["container_path_check"].get("path_non_empty_count") or 0
        )
        if container_non_empty == 0:
            decision = "source_absent_for_custom_field_container"
        elif statuses == {"already_replays_existing_scalar_columns"}:
            decision = "covered_by_existing_scalar_decomposition_columns"
        elif statuses <= {
            "already_replays_existing_scalar_columns",
            "source_absent_for_specific_scalar_column",
        } and "already_replays_existing_scalar_columns" in statuses:
            decision = "partially_covered_existing_scalar_columns"
        elif "array" in field["container_path_check"].get("shape_counts", {}):
            decision = "requires_generic_custom_field_value_table"
        else:
            decision = "custom_field_metadata_missing"
        if decision not in ALLOWED_CLASSIFICATIONS:
            raise ProofError(f"invalid Patch 5 decision: {decision}")
        parent_counts[decision] += 1
        field_rows.append(
            {
                "table": TABLE,
                "bare_column": bare_column,
                "endpoint_key": ENDPOINT,
                "container_path_check": field["container_path_check"],
                "bare_column_non_null_after_replay": post_by[bare_column][
                    "bare_column_non_null_count"
                ],
                "post_proof_decision": {
                    "decision_class": decision,
                    "decision_status": "custom_field_container_body_free_proof",
                    "mapping_candidate": False,
                    "next_action": (
                        "no_action_existing_scalar_decomposition_verified"
                        if decision
                        in {
                            "covered_by_existing_scalar_decomposition_columns",
                            "partially_covered_existing_scalar_columns",
                        }
                        else "review_custom_field_model_before_mapping"
                    ),
                    "evidence_basis": "Patch 5 copied-DB replay and body-free source-shape proof.",
                },
                "scalar_columns": scalar_outcomes,
                "comparative_sibling_columns": field["comparative_sibling_columns"],
                "raw_payload_values_emitted": False,
            }
        )
    return {
        "generated_at_utc": _utc_now(),
        "guardrails": BODY_FREE_GUARDRAILS,
        "target_container_count": len(field_rows),
        "target_scalar_count": sum(len(row["scalar_columns"]) for row in field_rows),
        "parent_status_counts": dict(sorted(parent_counts.items())),
        "scalar_status_counts": dict(sorted(scalar_status_counts.items())),
        "high_confidence_mapping_candidates": 0,
        "fields": field_rows,
    }


def write_markdown_report(
    *,
    out_path: str | Path,
    starting_commit: str | None,
    classifications: dict[str, Any],
    replay_receipt: dict[str, Any],
) -> None:
    lines = [
        "# Patch 5 Purchase-Order Custom-Field Container Evidence",
        "",
        f"Generated at: `{_utc_now()}`",
        "",
        "## Objective",
        "",
        "Classify the three purchase-order custom-field bare object/container fields "
        "using body-free source-shape metadata and copied-DB replay proof.",
        "",
        "## Starting Commit",
        "",
        f"`{starting_commit or 'not recorded'}`",
        "",
        "## Summary",
        "",
        f"- Target custom-field containers: `{classifications['target_container_count']}`",
        f"- Target scalar destination columns: `{classifications['target_scalar_count']}`",
        f"- Parent decision counts: `{classifications['parent_status_counts']}`",
        f"- Scalar status counts: `{classifications['scalar_status_counts']}`",
        "- Additional `*_value_label` scalar siblings are comparative metadata only.",
        "- Raw strict findings are not described as fixed; Patch 5 records post-proof dispositions.",
        "- Raw payload values emitted: `false`",
        "",
        "## Field Outcomes",
        "",
        "| Bare column | Decision | Bare non-null after replay | Comparative siblings |",
        "| --- | --- | ---: | --- |",
    ]
    for field in classifications["fields"]:
        siblings = ", ".join(
            f"`{row['column']}`" for row in field["comparative_sibling_columns"]
        ) or "none"
        lines.append(
            f"| `{field['bare_column']}` | "
            f"`{field['post_proof_decision']['decision_class']}` | "
            f"{field['bare_column_non_null_after_replay']} | {siblings} |"
        )
    lines.extend(
        [
            "",
            "## Replay Receipt",
            "",
            f"- `purchase-order-contracts`: ok=`{replay_receipt['receipt'].get('ok')}`, "
            f"returncode=`{replay_receipt['receipt'].get('returncode')}`, "
            f"primary_rows_written=`{replay_receipt['receipt'].get('primary_rows_written')}`",
            "",
            "## Guardrails",
            "",
            "- No raw custom-field values, raw payload bodies, names, emails, notes, comments, "
            "descriptions, URLs, signed URLs, credentials, or sample values are emitted.",
            "- Bare custom-field container columns were not reset or newly populated.",
            "- Budget Detail, `company_id`, child-table/entity-only fields, live calls, scheduler, "
            "SourceRefreshOrchestrator, writeback, production DB mutation, broad refresh, and push "
            "were not used.",
            "",
            "## Remaining Decisions After Patch 5",
            "",
            "- Future generic custom-field value-table design remains separate.",
            "- Out-of-scope comparative sibling columns require explicit approval before target expansion.",
            "- Raw strict detector findings remain preserved; Patch 5 adds post-proof dispositions only.",
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
    db_path = Path(args.db)
    if args.copy_from:
        _copy_db(args.copy_from, db_path)
    _integrity_check(db_path, out / "copied-db-integrity-check.txt")
    inventory = collect_inventory(db_path=db_path, inventory_json=args.inventory_json)
    (out / "target-custom-field-inventory.json").write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "custom-field-source-shape-summary.json").write_text(
        json.dumps(source_shape_summary(inventory), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    pre_counts = count_targets(db_path, inventory)
    (out / "pre-replay-scalar-counts.json").write_text(
        json.dumps(pre_counts, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    reset_counts = reset_scalar_columns(db_path, inventory) if args.apply else pre_counts
    (out / "reset-scalar-counts.json").write_text(
        json.dumps(reset_counts, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    replay_receipt = (
        run_replay(db_path=db_path, hb_assistant=args.hb_assistant, out_dir=out)
        if args.apply
        else {"generated_at_utc": _utc_now(), "guardrails": BODY_FREE_GUARDRAILS, "receipt": {}}
    )
    post_counts = count_targets(db_path, inventory)
    (out / "post-replay-scalar-counts.json").write_text(
        json.dumps(post_counts, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    classifications = classify_results(
        inventory=inventory, reset_counts=reset_counts, post_counts=post_counts
    )
    (out / "classification-summary.json").write_text(
        json.dumps(classifications, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "replay-receipt-summary.json").write_text(
        json.dumps(replay_receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_markdown_report(
        out_path=out / "patch5-custom-field-evidence.md",
        starting_commit=args.starting_commit,
        classifications=classifications,
        replay_receipt=replay_receipt,
    )
    return {
        "ok": classifications["high_confidence_mapping_candidates"] == 0,
        "out": str(out),
        "classification_summary": classifications,
        "raw_payload_values_emitted": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--copy-from")
    parser.add_argument("--inventory-json", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--hb-assistant",
        default="/Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant",
    )
    parser.add_argument("--starting-commit")
    parser.add_argument("--apply", action="store_true")
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
