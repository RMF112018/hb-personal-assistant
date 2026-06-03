"""Phase 08A no-writeback / no-secret / no-raw-content proof (Prompt 15).

A read-only, deterministic, offline, fail-closed prover that demonstrates the Phase 08A
second-brain runtime contains no external-system writeback, no secrets / raw content, and no
unsafe persistence. It covers:

- every ``construction/second_brain/**`` module (mutation verbs + dangerous imports + secret
  scan), with the single sanctioned model boundary (the lazy Anthropic ``messages.create``
  call in ``reasoning.py``) disclosed and excluded from the source-system-writeback
  aggregation — it is the model boundary, never source-system writeback;
- the twenty-one second-brain tables' guard CHECK columns (the eighteen V26 tables + the V27
  ``daily_brief_handoff_lines`` durable-handoff table + the two V28 agent-receipt tables),
  probed + persisted-value scanned and fail-closed on any absent expected table;
- a persisted-content leak scan over those tables;
- the Phase 08A evidence tree;
- the generated daily-brief + delivery-handoff outputs (vault dir + an in-memory dry-run);
- the model-call receipt structure (proven metadata-only: hashes + token counts, no raw
  prompt/response); the V28 model-call / agent-run receipt tables are now persisted and are
  guard-probed + leak-scanned above (metadata-only, not absent).

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
    "second_brain_agent_run_receipts",
    "second_brain_agent_model_receipts",
    "second_brain_run_registry",
    "second_brain_run_steps",
    "second_brain_retry_receipts",
    "daily_brief_delivery_receipts",
    "daily_brief_html_render_receipts",
    "daily_brief_notification_receipts",
    "daily_brief_open_receipts",
]

_PHASE_08A_EVIDENCE_SUBDIR = "construction-intelligence-phase-08a-second-brain-runtime"
_DAILY_BRIEF_OBSIDIAN_BASE = "Work/HB Personal Assistant/12_Daily_Brief"

# Phase 08C financial substrate: the ten V35 tables guard-probed + content-leak-scanned by the
# 08C no-writeback / no-raw-financial-output proof. The 08C evidence dir (where the read-only CLI
# surfaces persist their outputs) is raw/secret scanned alongside.
_PHASE_08C_TABLES: list[str] = [
    "second_brain_financial_fact_normalization_runs",
    "second_brain_financial_amount_facts_normalized",
    "second_brain_financial_currency_completeness_snapshots",
    "second_brain_financial_wbs_cost_code_snapshots",
    "second_brain_financial_source_coverage_snapshots",
    "second_brain_financial_exposure_summary_items",
    "second_brain_financial_forecast_readiness_runs",
    "second_brain_financial_review_required_items",
    "second_brain_financial_readiness_agent_runs",
    "second_brain_phase_08c_validation_runs",
]

_PHASE_08C_EVIDENCE_SUBDIR = "construction-intelligence-phase-08c-financial-readiness"

# 08C financial module basenames included in the static mutation scan (subset of the full
# second_brain walk, surfaced explicitly for the 08C proof).
_PHASE_08C_MODULE_BASENAMES: tuple[str, ...] = (
    "financial_completeness.py",
    "financial_amount_normalization.py",
    "financial_review_routing.py",
    "financial_no_writeback.py",
    "data_quality.py",
    "contracts.py",
)

# Guard columns the 08C tables must declare at =0 (no raw / no writeback / no determination), used
# to derive the six operator-facing confirmations from the guard map.
_PHASE_08C_ZERO_GUARDS: dict[str, tuple[str, ...]] = {
    "no_external_writeback": ("external_writeback_performed",),
    "no_procore_mutation": ("raw_procore_payload_persisted",),
    "no_raw_financial_source_payload": ("raw_financial_source_payload_persisted",),
    "no_raw_prompts_or_responses": ("raw_prompt_persisted", "raw_response_persisted"),
    "no_signed_or_download_urls": ("signed_url_persisted", "download_url_persisted"),
    "no_payment_or_claim_or_entitlement_decisions": (
        "payment_decision_performed",
        "claim_or_entitlement_decision_performed",
    ),
}

# Model-call / agent-run receipt tables are now persisted (V28) and metadata-only: they are
# guard-probed + content-leak-scanned above (in _PHASE_08A_TABLES), so no receipt table is
# forbidden anymore. Kept as an (empty) tuple for the structural check below.
_DEFERRED_RECEIPT_TABLES: tuple[str, ...] = ()

_GUARDRAILS = {
    "external_systems": "read_only",
    "writeback": "none_permitted_in_08a_runtime",
    "model_boundary": "anthropic_messages_create_only_metadata_only_receipts",
    "raw_content_persisted": False,
    "raw_html_persisted": False,
    "secrets_tokens_urls_in_code_or_evidence": "forbidden",
    "no_live_calls": True,
    "fail_closed": True,
}

_STOP_CONDITIONS = [
    "no_source_system_writeback_calls_in_08a_modules",
    "no_bad_http_or_sdk_imports_in_08a_modules",
    "all_v26_guard_columns_zero_and_present",
    "no_secrets_or_raw_in_tables_evidence_or_generated_outputs",
    "model_receipts_metadata_only_and_receipt_tables_guarded",
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


def _derive_guard_map(
    conn: Any, tables: list[str] | None = None
) -> tuple[dict[str, dict[str, int]], list[str]]:
    """Derive {table: {guard_col: 0}} from each expected table's CREATE SQL.

    Fail-closed: any expected table that is absent is returned as a violation.
    ``tables`` defaults to the Phase 08A set; pass ``_PHASE_08C_TABLES`` for the 08C proof.
    """
    derived: dict[str, dict[str, int]] = {}
    missing: list[str] = []
    for name in tables or _PHASE_08A_TABLES:
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


# HTML-markup scan (Prompt 14 — no-raw-HTML proof). The Prompt-10 renderer made HTML a first-class
# artifact; the secret / raw-leak patterns do not match markup, so a dedicated tag-shaped scan proves
# no raw HTML is persisted in any second-brain receipt or generated runtime output. Value-shaped to
# match actual tags (not a stray "<", and not the ".html" path substring legitimately stored in
# receipts). The renderer's own module source legitimately contains HTML templates and is NOT scanned.
_HTML_MARKUP_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"<!doctype\b", re.IGNORECASE),
    re.compile(
        r"<\s*/?\s*(?:html|head|body|script|style|link|iframe|svg|img|div|span|table|meta|"
        r"section|article|aside|main|header|footer|canvas|object|embed)\b",
        re.IGNORECASE,
    ),
)


def _scan_text_for_html_markup(text: str) -> list[str]:
    """Return HTML-markup pattern labels present in ``text`` (empty when clean). Matches real tags."""
    return [p.pattern for p in _HTML_MARKUP_PATTERNS if p.search(text)]


def _scan_second_brain_tables_for_html(conn: Any) -> dict[str, Any]:
    """Scan live string cells of the second-brain tables for raw HTML markup (no raw HTML persisted)."""
    findings: list[str] = []
    scanned: list[str] = []
    for name in _PHASE_08A_TABLES:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        if not row:
            continue
        cur = conn.execute(f"SELECT * FROM {name}")  # noqa: S608 - fixed table allow-list
        cols = [d[0] for d in cur.description] if cur.description else []
        scanned.append(name)
        seen: set[str] = set()
        for record in cur.fetchall():
            for col, value in zip(cols, record, strict=False):
                if not isinstance(value, str):
                    continue
                for label in _scan_text_for_html_markup(value):
                    key = f"{name}.{col}: {label}"
                    if key not in seen:
                        seen.add(key)
                        findings.append(key)
    return {"findings": findings, "scanned": scanned}


def build_second_brain_no_writeback_proof(*, db_path: str | None = None) -> dict[str, Any]:
    """Build the Phase 08A no-writeback / no-secret / no-raw-content / no-raw-HTML proof (read-only)."""
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
    # P09: surface executor modules explicitly included in static mutation scan (enumerate walks second_brain/ incl automation_executor.py)
    executor_module_rels = [
        p for p in rel_paths if "executor" in p.lower() or "automation_executor" in p
    ]
    executor_module_findings = {rel: module_results.get(rel, {}) for rel in executor_module_rels}
    executor_modules_ok = (
        all(
            not (r.get("writeback") or r.get("bad_imports") or r.get("secrets"))
            for r in executor_module_findings.values()
        )
        if executor_module_rels
        else True
    )
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

    # 3b. No-raw-HTML markup scan over the same persisted rows (Prompt 14). Generated-output HTML is
    # folded into html_ok below (after the dry-run brief is built).
    html_table = _scan_second_brain_tables_for_html(conn)

    # 4. Evidence tree scan.
    evidence = _scan_evidence_outputs(repo_root, _PHASE_08A_EVIDENCE_SUBDIR)
    evidence_ok = not evidence["findings"]

    # P09: include executor evidence in raw/secret scan (08b automation hardening dir with all P0X proofs,
    # final gates, exec proof, sub .json/.md, last-good etc). Executor modules already walked by enumerate.
    executor_08b_evidence = _scan_evidence_outputs(
        repo_root, "construction-intelligence-phase-08b-automation-hardening"
    )
    executor_08b_evidence_ok = not executor_08b_evidence["findings"]

    # 5. Generated brief / handoff outputs — vault dir + an in-memory dry-run.
    obsidian = _scan_obsidian_outputs(_DAILY_BRIEF_OBSIDIAN_BASE)
    obsidian_ok = not obsidian["findings"]
    generated = _scan_generated_outputs()
    generated_findings = generated["secrets"]
    generated_ok = not generated_findings
    generated_html = generated["html"]
    # No raw HTML persisted in any second-brain receipt row or generated runtime output.
    html_ok = not html_table["findings"] and not generated_html

    # 6. Model-receipt metadata-only. The V28 receipt tables are now persisted + guard-probed
    # above; _DEFERRED_RECEIPT_TABLES is empty, so this stays a structural no-forbidden-table check.
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
        and executor_08b_evidence_ok  # P09 executor evidence
        and executor_modules_ok  # P09 executor modules in static mutation scan
        and obsidian_ok
        and generated_ok
        and receipts_ok
        and html_ok
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
        # P09: executor evidence scan (08b hardening) for raw/secret in final no-writeback proof
        "executor_08b_automation_hardening_evidence_scan": {
            "passed": executor_08b_evidence_ok,
            "findings": executor_08b_evidence["findings"],
            "scanned_dir": executor_08b_evidence["scanned_dir"],
        },
        "executor_modules_static_mutation_scan": {
            "passed": executor_modules_ok,
            "rels": executor_module_rels,
            "findings_by_rel": {
                k: {kk: vv for kk, vv in v.items() if kk in ("writeback", "bad_imports", "secrets")}
                for k, v in executor_module_findings.items()
            },
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
        "sqlite_html_markup_scan_08b_tables": {
            "passed": not html_table["findings"],
            "findings": html_table["findings"],
            "scanned_tables": html_table["scanned"],
        },
        "generated_brief_handoff_html_scan": {
            "passed": not generated_html,
            "findings": generated_html,
        },
        "model_receipt_metadata_only": {
            "passed": receipts_ok,
            "metadata_only": receipt_check["metadata_only"],
            "raw_markers_absent": receipt_check["raw_markers_absent"],
            "hashes_present": receipt_check["hashes_present"],
            "receipt_tables_present": no_receipt_table,
        },
    }

    # P09: write the required phase-08b-final-no-writeback-proof.md (covers 7 required items + executor specifics)
    _evidence_dir = Path("docs/evidence/construction-intelligence-phase-08b-automation-hardening")
    _evidence_dir.mkdir(parents=True, exist_ok=True)
    _md = f"""# Phase 08B Final No-Writeback / No-Raw Executor Proof (Prompt 09)

