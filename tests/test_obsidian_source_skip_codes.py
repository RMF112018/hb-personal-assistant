"""Skip-code normalization: new code-less skips never land as NULL, distinct from legacy data."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_skip_codes import (
    SKIP_CODES,
    TOO_LARGE,
    UNSPECIFIED_SKIP,
    normalize_skip_code,
)
from hb_assistant.store.migrator import SQLiteMigrator


def test_normalize_skip_code_fills_empty_only() -> None:
    assert normalize_skip_code(None) == UNSPECIFIED_SKIP
    assert normalize_skip_code("") == UNSPECIFIED_SKIP
    assert normalize_skip_code("   ") == UNSPECIFIED_SKIP
    assert normalize_skip_code("excluded_path") == "excluded_path"
    assert normalize_skip_code(TOO_LARGE) == "too_large"
    # The fallback itself is part of the recognized vocabulary.
    assert UNSPECIFIED_SKIP in SKIP_CODES


def _repo(tmp_path: Path) -> tuple[SourceIndexRepository, str]:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return SourceIndexRepository(db), db


def test_complete_event_coalesces_codeless_skip(tmp_path: Path) -> None:
    """A new skip with error_code=None is stamped 'unspecified_skip' (a regression signal)."""
    repo, _db = _repo(tmp_path)
    eid = repo.enqueue_event(event_type="modified", rel_path="x/y.md", source_root_key="proj")
    repo.complete_event(eid, "skipped")  # no code passed
    by_code = repo.index_status()["skipped_by_code"]
    assert by_code.get(UNSPECIFIED_SKIP) == 1
    assert "unspecified" not in by_code  # NOT the legacy read-time NULL bucket


def test_complete_event_preserves_named_skip(tmp_path: Path) -> None:
    repo, _db = _repo(tmp_path)
    eid = repo.enqueue_event(event_type="modified", rel_path="big.zip", source_root_key="proj")
    repo.complete_event(eid, "skipped", error_code=TOO_LARGE)
    assert repo.index_status()["skipped_by_code"].get(TOO_LARGE) == 1


def test_non_skip_status_keeps_none(tmp_path: Path) -> None:
    """done/error coalescing must not happen — only skipped is normalized."""
    repo, db = _repo(tmp_path)
    eid = repo.enqueue_event(event_type="modified", rel_path="ok.md", source_root_key="proj")
    repo.complete_event(eid, "done")
    with sqlite3.connect(db) as c:
        row = c.execute(
            "SELECT status, error_code FROM source_intelligence_events WHERE event_id=?", (eid,)
        ).fetchone()
    assert row[0] == "done"
    assert row[1] is None


def test_legacy_null_and_new_unspecified_are_distinct(tmp_path: Path) -> None:
    """Legacy NULL skip rows roll up as 'unspecified'; new code-less skips as 'unspecified_skip'."""
    repo, db = _repo(tmp_path)
    # Simulate a legacy historical skip row written before normalization (error_code NULL).
    with sqlite3.connect(db) as c:
        c.execute(
            "INSERT INTO source_intelligence_events "
            "(event_id, rel_path, source_root_key, event_type, status, attempts, created_at, updated_at) "
            "VALUES ('legacy1','old/a.md','proj','modified','skipped',1,'2000-01-01T00:00:00+00:00','2000-01-01T00:00:00+00:00')"
        )
        c.commit()
    # A new code-less skip via the normalized write boundary.
    eid = repo.enqueue_event(event_type="modified", rel_path="new/b.md", source_root_key="proj")
    repo.complete_event(eid, "skipped")
    by_code = repo.index_status()["skipped_by_code"]
    assert by_code.get("unspecified") == 1        # legacy NULL bucket (read-time coalesce)
    assert by_code.get(UNSPECIFIED_SKIP) == 1     # new regression bucket (write-time coalesce)
