"""Phase 10 Prompt 03 — local model runtime provider abstraction + readiness status.

A thin, local-first provider layer over the Phase 10 model-profile tiers. Readiness is checked
**without** running a generation: the Ollama provider probes ``/api/tags`` only. A mock provider
backs offline tests. Heavy profiles stay blocked unless explicitly enabled. This module performs
no generation, no DB write, no persistence, and no external writeback — it is a read-only status
surface. Errors are redacted to category codes (never a raw body, URL, or token).

Public entry point:
    build_local_model_status(*, provider_name="ollama", heavy_enabled=False, ...) -> dict
CLI: hb-assistant second-brain local-model status --json
"""

from __future__ import annotations

import json as _json
import os
import subprocess
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from hb_assistant.config.path_policy import PathPolicy

from .contracts import Phase10ContractError, load_local_model_profiles, load_phase_10_contract
from .models import LocalModelProfiles

_DEFAULT_ENDPOINT = "http://localhost:11434"
_TAGS_PATH = "/api/tags"
_DEFAULT_TIMEOUT = 5.0

#: Probe result: (present model names, redacted-error-or-None). ``None`` models ⇒ daemon unreachable.
ProbeResult = tuple[set[str] | None, str | None]

_GUARDRAILS: dict[str, Any] = {
    "local_first": True,
    "read_only": True,
    "live_generation": False,
    "endpoint_path": _TAGS_PATH,
    "no_external_writeback": True,
    "no_raw_persistence": True,
    "heavy_profile_default_blocked": True,
}


