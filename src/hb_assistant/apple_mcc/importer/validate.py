"""Batch/item validation for importer."""

from __future__ import annotations

from typing import Any


class ValidationError(ValueError):
    pass


REQUIRED_COMMON = ("domain", "payload_hash", "observed_at_utc")


def _has_source_account(item: dict[str, Any], *fallback_keys: str) -> bool:
    for key in ("source_account",) + fallback_keys:
        val = item.get(key)
        if val is not None and str(val).strip():
            return True
    return False


def validate_item(item: dict[str, Any]) -> None:
    for k in REQUIRED_COMMON:
        if k not in item or item[k] in (None, ""):
            raise ValidationError(f"missing:{k}")
    domain = item["domain"]
    if domain not in {"mail", "calendar", "contacts"}:
        raise ValidationError("bad_domain")
    if domain == "mail" and "account_name" not in item and "account_locator_hash" not in item:
        raise ValidationError("mail_account_required")
    # V135: every domain must carry a human-readable source account (or legacy alias).
    if domain == "mail" and not _has_source_account(item, "account_name"):
        raise ValidationError("source_account_required")
    if domain == "calendar" and not _has_source_account(item, "source_title"):
        raise ValidationError("source_account_required")
    if domain == "contacts" and not _has_source_account(item, "container"):
        raise ValidationError("source_account_required")
