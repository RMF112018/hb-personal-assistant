"""Schedule clean-DB path guards — delegates to neutral config.db_path_guard only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hb_assistant.config.db_path_guard import (
    assert_clean_copy_path,
    assert_not_live_db,
    is_live_db_path,
    is_under_clean_db_copy,
    resolve_clean_copy_guard,
)

__all__ = [
    "assert_clean_copy_path",
    "assert_not_live_db",
    "is_live_db_path",
    "is_under_clean_db_copy",
    "resolve_clean_copy_guard",
]


def require_confirm_clean_copy(confirm: bool) -> None:
    if not confirm:
        raise ValueError("--confirm-clean-copy is required for this operation")
