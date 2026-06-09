"""Local model profile router (deterministic, fail-closed, no cloud path).

Chooses the local model **profile** for a task family, validates that the chosen profile's model is
actually installed, and walks an ordered **local-only** fallback chain when it is not. It never
falls back to a cloud model (there is no cloud route), never makes a network call beyond the local
Ollama readiness probe owned by :mod:`provider`, and fails *closed* — an unavailable model yields a
blocker and a clearly-marked unavailable route, not a silent substitution.

Config lives in ``resources/config/local_model_task_routing.seed.yaml`` (task family → profile +
fallback chains). The proven :class:`LocalModelProfiles` seed (model names, timeouts, heavy gate) is
read but never mutated. This module is additive: existing consumers keep their hardcoded profile
defaults until they opt into :func:`route_task_family`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

from hb_assistant.config.path_policy import PathPolicy

from .contracts import load_local_model_profiles
from .models import LocalModelProfiles

_SEED_FILENAME = "local_model_task_routing.seed.yaml"
_SEED_ENV_VAR = "HB_LOCAL_MODEL_TASK_ROUTING"


class RouterConfigError(RuntimeError):
    """Raised when the routing config cannot be resolved/validated (fail-closed)."""


class LocalModelTaskRouting(BaseModel):
    """The ``local_model_task_routing`` seed policy (task family → profile + fallback chains)."""

    version: str
    routes: dict[str, str] = Field(min_length=1)
    fallback_chains: dict[str, list[str]] = Field(default_factory=dict)
    guardrails: dict[str, bool] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _routing_invariants(self) -> "LocalModelTaskRouting":
        # Local-first guardrails must never be relaxed: there is no cloud route here.
        for key in ("local_only", "no_cloud", "no_raw_persistence"):
            if key in self.guardrails and not self.guardrails[key]:
                raise ValueError(f"routing guardrail {key!r} must be true")
        return self


def _seed_path() -> Path:
    override = os.environ.get(_SEED_ENV_VAR)
    if override:
        return Path(override).expanduser()
    return PathPolicy().resolve_repo_root() / "resources" / "config" / _SEED_FILENAME


def load_local_model_task_routing() -> LocalModelTaskRouting:
    """Load + validate the task routing seed (fail-closed)."""
    path = _seed_path()
    if not path.exists():
        raise RouterConfigError(f"task routing seed not found at {path}")
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise RouterConfigError("task routing seed is not a mapping")
    try:
        return LocalModelTaskRouting.model_validate(parsed)
    except Exception as exc:  # pydantic ValidationError -> fail-closed RouterConfigError
        raise RouterConfigError(f"invalid task routing seed: {str(exc)[:160]}") from exc


class RouteResult(BaseModel):
    """The deterministic routing decision for one task family (raw-safe)."""

    task_family: str
    selected_profile: str | None = None
    model_name: str | None = None
    available: bool = False
    blocked: bool = False
    blockers: list[str] = Field(default_factory=list)
    reason_code: str = ""
    fallback_chain: list[str] = Field(default_factory=list)
    considered: list[dict[str, Any]] = Field(default_factory=list)
    no_cloud: bool = True

    model_config = {"extra": "forbid"}


def _resolve_chain(
    primary: str,
    routing: LocalModelTaskRouting,
    profiles: LocalModelProfiles,
) -> list[str]:
    """Build the ordered, de-duplicated, local-only profile chain to consider for a route."""
    chain: list[str] = [primary]
    explicit = routing.fallback_chains.get(primary)
    if explicit:
        chain.extend(explicit)
    else:
        single = profiles.fallbacks.get(primary)
        if single:
            chain.append(single)
    seen: set[str] = set()
    ordered: list[str] = []
    known = {p.profile_id for p in profiles.profiles}
    for pid in chain:
        if pid in seen or pid not in known:
            continue
        seen.add(pid)
        ordered.append(pid)
    return ordered


def route_task_family(
    task_family: str,
    *,
    profiles: LocalModelProfiles | None = None,
    routing: LocalModelTaskRouting | None = None,
    present_models: set[str] | None = None,
    heavy_enabled: bool = False,
) -> RouteResult:
    """Select the local profile for ``task_family`` (deterministic, fail-closed, never cloud).

    ``present_models`` is the set of installed Ollama model names (``None`` ⇒ daemon unreachable /
    availability unknown). Availability is reported but the routing *decision* is always returned so
    the operator can see what would run.
    """
    try:
        profiles = profiles or load_local_model_profiles()
        routing = routing or load_local_model_task_routing()
    except Exception as exc:
        return RouteResult(
            task_family=task_family,
            blocked=True,
            blockers=[f"config_error:{str(exc)[:80]}"],
            reason_code="config_error",
        )

    if task_family not in routing.routes:
        return RouteResult(
            task_family=task_family,
            blocked=True,
            blockers=[f"unknown_task_family:{task_family}"],
            reason_code="unknown_task_family",
        )

    by_id = {p.profile_id: p for p in profiles.profiles}
    chain = _resolve_chain(routing.routes[task_family], routing, profiles)
    considered: list[dict[str, Any]] = []
    selected: str | None = None
    daemon_unknown = present_models is None

    for pid in chain:
        profile = by_id[pid]
        heavy_blocked = profile.heavy_profile and not heavy_enabled
        if heavy_blocked:
            reason = "heavy_profile_requires_explicit_enable"
            available = False
        elif not profile.enabled:
            reason = "profile_disabled"
            available = False
        elif present_models is None:
            reason = "daemon_unreachable"
            available = False
        elif profile.model_name not in present_models:
            reason = "model_missing"
            available = False
        else:
            reason = "available"
            available = True
        considered.append(
            {
                "profile_id": pid,
                "model_name": profile.model_name,
                "available": available,
                "reason": reason,
            }
        )
        if available and selected is None:
            selected = pid

    if selected is not None:
        is_primary = selected == chain[0]
        sel_profile = by_id[selected]
        return RouteResult(
            task_family=task_family,
            selected_profile=selected,
            model_name=sel_profile.model_name,
            available=True,
            blocked=False,
            reason_code="selected_routed" if is_primary else "selected_fallback",
            fallback_chain=chain,
            considered=considered,
        )

    # Nothing available -> fail closed (decision still reported as the primary profile).
    primary = chain[0]
    blockers = ["daemon_unreachable"] if daemon_unknown else ["no_available_local_model"]
    return RouteResult(
        task_family=task_family,
        selected_profile=primary,
        model_name=by_id[primary].model_name,
        available=False,
        blocked=True,
        blockers=blockers,
        reason_code="daemon_unreachable" if daemon_unknown else "no_available_local_model",
        fallback_chain=chain,
        considered=considered,
    )


def build_profiles_report(
    *,
    profiles: LocalModelProfiles | None = None,
    routing: LocalModelTaskRouting | None = None,
    present_models: set[str] | None = None,
    heavy_enabled: bool = False,
) -> dict[str, Any]:
    """Report every profile with its served task families and current availability (raw-safe)."""
    profiles = profiles or load_local_model_profiles()
    routing = routing or load_local_model_task_routing()

    served: dict[str, list[str]] = {}
    for family, profile_id in routing.routes.items():
        served.setdefault(profile_id, []).append(family)

    rows: list[dict[str, Any]] = []
    for p in profiles.profiles:
        heavy_blocked = p.heavy_profile and not heavy_enabled
        if heavy_blocked:
            available, reason = False, "heavy_profile_requires_explicit_enable"
        elif not p.enabled:
            available, reason = False, "profile_disabled"
        elif present_models is None:
            available, reason = False, "daemon_unreachable"
        elif p.model_name not in present_models:
            available, reason = False, "model_missing"
        else:
            available, reason = True, None
        rows.append(
            {
                "profile_id": p.profile_id,
                "model_name": p.model_name,
                "role": p.role,
                "enabled": p.enabled,
                "heavy_profile": p.heavy_profile,
                "task_families": sorted(served.get(p.profile_id, [])),
                "available": available,
                "blocked_reason": reason,
            }
        )

    return {
        "version": routing.version,
        "profiles": rows,
        "routes": dict(sorted(routing.routes.items())),
        "guardrails": {"local_only": True, "no_cloud": True, "no_raw_persistence": True},
    }
