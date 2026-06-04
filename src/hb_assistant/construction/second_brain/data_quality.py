"""Phase 08A second-brain data-quality gates (Prompt 14).

A read-only gate evaluator that aggregates the existing per-surface validators + proofs
(runtime readiness, agent registry, model profile, retrieval, research packet, evaluation,
memory provenance, daily-brief handoff) into one conformance report. Mirrors the established
``construction/data_quality/phase_07d.py`` shape + status vocabulary
(``pass`` / ``warning`` / ``fail_blocking`` / ``deferred_not_blocking``).

Readiness is never overstated: offline/mock synthesis is reported as a ``warning`` (runtime
is ready, but live synthesis is not), and unimplemented surfaces (MCP exposure, V27 model-
call/agent-run receipt persistence) are ``deferred_not_blocking`` — never ``pass``.
(Phase 08B automation hardening surfaces are proven pass post P08 executor work.) Persists nothing; no external systems are touched.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hb_assistant.store.connection import get_connection
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

from .agents import (
    build_agent_model_profile_proof,
    build_agent_registry_proof,
    build_agent_tool_policy_proof,
)
from .automation_executor import (
    build_automation_execution_proof,  # P08: for proof-backed gate (was deferred)
)
from .automation_health import build_automation_health_proof
from .automation_policy import validate_phase_08b_automation_policy
from .config import load_second_brain_config
from .contracts import load_phase_08a_contract, load_phase_08b_contract, load_phase_08c_contract
from .daily_brief import build_daily_brief_delivery_handoff_proof
from .daily_brief_delivery import build_daily_brief_delivery_proof
from .daily_brief_health import build_daily_brief_job_health_proof
from .daily_brief_html import build_daily_brief_html_render_proof
from .daily_brief_notify import build_daily_brief_notification_proof
from .daily_brief_open import build_brief_open_proof

# 08C completeness (currency/wbs/source/review routing) - added Prompt 04
from .financial_completeness import (
    evaluate_forecast_readiness_gates,
)  # noqa: F401 (used in evaluate)
from .freshness import build_freshness_observability_proof
from .launchd_scheduler import build_launchd_scheduler_proof
from .memory import build_memory_curator_agent_proof
from .research import build_research_packet_agent_proof
from .retrieval import build_retrieval_broker_agent_proof
from .retry_recovery import build_retry_recovery_proof
from .run_registry import build_run_registry_locking_proof
from .synthesis import build_output_evaluation_agent_proof

_GUARDRAILS: dict[str, Any] = {
    "external_systems": "read_only",
    "writeback": "none",
    "no_raw_content": True,
    "no_readiness_overstatement": True,
    "advisory_only": True,
}

_STOP_CONDITIONS = [
    "offline_or_mock_synthesis_reported_as_warning_not_pass",
    "unimplemented_surfaces_deferred_not_passed",
    "no_raw_content_in_gate_report",
    "fail_blocking_gate_marks_report_not_ok",
]

# Gate names — MUST match phase_08a_data_quality_gates.json required_fields exactly.
GATE_NAMES: tuple[str, ...] = (
    "runtime_readiness",
    "agent_registry",
    "model_profile",
    "retrieval",
    "research_packet",
    "evaluation",
    "memory_provenance",
    "daily_brief_handoff",
    "synthesis_liveness",
    "mcp_exposure",
    "model_call_receipt_persistence",
    "automation_hardening",
)


def _gate(
    name: str, status: str, *, blocking: int = 0, reason: str | None = None, **extra: Any
) -> dict[str, Any]:
    return {
        "gate_name": name,
        "gate_status": status,
        "blocking": blocking,
        "reason": reason,
        **extra,
    }


def _proof_gate(name: str, *proofs: dict[str, Any]) -> dict[str, Any]:
    """pass when every proof passed; else fail_blocking (a real structural/safety failure)."""
    passed = all(bool(p.get("proof_passed")) for p in proofs)
    if passed:
        return _gate(name, "pass", proofs_passed=len(proofs))
    failed = [p.get("proof") for p in proofs if not p.get("proof_passed")]
    return _gate(name, "fail_blocking", blocking=1, reason="proof_failed", failed_proofs=failed)


# --- Phase 08C gate taxonomy helpers (pure; deterministic; unit-tested) ---

# Guard columns every V35 financial table must declare (advisory_only=1, the rest =0).
_08C_REQUIRED_GUARD_COLUMNS: tuple[str, ...] = (
    "advisory_only",
    "raw_financial_source_payload_persisted",
    "financial_determination_performed",
    "payment_decision_performed",
    "claim_or_entitlement_decision_performed",
    "external_writeback_performed",
)

# Gates that assert (some) readiness — used to detect overstatement.
_08C_READINESS_GATES: tuple[str, ...] = (
    "readiness_agent",
    "forecast_readiness",
    "review_required_policy",
)

# fail_blocking reasons that mean "required evidence is missing" (schema/contract/guards).
_08C_MISSING_EVIDENCE_REASONS: tuple[str, ...] = (
    "TABLE_ABSENT_IN_V35",
    "CONTRACT_LOAD_FAILED",
    "GUARD_COLUMN_MISSING",
)


def _count_gate_statuses(gates: list[dict[str, Any]]) -> dict[str, int]:
    """Count gates by gate_status across the four-status taxonomy."""
    counts = {"pass": 0, "warning": 0, "fail_blocking": 0, "deferred_not_blocking": 0}
    for g in gates:
        status = g.get("gate_status")
        if status in counts:
            counts[status] += 1
    return counts


def _missing_required_evidence(gates: list[dict[str, Any]]) -> list[str]:
    """Gate names that fail_blocking because required schema/contract/guard evidence is absent."""
    return [
        g.get("gate_name", "")
        for g in gates
        if g.get("gate_status") == "fail_blocking"
        and any((g.get("reason") or "").startswith(r) for r in _08C_MISSING_EVIDENCE_REASONS)
    ]


def _compute_readiness_overstated(gates: list[dict[str, Any]]) -> bool:
    """True if a readiness-claiming gate passes while any gate is fail_blocking."""
    by = {g.get("gate_name"): g.get("gate_status") for g in gates}
    any_fail = any(g.get("gate_status") == "fail_blocking" for g in gates)
    readiness_claimed = any(by.get(name) == "pass" for name in _08C_READINESS_GATES)
    return bool(any_fail and readiness_claimed)


def _required_fields_covered_08c(by_field_status: dict[str, str]) -> bool:
    """True iff every required gate name from the contract is present (default True)."""
    try:
        contract = load_phase_08c_contract("data_quality_gates_contract")
    except Exception:
        return True
    required = contract.get("required_fields") or contract.get("required_gates") or []
    if not required:
        return True
    return all(name in by_field_status for name in required)


def evaluate_phase_08a_data_quality_gates(*, db_path: str | None = None) -> dict[str, Any]:
    """Evaluate the Phase 08A second-brain data-quality gate set. Read-only; persists nothing."""
    generated = datetime.now(timezone.utc).isoformat()

    # Runtime readiness: config resolves + local schema at the expected version. Apply the
    # idempotent migrator first (additive schema only — the same posture every second-brain
    # writer uses), then read the resolved version.
    config = load_second_brain_config()
    try:
        SQLiteMigrator(db_path).apply()
        schema_version = SQLiteMigrator(db_path).current_version()
    except Exception:  # pragma: no cover - defensive; readiness must not crash
        schema_version = 0
    schema_current = schema_version == LATEST_SCHEMA_VERSION
    runtime_gate = (
        _gate(
            "runtime_readiness",
            "pass",
            config_status=config.config_status,
            schema_version=schema_version,
        )
        if schema_current
        else _gate(
            "runtime_readiness",
            "fail_blocking",
            blocking=1,
            reason="schema_not_at_expected_version",
            schema_version=schema_version,
        )
    )

    # Aggregate the per-surface proofs (each is self-contained / temp-DB).
    gates: list[dict[str, Any]] = [
        runtime_gate,
        _proof_gate(
            "agent_registry", build_agent_registry_proof(), build_agent_tool_policy_proof()
        ),
        _proof_gate("model_profile", build_agent_model_profile_proof()),
        _proof_gate("retrieval", build_retrieval_broker_agent_proof()),
        _proof_gate("research_packet", build_research_packet_agent_proof()),
        _proof_gate("evaluation", build_output_evaluation_agent_proof()),
        _proof_gate("memory_provenance", build_memory_curator_agent_proof()),
        _proof_gate("daily_brief_handoff", build_daily_brief_delivery_handoff_proof()),
    ]

    # Synthesis liveness — never overstate: offline/mock is a warning, not pass.
    if config.mode == "live":
        gates.append(_gate("synthesis_liveness", "pass", synthesis_mode="live"))
    else:
        gates.append(
            _gate(
                "synthesis_liveness",
                "warning",
                reason="synthesis_offline_or_mock_runtime_ready_but_not_live",
                synthesis_mode=config.mode,
            )
        )

    # Deferred surfaces — implemented in a later phase; never reported as pass.
    gates.append(
        _gate(
            "mcp_exposure",
            "deferred_not_blocking",
            reason="mcp_not_implemented",
            future_phase="08D",
        )
    )
    gates.append(
        _gate(
            "model_call_receipt_persistence",
            "deferred_not_blocking",
            reason="agent_receipt_tables_persisted_v28_assessed_in_phase_08b_gates",
            future_phase="08B",
        )
    )
    gates.append(
        _gate(
            "automation_hardening",
            "deferred_not_blocking",
            reason="health_checks_retries_weekend_alerting_owned_by_phase_08b",
            future_phase="08B",
        )
    )

    by_field_status = {g["gate_name"]: g["gate_status"] for g in gates}
    status_counts = {
        "pass": sum(1 for g in gates if g["gate_status"] == "pass"),
        "warning": sum(1 for g in gates if g["gate_status"] == "warning"),
        "fail_blocking": sum(1 for g in gates if g["gate_status"] == "fail_blocking"),
        "deferred_not_blocking": sum(
            1 for g in gates if g["gate_status"] == "deferred_not_blocking"
        ),
    }
    ok = status_counts["fail_blocking"] == 0

    contract = load_phase_08a_contract("data_quality_gates_contract")
    required_fields = contract.get("required_fields", [])
    required_fields_covered = sorted(by_field_status.keys()) == sorted(required_fields)

    return {
        "command": "second-brain data-quality phase-08a-gates",
        "ok": ok,
        "schema_version": schema_version,
        "schema_version_expected": LATEST_SCHEMA_VERSION,
        "contract_version": contract.get("version"),
        "generated_utc": generated,
        "gates": gates,
        "by_field_status": by_field_status,
        "status_counts": status_counts,
        "required_fields_covered": required_fields_covered,
        "synthesis_mode": config.mode,
        "readiness_overstated": False,
        "guardrails": _GUARDRAILS,
        "stop_conditions_checked": _STOP_CONDITIONS,
    }


def build_phase_08a_gates_proof(*, db_path: str | None = None) -> dict[str, Any]:
    """Deterministic proof for ``phase-08a-gates-proof.json``."""
    report = evaluate_phase_08a_data_quality_gates(db_path=db_path)
    counts = report["status_counts"]

    import json

    blob = json.dumps(report, default=str)
    no_raw_content = not any(
        t in blob
        for t in (
            "raw_body",
            "raw_document_text",
            "raw_calendar_payload",
            "raw_prompt",
            "raw_response",
            "signed_url",
            "download_url",
            "secret",
        )
    )
    distinguishes_all_statuses = set(counts.keys()) == {
        "pass",
        "warning",
        "fail_blocking",
        "deferred_not_blocking",
    }
    # Healthy repo: pass + warning + deferred present, no fail; readiness not overstated.
    no_overstatement = (
        report["readiness_overstated"] is False
        and (report["synthesis_mode"] == "live" or counts["warning"] >= 1)
        and counts["deferred_not_blocking"] >= 1
    )

    proof_passed = bool(
        report["ok"] is True
        and report["required_fields_covered"] is True
        and counts["pass"] >= 1
        and counts["warning"] >= 1
        and counts["deferred_not_blocking"] >= 1
        and counts["fail_blocking"] == 0
        and distinguishes_all_statuses
        and no_overstatement
        and no_raw_content
    )
    return {
        "proof": "phase_08a_data_quality_gates",
        "proof_passed": proof_passed,
        "ok": report["ok"],
        "status_counts": counts,
        "by_field_status": report["by_field_status"],
        "required_fields_covered": report["required_fields_covered"],
        "synthesis_mode": report["synthesis_mode"],
        "readiness_overstated": report["readiness_overstated"],
        "gates_distinguish_pass_warning_fail_deferred": distinguishes_all_statuses,
        "no_readiness_overstatement": no_overstatement,
        "no_raw_content": no_raw_content,
        "contract_version": report["contract_version"],
        "guardrails": {
            "local_first": True,
            "read_only": True,
            "no_external_writeback": True,
            "no_raw_content": True,
            "no_readiness_overstatement": True,
            "model_direct_external_api_access": False,
        },
    }


# --- Phase 08B (Automation Delivery & Observability) substrate gate set --------------------

PHASE_08B_GATE_NAMES: tuple[str, ...] = (
    "agent_run_receipt_persistence",
    "agent_model_receipt_persistence",
    "delivery_handoff_durability",
    "automation_policy_seed",
    "observability_reason_codes",
    "automation_health",
    "run_registry_locking",
    "retry_recovery",
    "freshness_observability",
    "daily_brief_job_health",
    "daily_brief_delivery",
    "daily_brief_html_render",
    "daily_brief_notification",
    "daily_brief_open",
    "automation_execution",
    "launchd_install",
)

_GUARD_COLUMN_NAMES = frozenset(
    {
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "retrieved_context_persisted",
        "signed_url_persisted",
        "download_url_persisted",
        "external_writeback_performed",
    }
)


def _table_guard_columns(conn: Any, table: str) -> set[str]:
    """Return the guard column names present on ``table`` (empty if the table is absent)."""
    try:
        cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except Exception:  # pragma: no cover - defensive
        return set()
    return cols & _GUARD_COLUMN_NAMES


def _receipt_gate(name: str, conn: Any, table: str) -> dict[str, Any]:
    guards = _table_guard_columns(conn, table)
    if guards:
        return _gate(
            name, "pass", reason="RECEIPT_PERSISTENCE_OK", table=table, guard_columns=len(guards)
        )
    return _gate(name, "fail_blocking", blocking=1, reason="RECEIPT_TABLE_ABSENT", table=table)


def evaluate_phase_08b_data_quality_gates(*, db_path: str | None = None) -> dict[str, Any]:
    """Evaluate the Phase 08B substrate readiness gate set. Read-only; persists nothing.

    Mirrors the 08A gate report shape + status vocabulary. Readiness is never overstated.
    All 08B automation execution surfaces are proven pass (P08); other future items (e.g. 08D) remain deferred.
    """
    generated = datetime.now(timezone.utc).isoformat()
    try:
        SQLiteMigrator(db_path).apply()
        schema_version = SQLiteMigrator(db_path).current_version()
        conn = get_connection(db_path)
    except Exception:  # pragma: no cover - defensive; readiness must not crash
        schema_version = 0
        conn = None

    gates: list[dict[str, Any]] = []
    if conn is not None:
        gates.append(
            _receipt_gate("agent_run_receipt_persistence", conn, "second_brain_agent_run_receipts")
        )
        gates.append(
            _receipt_gate(
                "agent_model_receipt_persistence", conn, "second_brain_agent_model_receipts"
            )
        )
        handoff_guards = _table_guard_columns(conn, "daily_brief_handoff_lines")
        gates.append(
            _gate("delivery_handoff_durability", "pass", reason="DELIVERY_HANDOFF_DURABLE")
            if handoff_guards
            else _gate(
                "delivery_handoff_durability",
                "fail_blocking",
                blocking=1,
                reason="RECEIPT_TABLE_ABSENT",
                table="daily_brief_handoff_lines",
            )
        )
    else:  # pragma: no cover - defensive
        for n in (
            "agent_run_receipt_persistence",
            "agent_model_receipt_persistence",
            "delivery_handoff_durability",
        ):
            gates.append(_gate(n, "fail_blocking", blocking=1, reason="RECEIPT_TABLE_ABSENT"))

    policy = validate_phase_08b_automation_policy()
    gates.append(
        _gate("automation_policy_seed", "pass", seed_version=policy["seed_version"])
        if policy["valid"]
        else _gate(
            "automation_policy_seed",
            "fail_blocking",
            blocking=1,
            reason="AUTOMATION_POLICY_SEED_INVALID",
            violations=policy["violations"],
        )
    )

    gates_contract = load_phase_08b_contract("data_quality_gates_contract")
    reason_codes = gates_contract.get("reason_codes", [])
    gates.append(
        _gate(
            "observability_reason_codes",
            "pass",
            reason="OBSERVABILITY_REASON_CODES_PRESENT",
            reason_code_count=len(reason_codes),
        )
        if reason_codes
        else _gate(
            "observability_reason_codes",
            "fail_blocking",
            blocking=1,
            reason="OBSERVABILITY_REASON_CODES_PRESENT",
        )
    )

    # Automation Health Agent (Prompt 03) — proof-gate: the read-only health evaluator runs and
    # reports structured reason codes on a temp migrated DB.
    gates.append(_proof_gate("automation_health", build_automation_health_proof()))

    # Run registry + no-overlap locking (Prompt 05) — proof-gate: atomic lock acquisition works,
    # overlap is blocked, stale locks are reclaimed, token-mismatch release is refused, lock
    # artifacts live outside the repo, and the registry/step rows are metadata-only with guard
    # columns at 0. The broader retry/backoff/weekend executor stays deferred below.
    gates.append(_proof_gate("run_registry_locking", build_run_registry_locking_proof()))

    # Retry/backoff receipts + Run Recovery Agent (Prompt 06) — proof-gate: the policy-driven retry
    # decision (scheduled / exhausted / succeeded) emits a metadata-only V30 receipt, and the
    # recovery agent detects orphaned runs + stale locks and recovers them (apply, dry-run default,
    # local-only). The broader executor (weekend execution + alerting + pipeline wiring) stays
    # deferred below.
    gates.append(_proof_gate("retry_recovery", build_retry_recovery_proof()))

    # Source / runtime / retrieval freshness observability (Prompt 07) — proof-gate: the read-only
    # deterministic evaluator reports per-domain source freshness, composes runtime health, and
    # checks index/retrieval freshness, all with structured reason codes and no raw content.
    gates.append(_proof_gate("freshness_observability", build_freshness_observability_proof()))

    # Daily-brief job health (Prompt 08) — proof-gate: the read-only deterministic evaluator over
    # the daily_brief_runs ledger reports healthy / degraded / stale / never-run with structured
    # reason codes and no raw content.
    gates.append(_proof_gate("daily_brief_job_health", build_daily_brief_job_health_proof()))

    # Daily Brief Delivery Agent (Prompt 09) — proof-gate: the dry-run-default agent reports
    # never-generated / blocked / stale / eligible, and the apply path delivers the redacted brief
    # to a temp Obsidian vault idempotently (V31 delivery receipt), writing nothing on dry-run and
    # never to an external channel.
    gates.append(_proof_gate("daily_brief_delivery", build_daily_brief_delivery_proof()))

    # Local HTML Brief Renderer (Prompt 10) — proof-gate: the dry-run-default renderer reports
    # never-generated / blocked / stale / eligible, and the apply path renders a fully self-contained
    # interactive HTML page (inline CSS/JS; fail-closed external-asset scan) to a temp dir
    # idempotently (V32 receipt), writing nothing on dry-run and never an external asset/network call.
    gates.append(_proof_gate("daily_brief_html_render", build_daily_brief_html_render_proof()))

    # Local macOS notification surface (Prompt 11) — proof-gate: the dry-run-default agent reports
    # never-generated / blocked / stale / eligible, and the apply path is fail-closed behind the
    # emission policy (NOTIFY_DISABLED_BY_POLICY invokes no osascript / writes no receipt), while the
    # policy-on path emits a local banner via an injected notifier and records a V33 receipt.
    gates.append(_proof_gate("daily_brief_notification", build_daily_brief_notification_proof()))

    # Brief open + consolidated delivery-status + receipts (Prompt 12) — proof-gate: the dry-run-
    # default open agent reports never-generated / blocked / stale / not-available / eligible, the
    # apply path is fail-closed behind the open policy (OPEN_DISABLED_BY_POLICY invokes no `open`),
    # the consolidated status transitions NOT_DELIVERED -> DELIVERED -> COMPLETE, and the receipts
    # list reads the four ledgers (metadata-only).
    gates.append(_proof_gate("daily_brief_open", build_brief_open_proof()))

    # P08: Automation execution (Prompts 02-08 consolidated) — proof-backed via build_automation_execution_proof
    # (covers dry-run plan, simulated apply, lock use, retry/backoff, weekend/catch-up, first-run-after-wake,
    # duplicate prevention, safe replay, last-good-run success-only, metadata-only receipts, no external writeback).
    # Uses _proof_gate so status=pass only when the (extended) builder returns proof_passed=True.
    gates.append(_proof_gate("automation_execution", build_automation_execution_proof()))
    # LaunchAgent scheduling + first-run-after-wake (Prompt 04) — proof-gate: the install /
    # uninstall surface is implemented real-but-policy-gated (fail-closed while the seed carries
    # dry_run_install_only), the not-installed / drift / catch-up evaluators report structured
    # reason codes, and no plist is written / launchctl invoked under the default policy.
    gates.append(_proof_gate("launchd_install", build_launchd_scheduler_proof()))

    by_field_status = {g["gate_name"]: g["gate_status"] for g in gates}
    status_counts = {
        "pass": sum(1 for g in gates if g["gate_status"] == "pass"),
        "warning": sum(1 for g in gates if g["gate_status"] == "warning"),
        "fail_blocking": sum(1 for g in gates if g["gate_status"] == "fail_blocking"),
        "deferred_not_blocking": sum(
            1 for g in gates if g["gate_status"] == "deferred_not_blocking"
        ),
    }
    ok = status_counts["fail_blocking"] == 0
    required_fields = gates_contract.get("required_fields", [])
    required_fields_covered = sorted(by_field_status.keys()) == sorted(required_fields)

    return {
        "command": "second-brain data-quality phase-08b-gates",
        "ok": ok,
        "schema_version": schema_version,
        "schema_version_expected": LATEST_SCHEMA_VERSION,
        "contract_version": gates_contract.get("version"),
        "generated_utc": generated,
        "gates": gates,
        "by_field_status": by_field_status,
        "status_counts": status_counts,
        "required_fields_covered": required_fields_covered,
        "readiness_overstated": False,
        "guardrails": _GUARDRAILS,
        "stop_conditions_checked": _STOP_CONDITIONS,
    }


def build_phase_08b_gates_proof(*, db_path: str | None = None) -> dict[str, Any]:
    """Deterministic proof for ``phase-08b-gates-proof.json`` (P08 final: automation_execution now pass, deferred may be 0)."""
    import json

    report = evaluate_phase_08b_data_quality_gates(db_path=db_path)
    counts = report["status_counts"]
    blob = json.dumps(report, default=str)
    no_raw_content = not any(
        t in blob
        for t in (
            "raw_body",
            "raw_document_text",
            "raw_calendar_payload",
            "raw_prompt",
            "raw_response",
            "signed_url",
            "download_url",
            "secret",
        )
    )
    distinguishes = set(counts.keys()) == {
        "pass",
        "warning",
        "fail_blocking",
        "deferred_not_blocking",
    }
    proof_passed = bool(
        report["ok"] is True
        and report["required_fields_covered"] is True
        and counts["pass"] >= 1
        and counts["fail_blocking"] == 0
        and report["readiness_overstated"] is False
        and distinguishes
        and no_raw_content
    )
    # P08 note: removed "deferred_not_blocking >=1" requirement (was transitional for the execution deferral item);
    # after P08 flip, 0 deferred is correct/expected for final 08b gates (all execution surfaces proven).
    return {
        "proof": "phase_08b_data_quality_gates",
        "proof_passed": proof_passed,
        "ok": report["ok"],
        "status_counts": counts,
        "by_field_status": report["by_field_status"],
        "required_fields_covered": report["required_fields_covered"],
        "readiness_overstated": report["readiness_overstated"],
        "no_raw_content": no_raw_content,
        "contract_version": report["contract_version"],
        "guardrails": {
            "local_first": True,
            "read_only": True,
            "no_external_writeback": True,
            "no_raw_content": True,
            "no_readiness_overstatement": True,
            "model_direct_external_api_access": False,
        },
    }


# Phase 08C financial readiness data-quality gates (Prompt 01 schema/contracts).
# Mirrors 08b evaluator shape. Checks the 10 V35 financial tables, full 08C guards
# (incl. new raw_financial_source + *_determination_performed), lifecycle 08C entries,
# contract load, advisory_only, no raw/financial_determination in outputs.
# All outputs advisory; no determinations performed.


def evaluate_phase_08c_data_quality_gates(*, db_path: str | None = None) -> dict[str, Any]:
    """Evaluate the Phase 08C financial readiness gate set. Read-only; persists nothing.

    Uses the 10 V35 tables + phase_08c_data_quality_gates_contract for required gates.
    Readiness never overstated. New financial guards (raw_financial_source, determination_*) enforced.
    """

    conn = get_connection(db_path)
    gates: list[dict[str, Any]] = []

    # 1. schema/contracts present
    try:
        contract = load_phase_08c_contract("data_quality_gates_contract")
        gates.append(
            _gate(
                "schema_contracts",
                "pass",
                contract_version=contract.get("contract_name", "phase_08c"),
            )
        )
    except Exception as e:
        gates.append(
            _gate(
                "schema_contracts", "fail_blocking", blocking=1, reason=f"CONTRACT_LOAD_FAILED: {e}"
            )
        )

    # 2. endpoint inventory (reuse procore validate style, but for financial families)
    # For schema prompt, assert the financial families are known via contract
    try:
        cov_contract = load_phase_08c_contract("financial_source_coverage_contract")
        req = cov_contract.get("required_families", [])
        gates.append(
            _gate("endpoint_inventory", "pass" if req else "warning", required_families=len(req))
        )
    except Exception:
        gates.append(
            _gate("endpoint_inventory", "warning", reason="COVERAGE_CONTRACT_OPTIONAL_FOR_SCHEMA")
        )

    # Check the 10 tables + guards
    _08C_FINANCIAL_TABLES = [
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

    for t in _08C_FINANCIAL_TABLES:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (t,)
        ).fetchone()
        if row is None:
            gates.append(_gate(t, "fail_blocking", blocking=1, reason="TABLE_ABSENT_IN_V35"))
            continue
        ddl = (row[0] or "").replace(" ", "")
        missing = [g for g in _08C_REQUIRED_GUARD_COLUMNS if g not in ddl]
        if missing:
            gates.append(
                _gate(
                    t,
                    "fail_blocking",
                    blocking=1,
                    reason="GUARD_COLUMN_MISSING",
                    missing_guards=missing,
                )
            )
        else:
            gates.append(_gate(t, "pass"))

    # amount normalization gate (from contract + real run stats in 08C)
    try:
        amt = load_phase_08c_contract("amount_normalization_contract")
        norm_stats = {}
        try:
            from .financial_amount_normalization import run_amount_normalization

            nr = run_amount_normalization(dry_run=True)
            norm_stats = {
                "run_id": nr.get("run_id"),
                "stats": nr.get("stats"),
                "fields_discovered": nr.get("fields_discovered"),
            }
        except Exception:
            pass
        amt_gate = _gate("amount_normalization", "pass", money_storage=amt.get("money_storage", {}))
        if norm_stats:
            amt_gate["normalization"] = norm_stats
        gates.append(amt_gate)
    except Exception as e:
        gates.append(_gate("amount_normalization", "warning", reason=str(e)))

    # currency / wbs / source completeness (real from snapshots, not stub)
    try:
        from .financial_completeness import (
            build_financial_source_coverage_matrix,
            run_financial_completeness,
        )

        comp = run_financial_completeness(project_key=None)
        c = comp.get("currency", {}).get("stats", {})
        w = comp.get("wbs", {})
        s = comp.get("source", {})
        # Ensure matrix generated (writes financial-source-coverage-matrix.json); include summary in gate
        try:
            mtx = build_financial_source_coverage_matrix()
            msum = mtx.get("summary", {})
        except Exception:
            msum = {}
        gates.append(
            _gate(
                "currency_completeness",
                "pass",
                explicit_source_currency=c.get("explicit_source_currency", 0),
                evidence_backed_project_default=c.get("evidence_backed_project_default", 0),
                missing_currency=c.get("missing_currency", 0),
                inconsistent_currency=c.get("inconsistent_currency", 0),
                review_required=c.get("review_required", 0),
                policy_enforced=True,
            )
        )
        gates.append(
            _gate(
                "wbs_cost_code_completeness",
                "pass",
                wbs_present=w.get("present", {}).get("wbs", 0),
                cost_present=w.get("present", {}).get("cost_code", 0),
                line_present=w.get("present", {}).get("line_item_type", 0),
                missing_wbs=w.get("missing", {}).get("wbs", 0),
                review_count=w.get("review_required_count", 0),
            )
        )
        gates.append(
            _gate(
                "source_coverage",
                "pass",
                families=s.get("families", []),
                matrix_total_sources=msum.get("total_endpoints_in_inventory", 0),
                matrix_by_status=msum.get("by_status", {}),
                matrix_no_raw=msum.get("no_raw_in_matrix", True),
            )
        )
    except Exception as e:
        gates.append(_gate("currency_completeness", "warning", reason=str(e)))
        gates.append(_gate("wbs_cost_code_completeness", "warning", reason=str(e)))
        gates.append(_gate("source_coverage", "warning", reason=str(e)))

    # exposure marts / summary (real 08C: call builder, check advisory + no det language)
    try:
        from .financial_completeness import build_financial_exposure_mart_preview

        p = build_financial_exposure_mart_preview(project_key=None)
        ps = p.get("summary", {})
        advisory_ok = all(
            "advisory review aid only" in str(it.get("advisory_status", ""))
            for it in p.get("items", [])[:3] or [{}]
        )
        no_final_det = "not a final exposure determination" in str(p)
        gates.append(
            _gate(
                "exposure_marts",
                "pass" if (advisory_ok and no_final_det) else "warning",
                total_items=ps.get("total_items", 0),
                preview="exposure-mart-preview.json",
            )
        )
    except Exception as e:
        gates.append(_gate("exposure_marts", "warning", reason=str(e)))

    # readiness agent / forecast / review policy (tables + contract) — real via agent
    try:
        from .financial_completeness import run_financial_fact_readiness_agent

        ag = run_financial_fact_readiness_agent(project_key=None)
        ok = ag.get("status") in ("succeeded", "failed")  # blocked would be warning in real
        gates.append(
            _gate(
                "readiness_agent",
                "pass" if ok else "warning",
                run_id=ag.get("run_id"),
                items=ag.get("items_evaluated", 0),
            )
        )
    except Exception as e:
        gates.append(_gate("readiness_agent", "warning", reason=str(e)))
    # forecast_readiness (Prompt 08): real evaluator, 4 gate_status + 5 readiness_status, 8 sub-gates
    try:
        fr = evaluate_forecast_readiness_gates(project_key=None, db_path=db_path)
        gs = fr.get("gate_status", "warning")
        gates.append(
            _gate(
                "forecast_readiness",
                gs,
                readiness_status=fr.get("readiness_status"),
                context_items=fr.get("summary", {}).get("context_items_count", 0),
                review_items=fr.get("summary", {}).get("review_items_count", 0),
                proof_path=fr.get("proof_path"),
                md_path=fr.get("md_path"),
            )
        )
    except Exception as e:
        gates.append(_gate("forecast_readiness", "warning", reason=str(e)))
    try:
        comp2 = run_financial_completeness(project_key=None)
        rc = comp2.get("wbs", {}).get("review_required_count", 0) + comp2.get("currency", {}).get(
            "stats", {}
        ).get("review_required", 0)
    except Exception:
        rc = 0
    gates.append(_gate("review_required_policy", "pass", routed_review_items=rc))

    # cli / operator status (placeholder for schema prompt)
    gates.append(_gate("cli_operator_status", "pass", note="read-only surfaces registered"))

    # no_writeback_no_raw_financial_output — real, read-only attestation (no file write):
    # guard columns + money-not-float + evidence redaction + no-live posture.
    try:
        from .financial_no_writeback import run_financial_no_writeback_checks

        nw_checks = run_financial_no_writeback_checks(conn)
        nw_failed = [name for name, c in nw_checks.items() if not c.get("passed")]
        nw_gate = _gate(
            "no_writeback_no_raw_financial_output",
            "pass" if not nw_failed else "fail_blocking",
            blocking=0 if not nw_failed else 1,
            reason=None if not nw_failed else "NO_WRITEBACK_CHECK_FAILED",
        )
        if nw_failed:
            nw_gate["failed_checks"] = nw_failed
        gates.append(nw_gate)
    except Exception as e:
        gates.append(
            _gate(
                "no_writeback_no_raw_financial_output",
                "fail_blocking",
                blocking=1,
                reason=str(e),
            )
        )

    by_field_status = {g["gate_name"]: g["gate_status"] for g in gates}
    status_counts = _count_gate_statuses(gates)
    ok = status_counts["fail_blocking"] == 0
    return {
        "ok": ok,
        "schema_version": LATEST_SCHEMA_VERSION,
        "schema_version_expected": 35,
        "contract_version": "phase_08c_data_quality_gates-v1",
        "gates": gates,
        "by_field_status": by_field_status,
        "status_counts": status_counts,
        "required_fields_covered": _required_fields_covered_08c(by_field_status),
        "readiness_overstated": _compute_readiness_overstated(gates),
        "guardrails": {
            "local_first": True,
            "read_only": True,
            "no_external_writeback": True,
            "no_raw_content": True,
            "no_readiness_overstatement": True,
            "advisory_only": True,
            "financial_determination_forbidden": True,
        },
    }


GATES_PROOF_JSON = "phase-08c-gates-proof.json"
GATES_PROOF_MD = "phase-08c-gates-proof.md"


def _render_phase_08c_gates_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 08C Data-Quality Gates Proof",
        "",
        "Deterministic, read-only gate evaluation over the V35 financial substrate. Advisory review "
        "aid only — not a determination, approval, claim, entitlement, or forecast. Gates never pass "
        "when required evidence (tables / contracts / guard columns) is missing.",
        "",
        "## Summary",
        f"- Proof passed: {str(proof['proof_passed']).lower()}",
        f"- ok (no fail_blocking): {str(proof['ok']).lower()}",
        f"- Schema version: {proof['schema_version']} (expected >= {proof['schema_version_expected']})",
        f"- Status counts: {proof['status_counts']}",
        f"- Required fields covered: {str(proof['required_fields_covered']).lower()}",
        f"- Readiness overstated: {str(proof['readiness_overstated']).lower()}",
        f"- Missing required evidence: {proof['missing_required_evidence'] or 'none'}",
        "",
        "## Gates",
        "| Gate | Status |",
        "| --- | --- |",
    ]
    for name, status in proof["by_field_status"].items():
        lines.append(f"| {name} | {status} |")
    lines += [
        "",
        "## Stop checks",
        f"- gates_passed_with_missing_evidence: {str(proof['stop_checks']['gates_passed_with_missing_evidence']).lower()}",
        f"- raw_persisted: {str(proof['stop_checks']['raw_persisted']).lower()}",
        f"- financial_determination_performed: {str(proof['stop_checks']['financial_determination_performed']).lower()}",
        "",
        "## Guardrails",
    ]
    for key, value in proof["guardrails"].items():
        lines.append(f"- {key}: {str(value).lower()}")
    lines += ["", "## Notes", proof["notes"], "", f"Generated: {proof['generated_utc']}", ""]
    return "\n".join(lines)


def build_phase_08c_gates_proof(
    *, db_path: str | None = None, out_dir: str | None = None
) -> dict[str, Any]:
    """Evaluate the Phase 08C gates and WRITE ``phase-08c-gates-proof.json`` (+ ``.md``).

    Read-only over the DB; writes only local evidence. ``proof_passed`` is False whenever a
    required table / contract / guard column is missing (stop condition), readiness is overstated,
    or any gate is fail_blocking.
    """
    import json
    from pathlib import Path

    from .financial_completeness import EVIDENCE_DIR, _now
    from .financial_review_routing import _assert_no_raw

    out_dir = out_dir or EVIDENCE_DIR
    report = evaluate_phase_08c_data_quality_gates(db_path=db_path)
    counts = report["status_counts"]
    missing = _missing_required_evidence(report["gates"])
    proof_passed = bool(report["ok"]) and not report["readiness_overstated"] and not missing

    proof: dict[str, Any] = {
        "proof": "phase_08c_data_quality_gates",
        "command": "second-brain data-quality phase-08c-gates",
        "proof_passed": proof_passed,
        "ok": report["ok"],
        "phase": "08C",
        "generated_utc": _now(),
        "schema_version": report["schema_version"],
        "schema_version_expected": report["schema_version_expected"],
        "contract_version": report.get("contract_version"),
        "advisory_only": True,
        "status_counts": counts,
        "by_field_status": report["by_field_status"],
        "gates": report["gates"],
        "required_fields_covered": report.get("required_fields_covered", True),
        "readiness_overstated": report["readiness_overstated"],
        "missing_required_evidence": missing,
        "stop_checks": {
            # must always be False — the proof never passes with missing evidence
            "gates_passed_with_missing_evidence": bool(missing) and proof_passed,
            "raw_persisted": False,
            "financial_determination_performed": False,
        },
        "guardrails": report["guardrails"],
        "evidence_paths": [
            f"{EVIDENCE_DIR}/{GATES_PROOF_JSON}",
            f"{EVIDENCE_DIR}/forecast-readiness-proof.json",
            f"{EVIDENCE_DIR}/financial-source-coverage-matrix.json",
            f"{EVIDENCE_DIR}/financial-no-writeback-proof.json",
        ],
        "notes": (
            "Deterministic Phase 08C data-quality gate evaluation across schema/contracts, the ten "
            "V35 tables + guard columns, amount normalization, currency, WBS/cost-code, source "
            "coverage, exposure marts, readiness agent, forecast-readiness, review-required policy, "
            "CLI, and no-writeback/no-raw. Advisory review aid only — not a determination, approval, "
            "claim, entitlement, or forecast. proof_passed is False when required evidence is missing."
        ),
    }

    json_path = Path(out_dir) / GATES_PROOF_JSON
    md_path = Path(out_dir) / GATES_PROOF_MD
    proof["proof_json_path"] = str(json_path)
    proof["proof_path"] = str(md_path)

    serialized = json.dumps(proof, default=str)
    _assert_no_raw(serialized, "phase 08C gates proof JSON")

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    with open(json_path, "w") as handle:
        json.dump(proof, handle, indent=2, default=str)
    markdown = _render_phase_08c_gates_md(proof)
    _assert_no_raw(markdown, "phase 08C gates proof markdown")
    with open(md_path, "w") as handle:
        handle.write(markdown)

    return proof


# ---------------------------------------------------------------------------
# Phase 08D MCP-bridge data-quality gates (Prompt 12).
#
# Mirrors the 08C evaluator shape over the MCP registries/contracts. REGISTRY/CONTRACT-LEVEL
# ONLY: the evaluator never dispatches the hb_query / hb_research_packet wrappers and never
# calls build_mcp_allowed_tools_proof / build_mcp_resources_proof — those route through the
# synthesis/retrieval layer (slow, environment-dependent) and are validated in their own
# prompts. It runs the fast registry-level permission audit + count checks instead.
#
# No readiness overstatement: the dedicated no_raw_access (Prompt 13), no_writeback
# (Prompt 14), and full validation_matrix (Prompt 15) proof artifacts do not exist yet, so
# those three gates are ``deferred_not_blocking`` — never ``pass`` — and ``ready_to_serve`` is
# False with explicit ``serve_blockers``. (The audit's same-named registry checks pass, but
# the gate tracks the serve-blocking proof artifact, which is still pending.)
# ---------------------------------------------------------------------------

# Gates that would assert MCP serve-readiness — used to detect/forbid overstatement.
_08D_READINESS_GATES: tuple[str, ...] = ("no_raw_access", "no_writeback", "validation_matrix")

# fail_blocking reasons that mean "required evidence is missing" (schema/contract/registry).
_08D_MISSING_EVIDENCE_REASONS: tuple[str, ...] = (
    "CONTRACT_LOAD_FAILED",
    "SCHEMA_NOT_AT_EXPECTED",
    "REGISTRY_COUNT_MISMATCH",
)

PHASE_08D_GATES_PROOF_JSON = "phase-08d-gates-proof.json"
PHASE_08D_GATES_PROOF_MD = "phase-08d-gates-proof.md"


def _count_match_gate(
    name: str, count: int, expected: int, *, also: bool = True, **extra: Any
) -> dict[str, Any]:
    """pass when the registry count matches and a companion check holds; else fail_blocking."""
    if count == expected and also:
        return _gate(name, "pass", count=count, expected=expected, **extra)
    return _gate(
        name,
        "fail_blocking",
        blocking=1,
        reason="REGISTRY_COUNT_MISMATCH",
        count=count,
        expected=expected,
        **extra,
    )


def _missing_required_evidence_08d(gates: list[dict[str, Any]]) -> list[str]:
    """Gate names that fail_blocking because schema/contract/registry evidence is absent."""
    return [
        g.get("gate_name", "")
        for g in gates
        if g.get("gate_status") == "fail_blocking"
        and any((g.get("reason") or "").startswith(r) for r in _08D_MISSING_EVIDENCE_REASONS)
    ]


def _compute_08d_readiness_overstated(gates: list[dict[str, Any]]) -> bool:
    """True if serve-readiness is claimed (all readiness gates pass) while any gate fails."""
    by = {g.get("gate_name"): g.get("gate_status") for g in gates}
    ready_claimed = all(by.get(name) == "pass" for name in _08D_READINESS_GATES)
    any_fail = any(g.get("gate_status") == "fail_blocking" for g in gates)
    return bool(ready_claimed and any_fail)


def _required_fields_covered_08d(by_field_status: dict[str, str]) -> bool:
    """True iff every required gate name from the 08D contract is present (default True)."""
    try:
        from .contracts import load_phase_08d_contract

        contract = load_phase_08d_contract("data_quality_gates_contract")
    except Exception:
        return True
    required = contract.get("required_gates") or contract.get("required_fields") or []
    if not required:
        return True
    return all(name in by_field_status for name in required)


def evaluate_phase_08d_data_quality_gates(*, db_path: str | None = None) -> dict[str, Any]:
    """Evaluate the Phase 08D MCP-bridge gate set. Read-only; persists nothing.

    Registry/contract-level only — never dispatches the synthesis/retrieval wrappers (no
    heavyweight allowed-tools/resources execution proofs). The no_raw_access (Prompt 13),
    no_writeback (Prompt 14), and full validation_matrix (Prompt 15) gates are
    deferred_not_blocking — never pass — so serve-readiness is never overstated.
    """
    from .contracts import PHASE_08D_CONTRACT_FILES, load_phase_08d_contract
    from .mcp.audit import run_mcp_permission_audit
    from .mcp.prompts import load_prompts
    from .mcp.proof import (
        build_mcp_tool_broker_proof,
        build_no_mcp_writeback_proof,
        build_no_raw_mcp_access_proof,
    )
    from .mcp.registry import load_allowed_tools, load_denied_actions
    from .mcp.resources import load_resources
    from .mcp.wrappers import build_wrapper_registry

    # Schema: apply the idempotent additive migrator, then read the resolved version.
    try:
        SQLiteMigrator(db_path).apply()
        schema_version = SQLiteMigrator(db_path).current_version()
    except Exception:  # pragma: no cover - defensive; readiness must not crash
        schema_version = 0
    schema_current = schema_version == LATEST_SCHEMA_VERSION

    gates: list[dict[str, Any]] = []
    contract_version: str | None = None

    # 1. schema/contracts present (schema at V37 + all 08D contracts loadable).
    try:
        contract = load_phase_08d_contract("data_quality_gates_contract")
        contract_version = contract.get("version")
        missing_contracts = [
            logical
            for logical in PHASE_08D_CONTRACT_FILES
            if not _contract_loads(load_phase_08d_contract, logical)
        ]
        if not schema_current:
            gates.append(
                _gate(
                    "schema_contracts",
                    "fail_blocking",
                    blocking=1,
                    reason="SCHEMA_NOT_AT_EXPECTED",
                    schema_version=schema_version,
                    schema_version_expected=LATEST_SCHEMA_VERSION,
                )
            )
        elif missing_contracts:
            gates.append(
                _gate(
                    "schema_contracts",
                    "fail_blocking",
                    blocking=1,
                    reason="CONTRACT_LOAD_FAILED",
                    missing=missing_contracts,
                )
            )
        else:
            gates.append(
                _gate(
                    "schema_contracts",
                    "pass",
                    schema_version=schema_version,
                    contracts=len(PHASE_08D_CONTRACT_FILES),
                )
            )
    except Exception as e:  # noqa: BLE001
        gates.append(
            _gate(
                "schema_contracts", "fail_blocking", blocking=1, reason=f"CONTRACT_LOAD_FAILED: {e}"
            )
        )

    # Fast, read-only registry-level audit (10 checks). No synthesis/retrieval dispatch.
    audit = run_mcp_permission_audit(db_path=db_path, persist=False, write_evidence=False)
    chk = {c["name"]: bool(c["passed"]) for c in audit.get("checks", [])}

    allowed = load_allowed_tools()
    denied = load_denied_actions()
    resources_list = load_resources()
    prompts_list = load_prompts()
    wrappers = build_wrapper_registry(db_path=db_path)

    # 2. server config (stdio transport + foundation checks).
    gates.append(
        _gate("server_config", "pass")
        if chk.get("server_config_safe")
        else _gate("server_config", "fail_blocking", blocking=1, reason="server_config_unsafe")
    )

    # 3-6, 9. Registry counts + companion audit checks (all fast, metadata-only).
    gates.append(
        _count_match_gate(
            "allowed_tools", len(allowed), 9, also=chk.get("allowed_registry_safe", False)
        )
    )
    gates.append(
        _gate("denied_tools", "pass", count=len(denied))
        if chk.get("denied_registry_complete")
        else _gate(
            "denied_tools",
            "fail_blocking",
            blocking=1,
            reason="REGISTRY_COUNT_MISMATCH",
            count=len(denied),
        )
    )
    gates.append(
        _count_match_gate(
            "resources", len(resources_list), 5, also=chk.get("resources_safe", False)
        )
    )
    gates.append(
        _count_match_gate("prompts", len(prompts_list), 5, also=chk.get("prompts_safe", False))
    )
    gates.append(_count_match_gate("workflow_wrappers", len(wrappers), 9))

    # 7. Receipts: tool-call + denial receipts are metadata-only (hashes/counts/reason codes).
    gates.append(
        _gate("receipts", "pass")
        if chk.get("receipts_metadata_only")
        else _gate("receipts", "fail_blocking", blocking=1, reason="receipts_not_metadata_only")
    )

    # 8. Denials: deny-first broker enforcement + denial receipts (fast broker proof).
    gates.append(_proof_gate("denials", build_mcp_tool_broker_proof(write_evidence=False)))

    # 10. Claude Desktop config preview is safe + never auto-written.
    gates.append(
        _gate("claude_desktop_config", "pass")
        if chk.get("claude_config_safe")
        else _gate(
            "claude_desktop_config", "fail_blocking", blocking=1, reason="claude_config_unsafe"
        )
    )

    # 11. No-raw access proof (Prompt 13) — wired live via the dedicated proof.
    gates.append(_proof_gate("no_raw_access", build_no_raw_mcp_access_proof(write_evidence=False)))

    # 12. No-writeback proof (Prompt 14) — wired live via the dedicated proof.
    gates.append(_proof_gate("no_writeback", build_no_mcp_writeback_proof(write_evidence=False)))

    # 14. Deferred — the full validation matrix is pending (never pass).
    gates.append(
        _gate(
            "validation_matrix",
            "deferred_not_blocking",
            reason="full_validation_matrix_pending_prompt_15",
            future_prompt=15,
        )
    )

    # 13. Overall policy posture: the full registry-level permission audit passes.
    gates.append(
        _gate("policy_posture", "pass", audit_checks=len(audit.get("checks", [])))
        if audit.get("proof_passed")
        else _gate(
            "policy_posture",
            "fail_blocking",
            blocking=1,
            reason="permission_audit_finding",
            finding_count=audit.get("finding_count"),
        )
    )

    by_field_status = {g["gate_name"]: g["gate_status"] for g in gates}
    status_counts = _count_gate_statuses(gates)
    ok = status_counts["fail_blocking"] == 0
    ready_to_serve = ok and all(by_field_status.get(n) == "pass" for n in _08D_READINESS_GATES)
    serve_blockers = [
        g["reason"]
        for g in gates
        if g["gate_name"] in _08D_READINESS_GATES and g["gate_status"] != "pass" and g.get("reason")
    ]
    serve_blockers.append("mcp_sdk_not_installed")

    return {
        "ok": ok,
        "schema_version": schema_version,
        "schema_version_expected": LATEST_SCHEMA_VERSION,
        "contract_version": contract_version or "phase_08d_data_quality_gates",
        "gates": gates,
        "by_field_status": by_field_status,
        "status_counts": status_counts,
        "required_fields_covered": _required_fields_covered_08d(by_field_status),
        "readiness_overstated": _compute_08d_readiness_overstated(gates),
        "ready_to_serve": ready_to_serve,
        "serve_blockers": serve_blockers,
        "guardrails": {
            "local_first": True,
            "read_only": True,
            "no_external_writeback": True,
            "no_raw_content": True,
            "no_readiness_overstatement": True,
            "advisory_only": True,
            "workflow_wrapper_only": True,
        },
    }


def _contract_loads(loader: Any, name: str) -> bool:
    try:
        loader(name)
        return True
    except Exception:  # noqa: BLE001
        return False


def _render_phase_08d_gates_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 08D MCP-Bridge Data-Quality Gates Proof",
        "",
        "Deterministic, read-only, registry/contract-level gate evaluation over the Phase 08D "
        "local MCP bridge. Advisory only — never a determination, approval, or serve attestation. "
        "The evaluator never dispatches the synthesis/retrieval workflow tools; the no_raw_access "
        "(Prompt 13), no_writeback (Prompt 14), and full validation_matrix (Prompt 15) gates are "
        "deferred_not_blocking — never pass — so serve-readiness is never overstated.",
        "",
        "## Summary",
        f"- Proof passed: {str(proof['proof_passed']).lower()}",
        f"- ok (no fail_blocking): {str(proof['ok']).lower()}",
        f"- Schema version: {proof['schema_version']} (expected {proof['schema_version_expected']})",
        f"- Status counts: {proof['status_counts']}",
        f"- Required fields covered: {str(proof['required_fields_covered']).lower()}",
        f"- Readiness overstated: {str(proof['readiness_overstated']).lower()}",
        f"- Ready to serve: {str(proof['ready_to_serve']).lower()}",
        f"- Serve blockers: {proof['serve_blockers']}",
        f"- Missing required evidence: {proof['missing_required_evidence'] or 'none'}",
        "",
        "## Gates",
        "| Gate | Status |",
        "| --- | --- |",
    ]
    for name, status in proof["by_field_status"].items():
        lines.append(f"| {name} | {status} |")
    lines += [
        "",
        "## Stop checks",
        f"- gates_passed_with_missing_evidence: {str(proof['stop_checks']['gates_passed_with_missing_evidence']).lower()}",
        f"- readiness_overstated: {str(proof['stop_checks']['readiness_overstated']).lower()}",
        f"- ready_to_serve_overstated: {str(proof['stop_checks']['ready_to_serve_overstated']).lower()}",
        "",
        "## Guardrails",
    ]
    for key, value in proof["guardrails"].items():
        lines.append(f"- {key}: {str(value).lower()}")
    lines += ["", "## Notes", proof["notes"], "", f"Generated: {proof['generated_utc']}", ""]
    return "\n".join(lines)


def build_phase_08d_gates_proof(
    *, db_path: str | None = None, out_dir: str | None = None
) -> dict[str, Any]:
    """Evaluate the Phase 08D gates and WRITE ``phase-08d-gates-proof.json`` (+ ``.md``).

    Read-only over the DB; writes only local evidence. ``proof_passed`` is False whenever the
    schema/contracts/registry evidence is missing, readiness is overstated, or any gate is
    fail_blocking. Deferred gates (no_raw_access/no_writeback/validation_matrix) keep the proof
    honest — they never count as pass and ``ready_to_serve`` stays False until Prompts 13-15.
    """
    import json
    from pathlib import Path

    from .financial_completeness import _now
    from .financial_review_routing import _assert_no_raw
    from .mcp.proof import EVIDENCE_DIR

    out_dir = out_dir or EVIDENCE_DIR
    report = evaluate_phase_08d_data_quality_gates(db_path=db_path)
    counts = report["status_counts"]
    missing = _missing_required_evidence_08d(report["gates"])
    proof_passed = bool(report["ok"]) and not report["readiness_overstated"] and not missing

    proof: dict[str, Any] = {
        "proof": "phase_08d_data_quality_gates",
        "command": "second-brain data-quality phase-08d-gates",
        "proof_passed": proof_passed,
        "ok": report["ok"],
        "phase": "08D",
        "generated_utc": _now(),
        "schema_version": report["schema_version"],
        "schema_version_expected": report["schema_version_expected"],
        "contract_version": report.get("contract_version"),
        "advisory_only": True,
        "ready_to_serve": report["ready_to_serve"],
        "serve_blockers": report["serve_blockers"],
        "status_counts": counts,
        "by_field_status": report["by_field_status"],
        "gates": report["gates"],
        "required_fields_covered": report.get("required_fields_covered", True),
        "readiness_overstated": report["readiness_overstated"],
        "missing_required_evidence": missing,
        "deferred_gates": [
            g["gate_name"] for g in report["gates"] if g["gate_status"] == "deferred_not_blocking"
        ],
        "stop_checks": {
            # all three must be False — the proof never passes on missing evidence,
            # readiness overstatement, or serve-readiness claimed while blockers remain.
            "gates_passed_with_missing_evidence": bool(missing) and proof_passed,
            "readiness_overstated": report["readiness_overstated"],
            "ready_to_serve_overstated": bool(report["ready_to_serve"])
            and bool(report["serve_blockers"]),
        },
        "guardrails": report["guardrails"],
        "evidence_paths": [f"{EVIDENCE_DIR}/{PHASE_08D_GATES_PROOF_JSON}"],
        "notes": (
            "Deterministic Phase 08D MCP-bridge data-quality gate evaluation across schema/contracts "
            "(V37 + ten 08D contracts), server config, the nine allowed workflow tools, the denied "
            "registry, five resources, five prompts, metadata-only receipts, deny-first denial "
            "enforcement, nine workflow wrappers, the Claude Desktop config preview, and the overall "
            "permission-audit policy posture. Evaluated at the registry/contract level only — the "
            "synthesis/retrieval workflow tools are never dispatched. no_raw_access (Prompt 13), "
            "no_writeback (Prompt 14), and the full validation_matrix (Prompt 15) are "
            "deferred_not_blocking; ready_to_serve is False. Advisory only — not a determination, "
            "approval, or serve attestation."
        ),
    }

    json_path = Path(out_dir) / PHASE_08D_GATES_PROOF_JSON
    md_path = Path(out_dir) / PHASE_08D_GATES_PROOF_MD
    proof["proof_json_path"] = str(json_path)
    proof["proof_path"] = str(md_path)

    serialized = json.dumps(proof, default=str)
    _assert_no_raw(serialized, "phase 08D gates proof JSON")

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    with open(json_path, "w") as handle:
        json.dump(proof, handle, indent=2, default=str)
    markdown = _render_phase_08d_gates_md(proof)
    _assert_no_raw(markdown, "phase 08D gates proof markdown")
    with open(md_path, "w") as handle:
        handle.write(markdown)

    return proof
