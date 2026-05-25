"""AliasResolver for body mention detection.

Defaults to Bobby Fetting variants from source-rules.example.yml (Phase 6).
Case-insensitive substring match on redacted preview only.
"""

from __future__ import annotations

from typing import List


DEFAULT_BOBBY_ALIASES: List[str] = [
    "Bobby",
    "Bobby Fetting",
    "Robert Fetting",
    "bfetting",
    "bfetting@outlook.com",
    "bfetting@hedrickbrothers.com",
]


class AliasResolver:
    """Resolves whether a (redacted) text mentions any of the configured aliases."""

    def __init__(self, aliases: List[str] | None = None):
        self.aliases = aliases or DEFAULT_BOBBY_ALIASES

    def matches(self, text: str | None) -> bool:
        if not text:
            return False
        t = text.lower()
        return any(alias.lower() in t for alias in self.aliases)
