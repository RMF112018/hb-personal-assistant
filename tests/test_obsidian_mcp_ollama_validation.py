"""A1.2 — Ollama model validation, configurable summary timeout, and distinct fallback reasons.

Covers ``list_ollama_models`` (/api/tags parsing), ``validate_summary_model`` (bare-tag
resolution + missing/unavailable), the configurable summary timeout threading into the
Ollama client, and ``summarize`` returning specific failure category codes instead of a
single generic fallback. No live daemon required — ``requests`` and the backend are faked.
"""

from __future__ import annotations

from typing import Any

import pytest

from hb_assistant.construction.classification import client as ollama_client
from hb_assistant.construction.classification.client import (
    OllamaUnavailable,
    list_ollama_models,
)
from hb_assistant.obsidian_mcp import llm
from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig

DETERMINISTIC = {"summary": "det", "key_points": [], "action_items": [], "decisions": [], "entities": []}


class _FakeResponse:
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


# --------------------------------------------------------------------------- list_ollama_models


def test_list_ollama_models_parses_and_sorts(monkeypatch: pytest.MonkeyPatch) -> None:
    def _get(url: str, timeout: float = 5.0) -> _FakeResponse:
        assert url.endswith("/api/tags")
        return _FakeResponse(200, {"models": [{"name": "qwen2.5:14b"}, {"name": "llama3.1:8b"}]})

    monkeypatch.setattr(ollama_client.requests, "get", _get)
    assert list_ollama_models() == ["llama3.1:8b", "qwen2.5:14b"]


def test_list_ollama_models_raises_on_non_200(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ollama_client.requests, "get", lambda url, timeout=5.0: _FakeResponse(500, {}))
    with pytest.raises(OllamaUnavailable):
        list_ollama_models()


# ------------------------------------------------------------------------ validate_summary_model


def _patch_models(monkeypatch: pytest.MonkeyPatch, models: list[str]) -> None:
    monkeypatch.setattr(llm, "_perf_counter", lambda: 0.0)
    monkeypatch.setattr(
        "hb_assistant.construction.classification.client.list_ollama_models",
        lambda **_: models,
    )


def test_validate_model_exact_match(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_models(monkeypatch, ["llama3.1:8b"])
    report = llm.validate_summary_model(ObsidianMcpConfig(summarization_model="llama3.1:8b"))
    assert report["available"] is True
    assert report["match"] == "exact"
    assert report["resolved"] == "llama3.1:8b"


def test_validate_model_bare_tag_resolves(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_models(monkeypatch, ["llama3.1:8b", "qwen2.5:14b"])
    report = llm.validate_summary_model(ObsidianMcpConfig(summarization_model="llama3.1"))
    assert report["match"] == "tag_resolved"
    assert report["resolved"] == "llama3.1:8b"


def test_validate_model_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_models(monkeypatch, ["mistral-nemo:12b"])
    report = llm.validate_summary_model(ObsidianMcpConfig(summarization_model="llama3.1"))
    assert report["match"] == "missing"
    assert report["resolved"] is None


def test_validate_model_daemon_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(**_: Any) -> list[str]:
        raise OllamaUnavailable("ollama_request_failed")

    monkeypatch.setattr("hb_assistant.construction.classification.client.list_ollama_models", _boom)
    report = llm.validate_summary_model(ObsidianMcpConfig(summarization_model="llama3.1"))
    assert report["available"] is False
    assert report["match"] == "ollama_unavailable"


# --------------------------------------------------------------------- configurable summary timeout


def test_resolve_backend_threads_configured_timeout() -> None:
    config = ObsidianMcpConfig(
        summarization_provider="ollama", source_summary_ollama_timeout_seconds=45
    )
    backend = llm._resolve_backend(config)
    assert backend is not None
    assert backend._timeout == 45.0  # not the client's 15.0 default


# ------------------------------------------------------------------------ summarize reason codes


class _Backend:
    def __init__(self, *, raises: Exception | None = None, raw: str | None = None) -> None:
        self._raises = raises
        self._raw = raw

    def generate_json(self, *, system: str, prompt: str) -> str:
        if self._raises is not None:
            raise self._raises
        assert self._raw is not None
        return self._raw


def _summ(backend: Any, *, deterministic_backend: bool = False) -> tuple[dict[str, Any], str, str]:
    cfg = ObsidianMcpConfig(
        summarization_backend="deterministic" if deterministic_backend else "auto"
    )
    return llm.summarize(cfg, text="some text", deterministic=DETERMINISTIC, backend=backend)


def test_summarize_ok() -> None:
    _r, mode, reason = _summ(_Backend(raw='{"summary": "model said"}'))
    assert mode == "llm" and reason == "ok"


def test_summarize_disabled() -> None:
    _r, mode, reason = _summ(_Backend(raw="{}"), deterministic_backend=True)
    assert mode == "deterministic_fallback" and reason == "disabled"


def test_summarize_timeout() -> None:
    _r, mode, reason = _summ(_Backend(raises=OllamaUnavailable("ollama_timeout")))
    assert mode == "deterministic_fallback" and reason == "timeout"


def test_summarize_empty_response_field() -> None:
    _r, mode, reason = _summ(_Backend(raises=OllamaUnavailable("ollama_missing_response_field")))
    assert reason == "empty_response"


def test_summarize_invalid_json() -> None:
    _r, mode, reason = _summ(_Backend(raw="not json at all"))
    assert reason == "invalid_json"


def test_summarize_empty_raw() -> None:
    _r, mode, reason = _summ(_Backend(raw="   "))
    assert reason == "empty_response"


def test_summarize_ollama_unavailable_when_no_backend() -> None:
    _r, mode, reason = llm.summarize(
        ObsidianMcpConfig(summarization_backend="auto", summarization_provider="anthropic"),
        text="x",
        deterministic=DETERMINISTIC,
        backend=None,
    )
    # anthropic extra is not installed in CI → backend resolves to None → category code.
    assert mode == "deterministic_fallback" and reason == "ollama_unavailable"


def test_generate_json_maps_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def _post(url: str, json: Any = None, timeout: float = 15.0) -> Any:
        raise ollama_client.requests.Timeout()

    monkeypatch.setattr(ollama_client.requests, "post", _post)
    backend = ollama_client.OllamaChatClient(model="llama3.1:8b")
    with pytest.raises(OllamaUnavailable) as ei:
        backend.generate_json(system="s", prompt="p")
    assert str(ei.value) == "ollama_timeout"
