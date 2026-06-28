"""Optional local-LLM summarization with a guaranteed deterministic fallback.

The summarize/extract tools prefer a local model (Ollama by default, optionally the
Anthropic ``second-brain`` extra) but must never *require* one: any unavailability,
import error, timeout, or malformed output falls back to the deterministic analysis from
``extract.py``. The returned ``mode`` tells the caller which path produced the result.

No prompt or model response is ever persisted. The backend is injectable (any object with
``generate_json(*, system, prompt) -> str``) so tests run without a live daemon.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from .config import ObsidianMcpConfig

_SUMMARY_KEYS = ("summary", "key_points", "action_items", "decisions", "entities", "suggested_tags", "suggested_links")

_SYSTEM_PROMPT = (
    "You summarize a single Obsidian note or email for a construction project executive. "
    "Return ONLY a JSON object with keys: summary (string), key_points (string array), "
    "action_items (string array), decisions (string array), entities (string array), "
    "suggested_tags (string array), suggested_links (string array). Be concise and factual; "
    "do not invent facts not present in the text."
)


class GenerationBackend(Protocol):
    def generate_json(self, *, system: str, prompt: str) -> str: ...


def _resolve_backend(config: ObsidianMcpConfig) -> GenerationBackend | None:
    """Construct the configured local-model backend, or None if unavailable."""
    provider = config.summarization_provider
    try:
        if provider == "ollama":
            from hb_assistant.construction.classification.client import OllamaChatClient

            return OllamaChatClient(model=config.summarization_model)
        if provider == "anthropic":
            return _AnthropicBackend(model=config.summarization_model)
    except Exception:  # noqa: BLE001 - optional dependency / construction import absent
        return None
    return None


def summarize(
    config: ObsidianMcpConfig,
    *,
    text: str,
    deterministic: dict[str, Any],
    backend: GenerationBackend | None = None,
) -> tuple[dict[str, Any], str]:
    """Return (result, mode). ``mode`` is ``"llm"`` or ``"deterministic_fallback"``."""
    if config.summarization_backend == "deterministic":
        return dict(deterministic), "deterministic_fallback"
    chosen = backend or _resolve_backend(config)
    if chosen is None:
        return dict(deterministic), "deterministic_fallback"
    try:
        raw = chosen.generate_json(system=_SYSTEM_PROMPT, prompt=text)
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("non_object_response")
    except (RuntimeError, ValueError, TypeError, KeyError):
        # RuntimeError covers OllamaUnavailable; ValueError covers JSON decode errors.
        return dict(deterministic), "deterministic_fallback"
    return _merge(data, deterministic), "llm"


def _merge(data: dict[str, Any], deterministic: dict[str, Any]) -> dict[str, Any]:
    """Take model fields where present and well-typed; fall back per-field otherwise."""
    result = dict(deterministic)
    for key in _SUMMARY_KEYS:
        value = data.get(key)
        if key == "summary":
            if isinstance(value, str) and value.strip():
                result[key] = value.strip()
        elif isinstance(value, list):
            result[key] = [str(v).strip() for v in value if str(v).strip()]
    return result


class _AnthropicBackend:
    """Lazy Anthropic adapter (only used when summarization_provider == 'anthropic')."""

    def __init__(self, *, model: str) -> None:
        from anthropic import Anthropic  # noqa: PLC0415 - optional 'second-brain' extra

        self._client = Anthropic()
        self._model = model

    def generate_json(self, *, system: str, prompt: str) -> str:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system + " Respond with JSON only.",
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [block.text for block in message.content if getattr(block, "type", None) == "text"]
        return "".join(parts)
