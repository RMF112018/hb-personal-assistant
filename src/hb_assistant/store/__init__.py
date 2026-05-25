"""Local SQLite state store and repositories (Phase 5).

Provides idempotent migrations, upsert-by-(source_type, source_key) for all core tables,
and integration points for the SourceLinkRegistry.
"""

from .connection import get_connection, transaction
from .migrator import SQLiteMigrator
from .repositories import Store

__all__ = [
    "get_connection",
    "transaction",
    "SQLiteMigrator",
    "Store",
]