class Phase10ProviderError(RuntimeError):
    """Raised when a local model provider cannot be constructed (fail-closed)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=PathPolicy().resolve_repo_root(),
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Status models
# ---------------------------------------------------------------------------
class ProfileAvailability(BaseModel):
    profile_id: str
    model_name: str
    role: str
    enabled: bool
    heavy_profile: bool
    requires_explicit_enable: bool
    available: bool
    blocked_reason: str | None = None

    model_config = {"extra": "forbid"}


class LocalModelStatus(BaseModel):
    provider: str
    endpoint_url: str
    endpoint_source: Literal["env", "arg", "default", "mock"]
    daemon_reachable: bool
    ready: bool
    present_models: list[str] = Field(default_factory=list)
    required_models: list[str] = Field(default_factory=list)
    missing_required_models: list[str] = Field(default_factory=list)
    profiles: list[ProfileAvailability] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    heavy_enabled: bool = False
    suggested_pull_commands: list[str] = Field(default_factory=list)
    error_redacted: str | None = None
    guardrails: dict[str, Any] = Field(default_factory=lambda: dict(_GUARDRAILS))

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------
class LocalModelProvider(ABC):
    """Abstract local model provider. Prompt 03 only needs readiness (no generation)."""

    name: str
    endpoint_url: str
    endpoint_source: Literal["env", "arg", "default", "mock"]

    @abstractmethod
    def probe_models(self, *, timeout: float = _DEFAULT_TIMEOUT) -> ProbeResult:
        """Return (present model names, redacted error). ``None`` model set ⇒ daemon unreachable."""
        raise NotImplementedError


class OllamaProvider(LocalModelProvider):
    """Ollama provider. Readiness via ``GET /api/tags`` only — never a generation call."""

    name = "ollama"

    def __init__(
        self,
        endpoint: str | None = None,
        *,
        requests_get: Callable[..., Any] | None = None,
    ) -> None:
        env = os.environ.get("OLLAMA_HOST")
        if env:
            self.endpoint_url, self.endpoint_source = _normalize_endpoint(env), "env"
        elif endpoint:
            self.endpoint_url, self.endpoint_source = _normalize_endpoint(endpoint), "arg"
        else:
            self.endpoint_url, self.endpoint_source = _DEFAULT_ENDPOINT, "default"
        self._get = requests_get

    def _resolve_get(self) -> Callable[..., Any]:
        # Default to a stdlib urllib getter (no `requests` dependency — the second-brain no-writeback
        # scanner forbids importing requests/httpx/aiohttp in these modules). Tests inject ``_get``.
        if self._get is not None:
            return self._get
        return _urllib_get

    def probe_models(self, *, timeout: float = _DEFAULT_TIMEOUT) -> ProbeResult:
        url = f"{self.endpoint_url}{_TAGS_PATH}"
        try:
            resp = self._resolve_get()(url, timeout=timeout)
        except Exception:
            return None, "ollama_request_failed"
        status_code = getattr(resp, "status_code", None)
        if status_code != 200:
            return None, f"ollama_status_{status_code}"
        try:
            data = resp.json()
        except Exception:
            return None, "ollama_invalid_json"
        models = data.get("models") if isinstance(data, dict) else None
        if not isinstance(models, list):
            return None, "ollama_missing_models_field"
        names = {
            m["name"] for m in models if isinstance(m, dict) and isinstance(m.get("name"), str)
        }
        return names, None


class _UrllibResponse:
    """Minimal response shim exposing the ``status_code`` / ``json()`` surface ``probe_models`` uses."""

    def __init__(self, status_code: int, body: bytes) -> None:
        self.status_code = status_code
        self._body = body

    def json(self) -> Any:
        return _json.loads(self._body.decode("utf-8"))


def _urllib_get(url: str, timeout: float = _DEFAULT_TIMEOUT) -> _UrllibResponse:
    """Stdlib GET returning a response shim. HTTP errors surface as a non-200 status (not a raise)."""
    req = urllib.request.Request(url, method="GET")  # noqa: S310 - fixed localhost Ollama endpoint
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return _UrllibResponse(getattr(resp, "status", 200) or 200, resp.read())
    except urllib.error.HTTPError as exc:  # preserve non-200 status for redacted ollama_status_<n>
        return _UrllibResponse(int(exc.code), b"")


class MockProvider(LocalModelProvider):
    """Offline mock provider. ``present_models=None`` simulates an unreachable daemon."""

    name = "mock"

    def __init__(self, present_models: set[str] | None) -> None:
        self.endpoint_url = "mock://local"
        self.endpoint_source = "mock"
        self._present = present_models

    def probe_models(self, *, timeout: float = _DEFAULT_TIMEOUT) -> ProbeResult:
        if self._present is None:
            return None, "daemon_unreachable_mock"
        return set(self._present), None


def _normalize_endpoint(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value.startswith(("http://", "https://")):
        value = f"http://{value}"
    return value


# ---------------------------------------------------------------------------
# Status builder
# ---------------------------------------------------------------------------
def _required_profile_ids() -> list[str]:
    try:
        contract = load_phase_10_contract("local_model_profile_contract")
        req = contract.get("required_profiles")
        if isinstance(req, list) and req:
            return [str(r) for r in req]
    except (Phase10ContractError, KeyError):
        pass
    return ["default_extract"]


def build_local_model_status(
    *,
    provider_name: str = "ollama",
    profiles: LocalModelProfiles | None = None,
    heavy_enabled: bool = False,
    endpoint: str | None = None,
    requests_get: Callable[..., Any] | None = None,
    mock_models: set[str] | None = None,
    timeout: float = _DEFAULT_TIMEOUT,
    evidence_dir: str | None = None,
    write_evidence: bool = False,
) -> dict[str, Any]:
    """Probe local model readiness against the Phase 10 profile tiers (read-only)."""
    profiles = profiles or load_local_model_profiles()

    if provider_name == "ollama":
        provider: LocalModelProvider = OllamaProvider(endpoint, requests_get=requests_get)
    elif provider_name == "mock":
        provider = MockProvider(mock_models)
    else:
        raise Phase10ProviderError(f"unknown provider {provider_name!r}")

    present_models, error_redacted = provider.probe_models(timeout=timeout)
    daemon_reachable = present_models is not None
    present = present_models or set()

    required_ids = set(_required_profile_ids())
    profile_reports: list[ProfileAvailability] = []
    pulls: list[str] = []
    for p in profiles.profiles:
        # A profile is "active" only when enabled, or when it's a heavy profile and heavy use is
        # explicitly enabled. Pull recommendations are emitted ONLY for active profiles, so a
        # disabled model (e.g. qwen3:*) is never suggested for pull unless explicitly enabled.
        active = p.enabled or (p.heavy_profile and heavy_enabled)
        if p.heavy_profile and not heavy_enabled:
            available, reason = False, "heavy_profile_requires_explicit_enable"
        elif not active:
            available, reason = False, "profile_disabled"
        elif not daemon_reachable:
            available, reason = False, "daemon_unreachable"
        elif p.model_name not in present:
            available, reason = False, "model_missing"
            pulls.append(f"ollama pull {p.model_name}")
        else:
            available, reason = True, None
        profile_reports.append(
            ProfileAvailability(
                profile_id=p.profile_id,
                model_name=p.model_name,
                role=p.role,
                enabled=p.enabled,
                heavy_profile=p.heavy_profile,
                requires_explicit_enable=p.requires_explicit_enable,
                available=available,
                blocked_reason=reason,
            )
        )

    required_models = sorted(
        {p.model_name for p in profiles.profiles if p.profile_id in required_ids}
    )
    missing_required = (
        [m for m in required_models if m not in present] if daemon_reachable else required_models
    )
    ready = daemon_reachable and not missing_required

    blockers: list[str] = []
    if not daemon_reachable:
        blockers.append("daemon_unreachable")
    else:
        blockers.extend(f"required_model_missing:{m}" for m in missing_required)

    status = LocalModelStatus(
        provider=provider.name,
        endpoint_url=provider.endpoint_url,
        endpoint_source=provider.endpoint_source,
        daemon_reachable=daemon_reachable,
        ready=ready,
        present_models=sorted(present),
        required_models=required_models,
        missing_required_models=missing_required,
        profiles=profile_reports,
        blockers=blockers,
        heavy_enabled=heavy_enabled,
        suggested_pull_commands=sorted(set(pulls)),
        error_redacted=error_redacted,
    )

    result: dict[str, Any] = {
        "command": "second-brain local-model status",
        "phase": "10",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "overall_status": "ready" if ready else "not_ready",
        **status.model_dump(),
    }

    if write_evidence:
        result["evidence_written"] = _write_evidence(result, evidence_dir)
    return result


_EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-10-local-action-intelligence"
_PROOF_JSON = "03-local-model-status-proof.json"
_PROOF_MD = "03-local-model-status-proof.md"


def _write_evidence(result: dict[str, Any], evidence_dir: str | None) -> dict[str, str]:
    import json

    base = Path(evidence_dir) if evidence_dir else PathPolicy().resolve_repo_root() / _EVIDENCE_DIR
    base.mkdir(parents=True, exist_ok=True)
    json_path = base / _PROOF_JSON
    md_path = base / _PROOF_MD
    json_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(result), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def _render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Phase 10 Prompt 03 — Local Model Runtime Status Proof",
        "",
        f"**Status:** {result['overall_status']} · **provider:** {result['provider']}"
        f" · **generated_utc:** {result['generated_utc']}",
        "",
        f"- repo_sha: `{result['repo_sha']}`",
        f"- endpoint: `{result['endpoint_url']}` ({result['endpoint_source']})"
        f" · daemon_reachable: {result['daemon_reachable']} · ready: {result['ready']}",
        f"- present_models: {result['present_models']}",
        f"- required_models: {result['required_models']}"
        f" · missing_required: {result['missing_required_models']}",
        f"- blockers: {result['blockers']}",
        "",
        "## Profiles",
        "",
        "| Profile | Model | Enabled | Heavy | Available | Blocked reason |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for p in result["profiles"]:
        lines.append(
            f"| {p['profile_id']} | {p['model_name']} | {p['enabled']} | {p['heavy_profile']} |"
            f" {p['available']} | {p['blocked_reason']} |"
        )
    if result["suggested_pull_commands"]:
        lines += ["", "## Suggested pulls", ""]
        lines += [f"- `{c}`" for c in result["suggested_pull_commands"]]
    lines += [
        "",
        "## Guardrails",
        "",
        "Local-first; readiness via `/api/tags` only (no generation); errors redacted to category"
        " codes (no raw body/URL/token); heavy profiles blocked unless explicitly enabled; status"
        " is read-only (no DB write, no persistence, no external writeback).",
    ]
    return "\n".join(lines) + "\n"