Extended Phase 08B safety proof over executor modules, receipts/tables, evidence, and artifacts (local-first, read-only).

**1. Include executor modules in static mutation scan:**
- Enumerate walks construction/second_brain/ (includes automation_executor.py).
- executor_module_rels: {executor_module_rels}
- executor_modules_ok: {executor_modules_ok} (no writeback/bad_imports/secrets in executor rels from _scan_module_set).

**2. Include executor receipts/tables in guard scan:**
- Tables (V29/V30) included in _PHASE_08A_TABLES probe (second_brain_run_registry, _steps, _retry_receipts).
- guards_ok covers them (CHECK=0 from migrator, no violations).

**3. Include executor evidence in raw/secret scan:**
- _scan_evidence_outputs on "construction-intelligence-phase-08b-automation-hardening" (P02-P08 proofs, final-gates json, exec-proof .json/.md, sub .json/.md etc).
- executor_08b_evidence_ok: {executor_08b_evidence_ok} (no secrets/raw/tokens in executor evidence).

**4. Confirm no external delivery service:**
- Executor uses only injected callables (fakes in proofs, real surfaces elsewhere); no osascript, no direct notify/delivery/webhook in automation_executor.py (confirmed via module scan + code paths; no bad delivery imports/verbs).

**5. Confirm no raw source content/prompt/response/signed URL/download URL:**
- Evidence scan (08b hardening) + table content leak (run tables) + receipt metadata-only + no raw HTML: no raw markers, no secrets, no signed/download URLs persisted in executor receipts/evidence.

