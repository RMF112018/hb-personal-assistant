"""Batch envelope tests."""

from __future__ import annotations

import pytest

from hb_assistant.apple_mcc.contracts.batch_envelope import BatchEnvelope


def test_envelope_roundtrip() -> None:
    env = BatchEnvelope.from_items(
        batch_id="b1",
        capture_run_id="r1",
        domain="mail",
        items=[{"id": "1"}],
        created_utc="2026-07-29T00:00:00Z",
    )
    env.validate()
    line = env.to_json_line()
    assert "apple_mcc_batch_envelope_v1" in line


def test_tamper_fails() -> None:
    env = BatchEnvelope.from_items(
        batch_id="b1",
        capture_run_id="r1",
        domain="mail",
        items=[{"id": "1"}],
        created_utc="2026-07-29T00:00:00Z",
    )
    env.items.append({"id": "2"})
    with pytest.raises(ValueError):
        env.validate()
