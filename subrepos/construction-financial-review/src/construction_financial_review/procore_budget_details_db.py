"""Read-only Procore Budget Detail Rows accessor and parity validation."""

from __future__ import annotations

import os
import sqlite3
from collections import OrderedDict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .common.io import read_json, read_jsonl

TARGET_CODE = "1000.15-01-426.MAT"
COMPARABLE_AMOUNT_FIELDS = (
    "revised_budget",
    "projected_budget",
    "committed_costs",
    "direct_costs",
    "erp_direct_costs",
    "erp_job_to_date_costs",
    "job_to_date_costs",
    "projected_costs",
    "forecast_to_complete",
    "estimated_cost_at_completion",
    "projected_over_under",
    "pending_budget_changes",
    "approved_change_orders",
)
TARGET_DIAGNOSTIC_FIELDS = (
    "revised_budget",
    "projected_budget",
    "committed_costs",
    "direct_costs",
    "erp_direct_costs",
    "erp_job_to_date_costs",
    "job_to_date_costs",
    "projected_costs",
    "forecast_to_complete",
    "estimated_cost_at_completion",
)
MISMATCH_CLASSES = (
    "decimal_format_only",
    "missing_vs_zero",
    "value_difference",
    "field_missing_in_db",
    "field_missing_in_package",
    "view_selection_difference",
)


def resolve_db_path(cfg: dict) -> Path:
    raw = (cfg.get("forecast_intelligence") or {}).get(
        "db_path",
        "~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite",
    )
    return Path(os.path.expanduser(raw))


