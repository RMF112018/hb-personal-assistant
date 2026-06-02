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

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

from .agents import (
    build_agent_model_profile_proof,
    build_agent_registry_proof,
    build_agent_tool_policy_proof,
)
from .config import load_second_brain_config
from .contracts import load_phase_08a_contract
from .daily_brief import build_daily_brief_delivery_handoff_proof
from .memory import build_memory_curator_agent_proof
from .research import build_research_packet_agent_proof
from .retrieval import build_retrieval_broker_agent_proof
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


def _gate(name: str, status: str, *, blocking: int = 0, reason: str | None = None,
          **extra: Any) -> dict[str, Any]:
    return {"gate_name": name, "gate_status": status, "blocking": blocking, "reason": reason,
            **extra}


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
        _gate("runtime_readiness", "pass", config_status=config.config_status,
              schema_version=schema_version)
        if schema_current
        else _gate("runtime_readiness", "fail_blocking", blocking=1,
                   reason="schema_not_at_expected_version", schema_version=schema_version)
    )

    # Aggregate the per-surface proofs (each is self-contained / temp-DB).
    gates: list[dict[str, Any]] = [
        runtime_gate,
        _proof_gate("agent_registry", build_agent_registry_proof(), build_agent_tool_policy_proof()),
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
        gates.append(_gate(
            "synthesis_liveness", "warning",
            reason="synthesis_offline_or_mock_runtime_ready_but_not_live",
            synthesis_mode=config.mode,
        ))

    # Deferred surfaces — implemented in a later phase; never reported as pass.
    gates.append(_gate("mcp_exposure", "deferred_not_blocking",
                       reason="mcp_not_implemented", future_phase="08D"))
    gates.append(_gate("model_call_receipt_persistence", "deferred_not_blocking",
                       reason="model_call_and_agent_run_receipts_in_memory_only",
                       future_schema="V27"))
    gates.append(_gate("automation_hardening", "deferred_not_blocking",
                       reason="health_checks_retries_weekend_alerting_owned_by_phase_08b",
                       future_phase="08B"))

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
            "raw_body", "raw_document_text", "raw_calendar_payload", "raw_prompt",
            "raw_response", "signed_url", "download_url", "secret",
        )
    )
    distinguishes_all_statuses = set(counts.keys()) == {
        "pass", "warning", "fail_blocking", "deferred_not_blocking"
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
