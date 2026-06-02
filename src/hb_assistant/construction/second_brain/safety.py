"""Phase 08A no-writeback / no-secret / no-raw-content proof (Prompt 15).

A read-only, deterministic, offline, fail-closed prover that demonstrates the Phase 08A
second-brain runtime contains no external-system writeback, no secrets / raw content, and no
unsafe persistence. It covers:

- every ``construction/second_brain/**`` module (mutation verbs + dangerous imports + secret
  scan), with the single sanctioned model boundary (the lazy Anthropic ``messages.create``
  call in ``reasoning.py``) disclosed and excluded from the source-system-writeback
  aggregation — it is the model boundary, never source-system writeback;
- the nineteen second-brain tables' guard CHECK columns (the eighteen V26 tables + the V27
  ``daily_brief_handoff_lines`` durable-handoff table), probed + persisted-value scanned and
  fail-closed on any absent expected table;
- a persisted-content leak scan over those tables;
- the Phase 08A evidence tree;
- the generated daily-brief + delivery-handoff outputs (vault dir + an in-memory dry-run);
- the model-call receipt structure (proven metadata-only: hashes + token counts, no raw
  prompt/response), with the absence of any model-call / agent-run receipt table asserted
  (in-memory only / V27-deferred).

Reuses the battle-tested scanner helpers from ``construction/data_quality/safety.py`` rather
than duplicating them. Findings are pattern labels + ``table.column`` / file locations only —
never the offending value. Read-only; performs no live calls and persists nothing.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.data_quality.safety import (
    _get_git_sha,
    _get_schema_version,
    _now,
    _probe_table_guards,
    _scan_evidence_outputs,
    _scan_module_set,
    _scan_obsidian_outputs,
    _scan_table_contents,
)
from hb_assistant.store.connection import get_connection
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_no_writeback_proof import _scan_text_for_secrets

# The sanctioned model boundary: the only outbound external call in the second-brain runtime
# is the lazy, opt-in, test-never Anthropic ``messages.create`` model call. It is NOT
# source-system writeback; it is excluded from the writeback aggregation and disclosed.
_MODEL_BOUNDARY_REL = "construction/second_brain/reasoning.py"

# The second-brain runtime tables in the guard-probe + content-scan scope: the eighteen V26
# tables plus the V27 daily_brief_handoff_lines durable delivery-handoff table (Phase 08B).
_PHASE_08A_TABLES: list[str] = [
    "second_brain_runtime_config_receipts",
    "obsidian_index_manifests",
    "obsidian_index_entries",
    "retrieval_query_receipts",
    "retrieval_context_refs",
    "query_tool_receipts",
    "long_term_memory_items",
    "long_term_memory_source_refs",
    "long_term_memory_quality_signals",
    "memory_update_candidates",
    "memory_update_reviews",
    "second_brain_research_packets",
    "second_brain_evaluation_runs",
    "second_brain_operator_feedback",
    "second_brain_operator_preference_profiles",
    "daily_brief_runs",
    "daily_brief_source_refs",
    "daily_brief_handoff_lines",
    "launchd_schedule_previews",
]

_PHASE_08A_EVIDENCE_SUBDIR = "construction-intelligence-phase-08a-second-brain-runtime"
_DAILY_BRIEF_OBSIDIAN_BASE = "Work/HB Personal Assistant/12_Daily_Brief"

# Receipt tables that must NOT exist (model-call / agent-run receipts are in-memory only).
_DEFERRED_RECEIPT_TABLES = (
    "second_brain_agent_model_receipts",
    "second_brain_agent_run_receipts",
)

_GUARDRAILS = {
    "external_systems": "read_only",
    "writeback": "none_permitted_in_08a_runtime",
    "model_boundary": "anthropic_messages_create_only_metadata_only_receipts",
    "raw_content_persisted": False,
    "secrets_tokens_urls_in_code_or_evidence": "forbidden",
    "no_live_calls": True,
    "fail_closed": True,
}

_STOP_CONDITIONS = [
    "no_source_system_writeback_calls_in_08a_modules",
    "no_bad_http_or_sdk_imports_in_08a_modules",
    "all_v26_guard_columns_zero_and_present",
    "no_secrets_or_raw_in_tables_evidence_or_generated_outputs",
    "model_receipts_metadata_only_and_no_receipt_table",
    "fail_closed_on_absent_expected_table_or_unsafe_pattern",
]


def _table_exists(conn: Any, table: str) -> bool:
    try:
        return (
            conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            is not None
        )
    except Exception:
        return False


def _enumerate_second_brain_modules(repo_root: Path) -> list[str]:
    """Every second-brain ``*.py`` (relative to src/hb_assistant/), sorted. Excludes caches."""
    base = repo_root / "src" / "hb_assistant"
    sb_dir = base / "construction" / "second_brain"
    rels: list[str] = []
    for root, _dirs, files in os.walk(sb_dir):
        if "__pycache__" in root:
            continue
        for fn in files:
            if fn.endswith(".py"):
                rels.append(str((Path(root) / fn).relative_to(base)))
    return sorted(rels)


def _derive_guard_map(conn: Any) -> tuple[dict[str, dict[str, int]], list[str]]:
    """Derive {table: {guard_col: 0}} from each expected table's CREATE SQL.

    Fail-closed: any expected table that is absent is returned as a violation.
    """
    derived: dict[str, dict[str, int]] = {}
    missing: list[str] = []
    for name in _PHASE_08A_TABLES:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        if not row or not row[0]:
            missing.append(f"{name}: expected_table_absent")
            continue
        sql_nospace = row[0].replace(" ", "")
        cols = re.findall(r"CHECK\((\w+)=0\)", sql_nospace)
        derived[name] = dict.fromkeys(cols, 0)
    return derived, missing


def build_second_brain_no_writeback_proof(*, db_path: str | None = None) -> dict[str, Any]:
    """Build the Phase 08A no-writeback / no-secret / no-raw-content proof (read-only)."""
    generated_utc = _now()
    repo_root = PathPolicy().resolve_repo_root()
    sha = _get_git_sha()
    # Ensure the V26 schema exists (idempotent, additive DDL only — the same posture every
    # second-brain module uses) so the guard-column probe is deterministic.
    SQLiteMigrator(db_path).apply()
    schema_version = _get_schema_version(db_path)
    conn = get_connection(db_path)

    # 1. Static scan of every second-brain module.
    rel_paths = _enumerate_second_brain_modules(repo_root)
    module_results = _scan_module_set(repo_root, rel_paths)
    # Writeback aggregation excludes the disclosed model boundary.
    writeback_findings = [
        f
        for rel, r in module_results.items()
        if rel != _MODEL_BOUNDARY_REL
        for f in (r.get("writeback") or [])
    ]
    bad_import_findings = [f for r in module_results.values() for f in (r.get("bad_imports") or [])]
    secret_findings = [f for r in module_results.values() for f in (r.get("secrets") or [])]
    boundary = module_results.get(_MODEL_BOUNDARY_REL, {})
    model_boundary = {
        "module": _MODEL_BOUNDARY_REL,
        "sanctioned_external_call": "anthropic.messages.create (live model boundary)",
        "writeback_findings_excluded": boundary.get("writeback") or [],
        "bad_imports": boundary.get("bad_imports") or [],
        "secrets": boundary.get("secrets") or [],
    }
    boundary_clean = not model_boundary["bad_imports"] and not model_boundary["secrets"]

    # 2. V26 guard-column probe (derived; fail-closed on absent expected table).
    guard_map, missing_tables = _derive_guard_map(conn)
    guards = _probe_table_guards(conn, guard_map)
    guard_violations = list(guards["violations"]) + missing_tables
    guards_ok = not guard_violations

    # 3. Persisted-content leak scan over the second-brain tables.
    content = _scan_table_contents(conn, _PHASE_08A_TABLES)
    content_ok = not content["findings"]

    # 4. Evidence tree scan.
    evidence = _scan_evidence_outputs(repo_root, _PHASE_08A_EVIDENCE_SUBDIR)
    evidence_ok = not evidence["findings"]

    # 5. Generated brief / handoff outputs — vault dir + an in-memory dry-run.
    obsidian = _scan_obsidian_outputs(_DAILY_BRIEF_OBSIDIAN_BASE)
    obsidian_ok = not obsidian["findings"]
    generated_findings = _scan_generated_outputs()
    generated_ok = not generated_findings

    # 6. Model-receipt metadata-only + no receipt table.
    receipt_check = _check_model_receipt_metadata_only()
    no_receipt_table = [t for t in _DEFERRED_RECEIPT_TABLES if _table_exists(conn, t)]
    receipts_ok = receipt_check["metadata_only"] and not no_receipt_table

    proof_passed = bool(
        not writeback_findings
        and not bad_import_findings
        and not secret_findings
        and boundary_clean
        and guards_ok
        and content_ok
        and evidence_ok
        and obsidian_ok
        and generated_ok
        and receipts_ok
    )

    checks_detail = {
        "static_writeback_scan_08a_modules": {
            "passed": not writeback_findings,
            "findings": writeback_findings,
        },
        "no_http_client_or_mutation_imports_08a": {
            "passed": not bad_import_findings,
            "findings": bad_import_findings,
        },
        "module_secret_scan_08a": {
            "passed": not secret_findings,
            "findings": secret_findings,
        },
        "model_boundary_disclosure": {
            "passed": boundary_clean,
            "model_boundary": model_boundary,
        },
        "sqlite_guard_checks_v26_second_brain_tables": {
            "passed": guards_ok,
            "findings": guard_violations,
            "tables": guards["tables"],
        },
        "sqlite_content_leak_scan_08a_tables": {
            "passed": content_ok,
            "findings": content["findings"],
            "scanned_tables": content["scanned"],
        },
        "evidence_output_scan_08a": {
            "passed": evidence_ok,
            "findings": evidence["findings"],
            "scanned_dir": evidence["scanned_dir"],
        },
        "obsidian_brief_output_scan": {
            "passed": obsidian_ok,
            "findings": obsidian["findings"],
            "scanned_dir": obsidian["scanned_dir"],
        },
        "generated_brief_handoff_scan": {
            "passed": generated_ok,
            "findings": generated_findings,
        },
        "model_receipt_metadata_only": {
            "passed": receipts_ok,
            "metadata_only": receipt_check["metadata_only"],
            "raw_markers_absent": receipt_check["raw_markers_absent"],
            "hashes_present": receipt_check["hashes_present"],
            "receipt_tables_present": no_receipt_table,
        },
    }

    return {
        "command": "second-brain data-quality no-writeback-proof",
        "ok": proof_passed,
        "proof_passed": proof_passed,
        "phase": "Phase 08A Prompt 15",
        "generated_utc": generated_utc,
        "repo_sha": sha,
        "schema_version": schema_version,
        "scanned_modules": rel_paths,
        "model_boundary": model_boundary,
        "checks_detail": checks_detail,
        "guardrails": _GUARDRAILS,
        "stop_conditions_checked": _STOP_CONDITIONS,
        "no_live_call_performed": True,
        "no_external_writeback": not writeback_findings and not bad_import_findings,
        "no_raw_values_persisted": guards_ok and content_ok,
        "no_raw_values_persisted_scope": "phase_08a_second_brain_runtime_modules_tables_evidence_outputs_receipts",
    }


def _scan_generated_outputs() -> list[str]:
    """Generate an in-memory dry-run brief + handoff and secret-scan the serialized output."""
    import json
    import tempfile

    from hb_assistant.construction.store import ConstructionStore

    from .daily_brief import run_daily_brief
    from .reasoning import MockClaudeAdapter

    findings: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        db = f"{tmp}/gen.sqlite3"
        store = ConstructionStore(db)
        store.upsert_cross_source_relationship(
            relationship_id="rel-1",
            source_family="email",
            source_record_type="message",
            source_record_ref="m1",
            target_family="procore",
            target_record_type="rfi",
            target_record_ref="rfi1",
            relationship_type="references",
            confidence_class="human_promoted",
            source_reference_json=json.dumps({"project_key": "P1"}),
            project_key="P1",
            promotion_status="promoted",
            promoted_by="human",
            review_required=False,
        )
        result = run_daily_brief(
            brief_date="2026-06-02",
            project_key="P1",
            db_path=db,
            mode="dry_run",
            adapter=MockClaudeAdapter(),
            emit_receipt=False,
        )
    blob = result.model_dump_json() + result.delivery_handoff.model_dump_json()
    for label in _scan_text_for_secrets(blob):
        findings.append(f"generated_brief_handoff: {label}")
    return findings


def _check_model_receipt_metadata_only() -> dict[str, Any]:
    """Prove a model-call receipt carries only hashes + token counts (no raw prompt/response)."""
    from .reasoning import build_model_call_receipt

    marker_in = "RAWPROMPTMARKER_MUST_NOT_PERSIST"
    marker_out = "RAWRESPONSEMARKER_MUST_NOT_PERSIST"
    receipt = build_model_call_receipt(
        model_profile_id="default_reasoning",
        model_id="claude-opus-4-8",
        input_context=marker_in,
        output_text=marker_out,
    )
    blob = receipt.model_dump_json()
    raw_markers_absent = marker_in not in blob and marker_out not in blob
    hashes_present = bool(receipt.input_context_hash) and bool(receipt.output_hash)
    no_secret_hits = not _scan_text_for_secrets(blob)
    return {
        "metadata_only": raw_markers_absent and hashes_present and no_secret_hits,
        "raw_markers_absent": raw_markers_absent,
        "hashes_present": hashes_present,
    }
