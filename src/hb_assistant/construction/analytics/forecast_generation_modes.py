"""Canonical forecast generation modes (Phase B — DB-native contract & routing boundary).

One typed source of truth for the three distinct generation behaviors the Run Center exposes. Before
this module the modes were bare strings (``"file_config"`` / ``"db_config"``) with no type, and true
DB-native generation was implicit (hidden behind an env flag on the db-config route). The enum makes
the boundary explicit without changing any wire/stored value.

Back-compat is deliberate: ``DB_CONFIG_PACKAGE.value == "db_config"`` so existing request rows, the
db-config route response, and the frontend (``generation_mode === 'db_config'``) stay byte-identical.
The *member name* carries the disambiguation (it is package-backed, NOT DB-native); ``db_backed`` is
never used as a mode value. ``StrEnum`` members are real ``str`` instances, so ``== "db_config"`` and
JSON/SQLite serialization are unchanged.
"""

from __future__ import annotations

from enum import StrEnum


class GenerationMode(StrEnum):
    """The three distinct forecast generation behaviors (persisted/API value == member value)."""

    # Legacy file/package-backed run (POST /api/forecast/runs).
    FILE_CONFIG = "file_config"
    # DB-config-backed *package* generation that consumes the live config snapshot
    # (POST /api/forecast/runs/db-config). Still package-backed — NOT DB-native. Value kept
    # "db_config" for back-compat; the member name is the only disambiguation.
    DB_CONFIG_PACKAGE = "db_config"
    # True DB-native generation + persistence (POST /api/forecast/runs/db-native). Fail-closed seam
    # only in Phase B; the calculation/persistence engine is supplied by later phases.
    DB_NATIVE = "db_native"
