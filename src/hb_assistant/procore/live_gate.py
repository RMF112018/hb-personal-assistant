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

from hb_assistant.procore.errors import ProcoreAPIError
from hb_assistant.procore.models import ProcoreProjectsRegistry

LIVE_ENV_VAR = "HB_PROCORE_LIVE"
LIVE_ENV_ENABLER = "1"


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
    """Raise :class:`ProcoreAPIError` if any target is not a mapped pilot.

    Live operations must target rows whose ``status == "pilot"`` and whose
    ``procore_project_id`` is non-empty. Pending / deprecated / unknown
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
        if project.status != "pilot":
            offenders.append(
                {"hb_project_key": key, "reason": f"status_not_pilot:{project.status}"}
            )
            continue
        if not (project.procore_project_id or "").strip():
            offenders.append({"hb_project_key": key, "reason": "procore_project_id_empty"})
    if offenders:
        raise ProcoreAPIError(
            status=0,
            code="live_mapping_strict_violation",
            message=(
                "live mapping strict-check rejected target(s); "
                f"offenders={offenders}"
            ),
        )


__all__ = [
    "LIVE_ENV_ENABLER",
    "LIVE_ENV_VAR",
    "LiveEnvNotSet",
    "assert_live_mapping_strict",
    "live_env_active",
    "require_live_env",
]
