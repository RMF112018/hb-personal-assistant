"""HB_PROCORE_LIVE environment-variable gate (Phase 04A Prompt 01).

Centralised opt-in gate for any CLI path that would issue real Procore
HTTP traffic. Imported by ``cli/procore.py`` for the live branches of
``audit execute`` and ``sync run --apply``. The default (dry-run) paths
do **not** call this gate.

The gate is intentionally restrictive: ``HB_PROCORE_LIVE`` must be set to
the exact string ``"1"``. Any other value — including ``"true"``,
``"yes"``, ``"on"`` — is treated as inactive. This keeps the operator-
intent boundary explicit and prevents truthy parsing accidents.

Companion helper :func:`assert_live_mapping_strict` raises before any
HTTP would fire if a live target carries an unmapped or non-pilot status.
This is a runtime gate at the live boundary; the registry-level
``mapping_consistent`` validate check stays separate (Phase 03 residual,
Phase 04A item 05-C).
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass

from hb_assistant.procore.errors import ProcoreAPIError
from hb_assistant.procore.models import (
    LIVE_REFRESH_ELIGIBLE_PROJECT_STATUSES,
    ProcoreProjectsRegistry,
)

LIVE_ENV_VAR = "HB_PROCORE_LIVE"
LIVE_ENV_ENABLER = "1"


@dataclass(frozen=True)
class DirectLiveProjectEligibility:
    """Project gate result for operator-authorized direct endpoint live sync."""

    ok: bool
    procore_project_id: str | None
    reason_code: str | None = None


class LiveEnvNotSet(ProcoreAPIError):
    """Raised when a live Procore command runs without ``HB_PROCORE_LIVE=1``."""

    def __init__(self, command: str) -> None:
        super().__init__(
            status=0,
            code="live_env_not_set",
            message=(
                f"live execution requires {LIVE_ENV_VAR}={LIVE_ENV_ENABLER}; "
                f"command={command!r} refused. "
                f"Set {LIVE_ENV_VAR}={LIVE_ENV_ENABLER} explicitly to opt in."
            ),
        )
        self.command = command


def live_env_active() -> bool:
    """True only when ``HB_PROCORE_LIVE`` is exactly ``"1"``."""
    return os.environ.get(LIVE_ENV_VAR) == LIVE_ENV_ENABLER


def require_live_env(*, command: str) -> None:
    """Raise :class:`LiveEnvNotSet` if the live env-var is not active."""
    if not live_env_active():
        raise LiveEnvNotSet(command=command)


def assert_live_mapping_strict(
    registry: ProcoreProjectsRegistry,
    target_keys: Iterable[str],
) -> None:
    """Raise :class:`ProcoreAPIError` if any target is not live-refresh eligible.

    Live operations must target rows whose status is exactly ``pilot`` or
    ``active`` and whose ``procore_project_id`` is non-empty. Pending /
    deprecated / unknown
    keys are rejected with an offender list. Distinct from the registry-
    level ``mapping_consistent`` check, which scores the whole registry
    rather than a specific target set.
    """
    by_key = {p.hb_project_key: p for p in registry.projects}
    offenders: list[dict[str, str]] = []
    for key in target_keys:
        project = by_key.get(key)
        if project is None:
            offenders.append({"hb_project_key": key, "reason": "unknown_key"})
            continue
        if project.status not in LIVE_REFRESH_ELIGIBLE_PROJECT_STATUSES:
            offenders.append(
                {
                    "hb_project_key": key,
                    "reason": f"status_not_live_refresh_eligible:{project.status}",
                }
            )
            continue
        if not (project.procore_project_id or "").strip():
            offenders.append({"hb_project_key": key, "reason": "procore_project_id_empty"})
    if offenders:
        raise ProcoreAPIError(
            status=0,
            code="live_mapping_strict_violation",
            message=(f"live mapping strict-check rejected target(s); offenders={offenders}"),
        )


def direct_live_project_eligibility(
    registry: ProcoreProjectsRegistry,
    project_key: str,
) -> DirectLiveProjectEligibility:
    """Resolve direct endpoint-live project eligibility.

    Unlike scheduled/all-mapped refresh, a direct operator-authorized endpoint sync
    only requires a configured project row with a valid Procore project id. Project
    status remains scheduler policy and is intentionally not enforced here.
    """
    by_key = {p.hb_project_key: p for p in registry.projects}
    project = by_key.get(project_key)
    if project is None:
        return DirectLiveProjectEligibility(
            ok=False,
            procore_project_id=None,
            reason_code="project_not_mapped",
        )
    value = (project.procore_project_id or "").strip()
    if not value:
        return DirectLiveProjectEligibility(
            ok=False,
            procore_project_id=None,
            reason_code="project_missing_procore_project_id",
        )
    return DirectLiveProjectEligibility(ok=True, procore_project_id=value)


__all__ = [
    "DirectLiveProjectEligibility",
    "LIVE_ENV_ENABLER",
    "LIVE_ENV_VAR",
    "LiveEnvNotSet",
    "assert_live_mapping_strict",
    "direct_live_project_eligibility",
    "live_env_active",
    "require_live_env",
]
