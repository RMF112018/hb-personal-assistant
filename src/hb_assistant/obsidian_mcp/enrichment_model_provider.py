"""Model provider abstraction for the enrichment worker (N8C-5).

``ModelProvider.generate(prompt, *, model, timeout_s) -> str`` returns raw model text. Two
implementations:

  * :class:`FakeModelProvider` — deterministic canned output for automated tests. **All tests use
    this; live Ollama is never required to run the suite.**
  * :class:`OllamaModelProvider` — thin wrapper over the existing
    ``construction.classification.client.OllamaChatClient`` (qwen2.5:14b via the local Ollama
    daemon). The client is imported lazily so importing this module never pulls ``requests`` (keeps
    the base install / worker-module import HTTP-free and the FakeModelProvider path dependency-free).

Providers never touch the DB or the vault — they only turn a prompt into text.
"""

from __future__ import annotations

from typing import Callable, Protocol

from .enrichment_models import DEFAULT_MODEL_NAME, RUNTIME_OLLAMA


class ModelUnavailable(RuntimeError):
    """The model runtime could not produce output (sanitized message — no env/URL/body detail)."""


class ModelProvider(Protocol):
    name: str
    runtime: str

    def generate(self, prompt: str, *, model: str, timeout_s: float) -> str:
        ...


class FakeModelProvider:
    """Deterministic in-process provider for tests. Maps a prompt to canned text via ``responder``.

    Default responder returns a per-job-type canned JSON payload keyed off a marker the worker embeds
    in the prompt (``[[job_type:...]]``), so a test needs no live model and gets stable output.
    """

    name = "fake"
    runtime = "fake"

    def __init__(self, responder: Callable[[str], str] | None = None) -> None:
        self._responder = responder or _default_fake_responder
        self.calls: list[dict[str, object]] = []

    def generate(self, prompt: str, *, model: str, timeout_s: float) -> str:
        self.calls.append({"prompt": prompt, "model": model, "timeout_s": timeout_s})
        return self._responder(prompt)


def _default_fake_responder(prompt: str) -> str:
    if "[[job_type:source_summary]]" in prompt:
        return (
            '{"summary": "Deterministic test summary of the source.", '
            '"key_points": ["point one", "point two"], "confidence": 0.7}'
        )
    if "[[job_type:claim_extraction]]" in prompt:
        return (
            '{"claims": [{"claim_type": "fact", "claim_text": "The kickoff is scheduled.", '
            '"evidence_excerpt": "Kickoff is scheduled for next week.", "confidence": 0.6}]}'
        )
    if "[[job_type:backlink_suggestions]]" in prompt:
        return (
            '{"suggestions": [{"target": "Related Note", "reason": "shared topic", '
            '"confidence": 0.5}]}'
        )
    return "{}"


class OllamaModelProvider:
    """Live provider backed by the local Ollama daemon (default model qwen2.5:14b)."""

    name = "ollama"
    runtime = RUNTIME_OLLAMA

    def __init__(self, *, base_url: str | None = None) -> None:
        self._base_url = base_url

    def generate(self, prompt: str, *, model: str = DEFAULT_MODEL_NAME, timeout_s: float = 60.0) -> str:
        # Lazy import: keep ``requests`` out of this module's import graph.
        from hb_assistant.construction.classification.client import (
            OllamaChatClient,
            OllamaUnavailable,
        )

        client = OllamaChatClient(model=model, base_url=self._base_url, timeout=timeout_s)
        system = (
            "You are a local enrichment model for a personal knowledge base. Respond with a single "
            "JSON object only — no prose, no markdown fences. Do not invent facts not supported by "
            "the provided source text."
        )
        try:
            return client.generate_json(system=system, prompt=prompt)
        except OllamaUnavailable as exc:
            raise ModelUnavailable(str(exc)) from None
