"""Store-specific structured runtime errors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class StoreReadinessError(RuntimeError):
    status: str
    message: str
    db_path: str
    report: dict[str, Any]

    def __str__(self) -> str:
        return self.message
