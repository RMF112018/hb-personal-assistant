"""Phase 08A second-brain runtime configuration (Prompt 03).

Resolves the local-first second-brain runtime posture from environment variables
and the existing :class:`~hb_assistant.config.models.AppConfig` security flag, and
exposes a non-secret, JSON-safe snapshot for status reporting and config receipts.

Hard guarantees:

* The Anthropic API key value is **never** stored on the model, logged, persisted,
  or returned — only its *presence* is recorded as ``api_key_configured``.
* Mode resolution is **fail-closed**: ``live`` requires an explicit
  ``HB_SECOND_BRAIN_MODE=live`` *and* a configured API key *and* the operator's
  existing ``security.external_llm_enabled`` master switch. Anything short of that
  degrades to ``mock`` (when enabled) or ``disabled``.
* No external API access, no writeback, no raw content. Dependency presence is
  probed with :func:`importlib.util.find_spec` (no import, no network).
"""

from __future__ import annotations

import importlib.util
import os
from typing import Literal, Mapping

from pydantic import BaseModel, Field

from hb_assistant.config.loader import load_config
from hb_assistant.config.models import AppConfig

Mode = Literal["disabled", "mock", "live"]

# Env var names (values are never persisted; the key var is presence-only).
ENV_ENABLED = "HB_SECOND_BRAIN_ENABLED"
ENV_MODE = "HB_SECOND_BRAIN_MODE"
ENV_API_KEY = "HB_ANTHROPIC_API_KEY"
ENV_MODEL = "HB_CLAUDE_MODEL"
ENV_MAX_INPUT_CHARS = "HB_CLAUDE_MAX_INPUT_CHARS"
ENV_MAX_OUTPUT_TOKENS = "HB_CLAUDE_MAX_OUTPUT_TOKENS"

DEFAULT_CLAUDE_MODEL = "claude-opus-4-8"
DEFAULT_MAX_INPUT_CHARS = 24000
DEFAULT_MAX_OUTPUT_TOKENS = 2048

# The dependency that backs live mode (declared in the optional `second-brain` extra).
LIVE_DEPENDENCY = "anthropic"


class SecondBrainConfig(BaseModel):
    """Resolved, non-secret second-brain runtime configuration snapshot."""

    mode: Mode = "disabled"
    enabled: bool = False
    claude_model: str = DEFAULT_CLAUDE_MODEL
    max_input_chars: int = DEFAULT_MAX_INPUT_CHARS
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    # Presence-only signals — never the secret value itself.
    api_key_configured: bool = False
    external_llm_enabled: bool = False
    anthropic_installed: bool = False
    synthesis_enabled: bool = False
    config_status: str = "offline_disabled"
    notes: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}

    def dependency_status(self) -> dict[str, bool]:
        """JSON-safe dependency/availability booleans (no values)."""
        return {
            "anthropic_installed": self.anthropic_installed,
            "api_key_configured": self.api_key_configured,
            "external_llm_enabled": self.external_llm_enabled,
        }


def _coerce_int(raw: str | None, default: int) -> int:
    if raw is None:
        return default
    try:
        value = int(raw.strip())
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _truthy(raw: str | None) -> bool:
    """Explicit opt-in only (mirrors the Procore live-gate exact-match posture)."""
    return (raw or "").strip().lower() in {"1", "true", "yes", "on"}


def load_second_brain_config(
    *,
    app_config: AppConfig | None = None,
    env: Mapping[str, str] | None = None,
) -> SecondBrainConfig:
    """Resolve the second-brain runtime configuration (fail-closed).

    ``app_config`` and ``env`` are injectable for deterministic tests; both default
    to live process state (``load_config()`` / ``os.environ``).
    """
    environ = env if env is not None else os.environ
    cfg = app_config if app_config is not None else load_config()

    enabled = _truthy(environ.get(ENV_ENABLED))
    requested_mode = (environ.get(ENV_MODE) or "").strip().lower()
    api_key_configured = bool((environ.get(ENV_API_KEY) or "").strip())
    external_llm_enabled = bool(cfg.security.external_llm_enabled)
    anthropic_installed = importlib.util.find_spec(LIVE_DEPENDENCY) is not None

    claude_model = (environ.get(ENV_MODEL) or "").strip() or DEFAULT_CLAUDE_MODEL
    max_input_chars = _coerce_int(environ.get(ENV_MAX_INPUT_CHARS), DEFAULT_MAX_INPUT_CHARS)
    max_output_tokens = _coerce_int(
        environ.get(ENV_MAX_OUTPUT_TOKENS), DEFAULT_MAX_OUTPUT_TOKENS
    )

    notes: list[str] = []

    # --- fail-closed mode resolution -------------------------------------------
    mode: Mode
    if not enabled:
        mode = "disabled"
        if requested_mode in {"mock", "live"}:
            notes.append(f"{ENV_ENABLED} not set; runtime forced to disabled")
    elif requested_mode == "live":
        if not external_llm_enabled:
            mode = "mock"
            notes.append(
                "live requested but security.external_llm_enabled is false; "
                "degraded to mock"
            )
        elif not api_key_configured:
            mode = "mock"
            notes.append(f"live requested but {ENV_API_KEY} not set; degraded to mock")
        elif not anthropic_installed:
            mode = "mock"
            notes.append(
                "live requested but 'anthropic' not installed "
                "(pip install -e .[second-brain]); degraded to mock"
            )
        else:
            mode = "live"
    elif requested_mode in {"mock", ""}:
        mode = "mock"
        if requested_mode == "":
            notes.append(f"{ENV_MODE} unset; defaulting enabled runtime to mock")
    else:
        mode = "mock"
        notes.append(f"unrecognized {ENV_MODE}={requested_mode!r}; defaulting to mock")

    synthesis_enabled = mode in {"mock", "live"}
    config_status = {
        "disabled": "offline_disabled",
        "mock": "mock_ready",
        "live": "live_ready",
    }[mode]

    return SecondBrainConfig(
        mode=mode,
        enabled=enabled,
        claude_model=claude_model,
        max_input_chars=max_input_chars,
        max_output_tokens=max_output_tokens,
        api_key_configured=api_key_configured,
        external_llm_enabled=external_llm_enabled,
        anthropic_installed=anthropic_installed,
        synthesis_enabled=synthesis_enabled,
        config_status=config_status,
        notes=notes,
    )
