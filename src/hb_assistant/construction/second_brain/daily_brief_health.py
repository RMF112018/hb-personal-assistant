"""Phase 08B daily-brief job health monitoring (Prompt 08).

A deterministic, read-only evaluator over the V26 ``daily_brief_runs`` ledger that answers
"is the daily-brief *job* healthy?" — running on cadence, succeeding, and not degrading. It reads
metadata columns only (status / generated_utc / degradation_mode / review_tier) and reports the
job's health with structured reason codes. Parallel to the automation-health (Prompt 03) and
freshness (Prompt 07) agents.

Reason codes: ``JOB_HEALTHY`` (recent successful run, no degradation), ``JOB_DEGRADED`` (last run
blocked / degradation_mode set), ``JOB_STALE`` (last run older than ``max_age_hours`` — missed
cadence), ``JOB_NEVER_RUN`` (no runs recorded).

Pure observability: the ONLY apply-capable path is the emit-gated V28 agent-run receipt (off by
default). No external writeback, no external delivery, no raw content.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, field_validator

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

from .automation_policy import load_phase_08b_automation_policy_seed
from .daily_brief.store import read_latest_daily_brief_runs

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

# Reason codes (declared in the Phase 08B automation policy + gate contracts).
JOB_HEALTHY = "JOB_HEALTHY"
JOB_DEGRADED = "JOB_DEGRADED"
JOB_STALE = "JOB_STALE"
JOB_NEVER_RUN = "JOB_NEVER_RUN"
DAILY_BRIEF_JOB_HEALTH_OK = "DAILY_BRIEF_JOB_HEALTH_OK"

_DEFAULT_MAX_AGE_HOURS = 36
_DEFAULT_HEALTHY_STATUSES = ("synthesized",)


class DailyBriefJobHealthStatus(BaseModel):
    """Daily-brief job-health snapshot (metadata-only; no raw content)."""

    overall_status: str  # "ok" | "attention"
    reason_code: str
    last_run_status: str | None = None
    last_run_utc: str | None = None
    last_run_date: str | None = None
    age_seconds: int | None = None
    degradation_mode: str | None = None
    review_tier: int | None = None
    consecutive_non_healthy: int = 0
    runs_examined: int = 0
    policy_version: str = "unknown"
    schema_version: int = 0
    schema_expected: int = LATEST_SCHEMA_VERSION
    generated_utc: str = ""
    detail: str | None = None

    model_config = {"extra": "forbid"}

    @field_validator("detail", "degradation_mode")
    @classmethod
    def _no_forbidden_tokens(cls, value: str | None) -> str | None:
        if value and any(t in value for t in _FORBIDDEN_TOKENS):
            raise ValueError("daily-brief-health field must not carry raw/forbidden tokens")
        return value


def _resolved_db(db_path: str | None) -> str:
    return db_path if db_path is not None else str(PathPolicy().get_db_path())


def _safe_seed() -> dict[str, Any]:
    try:
        seed = load_phase_08b_automation_policy_seed()
    except Exception:  # pragma: no cover - defensive
        return {}
    return seed if isinstance(seed, dict) else {}


def _cfg() -> dict[str, Any]:
    cfg = _safe_seed().get("daily_brief_job_health", {})
    return cfg if isinstance(cfg, dict) else {}


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        text = value.replace("Z", "+00:00") if value.endswith("Z") else value
        dt = datetime.fromisoformat(text)
    except (ValueError, AttributeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _values_only_blob(obj: Any) -> str:
    """Concatenate VALUES (not dict keys) so the raw-content scan ignores schema field names."""
    out: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                walk(v)
        elif node is not None:
            out.append(str(node))

    walk(obj)
    return " ".join(out)


def _is_healthy_run(run: dict[str, Any], healthy_statuses: tuple[str, ...]) -> bool:
    return run.get("status") in healthy_statuses and not run.get("degradation_mode")


def evaluate_daily_brief_job_health(
    *, db_path: str | None = None, now: datetime | None = None
) -> DailyBriefJobHealthStatus:
    """Read-only daily-brief job health over the most recent ``daily_brief_runs`` rows."""
    cfg = _cfg()
    max_age_hours = int(cfg.get("max_age_hours", _DEFAULT_MAX_AGE_HOURS))
    max_age_seconds = max_age_hours * 3600
    healthy_statuses = tuple(cfg.get("healthy_statuses") or _DEFAULT_HEALTHY_STATUSES)
    now = now or datetime.now(timezone.utc)
    seed = _safe_seed()
    try:
        schema_version = SQLiteMigrator(_resolved_db(db_path)).current_version()
    except Exception:  # pragma: no cover - defensive
        schema_version = 0
    generated = datetime.now(timezone.utc).isoformat()

    runs = read_latest_daily_brief_runs(db_path=db_path, limit=20)

    base: dict[str, Any] = {
        "policy_version": str(seed.get("version", "unknown")),
        "schema_version": schema_version,
        "generated_utc": generated,
        "runs_examined": len(runs),
    }

    if not runs:
        return DailyBriefJobHealthStatus(
            overall_status="attention",
            reason_code=JOB_NEVER_RUN,
            detail="no_daily_brief_runs_recorded",
            **base,
        )

    # Consecutive non-healthy streak from the newest run backward.
    streak = 0
    for run in runs:
        if _is_healthy_run(run, healthy_statuses):
            break
        streak += 1

    latest = runs[0]
    last_status = str(latest.get("status")) if latest.get("status") is not None else None
    degradation = latest.get("degradation_mode")
    review_tier = latest.get("review_tier")
    last_utc = latest.get("generated_utc")
    parsed = _parse_utc(str(last_utc) if last_utc else None)
    age = int((now.astimezone(timezone.utc) - parsed).total_seconds()) if parsed else None

    common: dict[str, Any] = {
        "last_run_status": last_status,
        "last_run_utc": str(last_utc) if last_utc else None,
        "last_run_date": str(latest.get("brief_date")) if latest.get("brief_date") else None,
        "age_seconds": age,
        "degradation_mode": str(degradation) if degradation else None,
        "review_tier": int(review_tier) if review_tier is not None else None,
        "consecutive_non_healthy": streak,
        **base,
    }

    if age is not None and age > max_age_seconds:
        return DailyBriefJobHealthStatus(
            overall_status="attention",
            reason_code=JOB_STALE,
            detail="latest_run_age_exceeds_threshold",
            **common,
        )
    if not _is_healthy_run(latest, healthy_statuses):
        return DailyBriefJobHealthStatus(
            overall_status="attention",
            reason_code=JOB_DEGRADED,
            detail="latest_run_blocked_or_degraded",
            **common,
        )
    return DailyBriefJobHealthStatus(
        overall_status="ok",
        reason_code=JOB_HEALTHY,
        detail="recent_successful_run",
        **common,
    )


def run_daily_brief_job_health(
    *, db_path: str | None = None, now: datetime | None = None, emit_receipt: bool = False
) -> tuple[DailyBriefJobHealthStatus, str | None]:
    """Evaluate job health (read-only); when ``emit_receipt``, persist a metadata-only V28 receipt."""
    status = evaluate_daily_brief_job_health(db_path=db_path, now=now)
    agent_run_id: str | None = None
    if emit_receipt:
        from .reasoning import build_agent_run_receipt
        from .store import write_agent_run_receipt

        receipt = build_agent_run_receipt(
            agent_id="daily_brief_job_health_agent",
            run_kind="daily_brief_job_health",
            status=status.overall_status,
            reason_code=status.reason_code,
            started_utc=status.generated_utc,
            finished_utc=datetime.now(timezone.utc).isoformat(),
        )
        agent_run_id = write_agent_run_receipt(receipt, db_path=db_path)
    return status, agent_run_id


def build_daily_brief_job_health_proof() -> dict[str, Any]:
    """Deterministic proof for ``daily-brief-job-health-proof.json`` (temp migrated DB)."""
    import sqlite3
    import tempfile
    import uuid
    from datetime import timedelta

    from hb_assistant.construction.store import ConstructionStore

    now = datetime(2026, 6, 2, 21, 0, tzinfo=timezone.utc)

    def _insert(
        db: str, *, status: str, generated_utc: str, degradation: str | None = None
    ) -> None:
        conn = sqlite3.connect(db)
        with conn:
            conn.execute(
                """
                INSERT INTO daily_brief_runs
                    (brief_run_id, brief_date, mode, status, degradation_mode, generated_utc)
                VALUES (?, '2026-06-02', 'apply', ?, ?, ?)
                """,
                (uuid.uuid4().hex, status, degradation, generated_utc),
            )
        conn.close()

    with tempfile.TemporaryDirectory() as tmp:
        empty_db = f"{tmp}/empty.sqlite3"
        ConstructionStore(empty_db)
        never_run = evaluate_daily_brief_job_health(db_path=empty_db, now=now)

        healthy_db = f"{tmp}/healthy.sqlite3"
        ConstructionStore(healthy_db)
        _insert(
            healthy_db, status="synthesized", generated_utc=(now - timedelta(hours=1)).isoformat()
        )
        healthy = evaluate_daily_brief_job_health(db_path=healthy_db, now=now)

        degraded_db = f"{tmp}/degraded.sqlite3"
        ConstructionStore(degraded_db)
        _insert(
            degraded_db,
            status="blocked",
            generated_utc=(now - timedelta(hours=1)).isoformat(),
            degradation="research_packet_blocked",
        )
        degraded = evaluate_daily_brief_job_health(db_path=degraded_db, now=now)

        stale_db = f"{tmp}/stale.sqlite3"
        ConstructionStore(stale_db)
        _insert(
            stale_db, status="synthesized", generated_utc=(now - timedelta(hours=72)).isoformat()
        )
        stale = evaluate_daily_brief_job_health(db_path=stale_db, now=now)

    blob = _values_only_blob(
        [never_run.model_dump(), healthy.model_dump(), degraded.model_dump(), stale.model_dump()]
    )
    no_raw_content = not any(t in blob for t in _FORBIDDEN_TOKENS)

    proof_passed = bool(
        never_run.reason_code == JOB_NEVER_RUN
        and healthy.reason_code == JOB_HEALTHY
        and healthy.overall_status == "ok"
        and degraded.reason_code == JOB_DEGRADED
        and stale.reason_code == JOB_STALE
        and no_raw_content
    )
    return {
        "proof": "phase_08b_daily_brief_job_health",
        "proof_passed": proof_passed,
        "never_run_reason_code": never_run.reason_code,
        "healthy_reason_code": healthy.reason_code,
        "degraded_reason_code": degraded.reason_code,
        "stale_reason_code": stale.reason_code,
        "no_raw_content": no_raw_content,
        "guardrails": {
            "local_first": True,
            "read_only": True,
            "deterministic": True,
            "no_external_writeback": True,
            "no_external_delivery": True,
            "no_raw_content": True,
            "model_direct_external_api_access": False,
        },
    }