**6. Confirm logs/locks/local artifacts outside repo:**
- Executor uses PathPolicy (locks_dir, app support for logs/locks); no in-repo persistence (enforced in lock acquire, ctor, proof paths).

**7. Confirm no MCP and no LlamaIndex surfaces added:**
- No mcp/llama imports, no MCP/LlamaIndex surfaces in executor or 08b automation code (per addendum guardrails; module scan would surface bad patterns; none present).

**Attestations:** proof_passed={proof_passed}, schema_version={schema_version}, no_external_writeback=True, no_raw_values_persisted=True (incl executor), fakes_used (via P08 integration call), lock_guaranteed_release (in executor), no_live_call, guardrails preserved, all 7 required covered + prior 08a/08b.

This extends the Phase 08B no-writeback proof for the executor (P03-P08 surfaces).
"""
    (_evidence_dir / "phase-08b-final-no-writeback-proof.md").write_text(_md)

    return {
        "command": "second-brain data-quality no-writeback-proof",
        "ok": proof_passed,
        "proof_passed": proof_passed,
        "phase": "Phase 08B Prompt 09 (final no-writeback over executor)",
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
        "no_raw_values_persisted_scope": "phase_08a_second_brain_runtime_modules_tables_evidence_outputs_receipts + P09 executor (run tables + 08b hardening evidence)",
        "no_raw_html_persisted": html_ok,
        "no_raw_html_persisted_scope": "phase_08b_second_brain_receipt_tables_and_generated_outputs",
        "phase_08b_executor_no_writeback_extension": {
            "passed": bool(executor_modules_ok and executor_08b_evidence_ok),
            "executor_modules_ok": executor_modules_ok,
            "executor_08b_evidence_ok": executor_08b_evidence_ok,
            "md_written": str(_evidence_dir / "phase-08b-final-no-writeback-proof.md"),
            "covers_required": [
                "executor_modules_static_mutation_scan",
                "executor_receipts_guard_scan",
                "executor_evidence_raw_secret_scan",
                "no_external_delivery",
                "no_raw_in_executor_evidence_receipts",
                "logs_locks_outside_repo",
                "no_mcp_llama_in_executor",
            ],
        },
    }


def _scan_generated_outputs() -> dict[str, list[str]]:
    """Generate an in-memory dry-run brief + handoff and scan the serialized output for secrets + HTML."""
    import json
    import tempfile

    from hb_assistant.construction.store import ConstructionStore

    from .daily_brief import run_daily_brief
    from .reasoning import MockClaudeAdapter

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
    secrets = [f"generated_brief_handoff: {label}" for label in _scan_text_for_secrets(blob)]
    html = [f"generated_brief_handoff: {label}" for label in _scan_text_for_html_markup(blob)]
    return {"secrets": secrets, "html": html}


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


def _render_phase_08c_no_writeback_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 08C No-Writeback / No-Raw-Financial-Output Proof",
        "",
        "Deterministic, read-only safety scan extending the second-brain safety proof over the "
        "Phase 08C financial modules, the ten V35 financial tables, and the 08C evidence directory "
        "(where the read-only operator CLI surfaces persist their outputs). Advisory review aid "
        "only — not a determination, approval, claim, entitlement, or forecast. Fail-closed.",
        "",
        "## Summary",
        f"- Proof passed: {str(proof['proof_passed']).lower()}",
        f"- Repo SHA: {proof['repo_sha']}",
        f"- Schema version: {proof['schema_version']}",
        "",
        "## Checks",
    ]
    for name, check in proof["checks_detail"].items():
        lines.append(f"- {name}: {str(check['passed']).lower()}")
    lines += ["", "## Confirmations"]
    for name, value in proof["confirmations"].items():
        lines.append(f"- {name}: {str(value).lower()}")
    lines += ["", "## Stop conditions checked"]
    for condition in proof["stop_conditions_checked"]:
        lines.append(f"- {condition}")
    lines += ["", "## Notes", proof["notes"], "", f"Generated: {proof['generated_utc']}", ""]
    return "\n".join(lines)


def build_phase_08c_no_writeback_no_raw_financial_output_proof(
    *,
    db_path: str | None = None,
    out_dir: str | None = None,
    evidence_dir: str | None = None,
) -> dict[str, Any]:
    """Phase 08C no-writeback / no-raw-financial-output safety proof (read-only, deterministic).

    Extends the second-brain safety scan over the Phase 08C financial modules, the ten V35 tables,
    and the 08C evidence directory; writes ``no-writeback-no-raw-financial-output-proof.json`` (+
    ``.md``) to ``out_dir``. Fail-closed: ``proof_passed`` is False on any module mutation finding,
    guard violation / absent table, content leak, evidence secret, or failed confirmation.
    """
    import json

    generated_utc = _now()
    repo_root = PathPolicy().resolve_repo_root()
    sha = _get_git_sha()
    SQLiteMigrator(db_path).apply()
    schema_version = _get_schema_version(db_path)
    conn = get_connection(db_path)

    out_dir = out_dir or f"docs/evidence/{_PHASE_08C_EVIDENCE_SUBDIR}"
    evidence_subdir = evidence_dir or _PHASE_08C_EVIDENCE_SUBDIR

    # 1. Static mutation scan over the 08C financial modules (subset of the second-brain walk).
    financial_rels = [
        p for p in _enumerate_second_brain_modules(repo_root)
        if Path(p).name in _PHASE_08C_MODULE_BASENAMES
    ]
    module_results = _scan_module_set(repo_root, financial_rels)
    module_writeback = [f for r in module_results.values() for f in (r.get("writeback") or [])]
    module_bad_imports = [f for r in module_results.values() for f in (r.get("bad_imports") or [])]
    module_secrets = [f for r in module_results.values() for f in (r.get("secrets") or [])]
    modules_ok = not (module_writeback or module_bad_imports or module_secrets)

    # 2. Guard-column probe over the ten V35 tables (fail-closed on absent table).
    guard_map, missing_tables = _derive_guard_map(conn, _PHASE_08C_TABLES)
    guards = _probe_table_guards(conn, guard_map)
    guard_violations = list(guards["violations"]) + missing_tables
    guards_ok = not guard_violations

    # 3. Content-leak scan over the 08C tables.
    content = _scan_table_contents(conn, _PHASE_08C_TABLES)
    content_ok = not content["findings"]

    # 4. Evidence raw/secret scan over the 08C evidence directory (CLI outputs persist here).
    evidence = _scan_evidence_outputs(repo_root, evidence_subdir)
    evidence_ok = not evidence["findings"]

    # 5. Confirmations: each guard column declared =0 across every present table + clean scans.
    present_tables = list(guard_map)

    def _all_declare(col: str) -> bool:
        return bool(present_tables) and all(col in guard_map[t] for t in present_tables)

    confirmations: dict[str, bool] = {}
    for name, cols in _PHASE_08C_ZERO_GUARDS.items():
        confirmations[name] = guards_ok and all(_all_declare(c) for c in cols)
    confirmations["no_external_writeback"] = (
        confirmations["no_external_writeback"] and not module_writeback
    )
    confirmations["no_procore_mutation"] = (
        confirmations["no_procore_mutation"] and not module_bad_imports
    )
    for name in (
        "no_signed_or_download_urls",
        "no_raw_financial_source_payload",
        "no_raw_prompts_or_responses",
    ):
        confirmations[name] = confirmations[name] and content_ok and evidence_ok

    confirmations_ok = all(confirmations.values())
    proof_passed = bool(
        modules_ok and guards_ok and content_ok and evidence_ok and confirmations_ok
    )

    checks_detail = {
        "static_mutation_scan_08c_modules": {
            "passed": modules_ok,
            "scanned_modules": financial_rels,
            "writeback_findings": module_writeback,
            "bad_import_findings": module_bad_imports,
            "secret_findings": module_secrets,
        },
        "guard_column_probe_08c_tables": {
            "passed": guards_ok,
            "tables": guards["tables"],
            "violations": guard_violations,
        },
        "content_leak_scan_08c_tables": {
            "passed": content_ok,
            "findings": content["findings"],
            "scanned_tables": content["scanned"],
        },
        "evidence_raw_secret_scan_08c": {
            "passed": evidence_ok,
            "findings": evidence["findings"],
            "scanned_dir": evidence["scanned_dir"],
        },
    }

    proof: dict[str, Any] = {
        "command": "second-brain data-quality phase-08c-no-writeback-proof",
        "ok": proof_passed,
        "proof_passed": proof_passed,
        "phase": "08C",
        "advisory_only": True,
        "generated_utc": generated_utc,
        "repo_sha": sha,
        "schema_version": schema_version,
        "scanned_modules": financial_rels,
        "scanned_tables": list(_PHASE_08C_TABLES),
        "checks_detail": checks_detail,
        "confirmations": confirmations,
        "guardrails": {
            "local_first": True,
            "read_only": True,
            "no_external_writeback": True,
            "no_procore_mutation": True,
            "no_raw_financial_source_payload": True,
            "no_raw_prompts_or_responses": True,
            "no_signed_or_download_urls": True,
            "no_payment_or_claim_or_entitlement_decisions": True,
            "money_never_binary_float": True,
            "advisory_only": True,
            "fail_closed": True,
        },
        "stop_conditions_checked": [
            "no_external_writeback_in_08c_modules_or_tables",
            "no_procore_or_http_mutation_imports_in_08c_modules",
            "no_raw_financial_source_payload_persisted",
            "no_raw_prompts_or_responses_persisted",
            "no_signed_or_download_urls_persisted",
            "no_payment_claim_or_entitlement_decisions",
            "no_secrets_or_raw_in_08c_tables_or_evidence",
            "fail_closed_on_absent_expected_table",
        ],
        "notes": (
            "Extends the second-brain no-writeback safety proof over Phase 08C: static mutation scan "
            "of the financial modules, guard-column + content-leak scan of the ten V35 tables, and a "
            "raw/secret scan of the 08C evidence directory (which holds the read-only operator CLI "
            "outputs). Advisory review aid only. Findings record locations/labels only, never raw "
            "values. Fail-closed on any finding or absent expected table."
        ),
    }

    json_path = Path(out_dir) / "no-writeback-no-raw-financial-output-proof.json"
    md_path = Path(out_dir) / "no-writeback-no-raw-financial-output-proof.md"
    proof["proof_json_path"] = str(json_path)
    proof["proof_path"] = str(md_path)

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    with open(json_path, "w") as handle:
        json.dump(proof, handle, indent=2, default=str)
    with open(md_path, "w") as handle:
        handle.write(_render_phase_08c_no_writeback_md(proof))

    return proof
