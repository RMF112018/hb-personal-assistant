"""Phase 07D Prompt 12 — 07D data-quality gates (full 12-field conformance report).

Assembles the complete Phase 07D data-quality gate report keyed to the twelve
``phase_07d_data_quality_gates.json`` required fields:

- the five meeting-prep prerequisite gates already evaluated by ``gates.GateEvaluator`` (Prompt 05),
  reused here via ``evaluate_data_quality_gates`` (no duplication);
- four 07D output-coverage gates over the V25 read models (brief / issue-history / risk-digest /
  aging-exposure);
- ``obsidian_output_safety`` (guard-column scan of the obsidian-run audit table);
- ``stale_unknown_warning_coverage`` (stale/unknown warnings are being surfaced);
- ``no_writeback_no_secret_no_raw_content_proof`` (a 07D-scoped guard + forbidden-pattern scan over
  all ten V25 tables).

It also emits the four OneDrive/SharePoint **source-scope safe counts** (counts only — never folder
names, paths, web URLs, drive IDs, or item IDs), keeping explicit all-folders selection compliant.

Read-only; persists nothing. Coverage gates ``deferred_not_blocking`` on empty data (never overstated
as ``pass``); model/weak/sensitive remain review-required and are never auto-promoted.
"""

from __future__ import annotations

import contextlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from hb_assistant.construction.data_quality.gates import evaluate_data_quality_gates
from hb_assistant.construction.relationships.contracts import load_phase_07d_contract
from hb_assistant.construction.store.repositories import ConstructionStore
from hb_assistant.store.connection import get_connection
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

_GUARDRAILS: dict[str, Any] = {
    "external_systems": "read_only",
    "writeback": "none",
    "no_raw_content": True,
    "safe_counts_only": True,
    "candidates_promoted_as_authoritative": False,
    "advisory_only": True,
}

_STOP_CONDITIONS = [
    "coverage_gates_defer_not_pass_on_empty_data",
    "no_raw_folder_path_url_or_id_emitted",
    "no_writeback_no_secret_no_raw_content_scanned_over_v25",
    "model_weak_sensitive_never_auto_promoted",
]

# The five prerequisite gates already produced by the main GateEvaluator (Prompt 05).
_PREREQ_FIELDS = (
    "cross_source_relationship_candidate_coverage",
    "deterministic_relationship_quality",
    "evidence_trail_completeness",
    "weak_model_sensitive_review_routing_accuracy",
    "meeting_prep_prerequisite_status",
)

# (table, guard columns, safe text columns) for the 07D no-writeback / no-raw-content proof.
_V25_GUARDS = [
    "raw_email_body_persisted", "raw_document_text_persisted", "raw_calendar_payload_persisted",
    "raw_prompt_persisted", "raw_response_persisted", "signed_url_persisted",
    "download_url_persisted", "external_writeback_performed",
]
_V25_SCAN: list[tuple[str, list[str]]] = [
    ("cross_source_relationship_candidates", ["signals_json", "source_reference_json"]),
    ("cross_source_relationships", ["signals_json", "source_reference_json"]),
    ("source_evidence_trails", ["source_refs_json", "stale_unknown_flags_json"]),
    ("meeting_prep_brief_runs", []),
    ("meeting_prep_brief_sections", ["section_redacted", "stale_unknown_flags_json"]),
    ("project_issue_history_items", ["source_families_json", "stale_unknown_flags_json"]),
    ("project_risk_digest_items", ["summary_redacted", "stale_unknown_flags_json"]),
    ("aging_exposure_report_items", []),
    ("cross_source_intelligence_obsidian_runs", ["error_redacted"]),
    ("phase_07d_validation_runs", ["commands_json", "error_redacted"]),
]
_FORBIDDEN_PATTERNS = ["%http://%", "%https://%", "%token=%", "%access_token%", "%bearer %", "%-----begin%"]


def _table_exists(conn: Any, table: str) -> bool:
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        return row is not None
    except Exception:
        return False


def _scalar(conn: Any, sql: str, params: tuple = ()) -> int:
    try:
        row = conn.execute(sql, params).fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    except Exception:
        return 0


def _gate(name: str, status: str, *, blocking: int = 0, reason: Optional[str] = None,
          **extra: Any) -> dict[str, Any]:
    return {"gate_name": name, "gate_status": status, "blocking": blocking, "reason": reason,
            "future_phase": "07D", **extra}


def _coverage(name: str, count: int) -> dict[str, Any]:
    status = "pass" if count > 0 else "deferred_not_blocking"
    reason = None if count > 0 else "no_rows_yet_deferred_to_07D"
    return _gate(name, status, reason=reason, observed=count)


