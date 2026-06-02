"""Phase 08B Automation Health Agent (Prompt 03).

A deterministic, offline, read-only health evaluator for the second-brain runtime. It runs the
health checks named in the Phase 08B automation policy seed (path readiness, store readiness, schema
at latest, durable delivery-handoff) and reports per-check + overall status with the policy's
structured reason codes. It NEVER migrates, writes external systems, sends an alert, or persists raw
content. An optional emit-gated metadata-only V28 agent-run receipt records that a health run
happened (status + reason code only).
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, field_validator

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.connection import get_connection
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

from .automation_policy import load_phase_08b_automation_policy_seed

_DEFAULT_CHECKS = (
    "path_readiness",
    "store_readiness",
    "schema_at_latest",
    "daily_brief_handoff_durable",
)
_FORBIDDEN_TOKENS = (
    "raw_body",
    "raw_document_text",
    "raw_calendar_payload",
    "raw_prompt",
    "raw_response",
    "signed_url",
    "download_url",
    "secret",
    "token",
)


class HealthCheckResult(BaseModel):
    """One deterministic health-check result (metadata-only; no raw content)."""

    check: str
    status: str  # "ok" | "degraded"
    reason_code: str | None = None
    detail: str | None = None

    model_config = {"extra": "forbid"}

    @field_validator("detail")
    @classmethod
    def _no_forbidden_tokens(cls, value: str | None) -> str | None:
        if value and any(t in value for t in _FORBIDDEN_TOKENS):
            raise ValueError("health-check detail must not carry raw/forbidden tokens")
        return value


class AutomationHealthStatus(BaseModel):
    """Overall automation-health snapshot the status surface reports (no raw content)."""

    overall_status: str  # "ok" | "degraded"
    reason_code: str
    checks: list[HealthCheckResult] = []
    policy_version: str = "unknown"
    schema_version: int = 0
    schema_expected: int = LATEST_SCHEMA_VERSION
    degraded_checks: list[str] = []
    generated_utc: str = ""

    model_config = {"extra": "forbid"}


def _resolved_db(db_path: str | None) -> str:
    return db_path if db_path is not None else str(PathPolicy().get_db_path())


def _ok(check: str, detail: str | None = None) -> HealthCheckResult:
    return HealthCheckResult(check=check, status="ok", detail=detail)


def _degraded(check: str, reason_code: str, detail: str | None = None) -> HealthCheckResult:
    return HealthCheckResult(check=check, status="degraded", reason_code=reason_code, detail=detail)


def _check_path_readiness(db_path: str | None, fail_code: str) -> HealthCheckResult:
    """Read-only DB-path readiness (parent exists/writable + sqlite openable). No mkdir."""
    if db_path is None:
        report = PathPolicy().ensure_db_ready(return_report=True) or {}
        if report.get("ok"):
            return _ok("path_readiness", detail=str(report.get("status")))
        return _degraded("path_readiness", fail_code, detail=str(report.get("error")))
    parent = Path(db_path).parent
    if not (parent.exists() and parent.is_dir() and os.access(parent, os.W_OK)):
        return _degraded("path_readiness", fail_code, detail="db_parent_unavailable")
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        conn.close()
    except Exception:
        return _degraded("path_readiness", fail_code, detail="sqlite_open_failed")
    return _ok("path_readiness", detail="ok")


def _table_exists(conn: Any, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _check_store_readiness(db_path: str, fail_code: str) -> HealthCheckResult:
    """Read-only: the store is connectable and carries an applied migration ledger."""
    try:
        conn = get_connection(Path(db_path))
        if not _table_exists(conn, "schema_migrations"):
            return _degraded("store_readiness", fail_code, detail="no_schema_migrations")
    except Exception:
        return _degraded("store_readiness", fail_code, detail="store_unavailable")
    return _ok("store_readiness", detail="ok")


def _check_schema_at_latest(db_path: str, fail_code: str) -> HealthCheckResult:
    current = SQLiteMigrator(db_path).current_version()
    if current == LATEST_SCHEMA_VERSION:
        return _ok("schema_at_latest", detail=f"v{current}")
    return _degraded("schema_at_latest", fail_code, detail=f"v{current}!=v{LATEST_SCHEMA_VERSION}")


def _check_handoff_durable(db_path: str, fail_code: str) -> HealthCheckResult:
    try:
        conn = get_connection(Path(db_path))
        present = _table_exists(conn, "daily_brief_handoff_lines")
    except Exception:
        return _degraded("daily_brief_handoff_durable", fail_code, detail="store_unavailable")
    if present:
        return _ok("daily_brief_handoff_durable", detail="table_present")
    return _degraded("daily_brief_handoff_durable", fail_code, detail="table_absent")


def evaluate_automation_health(*, db_path: str | None = None) -> AutomationHealthStatus:
    """Run the seeded health checks read-only and report status + reason codes. No writes."""
    generated = datetime.now(timezone.utc).isoformat()
    try:
        seed = load_phase_08b_automation_policy_seed()
    except Exception:  # pragma: no cover - defensive: health must not crash
        seed = {}
    health_cfg = seed.get("health_checks", {}) if isinstance(seed, dict) else {}
    checks_requested = health_cfg.get("checks") or list(_DEFAULT_CHECKS)
    fail_code = health_cfg.get("fail_reason_code", "HEALTH_CHECK_FAILED")
    ok_code = "RUN_OK"
    degraded_code = "RUN_DEGRADED"

    resolved = _resolved_db(db_path)
    runners = {
        "path_readiness": lambda: _check_path_readiness(db_path, fail_code),
        "store_readiness": lambda: _check_store_readiness(resolved, fail_code),
        "schema_at_latest": lambda: _check_schema_at_latest(resolved, fail_code),
        "daily_brief_handoff_durable": lambda: _check_handoff_durable(resolved, fail_code),
    }
    results: list[HealthCheckResult] = []
    for name in checks_requested:
        runner = runners.get(name)
        if runner is None:
            results.append(_degraded(name, fail_code, detail="unknown_check"))
        else:
            results.append(runner())

    degraded = [r.check for r in results if r.status != "ok"]
    overall = "ok" if not degraded else "degraded"
    schema_version = SQLiteMigrator(resolved).current_version()
    return AutomationHealthStatus(
        overall_status=overall,
        reason_code=ok_code if overall == "ok" else degraded_code,
        checks=results,
        policy_version=str(seed.get("version", "unknown")) if isinstance(seed, dict) else "unknown",
        schema_version=schema_version,
        degraded_checks=degraded,
        generated_utc=generated,
    )


def run_automation_health(
    *, db_path: str | None = None, emit_receipt: bool = False
) -> tuple[AutomationHealthStatus, str | None]:
    """Evaluate health (read-only); when ``emit_receipt``, persist a metadata-only V28 receipt.

    Returns ``(status, agent_run_id|None)``. Receipt persistence is the only apply-capable path and
    is off by default. The receipt carries status + reason code only — never raw content.
    """
    status = evaluate_automation_health(db_path=db_path)
    agent_run_id: str | None = None
    if emit_receipt:
        from .reasoning import build_agent_run_receipt
        from .store import write_agent_run_receipt

        receipt = build_agent_run_receipt(
            agent_id="automation_health_agent",
            run_kind="health_check",
            status=status.overall_status,
            reason_code=status.reason_code,
            started_utc=status.generated_utc,
            finished_utc=datetime.now(timezone.utc).isoformat(),
        )
        agent_run_id = write_agent_run_receipt(receipt, db_path=db_path)
    return status, agent_run_id


def build_automation_health_proof() -> dict[str, Any]:
    """Deterministic proof for ``automation-health-agent-proof.json`` (temp migrated DB)."""
    import tempfile

    from hb_assistant.construction.store import ConstructionStore

    with tempfile.TemporaryDirectory() as tmp:
        db = f"{tmp}/health.sqlite3"
        ConstructionStore(db)  # migrate to LATEST so all checks are healthy
        status = evaluate_automation_health(db_path=db)

    blob = status.model_dump_json()
    no_raw_content = not any(t in blob for t in _FORBIDDEN_TOKENS)
    checks_named = {c.check for c in status.checks}
    all_ok = status.overall_status == "ok"
    reason_code_present = bool(status.reason_code) and all(
        c.reason_code or c.status == "ok" for c in status.checks
    )
    proof_passed = bool(
        all_ok
        and status.reason_code == "RUN_OK"
        and checks_named >= set(_DEFAULT_CHECKS)
        and reason_code_present
        and no_raw_content
    )
    return {
        "proof": "phase_08b_automation_health_agent",
        "proof_passed": proof_passed,
        "overall_status": status.overall_status,
        "reason_code": status.reason_code,
        "checks": [c.model_dump() for c in status.checks],
        "schema_version": status.schema_version,
        "no_raw_content": no_raw_content,
        "guardrails": {
            "local_first": True,
            "read_only": True,
            "no_external_writeback": True,
            "no_external_delivery": True,
            "no_alert_emitted": True,
            "no_raw_content": True,
            "model_direct_external_api_access": False,
        },
    }
