"""Stdlib-only Ollama client (no third-party deps).

Mirrors the parent repo's proven pattern: POST /api/generate with format=json, temperature 0 + fixed
seed for near-determinism, redacted category-code errors (never leak body/url/token). Readiness via
GET /api/tags. Used only against localhost.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Optional

DEFAULT_ENDPOINT = "http://localhost:11434"


class OllamaUnavailable(Exception):
    """Raised with a redacted category code only (no raw body/url/token)."""


class OllamaClient:
    def __init__(self, model: str, endpoint: str = DEFAULT_ENDPOINT,
                 temperature: float = 0.0, seed: int = 7, timeout: float = 60.0):
        self._model = model
        self._endpoint = endpoint.rstrip("/")
        self._temperature = temperature
        self._seed = seed
        self._timeout = timeout

    def available(self) -> tuple[bool, list]:
        """Return (server_up, installed_model_names). Never raises."""
        try:
            req = urllib.request.Request(f"{self._endpoint}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=min(self._timeout, 10.0)) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("name") for m in data.get("models", []) if m.get("name")]
            return True, models
        except Exception:
            return False, []

    def model_present(self) -> bool:
        up, models = self.available()
        if not up:
            return False
        # match exact or base name (qwen2.5:14b matches qwen2.5:14b)
        return any(m == self._model or m.split(":")[0] == self._model.split(":")[0] for m in models)

    def generate_json(self, *, system: str, prompt: str) -> str:
        """POST /api/generate (format=json). Returns the raw model 'response' string."""
        payload = {
            "model": self._model,
            "system": system,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {"temperature": self._temperature, "seed": self._seed},
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self._endpoint}/api/generate", data=body, method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                status = getattr(resp, "status", 200) or 200
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise OllamaUnavailable(f"ollama_status_{exc.code}")
        except urllib.error.URLError:
            raise OllamaUnavailable("ollama_request_failed")
        except TimeoutError:
            raise OllamaUnavailable("ollama_timeout")
        except Exception:
            raise OllamaUnavailable("ollama_request_failed")
        if status != 200:
            raise OllamaUnavailable(f"ollama_status_{status}")
        try:
            envelope = json.loads(raw)
        except ValueError:
            raise OllamaUnavailable("ollama_invalid_envelope")
        response = envelope.get("response")
        if not isinstance(response, str):
            raise OllamaUnavailable("ollama_missing_response_field")
        return response