def evaluate_phase_07d_data_quality_gates(*, db_path: Optional[str | Path] = None) -> dict[str, Any]:
    """Evaluate the full Phase 07D data-quality gate set. Read-only; persists nothing."""
    generated = datetime.now(timezone.utc).isoformat()
    store = ConstructionStore(db_path=db_path)
    conn = get_connection(db_path)

    # 1. Reuse the five Prompt-05 prerequisite gates + readiness from the main evaluator.
    base = evaluate_data_quality_gates(db_path=db_path, persist=False)
    by_name = {g["gate_name"]: g for g in base["gates"]}
    meeting_prep_readiness = base["phase_go_nogo"]["07D"]["meeting_prep_readiness"]
    prereq_gates = [by_name[f] for f in _PREREQ_FIELDS if f in by_name]
    safe_counts = (by_name.get("meeting_prep_prerequisite_status") or {}).get(
        "source_scope_safe_counts"
    )

    # 2. Coverage gates over the V25 read models.
    brief_runs = 0
    issue_n = risk_n = aging_n = obsidian_n = 0
    with contextlib.suppress(Exception):
        brief_runs = store.count_meeting_prep_brief_runs()
        issue_n = store.count_project_issue_history_items()
        risk_n = store.count_project_risk_digest_items()
        aging_n = store.count_aging_exposure_report_items()
        obsidian_n = store.count_cross_source_intelligence_obsidian_runs()

    coverage_gates = [
        _coverage("meeting_prep_brief_generation_coverage", brief_runs),
        _coverage("issue_history_coverage", issue_n),
        _coverage("risk_digest_coverage", risk_n),
        _coverage("aging_report_coverage", aging_n),
    ]

    # 3. obsidian_output_safety — guard columns of the obsidian-run audit table all 0.
    if obsidian_n == 0:
        obsidian_gate = _gate("obsidian_output_safety", "deferred_not_blocking",
                              reason="no_obsidian_runs_yet")
    else:
        guard_sum = _scalar(
            conn,
            "SELECT " + " + ".join(f"COALESCE(SUM({g}),0)" for g in _V25_GUARDS)
            + " FROM cross_source_intelligence_obsidian_runs",
        )
        obsidian_gate = (
            _gate("obsidian_output_safety", "pass", observed_guard_sum=guard_sum)
            if guard_sum == 0
            else _gate("obsidian_output_safety", "fail_blocking", blocking=1,
                       reason="obsidian_guard_violation", observed_guard_sum=guard_sum)
        )

    # 4. stale_unknown_warning_coverage — stale/unknown warnings are surfaced where data exists.
    stale_signals = 0
    source_rows = issue_n + risk_n + aging_n
    with contextlib.suppress(Exception):
        stale_signals += _scalar(
            conn, "SELECT COUNT(*) FROM project_issue_history_items "
            "WHERE stale_unknown_flags_json IS NOT NULL")
        stale_signals += _scalar(
            conn, "SELECT COUNT(*) FROM project_risk_digest_items "
            "WHERE stale_unknown_flags_json IS NOT NULL")
        stale_signals += _scalar(
            conn, "SELECT COUNT(*) FROM aging_exposure_report_items "
            "WHERE missing_status_flag = 1 OR threshold_band = 'unknown'")
    if source_rows == 0:
        stale_gate = _gate("stale_unknown_warning_coverage", "deferred_not_blocking",
                           reason="no_source_rows_yet")
    else:
        stale_gate = _gate("stale_unknown_warning_coverage", "pass",
                           observed_stale_unknown_warnings=stale_signals)

    # 5. no_writeback_no_secret_no_raw_content_proof — 07D-scoped guard + pattern scan.
    guard_violations = 0
    pattern_hits = 0
    tables_scanned = 0
    for table, text_cols in _V25_SCAN:
        if not _table_exists(conn, table):
            continue
        tables_scanned += 1
        guard_violations += _scalar(
            conn,
            "SELECT " + " + ".join(f"COALESCE(SUM({g}),0)" for g in _V25_GUARDS) + f" FROM {table}",
        )
        for col in text_cols:
            where = " OR ".join(f"lower({col}) LIKE ?" for _ in _FORBIDDEN_PATTERNS)
            pattern_hits += _scalar(
                conn, f"SELECT COUNT(*) FROM {table} WHERE {where}", tuple(_FORBIDDEN_PATTERNS)
            )
    proof_passed = guard_violations == 0 and pattern_hits == 0
    proof_gate = (
        _gate("no_writeback_no_secret_no_raw_content_proof", "pass")
        if proof_passed
        else _gate("no_writeback_no_secret_no_raw_content_proof", "fail_blocking", blocking=1,
                   reason="guard_or_forbidden_pattern_violation")
    )

    gates = [*prereq_gates, *coverage_gates, obsidian_gate, stale_gate, proof_gate]
    by_field_status = {g["gate_name"]: g["gate_status"] for g in gates}
    coverage_names = (
        "meeting_prep_brief_generation_coverage", "issue_history_coverage", "risk_digest_coverage",
        "aging_report_coverage",
    )
    intelligence_ready = all(by_field_status.get(n) == "pass" for n in coverage_names)
    review_required_total = len(base.get("review_items") or [])
    ok = not any(g["gate_status"] == "fail_blocking" for g in gates)

    contract = load_phase_07d_contract("phase_07d_data_quality_gates")
    return {
        "command": "construction-agent data-quality phase-07d-gates",
        "ok": ok,
        "schema_version": LATEST_SCHEMA_VERSION,
        "contract_version": contract.get("version"),
        "generated_utc": generated,
        "gates": gates,
        "by_field_status": by_field_status,
        "required_fields_covered": sorted(by_field_status.keys())
        == sorted(contract.get("required_fields", [])),
        "source_scope_safe_counts": safe_counts,
        "no_writeback_proof": {
            "proof_passed": proof_passed,
            "guard_violations": guard_violations,
            "pattern_hits": pattern_hits,
            "tables_scanned": tables_scanned,
        },
        "meeting_prep_readiness": meeting_prep_readiness,
        "phase_07d_intelligence_ready": intelligence_ready,
        "review_required_total": review_required_total,
        "guardrails": _GUARDRAILS,
        "stop_conditions_checked": _STOP_CONDITIONS,
    }
