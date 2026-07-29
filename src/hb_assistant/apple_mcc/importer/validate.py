"""Batch/item validation for importer."""

from __future__ import annotations

from typing import Any


class ValidationError(ValueError):
    pass


REQUIRED_COMMON = ("domain", "payload_hash", "observed_at_utc")


def validate_item(item: dict[str, Any]) -> None:
    for k in REQUIRED_COMMON:
        if k not in item or item[k] in (None, ""):
            raise ValidationError(f"missing:{k}")
    domain = item["domain"]
    if domain not in {"mail", "calendar", "contacts"}:
        raise ValidationError("bad_domain")
    if domain == "mail" and "account_name" not in item and "account_locator_hash" not in item:
        raise ValidationError("mail_account_required")
