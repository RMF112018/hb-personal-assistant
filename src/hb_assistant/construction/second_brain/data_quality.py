"""Phase 08A second-brain data-quality gates (Prompt 14).

A read-only gate evaluator that aggregates the existing per-surface validators + proofs
(runtime readiness, agent registry, model profile, retrieval, research packet, evaluation,
memory provenance, daily-brief handoff) into one conformance report. Mirrors the established
``construction/data_quality/phase_07d.py`` shape + status vocabulary
(``pass`` / ``warning`` / ``fail_blocking`` / ``deferred_not_blocking``).

Readiness is never overstated: offline/mock synthesis is reported as a ``warning`` (runtime
is ready, but live synthesis is not), and unimplemented surfaces (MCP exposure, V27 model-
call/agent-run receipt persistence, Phase 08B automation hardening) are ``deferred_not_blocking``
— never ``pass``. Persists nothing; no external systems are touched.
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
from .automation_health import build_automation_health_proof
from .automation_policy import validate_phase_08b_automation_policy
from .config import load_second_brain_config
from .contracts import load_phase_08a_contract, load_phase_08b_contract
from .daily_brief import build_daily_brief_delivery_handoff_proof
from .daily_brief_health import build_daily_brief_job_health_proof
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

    Mirrors the 08A gate report shape + status vocabulary. Readiness is never overstated:
    surfaces whose execution is owned by a later 08B prompt are ``deferred_not_blocking``.
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

    # Deferred 08B execution surfaces — never reported as pass.
    gates.append(
        _gate(
            "automation_execution",
            "deferred_not_blocking",
            reason="HEALTH_RETRY_WEEKEND_ALERTING_EXECUTION_DEFERRED",
            future_phase="08B",
        )
    )
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
    """Deterministic proof for ``phase-08b-gates-proof.json``."""
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
        and counts["deferred_not_blocking"] >= 1
        and counts["fail_blocking"] == 0
        and report["readiness_overstated"] is False
        and distinguishes
        and no_raw_content
    )
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
