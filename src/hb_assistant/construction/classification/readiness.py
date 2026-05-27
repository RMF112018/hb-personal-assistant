"""Ollama live-readiness probe (non-mutating).

GETs ``/api/tags`` on the resolved endpoint to report daemon reachability and
which expected models are present. The inference path is never touched —
this module exists precisely so CI / offline contexts can check readiness
without triggering inference. The CLI ``hb-assistant construction-agent
ollama status`` is the operator-facing surface.

Endpoint resolution precedence::

    OLLAMA_HOST env var > ModelRoutingConfig.endpoint_url > hardcoded default

The hardcoded default lives on :data:`hb_assistant.construction.classification
.models.DEFAULT_OLLAMA_ENDPOINT`.
"""

from __future__ import annotations

import os
from typing import Callable, Literal, Optional

import requests
from pydantic import BaseModel, Field

from .models import DEFAULT_OLLAMA_ENDPOINT, ModelRoutingConfig

EndpointSource = Literal["env", "config", "default"]
ReadinessStatus = Literal[
    "ready",
    "daemon_unreachable",
    "models_missing",
    "config_invalid",
]

OLLAMA_HOST_ENV_VAR = "OLLAMA_HOST"
TAGS_PATH = "/api/tags"

_READINESS_GUARDRAILS: dict[str, str] = {
    "external_systems": "read_only",
    "writeback": "none",
    "live_inference": "false",
    "endpoint_path": TAGS_PATH,
}


class ReadinessReport(BaseModel):
    endpoint_url: str
    endpoint_source: EndpointSource
    daemon_reachable: bool
    expected_models: list[str]
    present_models: list[str]
    missing_models: list[str]
    suggested_pull_commands: list[str] = Field(default_factory=list)
    status: ReadinessStatus
    ok: bool
    error_redacted: Optional[str] = None
    guardrails: dict[str, str] = Field(default_factory=lambda: dict(_READINESS_GUARDRAILS))

    model_config = {"extra": "forbid"}


def _resolve_endpoint(config: ModelRoutingConfig) -> tuple[str, EndpointSource]:
    """Return ``(endpoint_url, source)`` per the documented precedence."""
    env_value = os.environ.get(OLLAMA_HOST_ENV_VAR, "").strip()
    if env_value:
        return env_value.rstrip("/"), "env"
    if config.endpoint_url != DEFAULT_OLLAMA_ENDPOINT:
        return config.endpoint_url, "config"
    return DEFAULT_OLLAMA_ENDPOINT, "default"


def check_readiness(
    config: ModelRoutingConfig,
    *,
    timeout: float = 5.0,
    requests_get: Optional[Callable[..., requests.Response]] = None,
) -> ReadinessReport:
    """Probe ``/api/tags`` and report daemon + model presence.

    The ``requests_get`` parameter exists so tests (and callers that want a
    fake transport) can inject a substitute without monkey-patching
    ``requests`` globally.

    Errors are caught and serialized into a structured ``daemon_unreachable``
    report — this function never raises a network exception to its caller.
    """
    endpoint_url, endpoint_source = _resolve_endpoint(config)
    expected = config.resolved_expected_models()
    get = requests_get if requests_get is not None else requests.get

    try:
        response = get(endpoint_url + TAGS_PATH, timeout=timeout)
    except requests.RequestException:
        return ReadinessReport(
            endpoint_url=endpoint_url,
            endpoint_source=endpoint_source,
            daemon_reachable=False,
            expected_models=expected,
            present_models=[],
            missing_models=list(expected),
            suggested_pull_commands=[f"ollama pull {m}" for m in expected],
            status="daemon_unreachable",
            ok=False,
            error_redacted="ollama_request_failed",
        )

    status_code = getattr(response, "status_code", None)
    if status_code != 200:
        return ReadinessReport(
            endpoint_url=endpoint_url,
            endpoint_source=endpoint_source,
            daemon_reachable=False,
            expected_models=expected,
            present_models=[],
            missing_models=list(expected),
            suggested_pull_commands=[f"ollama pull {m}" for m in expected],
            status="daemon_unreachable",
            ok=False,
            error_redacted=f"ollama_status_{status_code}",
        )

    try:
        body = response.json()
    except ValueError:
        return ReadinessReport(
            endpoint_url=endpoint_url,
            endpoint_source=endpoint_source,
            daemon_reachable=False,
            expected_models=expected,
            present_models=[],
            missing_models=list(expected),
            suggested_pull_commands=[f"ollama pull {m}" for m in expected],
            status="daemon_unreachable",
            ok=False,
            error_redacted="ollama_invalid_envelope",
        )

    raw_models = body.get("models") if isinstance(body, dict) else None
    if not isinstance(raw_models, list):
        return ReadinessReport(
            endpoint_url=endpoint_url,
            endpoint_source=endpoint_source,
            daemon_reachable=False,
            expected_models=expected,
            present_models=[],
            missing_models=list(expected),
            suggested_pull_commands=[f"ollama pull {m}" for m in expected],
            status="daemon_unreachable",
            ok=False,
            error_redacted="ollama_missing_models_field",
        )

    present: list[str] = []
    for entry in raw_models:
        if isinstance(entry, dict):
            name = entry.get("name")
            if isinstance(name, str) and name:
                present.append(name)

    missing = [m for m in expected if m not in present]
    if missing:
        return ReadinessReport(
            endpoint_url=endpoint_url,
            endpoint_source=endpoint_source,
            daemon_reachable=True,
            expected_models=expected,
            present_models=present,
            missing_models=missing,
            suggested_pull_commands=[f"ollama pull {m}" for m in missing],
            status="models_missing",
            ok=False,
        )

    return ReadinessReport(
        endpoint_url=endpoint_url,
        endpoint_source=endpoint_source,
        daemon_reachable=True,
        expected_models=expected,
        present_models=present,
        missing_models=[],
        suggested_pull_commands=[],
        status="ready",
        ok=True,
    )
