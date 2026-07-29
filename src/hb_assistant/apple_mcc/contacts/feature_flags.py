"""Contacts capture feature flags."""

from __future__ import annotations

import os


def contacts_enabled() -> bool:
    return os.environ.get("APPLE_MCC_CONTACTS_ENABLED", "1").strip() not in {"0", "false", "False"}
