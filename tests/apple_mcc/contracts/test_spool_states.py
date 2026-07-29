"""Spool state machine tests."""

from __future__ import annotations

import pytest

from hb_assistant.apple_mcc.contracts.spool_states import SpoolState, can_transition, transition


def test_happy_path() -> None:
    s = SpoolState.CAPTURED
    s = transition(s, SpoolState.QUEUED)
    s = transition(s, SpoolState.TRANSPORTING)
    s = transition(s, SpoolState.DELIVERED)
    s = transition(s, SpoolState.ACKED)
    assert s is SpoolState.ACKED
    assert not can_transition(SpoolState.ACKED, SpoolState.QUEUED)


def test_illegal() -> None:
    with pytest.raises(ValueError):
        transition(SpoolState.CAPTURED, SpoolState.ACKED)
