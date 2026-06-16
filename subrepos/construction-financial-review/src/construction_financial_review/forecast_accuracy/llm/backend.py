"""Generation backends. Production uses the live OllamaClient; tests inject StaticBackend."""
from __future__ import annotations

from typing import Protocol

from .client import OllamaUnavailable


class GenerationBackend(Protocol):
    def generate_json(self, *, system: str, prompt: str) -> str:  # pragma: no cover - protocol
        ...


class StaticBackend:
    """Offline test backend returning canned JSON (or raising), no daemon/network."""

    def __init__(self, *, outputs: list[str] | None = None, raise_unavailable: bool = False,
                 error_code: str = "ollama_request_failed"):
        self._outputs = list(outputs) if outputs else ["{}"]
        self._raise = raise_unavailable
        self._error_code = error_code
        self._calls = 0

    def generate_json(self, *, system: str, prompt: str) -> str:
        if self._raise:
            raise OllamaUnavailable(self._error_code)
        idx = min(self._calls, len(self._outputs) - 1)
        self._calls += 1
        return self._outputs[idx]