def connect_read_only(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _context_package(cfg: dict, data_root: str | Path | None = None) -> Path:
    root = Path(data_root or cfg["default_data_root"])
    package = Path(cfg["forecast_context_package"])
    return package if package.is_absolute() else root / package


def _cells(conn: sqlite3.Connection, record_key: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT column_id, column_key, column_name, column_label, field_path,
               value_text, value_decimal_text, currency_iso_code
        FROM procore_ep_budget_detail_row_cells
        WHERE record_key = ?
        ORDER BY field_path
        """,
        (record_key,),
    ).fetchall()
    return [dict(row) for row in rows]


def lookup_budget_detail_rows(
    cfg: dict,
    *,
    project_key: str,
    canonical_budget_code_key: str | None = None,
    wbs_flat_code: str | None = None,
    cost_code_id: str | None = None,
    text_fallback: str | None = None,
    db_path: str | Path | None = None,
) -> list[OrderedDict]:
    """Return structured records from the endpoint-specific read model.

    The connection is opened with SQLite ``mode=ro``. Raw payload bodies are not
    selected or returned.
    """
    path = Path(db_path).expanduser() if db_path else resolve_db_path(cfg)
    clauses = ["project_key = ?"]
    params: list[Any] = [project_key]
    if canonical_budget_code_key:
        clauses.append("(canonical_budget_code_key = ? OR wbs_flat_code = ?)")
        params.extend([canonical_budget_code_key, canonical_budget_code_key])
    if wbs_flat_code:
        clauses.append("wbs_flat_code = ?")
        params.append(wbs_flat_code)
    if cost_code_id:
        clauses.append("cost_code_id = ?")
        params.append(cost_code_id)
    sql = (
        "SELECT record_key, raw_payload_id, budget_view_id, row_id, wbs_flat_code, "
        "canonical_budget_code_key, cost_code_id, cost_code, cost_type_id, cost_type, "
        "original_budget_amount, revised_budget, projected_budget, committed_costs, "
        "direct_costs, erp_direct_costs, actual_cost, job_to_date_costs, "
        "projected_costs, erp_job_to_date_costs, forecast_to_complete, "
        "estimated_cost_at_completion, projected_over_under, pending_budget_changes, "
        "approved_change_orders, "
        "payload_hash, source_quality, payload_seen_first_utc, payload_seen_last_utc "
        "FROM procore_ep_budget_detail_rows "
        f"WHERE {' AND '.join(clauses)} ORDER BY budget_view_id, record_key"
    )
    with connect_read_only(path) as conn:
        rows = [dict(row) for row in conn.execute(sql, tuple(params)).fetchall()]
        if text_fallback and not rows:
            rows = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT DISTINCT r.record_key, r.raw_payload_id, r.budget_view_id, r.row_id,
                           r.wbs_flat_code, r.canonical_budget_code_key, r.cost_code_id,
                           r.cost_code, r.cost_type_id, r.cost_type,
                           r.original_budget_amount, r.revised_budget, r.projected_budget,
                           r.committed_costs, r.direct_costs, r.erp_direct_costs,
                           r.actual_cost, r.job_to_date_costs, r.projected_costs,
                           r.erp_job_to_date_costs, r.forecast_to_complete,
                           r.estimated_cost_at_completion, r.projected_over_under,
                           r.pending_budget_changes, r.approved_change_orders,
                           r.payload_hash, r.source_quality, r.payload_seen_first_utc,
                           r.payload_seen_last_utc
                    FROM procore_ep_budget_detail_rows r
                    JOIN procore_ep_budget_detail_row_cells c
                      ON c.record_key = r.record_key
                    WHERE r.project_key = ? AND c.value_text LIKE ?
                    ORDER BY r.budget_view_id, r.record_key
                    """,
                    (project_key, f"%{text_fallback}%"),
                ).fetchall()
            ]
        out: list[OrderedDict] = []
        for row in rows:
            cells = _cells(conn, row["record_key"])
            out.append(
                OrderedDict(
                    [
                        ("record_key", row["record_key"]),
                        ("raw_payload_id", row["raw_payload_id"]),
                        ("budget_view_id", row["budget_view_id"]),
                        ("row_id", row["row_id"]),
                        ("wbs_flat_code", row["wbs_flat_code"]),
                        ("canonical_budget_code_key", row["canonical_budget_code_key"]),
                        ("cost_code_id", row["cost_code_id"]),
                        ("cost_code", row["cost_code"]),
                        ("cost_type_id", row["cost_type_id"]),
                        ("cost_type", row["cost_type"]),
                        (
                            "amounts",
                            OrderedDict(
                                [
                                    ("original_budget_amount", row["original_budget_amount"]),
                                    ("revised_budget", row["revised_budget"]),
                                    ("projected_budget", row["projected_budget"]),
                                    ("committed_costs", row["committed_costs"]),
                                    ("direct_costs", row["direct_costs"]),
                                    ("erp_direct_costs", row["erp_direct_costs"]),
                                    ("actual_cost", row["actual_cost"]),
                                    ("job_to_date_costs", row["job_to_date_costs"]),
                                    ("projected_costs", row["projected_costs"]),
                                    ("erp_job_to_date_costs", row["erp_job_to_date_costs"]),
                                    ("forecast_to_complete", row["forecast_to_complete"]),
                                    (
                                        "estimated_cost_at_completion",
                                        row["estimated_cost_at_completion"],
                                    ),
                                    ("projected_over_under", row["projected_over_under"]),
                                    ("pending_budget_changes", row["pending_budget_changes"]),
                                    ("approved_change_orders", row["approved_change_orders"]),
                                ]
                            ),
                        ),
                        ("dynamic_cells", cells),
                        ("dynamic_cell_count", len(cells)),
                        ("source_quality", row["source_quality"]),
                        ("payload_hash", row["payload_hash"]),
                        ("payload_seen_first_utc", row["payload_seen_first_utc"]),
                        ("payload_seen_last_utc", row["payload_seen_last_utc"]),
                    ]
                )
            )
        return out


