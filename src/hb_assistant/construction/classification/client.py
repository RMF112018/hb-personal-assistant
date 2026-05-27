"""Minimal Ollama chat client for strict-JSON classification.

POSTs to ``/api/generate`` with ``format: "json"`` so the local Ollama daemon
returns a single-shot JSON object. The shape of that object is validated
downstream by :mod:`validator` against the Pydantic
:class:`ModelClassification` schema.

Mirrors the HTTP shape of :class:`hb_assistant.retrieval.embedder.OllamaEmbedder`
but is generation-focused (not embeddings). Subclass-friendly so tests can
inject a fake without monkeypatching ``requests``.
"""

from __future__ import annotations

import requests


class OllamaUnavailable(RuntimeError):
    """Raised when the local Ollama daemon cannot be reached or returns a non-200.

    The exception message is sanitized — it never echoes the request URL,
    response body, or any environmental detail beyond a short category code.
    """


class OllamaChatClient:
    DEFAULT_BASE_URL = "http://localhost:11434"
    GENERATE_PATH = "/api/generate"

    def __init__(
        self,
        *,
        model: str,
        base_url: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._model = model
        self._base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._timeout = timeout

    @property
    def model(self) -> str:
        return self._model

    def generate_json(self, *, system: str, prompt: str) -> str:
        """Issue a single-shot JSON-mode generation. Returns the raw response text.

        Validation is performed by the caller via
        :func:`hb_assistant.construction.classification.validator.parse_and_validate`.
        """

        url = self._base_url + self.GENERATE_PATH
        payload = {
            "model": self._model,
            "system": system,
            "prompt": prompt,
            "format": "json",
            "stream": False,
        }
        try:
            r = requests.post(url, json=payload, timeout=self._timeout)
        except requests.RequestException:
            raise OllamaUnavailable("ollama_request_failed") from None
        if r.status_code != 200:
            raise OllamaUnavailable(f"ollama_status_{r.status_code}")
        try:
            body = r.json()
        except ValueError:
            raise OllamaUnavailable("ollama_invalid_envelope") from None
        response = body.get("response")
        if not isinstance(response, str):
            raise OllamaUnavailable("ollama_missing_response_field")
        return response
