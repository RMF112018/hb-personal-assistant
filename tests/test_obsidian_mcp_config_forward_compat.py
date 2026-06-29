"""Forward-compatible config loading: unknown persisted keys must not crash an older build.

A newer feature branch may write config keys this code does not know yet. ``load_config``
must tolerate them (drop + warn) instead of 500ing, while the typed patch path keeps
``extra="forbid"`` so programmer error is still rejected and invalid *values* on known
keys still raise.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from hb_assistant.obsidian_mcp import config as config_mod
from hb_assistant.obsidian_mcp.config import (
    ObsidianMcpConfig,
    ObsidianMcpConfigPatch,
    load_config,
    load_config_with_warnings,
)


def _point_config_at(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cfg = tmp_path / "obsidian_mcp_config.json"
    monkeypatch.setattr(config_mod, "config_path", lambda: cfg)
    return cfg


def test_missing_file_returns_default_no_warnings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _point_config_at(tmp_path, monkeypatch)
    cfg, warnings = load_config_with_warnings()
    assert isinstance(cfg, ObsidianMcpConfig)
    assert warnings == []


def test_unknown_key_is_dropped_and_warned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _point_config_at(tmp_path, monkeypatch)
    path.write_text(
        json.dumps(
            {
                "port": 3010,
                # keys a future branch added that this build does not model:
                "some_future_field": True,
                "another_unknown": "x",
            }
        ),
        encoding="utf-8",
    )
    cfg, warnings = load_config_with_warnings()
    assert cfg.port == 3010
    assert len(warnings) == 1
    assert warnings[0].startswith("unknown_keys_ignored:")
    # both unknown keys reported, sorted, csv-joined
    assert "another_unknown" in warnings[0]
    assert "some_future_field" in warnings[0]
    # load_config() delegates and discards warnings (never crashes)
    assert load_config().port == 3010


def test_known_keys_only_yields_no_warnings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _point_config_at(tmp_path, monkeypatch)
    path.write_text(json.dumps({"port": 3011, "enabled": True}), encoding="utf-8")
    cfg, warnings = load_config_with_warnings()
    assert cfg.port == 3011
    assert cfg.enabled is True
    assert warnings == []


def test_invalid_value_on_known_key_still_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _point_config_at(tmp_path, monkeypatch)
    # port out of range is real corruption, not forward-compat — must still raise.
    path.write_text(json.dumps({"port": 999999}), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_config_with_warnings()


def test_patch_model_still_forbids_unknown_keys() -> None:
    # The typed patch path is unchanged: extra="forbid" still rejects programmer error.
    with pytest.raises(ValidationError):
        ObsidianMcpConfigPatch.model_validate({"definitely_not_a_field": 1})