def parity_report(
    cfg: dict,
    *,
    project_key: str,
    data_root: str | Path | None = None,
    db_path: str | Path | None = None,
    target_code: str = TARGET_CODE,
) -> OrderedDict:
    context = _context_package(cfg, data_root)
    budget_codes_path = context / "canonical" / "budget_codes.jsonl"
    package_rows = list(read_jsonl(budget_codes_path))
    package_by_key = {row.get("budget_code_key"): row for row in package_rows if row.get("budget_code_key")}
    package_generated_at, package_generated_at_source = _package_generated_at(context)
    db_rows = lookup_budget_detail_rows(
        cfg, project_key=project_key, db_path=db_path, text_fallback=None
    )
    package_keys = set(package_by_key)
    rows_by_view = _rows_by_budget_view(db_rows)
    candidate_view_ids = sorted(rows_by_view)
    configured_view_ids = _configured_budget_view_ids(cfg)
    evaluations = {
        view_id: _evaluate_budget_view(
            view_id=view_id,
            package_by_key=package_by_key,
            db_rows=rows,
        )
        for view_id, rows in rows_by_view.items()
    }
    selected_view_id, selection_mode, tied_view_ids = _select_budget_view(
        candidate_view_ids=candidate_view_ids,
        configured_view_ids=configured_view_ids,
        evaluations=evaluations,
    )
    selected_eval = evaluations.get(selected_view_id) if selected_view_id else None
    selected_db_by_key = selected_eval["db_by_key"] if selected_eval else {}
    selected_db_keys = set(selected_db_by_key)
    selected_mismatches = selected_eval["amount_mismatches"] if selected_eval else []
    selected_class_counts = OrderedDict(
        selected_eval["mismatch_class_counts"] if selected_eval else _empty_mismatch_class_counts()
    )
    if selection_mode in {
        "ambiguous_best_match_no_configured_view",
        "configured_budget_view_ambiguous",
        "no_budget_view",
    }:
        selected_class_counts["view_selection_difference"] += 1
    best_match_view_id = tied_view_ids[0] if tied_view_ids else None
    best_match_mismatch_count = (
        evaluations[best_match_view_id]["amount_mismatch_count"] if best_match_view_id else None
    )
    all_candidate_class_counts = _sum_mismatch_class_counts(
        [evaluations[vid]["mismatch_class_counts"] for vid in candidate_view_ids]
    )
    recommended_configured_budget_view_id = best_match_view_id if len(tied_view_ids) == 1 else None
    recommended_configured_budget_view_ids = tied_view_ids if len(tied_view_ids) > 1 else []
    included_classes = [
        "missing_vs_zero",
        "value_difference",
        "field_missing_in_db",
        "field_missing_in_package",
    ]
    excluded_classes = ["decimal_format_only", "view_selection_difference"]
    amount_count_from_classes = sum(int(selected_class_counts[key]) for key in included_classes)
    amount_mismatch_count_reconciles = amount_count_from_classes == len(selected_mismatches)
    db_seen_last_max = max(
        (
            row.get("payload_seen_last_utc")
            for row in selected_db_by_key.values()
            if row.get("payload_seen_last_utc")
        ),
        default=None,
    )
    temporal_warning, temporal_classification = _temporal_lineage(
        package_generated_at, db_seen_last_max
    )
    potentially_temporal_value_difference_count = (
        int(selected_class_counts["value_difference"]) if temporal_warning else 0
    )
    target_rows = lookup_budget_detail_rows(
        cfg,
        project_key=project_key,
        canonical_budget_code_key=target_code,
        text_fallback=target_code,
        db_path=db_path,
    )
    target_selected_rows = [
        row for row in target_rows if selected_view_id is not None and row["budget_view_id"] == selected_view_id
    ]
    target_presence = _target_amount_presence(target_selected_rows)
    source_quality_issues = sorted(
        {
            key
            for key, row in selected_db_by_key.items()
            if row.get("source_quality") != "live_full_payload"
        }
    )
    strict_ok = (
        bool(selected_eval)
        and selected_eval["coverage_complete"]
        and not source_quality_issues
        and len(tied_view_ids) == 1
        and selected_eval["amount_mismatch_count"] == 0
    )
    return OrderedDict(
        [
            ("project_key", project_key),
            ("context_package", str(context)),
            ("budget_codes_file", str(budget_codes_path)),
            ("package_budget_code_count", len(package_keys)),
            ("db_budget_code_count", len(selected_db_keys)),
            ("matched_budget_code_count", len(package_keys & selected_db_keys)),
            ("db_only_budget_codes", sorted(selected_db_keys - package_keys)[:100]),
            ("package_only_budget_codes", sorted(package_keys - selected_db_keys)[:100]),
            ("budget_view_selection_mode", selection_mode),
            ("selected_budget_view_id", selected_view_id),
            ("candidate_budget_view_ids", candidate_view_ids),
            ("mismatch_count_by_budget_view_id", OrderedDict((vid, evaluations[vid]["amount_mismatch_count"]) for vid in candidate_view_ids)),
            ("coverage_by_budget_view_id", OrderedDict((vid, evaluations[vid]["coverage"]) for vid in candidate_view_ids)),
            ("best_match_budget_view_id", best_match_view_id),
            ("best_match_amount_mismatch_count", best_match_mismatch_count),
            ("best_match_tied_budget_view_ids", tied_view_ids),
            ("recommended_configured_budget_view_id", recommended_configured_budget_view_id),
            ("recommended_configured_budget_view_ids", recommended_configured_budget_view_ids),
            ("amount_mismatch_count", len(selected_mismatches)),
            ("amount_mismatches", selected_mismatches[:100]),
            ("selected_view_mismatch_class_counts", selected_class_counts),
            ("mismatch_class_counts_all_candidate_views", all_candidate_class_counts),
            ("amount_mismatch_count_included_classes", included_classes),
            ("amount_mismatch_count_excluded_classes", excluded_classes),
            ("amount_mismatch_count_reconciles", amount_mismatch_count_reconciles),
            ("package_generated_at", package_generated_at),
            ("package_generated_at_source", package_generated_at_source),
            ("db_payload_seen_last_utc_max", db_seen_last_max),
            ("temporal_lineage_warning", temporal_warning),
            ("temporal_lineage_classification", temporal_classification),
            ("potentially_temporal_value_difference_count", potentially_temporal_value_difference_count),
            ("missing_erp_job_to_date_costs_count", _missing_count(selected_db_by_key, "erp_job_to_date_costs")),
            ("missing_erp_direct_costs_count", _missing_count(selected_db_by_key, "erp_direct_costs")),
            ("missing_job_to_date_costs_count", _missing_count(selected_db_by_key, "job_to_date_costs")),
            ("missing_pending_budget_changes_count", _missing_count(selected_db_by_key, "pending_budget_changes")),
            ("missing_approved_change_orders_count", _missing_count(selected_db_by_key, "approved_change_orders")),
            ("missing_projected_budget_values_count", _missing_count(selected_db_by_key, "projected_budget")),
            ("missing_projected_cost_values_count", _missing_count(selected_db_by_key, "projected_costs")),
            ("source_quality_issues", source_quality_issues),
            ("target_code", target_code),
            ("target_code_queryable", bool(target_rows)),
            ("target_code_budget_view_ids", sorted({row["budget_view_id"] for row in target_rows if row["budget_view_id"]})),
            ("target_code_selected_budget_view_id", selected_view_id),
            ("target_code_selected_view_queryable", bool(target_selected_rows)),
            ("target_code_selected_view_amount_presence", target_presence),
            ("target_code_dynamic_cell_count", sum(int(row["dynamic_cell_count"]) for row in target_rows)),
            ("raw_payload_body_emitted", False),
            ("strict_ok", strict_ok),
        ]
    )


