"""
Normalized, always-safe error types for the GET-only Procore HTTP client.

All exceptions are constructed with fully redacted request/response info only.
They are guaranteed safe to str(), repr(), log, or serialize into evidence.

Design directly from subagent exploration (019e6b5b-16b6-7f60-85ae-37dd43872fec).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ProcoreAPIError(Exception):
    """Primary safe error type. Never contains secrets or raw bodies."""

    status: int
    code: Optional[str] = None
    message: str = "Unknown"
    correlation_id: Optional[str] = None
    request: dict[str, Any] = field(default_factory=dict)
    response: dict[str, Any] = field(default_factory=dict)
    retry_after: Optional[int] = None

    def __post_init__(self) -> None:
        # Truncate message for safety
        if self.message:
            self.message = self.message[:500]

    def __str__(self) -> str:
        return (
            f"ProcoreAPIError(status={self.status}, code={self.code}, "
            f"message={self.message!r}, correlation_id={self.correlation_id}, "
            f"retry_after={self.retry_after}, request={self.request}, response={self.response})"
        )

    def __repr__(self) -> str:
        return f"<ProcoreAPIError status={self.status} code={self.code} corr={self.correlation_id}>"


class ProcoreRateLimitError(ProcoreAPIError):
    """Specialization for 429 responses (promotes rate headers)."""

    pass
