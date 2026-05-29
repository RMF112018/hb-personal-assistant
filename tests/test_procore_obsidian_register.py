"""Phase 04A Prompt 09A — register projection from procore_live_records.

All tests are 100% local: no network, no real vault, no real app-support DB.
We seed an isolated SQLite DB through the V6 migrator + the existing
``upsert_procore_live_record`` repository helper so the schema and JSON
shape stay in lockstep with the production write path.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from hb_assistant.procore.obsidian import (
    _ENDPOINT_TO_REGISTER_TEMPLATE,
    _REGISTER_FILENAME_SUFFIX,
    procore_obsidian_register,
    reset_procore_obsidian_caches,
)
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_repositories import (
    record_sync_run_start,
    upsert_procore_live_record,
)

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")


def _new_db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        path = Path(tf.name)
    SQLiteMigrator(db_path=str(path)).apply()
    return path


def _seed_run(db: Path, *, sync_run_id: str = "run-09a", endpoint_id: str = "rfis") -> None:
    record_sync_run_start(
        sync_run_id=sync_run_id,
        endpoint_id=endpoint_id,
        command_endpoint=endpoint_id,
        legacy_endpoint_alias=None,
        project_key="tropical",
        procore_project_id="2525840",
        company_id="5280",
        mode="live_apply",
        started_at_utc="2026-05-29T00:00:00+00:00",
        db_path=db,
    )


def _insert(
    db: Path,
    *,
    endpoint_id: str,
    record_id: str,
    fields: dict,
    review_required: bool = False,
    sensitive_reason: str | None = None,
    sync_run_id: str = "run-09a",
) -> None:
    upsert_procore_live_record(
        project_key="tropical",
        procore_project_id="2525840",
        endpoint_id=endpoint_id,
        procore_record_id=record_id,
        parent_procore_id=fields.get("__parent"),
        normalized_fields={k: v for k, v in fields.items() if k != "__parent"},
        review_required=review_required,
        sensitive_reason=sensitive_reason,
        source_url_redacted=f"/rest/v1.0/projects/2525840/{endpoint_id}",
        last_sync_run_id=sync_run_id,
        now_utc="2026-05-29T00:00:00+00:00",
        db_path=db,
    )


@pytest.fixture(autouse=True)
def _clear_caches() -> Iterator[None]:
    reset_procore_obsidian_caches()
    yield
    reset_procore_obsidian_caches()


# --- dry-run ----------------------------------------------------------------

def test_dry_run_renders_table_and_excludes_review_required() -> None:
    db = _new_db()
    _seed_run(db, endpoint_id="rfis")
    _insert(db, endpoint_id="rfis", record_id="100", fields={
        "number": "RFI-100", "subject": "Door spec", "status": "open", "due_date": "2026-06-01",
    })
    _insert(db, endpoint_id="rfis", record_id="101", fields={
        "number": "RFI-101", "subject": "Slab elev", "status": "closed", "due_date": "2026-05-15",
    })
    _insert(db, endpoint_id="rfis", record_id="200", fields={
        "number": "RFI-200", "subject": "redacted", "status": "open",
    }, review_required=True, sensitive_reason="assignee_missing")

    result = procore_obsidian_register(
        project_key="tropical",
        endpoint_id="rfis",
        dry_run=True,
        apply=False,
        db_path=db,
    )

    assert result["ok"] is True
    assert result["status"] == "ok"
    assert result["source_table"] == "procore_live_records"
    assert result["family_template"] == "rfi_register"
    assert result["count_from_sqlite"] == 3
    assert result["review_count"] == 1
    assert result["review_items"][0]["procore_record_id"] == "200"
    assert result["dry_run"] is True
    assert result["written_paths"] == []
    assert "RFI-100" in result["rendered"]
    assert "RFI-101" in result["rendered"]
    assert "RFI-200" not in result["rendered"]


def test_dry_run_empty_table_when_all_rows_review_required() -> None:
    db = _new_db()
    _seed_run(db, endpoint_id="rfis")
    _insert(db, endpoint_id="rfis", record_id="300", fields={"number": "RFI-300"},
            review_required=True, sensitive_reason="assignee_missing")

    result = procore_obsidian_register(
        project_key="tropical", endpoint_id="rfis",
        dry_run=True, apply=False, db_path=db,
    )

    assert result["ok"] is True
    assert result["count_from_sqlite"] == 1
    assert result["review_count"] == 1
    assert "(no non-sensitive records in procore_live_records)" in result["rendered"]


# --- unsupported endpoint ---------------------------------------------------

def test_unsupported_endpoint_returns_structured_error() -> None:
    db = _new_db()
    result = procore_obsidian_register(
        project_key="tropical", endpoint_id="punch-items",
        dry_run=True, apply=False, db_path=db,
    )
    assert result["ok"] is False
    assert result["status"] == "unsupported_endpoint"
    assert "punch-items" in result["error"]
    assert "rfis" in result["error"]
    assert "next_steps" in result
    assert result["count_from_sqlite"] == 0


def test_endpoint_to_register_map_covers_supported_families() -> None:
    # Sanity check the contract.
    assert _ENDPOINT_TO_REGISTER_TEMPLATE["rfis"] == "rfi_register"
    assert _ENDPOINT_TO_REGISTER_TEMPLATE["submittals"] == "submittal_register"
    assert _ENDPOINT_TO_REGISTER_TEMPLATE["observations"] == "observation_register"
    assert _ENDPOINT_TO_REGISTER_TEMPLATE["meetings"] == "meeting_register"
    assert _ENDPOINT_TO_REGISTER_TEMPLATE["daily-log-weather"] == "daily_log_index"
    for unsupported in ("projects", "punch-items", "schedules", "activities"):
        assert unsupported not in _ENDPOINT_TO_REGISTER_TEMPLATE


# --- apply + idempotency ----------------------------------------------------

def test_apply_writes_marker_bounded_file_and_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = tmp_path / "construction-vault"
    vault.mkdir()
    monkeypatch.setenv("HB_CONSTRUCTION_VAULT_ROOT", str(vault))

    db = _new_db()
    _seed_run(db, endpoint_id="rfis")
    _insert(db, endpoint_id="rfis", record_id="100", fields={
        "number": "RFI-100", "subject": "First", "status": "open"
    })
    _insert(db, endpoint_id="rfis", record_id="101", fields={
        "number": "RFI-101", "subject": "Second", "status": "open"
    })

    first = procore_obsidian_register(
        project_key="tropical", endpoint_id="rfis",
        dry_run=False, apply=True, db_path=db,
    )
    assert first["ok"] is True
    assert len(first["written_paths"]) == 1
    written = Path(first["written_paths"][0])
    expected_suffix = _REGISTER_FILENAME_SUFFIX["rfi_register"]
    assert written.name == f"tropical.{expected_suffix}"
    assert written.parent == vault / "01_Projects"
    assert written.exists()

    first_bytes = written.read_bytes()
    assert b"<!-- HB-PROCORE-RFI-REGISTER:START -->" in first_bytes
    assert b"<!-- HB-PROCORE-RFI-REGISTER:END -->" in first_bytes
    assert b"RFI-100" in first_bytes
    assert b"RFI-101" in first_bytes

    second = procore_obsidian_register(
        project_key="tropical", endpoint_id="rfis",
        dry_run=False, apply=True, db_path=db,
    )
    assert second["ok"] is True
    second_bytes = written.read_bytes()
    assert second_bytes == first_bytes, "register apply must be byte-identical on rerun"


def test_apply_preserves_content_outside_marker_region(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = tmp_path / "construction-vault"
    vault.mkdir()
    monkeypatch.setenv("HB_CONSTRUCTION_VAULT_ROOT", str(vault))

    target_dir = vault / "01_Projects"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / f"tropical.{_REGISTER_FILENAME_SUFFIX['rfi_register']}"
    user_prefix = "# Operator notes (do not touch)\n\nManual section.\n"
    user_suffix = "\n## Trailing notes\nKeep me.\n"
    target_file.write_text(
        user_prefix
        + "<!-- HB-PROCORE-RFI-REGISTER:START -->\nold content\n<!-- HB-PROCORE-RFI-REGISTER:END -->\n"
        + user_suffix,
        encoding="utf-8",
    )

    db = _new_db()
    _seed_run(db, endpoint_id="rfis")
    _insert(db, endpoint_id="rfis", record_id="100", fields={"number": "RFI-100", "subject": "X"})

    procore_obsidian_register(
        project_key="tropical", endpoint_id="rfis",
        dry_run=False, apply=True, db_path=db,
    )

    contents = target_file.read_text(encoding="utf-8")
    assert contents.startswith(user_prefix)
    assert contents.endswith(user_suffix)
    assert "RFI-100" in contents
    assert "old content" not in contents


# --- endpoint families cross-check ------------------------------------------

def test_meeting_topics_endpoint_renders_topic_table_only() -> None:
    db = _new_db()
    _seed_run(db, endpoint_id="meeting-topics")
    _insert(db, endpoint_id="meeting-topics", record_id="500", fields={
        "title": "Schedule check-in", "status": "open", "due_date": "2026-06-10",
        "__parent": "5000",
    })

    result = procore_obsidian_register(
        project_key="tropical", endpoint_id="meeting-topics",
        dry_run=True, apply=False, db_path=db,
    )
    assert result["ok"] is True
    assert result["family_template"] == "meeting_register"
    rendered = result["rendered"]
    assert "Schedule check-in" in rendered
    # meeting (upper) table should be the empty placeholder; topic table populated.
    assert "## Meetings" in rendered
    assert "## Topics" in rendered


def test_submittal_endpoint_writes_submittal_register_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = tmp_path / "construction-vault"
    vault.mkdir()
    monkeypatch.setenv("HB_CONSTRUCTION_VAULT_ROOT", str(vault))
    db = _new_db()
    _seed_run(db, endpoint_id="submittals")
    _insert(db, endpoint_id="submittals", record_id="700", fields={
        "number": "SUB-700", "title": "HVAC shop drawings", "spec_section": "23 00 00",
        "status": "open", "due_date": "2026-07-01",
    })

    result = procore_obsidian_register(
        project_key="tropical", endpoint_id="submittals",
        dry_run=False, apply=True, db_path=db,
    )
    assert result["ok"] is True
    assert result["family_template"] == "submittal_register"
    written = Path(result["written_paths"][0])
    assert written.name == "tropical.procore-submittal-register.md"
    body = written.read_text(encoding="utf-8")
    assert "SUB-700" in body
    assert "HVAC shop drawings" in body


# --- canonical JSON parsing edge case ---------------------------------------

def test_corrupted_canonical_json_is_silently_tolerated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If canonical_json_redacted is unparseable, the row uses fallback columns
    (procore_record_number, title_redacted, status) so the projection never
    raises on per-row data."""
    db = _new_db()
    _seed_run(db, endpoint_id="rfis")
    _insert(db, endpoint_id="rfis", record_id="900", fields={
        "number": "RFI-900", "subject": "fine", "status": "open"
    })
    # Manually corrupt one row's canonical_json_redacted.
    import sqlite3
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "UPDATE procore_live_records SET canonical_json_redacted = ? "
            "WHERE procore_record_id = ?",
            ("not-json", "900"),
        )
        conn.commit()
    finally:
        conn.close()

    result = procore_obsidian_register(
        project_key="tropical", endpoint_id="rfis",
        dry_run=True, apply=False, db_path=db,
    )
    assert result["ok"] is True
    assert result["count_from_sqlite"] == 1
    assert "RFI-900" in result["rendered"]


# --- verify JSON serializability --------------------------------------------

def test_result_is_json_serializable() -> None:
    db = _new_db()
    _seed_run(db, endpoint_id="rfis")
    _insert(db, endpoint_id="rfis", record_id="100", fields={"number": "RFI-100"})
    result = procore_obsidian_register(
        project_key="tropical", endpoint_id="rfis",
        dry_run=True, apply=False, db_path=db,
    )
    # Must not raise.
    json.dumps(result)
