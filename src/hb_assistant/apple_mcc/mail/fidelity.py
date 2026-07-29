"""Mail capture fidelity classification."""

from __future__ import annotations

from enum import Enum


class FidelityClass(str, Enum):
    FULL_MIME = "full_mime"
    BODY_ONLY = "body_only"
    PREVIEW = "preview"
    METADATA = "metadata"
    CONFIRMED_EMPTY = "confirmed_empty"


def classify_fidelity(*, has_raw_eml: bool, body_text: str | None, body_html: str | None, preview: str | None) -> FidelityClass:
    if has_raw_eml:
        return FidelityClass.FULL_MIME
    if body_text or body_html:
        return FidelityClass.BODY_ONLY
    if preview:
        return FidelityClass.PREVIEW
    return FidelityClass.METADATA