def _missing_count(rows: dict[str, OrderedDict], field: str) -> int:
    return sum(1 for row in rows.values() if not (row.get("amounts") or {}).get(field))


def _rows_by_budget_view(rows: list[OrderedDict]) -> dict[str, list[OrderedDict]]:
    out: dict[str, list[OrderedDict]] = {}
    for row in rows:
        view_id = str(row.get("budget_view_id") or "")
        if not view_id:
            continue
        out.setdefault(view_id, []).append(row)
    return out


def _configured_budget_view_ids(cfg: dict) -> list[str]:
    candidates: list[Any] = []
    for container_key in ("procore", "budget_details", "forecast_intelligence"):
        container = cfg.get(container_key)
        if isinstance(container, dict):
            candidates.extend(
                [
                    container.get("budget_view_id"),
                    container.get("budget_detail_budget_view_id"),
                    container.get("budget_view_ids"),
                    container.get("budget_detail_budget_view_ids"),
                ]
            )
    candidates.extend(
        [
            cfg.get("budget_view_id"),
            cfg.get("budget_detail_budget_view_id"),
            cfg.get("budget_view_ids"),
            cfg.get("budget_detail_budget_view_ids"),
        ]
    )
    out: list[str] = []
    for value in candidates:
        if isinstance(value, list):
            out.extend(str(item) for item in value if item not in (None, ""))
        elif value not in (None, ""):
            out.append(str(value))
    return sorted(set(out))


