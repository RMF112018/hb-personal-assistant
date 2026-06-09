"""Scheduler value types. No I/O."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

JobId = Literal["daily-source-refresh"]
Backend = Literal["launchd", "windows", "systemd", "foreground"]


class InstallPlan(BaseModel):
    """Inputs an OS scheduler backend needs to render/install its artifact."""

    environment: Literal["dev", "production"]
    job_id: JobId
    schedule_time_local: str = "20:00"
    timezone: str = "America/New_York"
    catch_up_on_wake: bool = True
    mock_data: bool = False
    executable: str
    working_directory: str
    label: str
    runner_argv: list[str]


class ScheduledRefreshReceipt(BaseModel):
    """Metadata-only receipt for one scheduled run (local-only vs live-source)."""

    command: str = "scheduler run daily-source-refresh"
    generated_utc: str
    repo_sha: str | None = None
    environment: Literal["dev", "production"]
    job_id: JobId = "daily-source-refresh"
    schedule_date: str
    trigger: str
    mode: Literal["local_only", "live_source"]
    live_reads_enabled: bool
    procore_live: bool
    graph_live: bool
    mock_data: bool
    db_path: str
    orchestrator_status: str
    ledger_run_id: int | None = None
    counts: dict[str, int] = Field(default_factory=dict)
    guardrails: dict[str, Any] = Field(default_factory=dict)
    # Operator-visible failure detail (redacted; no tokens/URLs/raw payloads). Populated from the
    # orchestrator summary so a degraded run is diagnosable from the receipt without re-running.
    failure_count: int = 0
    failures: list[dict[str, Any]] = Field(default_factory=list)
    stages: dict[str, Any] = Field(default_factory=dict)
    procore_auth_status: str | None = None
    next_operator_action: str | None = None
    evidence_summary_path: str | None = None
    receipt_path: str | None = None
    # Honest top-level status: mirrors the orchestrator ("ok" | "degraded" | "failed"). A degraded
    # run is NEVER reported as "ok".
    status: str = "ok"
