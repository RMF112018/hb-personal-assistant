"""Phase 08A Prompt 03 — second-brain config resolution (deterministic, offline).

Proves fail-closed mode resolution and that the Anthropic API key value is never
stored on the resolved config snapshot.
"""

from __future__ import annotations

import importlib.util

import pytest

from hb_assistant.config.models import AppConfig, SecurityConfig
from hb_assistant.construction.second_brain import config as cfg_mod
from hb_assistant.construction.second_brain.config import load_second_brain_config

_SECRET = "sk-ant-THISVALUEMUSTNEVERLEAK"


def _app(*, external_llm: bool) -> AppConfig:
    return AppConfig(security=SecurityConfig(external_llm_enabled=external_llm))


def test_disabled_by_default() -> None:
    c = load_second_brain_config(app_config=_app(external_llm=False), env={})
    assert c.mode == "disabled"
    assert c.enabled is False
    assert c.synthesis_enabled is False
    assert c.config_status == "offline_disabled"


def test_enabled_defaults_to_mock() -> None:
    c = load_second_brain_config(
        app_config=_app(external_llm=False),
        env={"HB_SECOND_BRAIN_ENABLED": "1"},
    )
    assert c.mode == "mock"
    assert c.synthesis_enabled is True
    assert c.config_status == "mock_ready"


def test_live_requires_enabled() -> None:
    # mode=live requested but not enabled -> disabled (fail-closed)
    c = load_second_brain_config(
        app_config=_app(external_llm=True),
        env={"HB_SECOND_BRAIN_MODE": "live", "HB_ANTHROPIC_API_KEY": _SECRET},
    )
    assert c.mode == "disabled"


def test_live_requires_external_llm_master_switch() -> None:
    c = load_second_brain_config(
        app_config=_app(external_llm=False),
        env={
            "HB_SECOND_BRAIN_ENABLED": "1",
            "HB_SECOND_BRAIN_MODE": "live",
            "HB_ANTHROPIC_API_KEY": _SECRET,
        },
    )
    assert c.mode == "mock"  # degraded, not live


def test_live_requires_api_key() -> None:
    c = load_second_brain_config(
        app_config=_app(external_llm=True),
        env={"HB_SECOND_BRAIN_ENABLED": "1", "HB_SECOND_BRAIN_MODE": "live"},
    )
    assert c.mode == "mock"
    assert c.api_key_configured is False


def test_live_requires_anthropic_installed_degrades_to_mock() -> None:
    # anthropic is NOT in the base install — even fully configured, degrade to mock.
    assert importlib.util.find_spec("anthropic") is None
    c = load_second_brain_config(
        app_config=_app(external_llm=True),
        env={
            "HB_SECOND_BRAIN_ENABLED": "1",
            "HB_SECOND_BRAIN_MODE": "live",
            "HB_ANTHROPIC_API_KEY": _SECRET,
        },
    )
    assert c.mode == "mock"


def test_live_resolves_when_all_gates_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    c = load_second_brain_config(
        app_config=_app(external_llm=True),
        env={
            "HB_SECOND_BRAIN_ENABLED": "1",
            "HB_SECOND_BRAIN_MODE": "live",
            "HB_ANTHROPIC_API_KEY": _SECRET,
        },
    )
    assert c.mode == "live"
    assert c.synthesis_enabled is True
    assert c.config_status == "live_ready"
    assert c.anthropic_installed is True


def test_api_key_value_never_stored() -> None:
    c = load_second_brain_config(
        app_config=_app(external_llm=True),
        env={
            "HB_SECOND_BRAIN_ENABLED": "1",
            "HB_SECOND_BRAIN_MODE": "live",
            "HB_ANTHROPIC_API_KEY": _SECRET,
        },
    )
    assert c.api_key_configured is True
    blob = c.model_dump_json()
    assert _SECRET not in blob
    assert _SECRET not in json_of(c.dependency_status())


def test_overrides_parse() -> None:
    c = load_second_brain_config(
        app_config=_app(external_llm=False),
        env={
            "HB_SECOND_BRAIN_ENABLED": "1",
            "HB_CLAUDE_MODEL": "claude-sonnet-4-6",
            "HB_CLAUDE_MAX_INPUT_CHARS": "12000",
            "HB_CLAUDE_MAX_OUTPUT_TOKENS": "999",
        },
    )
    assert c.claude_model == "claude-sonnet-4-6"
    assert c.max_input_chars == 12000
    assert c.max_output_tokens == 999


def test_bad_int_overrides_fall_back_to_defaults() -> None:
    c = load_second_brain_config(
        app_config=_app(external_llm=False),
        env={
            "HB_SECOND_BRAIN_ENABLED": "1",
            "HB_CLAUDE_MAX_INPUT_CHARS": "not-a-number",
            "HB_CLAUDE_MAX_OUTPUT_TOKENS": "-5",
        },
    )
    assert c.max_input_chars == cfg_mod.DEFAULT_MAX_INPUT_CHARS
    assert c.max_output_tokens == cfg_mod.DEFAULT_MAX_OUTPUT_TOKENS


def json_of(obj: object) -> str:
    import json

    return json.dumps(obj)