def _select_budget_view(
    *,
    candidate_view_ids: list[str],
    configured_view_ids: list[str],
    evaluations: dict[str, OrderedDict],
) -> tuple[str | None, str, list[str]]:
    configured_available = [vid for vid in configured_view_ids if vid in evaluations]
    if len(configured_available) == 1:
        return configured_available[0], "configured_budget_view", [configured_available[0]]
    if len(configured_available) > 1:
        return configured_available[0], "configured_budget_view_ambiguous", configured_available
    if not candidate_view_ids:
        return None, "no_budget_view", []
    ranked = sorted(
        candidate_view_ids,
        key=lambda vid: (
            0 if evaluations[vid]["coverage_complete"] else 1,
            evaluations[vid]["amount_mismatch_count"],
            evaluations[vid]["coverage"]["package_only_count"],
            evaluations[vid]["coverage"]["db_only_count"],
            vid,
        ),
    )
    best = ranked[0]
    best_key = (
        0 if evaluations[best]["coverage_complete"] else 1,
        evaluations[best]["amount_mismatch_count"],
        evaluations[best]["coverage"]["package_only_count"],
        evaluations[best]["coverage"]["db_only_count"],
    )
    tied = [
        vid
        for vid in ranked
        if (
            0 if evaluations[vid]["coverage_complete"] else 1,
            evaluations[vid]["amount_mismatch_count"],
            evaluations[vid]["coverage"]["package_only_count"],
            evaluations[vid]["coverage"]["db_only_count"],
        )
        == best_key
    ]
    mode = "best_match_no_configured_view" if len(tied) == 1 else "ambiguous_best_match_no_configured_view"
    return best, mode, tied


def _evaluate_budget_view(
    *,
    view_id: str,
    package_by_key: dict[str, dict],
    db_rows: list[OrderedDict],
) -> OrderedDict:
    db_by_key = {
        row.get("canonical_budget_code_key") or row.get("wbs_flat_code"): row
        for row in db_rows
        if row.get("canonical_budget_code_key") or row.get("wbs_flat_code")
    }
    package_keys = set(package_by_key)
    db_keys = set(db_by_key)
    matched_keys = package_keys & db_keys
    mismatches: list[OrderedDict] = []
    class_counts = _empty_mismatch_class_counts()
    for key in sorted(matched_keys):
        pkg_amounts = package_by_key[key].get("amounts") or {}
        db_amounts = db_by_key[key].get("amounts") or {}
        for field in COMPARABLE_AMOUNT_FIELDS:
            mismatch = _compare_amount(
                budget_code_key=key,
                budget_view_id=view_id,
                field=field,
                package_value=pkg_amounts.get(field),
                db_value=db_amounts.get(field),
            )
            if mismatch is None:
                continue
            class_counts[mismatch["mismatch_class"]] += 1
            if mismatch["mismatch_class"] != "decimal_format_only":
                mismatches.append(mismatch)
    coverage = OrderedDict(
        [
            ("package_code_count", len(package_keys)),
            ("db_code_count", len(db_keys)),
            ("matched_code_count", len(matched_keys)),
            ("db_only_count", len(db_keys - package_keys)),
            ("package_only_count", len(package_keys - db_keys)),
            ("db_only_budget_codes", sorted(db_keys - package_keys)[:100]),
            ("package_only_budget_codes", sorted(package_keys - db_keys)[:100]),
        ]
    )
    return OrderedDict(
        [
            ("budget_view_id", view_id),
            ("db_by_key", db_by_key),
            ("coverage", coverage),
            ("coverage_complete", not (db_keys - package_keys) and not (package_keys - db_keys)),
            ("amount_mismatch_count", len(mismatches)),
            ("amount_mismatches", mismatches),
            ("mismatch_class_counts", class_counts),
        ]
    )


def _compare_amount(
    *,
    budget_code_key: str,
    budget_view_id: str,
    field: str,
    package_value: Any,
    db_value: Any,
) -> OrderedDict | None:
    package_missing = _is_missing(package_value)
    db_missing = _is_missing(db_value)
    if package_missing and db_missing:
        return None
    package_decimal = None if package_missing else _decimal_or_none(package_value)
    db_decimal = None if db_missing else _decimal_or_none(db_value)
    if package_missing or db_missing:
        non_missing_decimal = db_decimal if package_missing else package_decimal
        mismatch_class = (
            "missing_vs_zero"
            if non_missing_decimal is not None and non_missing_decimal == Decimal("0")
            else ("field_missing_in_package" if package_missing else "field_missing_in_db")
        )
        return _mismatch(
            budget_code_key=budget_code_key,
            budget_view_id=budget_view_id,
            field=field,
            mismatch_class=mismatch_class,
            package_decimal=package_decimal,
            db_decimal=db_decimal,
        )
    if package_decimal is not None and db_decimal is not None and package_decimal == db_decimal:
        if str(package_value) != str(db_value):
            return _mismatch(
                budget_code_key=budget_code_key,
                budget_view_id=budget_view_id,
                field=field,
                mismatch_class="decimal_format_only",
                package_decimal=package_decimal,
                db_decimal=db_decimal,
            )
        return None
    if package_decimal is not None and db_decimal is not None:
        package_hash_value = _canonical_decimal_text(package_decimal)
        db_hash_value = _canonical_decimal_text(db_decimal)
    else:
        package_hash_value = str(package_value)
        db_hash_value = str(db_value)
    return _mismatch(
        budget_code_key=budget_code_key,
        budget_view_id=budget_view_id,
        field=field,
        mismatch_class="value_difference",
        package_decimal=package_hash_value,
        db_decimal=db_hash_value,
    )


