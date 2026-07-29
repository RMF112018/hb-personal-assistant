"""Contacts fetch (fixture + optional live probe)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hb_assistant.apple_mcc.contacts.feature_flags import contacts_enabled


def load_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_contacts_or_empty(*, fixtures: list[Path] | None = None) -> list[dict[str, Any]]:
    if not contacts_enabled():
        return []
    if fixtures:
        return [load_fixture(p) for p in fixtures]
    return []
