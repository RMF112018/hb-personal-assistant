"""Spool item state machine."""

from __future__ import annotations

from enum import Enum


class SpoolState(str, Enum):
    CAPTURED = "captured"
    QUEUED = "queued"
    TRANSPORTING = "transporting"
    DELIVERED = "delivered"
    ACKED = "acked"
    FAILED = "failed"
    QUARANTINED = "quarantined"


ALLOWED_TRANSITIONS: dict[SpoolState, frozenset[SpoolState]] = {
    SpoolState.CAPTURED: frozenset({SpoolState.QUEUED, SpoolState.FAILED, SpoolState.QUARANTINED}),
    SpoolState.QUEUED: frozenset({SpoolState.TRANSPORTING, SpoolState.FAILED, SpoolState.QUARANTINED}),
    SpoolState.TRANSPORTING: frozenset({SpoolState.DELIVERED, SpoolState.FAILED, SpoolState.QUEUED}),
    SpoolState.DELIVERED: frozenset({SpoolState.ACKED, SpoolState.FAILED}),
    SpoolState.ACKED: frozenset(),
    SpoolState.FAILED: frozenset({SpoolState.QUEUED, SpoolState.QUARANTINED}),
    SpoolState.QUARANTINED: frozenset(),
}


def can_transition(src: SpoolState, dst: SpoolState) -> bool:
    return dst in ALLOWED_TRANSITIONS.get(src, frozenset())


def transition(src: SpoolState, dst: SpoolState) -> SpoolState:
    if not can_transition(src, dst):
        raise ValueError(f"illegal_spool_transition:{src.value}->{dst.value}")
    return dst
