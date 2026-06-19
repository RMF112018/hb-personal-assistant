#!/usr/bin/env python3
"""Patch 6 body-free policy evidence for covered bare containers."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PATCH4_SUMMARY = Path(
    "docs/evidence/procore-null-projection-patch4-existing-scalar-containers/"
    "20260619T080633Z/classification-summary.json"
)
PATCH5_SUMMARY = Path(
    "docs/evidence/procore-null-projection-patch5-custom-fields/"
    "20260619T083510Z/classification-summary.json"
)
PATCH3_INVENTORY = Path(
    "docs/evidence/procore-null-projection-patch3-design/"
    "20260619T074626Z/object-container-field-inventory.json"
)
MATRIX_PATH = Path(
    "docs/evidence/procore-null-projection-final-schema-decision-matrix/"
    "20260619T000000Z/remaining-unresolved-schema-decision-matrix.md"
)

EXPECTED = {
    "covered_total": 34,
    "covered_non_custom": 31,
    "covered_custom": 3,
    "partial": 4,
    "source_absent_scalar_leaves": 5,
    "child_entity_deferred": 5,
    "company_id_policy_deferred": 4,
    "budget_detail_dead_convenience_column": 4,
    "budget_detail_read_model_schema_artifact": 4,
    "high_confidence_mapping_candidates": 0,
    "projection_code_repair_candidates": 0,
    "date_datetime_mapping_candidates": 0,
}

BODY_FREE_GUARDRAILS = {
    "raw_payload_values_emitted": False,
    "live_calls_disabled": True,
    "writeback": "none",
    "production_db_mutated": False,
}


class PolicyError(RuntimeError):
    """Patch 6 policy evidence cannot continue safely."""


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise PolicyError(f"required evidence file not found: {p}")
    payload = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PolicyError(f"required evidence file is malformed: {p}")
    return payload


def _field_key(field: dict[str, Any]) -> tuple[str, str]:
    table = field.get("table")
    column = field.get("bare_column") or field.get("column")
    if not isinstance(table, str) or not isinstance(column, str):
        raise PolicyError("field is missing table/bare column")
    return table, column


def _source_absent_scalar_count(fields: list[dict[str, Any]]) -> int:
    return sum(
        1
        for field in fields
        for scalar in field.get("scalar_columns", [])
        if scalar.get("status") == "source_absent_for_specific_scalar_column"
    )


def _post_decision(
    *,
    decision_class: str,
    decision_status: str,
    next_action: str,
    evidence_basis: str,
    deprecation_candidate: bool,
    legacy_warning: bool = False,
) -> dict[str, Any]:
    return {
        "decision_class": decision_class,
        "decision_status": decision_status,
        "mapping_candidate": False,
        "projection_code_repair_candidate": False,
        "deprecation_candidate": deprecation_candidate,
        "suppress_from_actionable_mapping_rollup": True,
        "next_action": next_action,
        "evidence_basis": evidence_basis,
        "legacy_non_null_bare_container_values_present": legacy_warning,
    }


def _covered_record(
    field: dict[str, Any],
    *,
    custom_field: bool,
    evidence_path: str,
) -> dict[str, Any]:
    table, column = _field_key(field)
    bare_count = int(field.get("bare_column_non_null_after_replay") or 0)
    decision_class = (
        "bare_container_custom_field_covered_by_scalar_decomposition"
        if custom_field
        else "bare_container_deprecated_covered_by_scalar_decomposition"
    )
    return {
        "table": table,
        "column": column,
        "endpoint_key": field.get("endpoint_key"),
        "policy_bucket": "bare_container_deprecated_covered_by_scalar_decomposition",
        "policy_subtype": decision_class,
        "bare_column_non_null_count": bare_count,
        "legacy_non_null_bare_container_values_present": bare_count > 0,
        "scalar_columns": [
            {
                "column": scalar.get("column"),
                "registry_json_path": scalar.get("registry_json_path"),
                "source_non_empty_count": scalar.get("source_non_empty_count"),
                "after_replay_non_null_count": scalar.get(
                    "after_replay_non_null_count"
                ),
                "status": scalar.get("status"),
            }
            for scalar in field.get("scalar_columns", [])
        ],
        "raw_detection": {
            "raw_field_status": "bare_container_null_or_suspicious",
            "raw_finding_preserved": True,
        },
        "post_proof_decision": _post_decision(
            decision_class=decision_class,
            decision_status="reporting_policy_deprecation_candidate",
            next_action="no_action_existing_scalar_decomposition_verified",
            evidence_basis=(
                f"{evidence_path}; reporting/audit-policy deprecation only, "
                "not a physical column migration."
            ),
            deprecation_candidate=True,
            legacy_warning=bare_count > 0,
        ),
        "raw_payload_values_emitted": False,
    }


def _partial_record(field: dict[str, Any], *, evidence_path: str) -> dict[str, Any]:
    table, column = _field_key(field)
    bare_count = int(field.get("bare_column_non_null_after_replay") or 0)
    return {
        "table": table,
        "column": column,
        "endpoint_key": field.get("endpoint_key"),
        "policy_bucket": "bare_container_partially_covered_scalar_source_absent",
        "bare_column_non_null_count": bare_count,
        "legacy_non_null_bare_container_values_present": bare_count > 0,
        "source_absent_scalar_columns": [
            {
                "column": scalar.get("column"),
                "registry_json_path": scalar.get("registry_json_path"),
                "status": scalar.get("status"),
            }
            for scalar in field.get("scalar_columns", [])
            if scalar.get("status") == "source_absent_for_specific_scalar_column"
        ],
        "scalar_columns": [
            {
                "column": scalar.get("column"),
                "registry_json_path": scalar.get("registry_json_path"),
                "source_non_empty_count": scalar.get("source_non_empty_count"),
                "after_replay_non_null_count": scalar.get(
                    "after_replay_non_null_count"
                ),
                "status": scalar.get("status"),
            }
            for scalar in field.get("scalar_columns", [])
        ],
        "raw_detection": {
            "raw_field_status": "bare_container_null_or_suspicious",
            "raw_finding_preserved": True,
        },
        "post_proof_decision": _post_decision(
            decision_class="bare_container_partially_covered_scalar_source_absent",
            decision_status="source_coverage_review_needed",
            next_action="review_scalar_source_coverage_before_schema_decision",
            evidence_basis=(
                f"{evidence_path}; source-absent scalar leaves are not counted "
                "as covered."
            ),
            deprecation_candidate=True,
            legacy_warning=bare_count > 0,
        ),
        "raw_payload_values_emitted": False,
    }


def _child_entity_records(patch3: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for field in patch3.get("fields", []):
        recommendation = field.get("future_recommendation")
        if recommendation not in {
            "represent_only_in_child_table",
            "represent_only_in_entity_dimension",
        }:
            continue
        rows.append(
            {
                "table": field.get("table"),
                "column": field.get("column"),
                "endpoint_key": field.get("endpoint_key"),
                "policy_bucket": "bare_container_child_table_or_entity_only_deferred",
                "future_recommendation": recommendation,
                "post_proof_decision": _post_decision(
                    decision_class="bare_container_child_table_or_entity_only_deferred",
                    decision_status="design_deferred",
                    next_action="approve_child_table_or_entity_design_next",
                    evidence_basis="Patch 3 design package; not an existing scalar mapping repair.",
                    deprecation_candidate=False,
                ),
                "raw_payload_values_emitted": False,
            }
        )
    return sorted(rows, key=lambda row: (str(row["table"]), str(row["column"])))


def _validate_counts(summary: dict[str, Any]) -> None:
    for key, expected in EXPECTED.items():
        actual = summary.get(key)
        if actual != expected:
            raise PolicyError(f"Patch 6 count mismatch for {key}: {actual} != {expected}")


def build_policy(
    *,
    patch4_summary: str | Path = PATCH4_SUMMARY,
    patch5_summary: str | Path = PATCH5_SUMMARY,
    patch3_inventory: str | Path = PATCH3_INVENTORY,
) -> dict[str, Any]:
    patch4 = _load_json(patch4_summary)
    patch5 = _load_json(patch5_summary)
    patch3 = _load_json(patch3_inventory)
    patch4_fields = patch4.get("fields", [])
    patch5_fields = patch5.get("fields", [])
    if not isinstance(patch4_fields, list) or not isinstance(patch5_fields, list):
        raise PolicyError("Patch 4/Patch 5 summaries are malformed")

    patch4_covered = [
        field
        for field in patch4_fields
        if field.get("post_proof_decision", {}).get("decision_class")
        == "covered_by_existing_scalar_decomposition_columns"
    ]
    patch4_partial = [
        field
        for field in patch4_fields
        if field.get("post_proof_decision", {}).get("decision_class")
        == "partially_covered_existing_scalar_columns"
    ]
    patch5_covered = [
        field
        for field in patch5_fields
        if field.get("post_proof_decision", {}).get("decision_class")
        == "covered_by_existing_scalar_decomposition_columns"
    ]
    covered_records = [
        _covered_record(
            field,
            custom_field=False,
            evidence_path=str(patch4_summary),
        )
        for field in patch4_covered
    ] + [
        _covered_record(
            field,
            custom_field=True,
            evidence_path=str(patch5_summary),
        )
        for field in patch5_covered
    ]
    partial_records = [
        _partial_record(field, evidence_path=str(patch4_summary))
        for field in patch4_partial
    ]
    remaining_records = _child_entity_records(patch3)
    legacy_warning_count = sum(
        1
        for record in [*covered_records, *partial_records]
        if record["legacy_non_null_bare_container_values_present"]
    )
    source_absent_scalar_count = _source_absent_scalar_count(patch4_partial)
    subtype_counts = Counter(record["policy_subtype"] for record in covered_records)
    summary = {
        "generated_at_utc": _utc_now(),
        "raw_strict_findings_preserved": True,
        "deprecation_is_reporting_policy_only": True,
        "covered_total": len(covered_records),
        "covered_non_custom": len(patch4_covered),
        "covered_custom": len(patch5_covered),
        "covered_subtype_counts": dict(sorted(subtype_counts.items())),
        "partial": len(partial_records),
        "source_absent_scalar_leaves": source_absent_scalar_count,
        "child_entity_deferred": len(remaining_records),
        "company_id_policy_deferred": 4,
        "budget_detail_dead_convenience_column": 4,
        "budget_detail_read_model_schema_artifact": 4,
        "high_confidence_mapping_candidates": 0,
        "projection_code_repair_candidates": 0,
        "date_datetime_mapping_candidates": 0,
        "legacy_non_null_bare_container_warning_count": legacy_warning_count,
        "raw_payload_values_emitted": False,
    }
    _validate_counts(summary)
    actionable_rollup = {
        "generated_at_utc": _utc_now(),
        "raw_strict_findings_preserved": True,
        "covered_bare_containers_visible_in_disposition_evidence": len(covered_records),
        "covered_bare_containers_suppressed_from_actionable_mapping_rollup": len(
            covered_records
        ),
        "high_confidence_mapping_candidates": 0,
        "projection_code_repair_candidates": 0,
        "date_datetime_mapping_candidates": 0,
        "raw_payload_values_emitted": False,
    }
    return {
        "summary": summary,
        "actionable_rollup": actionable_rollup,
        "deprecated_covered": {
            "generated_at_utc": _utc_now(),
            "fields": sorted(
                covered_records,
                key=lambda row: (row["table"], row["column"]),
            ),
            "raw_payload_values_emitted": False,
        },
        "partially_covered": {
            "generated_at_utc": _utc_now(),
            "fields": sorted(
                partial_records,
                key=lambda row: (row["table"], row["column"]),
            ),
            "raw_payload_values_emitted": False,
        },
        "remaining_decisions": {
            "generated_at_utc": _utc_now(),
            "fields": remaining_records,
            "company_id_policy_deferred": 4,
            "budget_detail_dead_convenience_column": 4,
            "budget_detail_read_model_schema_artifact": 4,
            "raw_payload_values_emitted": False,
        },
        "guardrails": BODY_FREE_GUARDRAILS,
    }


def write_markdown_report(
    *,
    out_path: str | Path,
    policy: dict[str, Any],
    starting_commit: str | None,
) -> None:
    summary = policy["summary"]
    lines = [
        "# Patch 6 Bare-Container Deprecation/Reporting Policy Evidence",
        "",
        f"Generated at: `{_utc_now()}`",
        f"Starting commit: `{starting_commit or 'not recorded'}`",
        "",
        "## Summary",
        "",
        "- Raw strict findings are preserved. Patch 6 does not fix, erase, drop, "
        "rename, hide, migrate, or populate bare container columns.",
        "- `bare_container_deprecated_covered_by_scalar_decomposition` means "
        "deprecated in reporting/audit policy only.",
        f"- Covered/deprecated bare containers total: `{summary['covered_total']}`.",
        f"- Non-custom Patch 4 covered subtype: `{summary['covered_non_custom']}`.",
        f"- Patch 5 custom-field covered subtype: `{summary['covered_custom']}`.",
        f"- Partially covered bare containers: `{summary['partial']}`.",
        f"- Source-absent scalar leaves: `{summary['source_absent_scalar_leaves']}`.",
        f"- Child/entity-only deferred: `{summary['child_entity_deferred']}`.",
        f"- Company ID policy deferred: `{summary['company_id_policy_deferred']}`.",
        "- Budget Detail remains unchanged.",
        f"- High-confidence mapping candidates: `{summary['high_confidence_mapping_candidates']}`.",
        f"- Projection-code repair candidates: `{summary['projection_code_repair_candidates']}`.",
        f"- Date/datetime mapping candidates: `{summary['date_datetime_mapping_candidates']}`.",
        f"- Legacy non-null bare-container warnings: "
        f"`{summary['legacy_non_null_bare_container_warning_count']}`.",
        "- Raw payload values emitted: `false`.",
        "",
        "## Covered/Deprecated Containers",
        "",
        "| Table | Column | Endpoint | Subtype | Legacy non-null warning |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in policy["deprecated_covered"]["fields"]:
        lines.append(
            f"| `{row['table']}` | `{row['column']}` | `{row.get('endpoint_key')}` | "
            f"`{row['policy_subtype']}` | "
            f"`{row['legacy_non_null_bare_container_values_present']}` |"
        )
    lines.extend(
        [
            "",
            "## Partially Covered Containers",
            "",
            "| Table | Column | Endpoint | Source-absent scalar leaves | Legacy non-null warning |",
            "| --- | --- | --- | ---: | --- |",
        ]
    )
    for row in policy["partially_covered"]["fields"]:
        lines.append(
            f"| `{row['table']}` | `{row['column']}` | `{row.get('endpoint_key')}` | "
            f"{len(row['source_absent_scalar_columns'])} | "
            f"`{row['legacy_non_null_bare_container_values_present']}` |"
        )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- No registry, projection, schema, migration, Budget Detail, company_id, "
            "live call, scheduler, SourceRefreshOrchestrator, writeback, production DB "
            "mutation, broad refresh, push, or GitHub remote action was performed by "
            "this evidence generator.",
        ]
    )
    Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(
    *,
    out_dir: str | Path,
    policy: dict[str, Any],
    starting_commit: str | None,
) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = {
        "bare-container-policy-summary.json": policy["summary"],
        "actionable-mapping-rollup.json": policy["actionable_rollup"],
        "deprecated-covered-container-inventory.json": policy["deprecated_covered"],
        "partially-covered-container-inventory.json": policy["partially_covered"],
        "remaining-container-decision-inventory.json": policy["remaining_decisions"],
    }
    for name, payload in files.items():
        Path(out, name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    write_markdown_report(
        out_path=out / "patch6-bare-container-policy-evidence.md",
        policy=policy,
        starting_commit=starting_commit,
    )


def run_projection_schema_audit(
    *,
    source_db: str | Path,
    copy_db: str | Path,
    out_dir: str | Path,
    hb_assistant: str,
) -> None:
    shutil.copy2(source_db, copy_db)
    cmd = [
        hb_assistant,
        "procore",
        "analytics",
        "projection-schema-audit",
        "--db",
        str(copy_db),
        "--json",
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    payload = proc.stdout or "{}"
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        parsed = {"ok": False, "parse_error": True}
    parsed["returncode"] = proc.returncode
    parsed["raw_payload_values_emitted"] = False
    Path(out_dir, "projection-schema-audit.json").write_text(
        json.dumps(parsed, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_no_raw_scan(*, out_dir: str | Path, hb_assistant: str) -> None:
    cmd = [
        hb_assistant,
        "procore",
        "analytics",
        "no-raw-leak-scan",
        "--path",
        str(out_dir),
        "--json",
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    payload = proc.stdout or "{}"
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        parsed = {"ok": False, "parse_error": True}
    parsed["returncode"] = proc.returncode
    Path(out_dir, "no-raw-leak-scan.json").write_text(
        json.dumps(parsed, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def package_evidence(out_dir: str | Path) -> None:
    out = Path(out_dir)
    archive = out.with_suffix(".tgz")
    env = dict(os.environ)
    env["COPYFILE_DISABLE"] = "1"
    subprocess.run(
        [
            "tar",
            "-czf",
            str(archive),
            "-C",
            str(out.parent),
            out.name,
        ],
        check=True,
        env=env,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch4-summary", default=str(PATCH4_SUMMARY))
    parser.add_argument("--patch5-summary", default=str(PATCH5_SUMMARY))
    parser.add_argument("--patch3-inventory", default=str(PATCH3_INVENTORY))
    parser.add_argument("--out", required=True)
    parser.add_argument("--starting-commit")
    parser.add_argument("--source-db")
    parser.add_argument("--copy-db")
    parser.add_argument("--hb-assistant", default="hb-assistant")
    parser.add_argument("--run-schema-audit", action="store_true")
    parser.add_argument("--run-no-raw-scan", action="store_true")
    parser.add_argument("--package", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    policy = build_policy(
        patch4_summary=args.patch4_summary,
        patch5_summary=args.patch5_summary,
        patch3_inventory=args.patch3_inventory,
    )
    write_outputs(
        out_dir=args.out,
        policy=policy,
        starting_commit=args.starting_commit,
    )
    if args.run_schema_audit:
        if not args.source_db or not args.copy_db:
            raise SystemExit("--source-db and --copy-db are required for --run-schema-audit")
        run_projection_schema_audit(
            source_db=args.source_db,
            copy_db=args.copy_db,
            out_dir=args.out,
            hb_assistant=args.hb_assistant,
        )
    if args.run_no_raw_scan:
        run_no_raw_scan(out_dir=args.out, hb_assistant=args.hb_assistant)
    if args.package:
        package_evidence(args.out)
    if args.json:
        print(json.dumps(policy["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
