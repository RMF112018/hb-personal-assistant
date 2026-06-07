"""Per-environment launcher session state (JSON, atomic), shared across CLI calls."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from hb_assistant.launcher.models import Environment, ProcessRecord


class SessionState(BaseModel):
    """Tracks the processes a launcher started for one environment."""

    environment: Environment
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    background_active: bool = False
    processes: list[ProcessRecord] = Field(default_factory=list)
    frontend_url: str | None = None
    frontend_display_name: str | None = None
    frontend_alias_url: str | None = None
    opened_url: str | None = None
    alias_resolution_status: str = "not_configured"
    last_open_warnings: list[str] = Field(default_factory=list)
    last_shutdown_receipt: str | None = None

    @classmethod
    def load(cls, path: Path, *, environment: Environment) -> "SessionState":
        if path.exists():
            try:
                return cls.model_validate_json(path.read_text())
            except Exception:
                pass
        return cls(environment=environment)

    def save(self, path: Path) -> Path:
        self.updated_at = datetime.now(timezone.utc).isoformat()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(self.model_dump_json(indent=2))
        os.replace(tmp, path)
        return path