def _mismatch(
    *,
    budget_code_key: str,
    budget_view_id: str,
    field: str,
    mismatch_class: str,
    package_decimal: Any,
    db_decimal: Any,
) -> OrderedDict:
    return OrderedDict(
        [
            ("budget_code_key", budget_code_key),
            ("budget_view_id", budget_view_id),
            ("field", field),
            ("mismatch_class", mismatch_class),
            ("package_normalized_hash", _hash_text(_hashable_amount(package_decimal))),
            ("db_normalized_hash", _hash_text(_hashable_amount(db_decimal))),
        ]
    )


def _is_missing(value: Any) -> bool:
    return value is None or value == ""


def _decimal_or_none(value: Any) -> Decimal | None:
    if _is_missing(value):
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def _canonical_decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal("1")))
    return format(normalized, "f")


def _hashable_amount(value: Any) -> str:
    if value is None:
        return "<missing>"
    if isinstance(value, Decimal):
        return _canonical_decimal_text(value)
    return str(value)


def _empty_mismatch_class_counts() -> OrderedDict:
    return OrderedDict((key, 0) for key in MISMATCH_CLASSES)


def _target_amount_presence(rows: list[OrderedDict]) -> OrderedDict:
    return OrderedDict(
        (field, any((row.get("amounts") or {}).get(field) not in (None, "") for row in rows))
        for field in TARGET_DIAGNOSTIC_FIELDS
    )


def _sum_mismatch_class_counts(counts: list[OrderedDict]) -> OrderedDict:
    out = _empty_mismatch_class_counts()
    for item in counts:
        for key in MISMATCH_CLASSES:
            out[key] += int(item.get(key, 0))
    return out


def _package_generated_at(context: Path) -> tuple[str | None, str | None]:
    manifest = context / "manifest.json"
    if manifest.exists():
        try:
            payload = read_json(manifest)
        except (OSError, ValueError):
            payload = {}
        for key in ("generated_timestamp_local", "generated_at", "generated_timestamp"):
            value = payload.get(key)
            if value not in (None, ""):
                return str(value), f"manifest.{key}"
        stamp = payload.get("generated_stamp")
        if stamp not in (None, ""):
            return str(stamp), "manifest.generated_stamp"
    parsed = _timestamp_from_package_name(context.name)
    if parsed:
        return parsed, "package_name"
    return None, None


def _timestamp_from_package_name(name: str) -> str | None:
    import re

    match = re.search(r"(20\d{6})_(\d{6})", name)
    if not match:
        return None
    date_part, time_part = match.groups()
    return (
        f"{date_part[0:4]}-{date_part[4:6]}-{date_part[6:8]}T"
        f"{time_part[0:2]}:{time_part[2:4]}:{time_part[4:6]}"
    )


def _temporal_lineage(package_generated_at: str | None, db_seen_last_utc: str | None) -> tuple[bool, str]:
    package_dt = _parse_datetime(package_generated_at)
    db_dt = _parse_datetime(db_seen_last_utc)
    if package_dt is None or db_dt is None:
        if package_generated_at or db_seen_last_utc:
            return True, "temporal_lineage_partially_unknown"
        return False, "temporal_lineage_unknown"
    if package_dt.date() == db_dt.date():
        return False, "same_date"
    if package_dt < db_dt:
        return True, "package_older_than_live_db"
    return True, "package_newer_than_live_db"


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _hash_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


__all__ = ["TARGET_CODE", "lookup_budget_detail_rows", "parity_report", "resolve_db_path"]
