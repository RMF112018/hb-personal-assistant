"""Background worker for schedule quality evaluation runs."""

from __future__ import annotations

from typing import Any

from .schedule_quality_service import ScheduleQualityService


def poll_and_process(*, db_path: str, limit: int = 1) -> list[dict[str, Any]]:
    service = ScheduleQualityService(db_path=db_path)
    results: list[dict[str, Any]] = []
    for _ in range(max(limit, 1)):
        out = service.process_next_pending()
        if out is None:
            break
        results.append(out)
    return results