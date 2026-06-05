"""Strict JSON + Pydantic validation for Ollama classification output.

Failures raise :class:`InvalidModelOutputError`. The exception message never
echoes the full raw output — only the first 200 characters of a sanitized
snippet. The router treats invalid output as a hard rejection (no decision is
persisted).
"""

from __future__ import annotations

import json

from pydantic import ValidationError

from .models import ModelClassification

_SNIPPET_CHARS = 200


class InvalidModelOutputError(ValueError):
    """Raised when the model's raw output cannot be parsed or fails schema validation."""

    def __init__(self, code: str, *, snippet: str = "", detail: str = "") -> None:
        self.code = code
        self.snippet = snippet[:_SNIPPET_CHARS] if snippet else ""
        self.detail = detail[:_SNIPPET_CHARS] if detail else ""
        super().__init__(self._format())

    def _format(self) -> str:
        parts = [f"invalid_model_output: {self.code}"]
        if self.detail:
            parts.append(f"detail={self.detail!r}")
        if self.snippet:
            parts.append(f"snippet={self.snippet!r}")
        return " ".join(parts)


def parse_and_validate(raw: str) -> ModelClassification:
    """Parse raw model output and validate against :class:`ModelClassification`.

    Raises :class:`InvalidModelOutputError` on any failure — never raises
    :class:`json.JSONDecodeError` or :class:`pydantic.ValidationError` directly.
    """

    if raw is None or not str(raw).strip():
        raise InvalidModelOutputError("empty_output", snippet=raw or "")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise InvalidModelOutputError(
            "json_parse_failed",
            snippet=raw,
            detail=str(e),
        ) from None
    if not isinstance(parsed, dict):
        raise InvalidModelOutputError("not_a_json_object", snippet=raw)
    try:
        return ModelClassification.model_validate(parsed)
    except ValidationError as e:
        # Use the count of errors as a stable detail — the full error list may
        # contain user-controlled raw values.
        raise InvalidModelOutputError(
            "schema_validation_failed",
            snippet=raw,
            detail=f"{len(e.errors())} validation error(s)",
        ) from None
