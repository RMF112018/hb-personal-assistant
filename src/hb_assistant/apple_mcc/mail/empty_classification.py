"""Confirmed-empty mail classification (no fabricated bodies)."""

from __future__ import annotations

from enum import Enum


class EmptyDisposition(str, Enum):
    CONFIRMED_EMPTY = "confirmed_empty"
    RETRIED = "retried"
    UNKNOWN = "unknown"
    OUT_OF_SCOPE = "out_of_scope"


def classify_empty(*, byte_length: int, provider_flags: dict | None = None) -> EmptyDisposition:
    provider_flags = provider_flags or {}
    if byte_length == 0 and provider_flags.get("confirmed_empty"):
        return EmptyDisposition.CONFIRMED_EMPTY
    if byte_length == 0:
        return EmptyDisposition.UNKNOWN
    return EmptyDisposition.OUT_OF_SCOPE
