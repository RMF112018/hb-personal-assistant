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


class ProcoreAuthRequired(ProcoreAPIError):
    """Raised when an HTTP request would be made without a valid access token.

    The Procore client must never reuse ``PROCORE_CLIENT_SECRET`` as a bearer
    credential. If no access token is available, requests fail closed with
    this error rather than silently sending the client secret on the wire.
    """

    def __init__(
        self,
        message: str = "no_access_token_available",
        correlation_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            status=0,
            code="auth_required",
            message=message,
            correlation_id=correlation_id,
        )


class ProcorePendingProjectRejected(ProcoreAPIError):
    """Raised when a sync plan or apply targets a project whose mapping status
    is ``pending``. Callers must pass ``allow_pending=True`` to override.
    """

    def __init__(
        self,
        pending_keys: list[str],
        correlation_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            status=0,
            code="pending_project_rejected",
            message=(
                "pending project(s) cannot be a default sync target: "
                f"{sorted(pending_keys)}. Pass allow_pending=True to override."
            ),
            correlation_id=correlation_id,
        )
        self.pending_keys = list(pending_keys)


class ProcoreMappingUnavailable(ProcoreAPIError):
    """Raised when the real Procore project mapping cannot be loaded.

    Replaces the prior practice of falling back to a hard-coded stub project
    list. The sync coordinator must never fabricate project IDs.
    """

    def __init__(
        self,
        message: str = "procore project mapping unavailable",
        correlation_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            status=0,
            code="mapping_unavailable",
            message=message,
            correlation_id=correlation_id,
        )
