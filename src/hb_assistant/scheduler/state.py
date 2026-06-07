"""Persisted scheduler state (JSON, atomic) — the authority for catch-up decisions."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

from hb_assistant.scheduler.models import JobId


class SchedulerState(BaseModel):
    """All scheduler state required to decide due/catch-up and report status."""

    environment: str
    job_id: JobId = "daily-source-refresh"
    schedule_time_local: str = "20:00"
    timezone: str = "America/New_York"
    catch_up_on_wake: bool = True
    last_started_at: str | None = None
    last_finished_at: str | None = None
    last_successful_schedule_date: str | None = None
    last_attempted_schedule_date: str | None = None
    last_status: str | None = None
    last_receipt_path: str | None = None
    consecutive_failures: int = 0
    next_expected_run: str | None = None
    current_process_ids: list[int] = Field(default_factory=list)

    @classmethod
    def load(cls, path: Path, *, environment: str) -> "SchedulerState":
        if path.exists():
            try:
                return cls.model_validate_json(path.read_text())
            except Exception:
                pass
        return cls(environment=environment)

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(self.model_dump_json(indent=2))
        os.replace(tmp, path)
        return path
