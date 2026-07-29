"""Historical empty classifier (no fabricated bodies)."""

from __future__ import annotations

from hb_assistant.apple_mcc.mail.empty_classification import EmptyDisposition, classify_empty


def classify_row(*, byte_length: int, confirmed: bool = False) -> EmptyDisposition:
    return classify_empty(byte_length=byte_length, provider_flags={"confirmed_empty": confirmed})
