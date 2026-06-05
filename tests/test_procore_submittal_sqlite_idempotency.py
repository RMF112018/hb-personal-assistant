"""Phase 04 Prompt 05 — Submittal sync SQLite idempotency tests.

Mocks the audit gate and Procore HTTP client; the real assertion is that
``coord.apply()`` writes submittal parent + response + package rows into the
caller-supplied temp SQLite, and that re-running the same apply does not
duplicate any row.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from hb_assistant.construction.fixtures.procore import SUBMITTAL_SAMPLE_PAYLOAD
from hb_assistant.procore.sync import ProcoreSyncCoordinator


def _temp_db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        return Path(tf.name)


def _apply_once(coord: ProcoreSyncCoordinator) -> dict:
    with (
        patch.object(coord, "auditor") as mock_auditor,
        patch("hb_assistant.procore.sync.ProcoreHTTPClient") as mock_client_cls,
    ):
        mock_auditor.audit_endpoints_for_pilots.return_value = {"submittal": "available"}
        mock_client = MagicMock()
        mock_client.paginate.return_value = list(SUBMITTAL_SAMPLE_PAYLOAD)
        mock_client_cls.return_value = mock_client
        result = coord.apply(project_key="tropical", endpoints=["list-submittals"])
    return result  # type: ignore[return-value]


def _row_counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(str(db_path))
    try:
        submittals = conn.execute(
            "SELECT COUNT(*) FROM procore_synced_entities WHERE category = 'submittals'"
        ).fetchone()[0]
        responses = conn.execute(
            "SELECT COUNT(*) FROM procore_synced_entities WHERE category = 'submittal_responses'"
        ).fetchone()[0]
        packages = conn.execute(
            "SELECT COUNT(*) FROM procore_synced_entities WHERE category = 'submittal_packages'"
        ).fetchone()[0]
        watermarks = conn.execute(
            "SELECT COUNT(*) FROM procore_sync_watermarks WHERE endpoint_id = 'list-submittals'"
        ).fetchone()[0]
        return {
            "submittals": submittals,
            "responses": responses,
            "packages": packages,
            "watermarks": watermarks,
        }
    finally:
        conn.close()


def test_submittal_apply_persists_parents_responses_packages_separately() -> None:
    db = _temp_db()
    coord = ProcoreSyncCoordinator(db_path=db)
    receipt = _apply_once(coord)

    assert receipt["mode"] == "apply"
    assert receipt["persisted_to_sqlite"] is True
    entry = next(e for e in receipt["per_endpoint"] if e["endpoint_id"] == "list-submittals")
    assert entry["status"] == "success"
    assert entry["submittal_records_written"] == 3
    assert entry["response_records_written"] == 4
    assert entry["package_records_written"] == 2
    counts = _row_counts(db)
    assert counts["submittals"] == 3
    assert counts["responses"] == 4
    assert counts["packages"] == 2
    assert counts["watermarks"] == 1


def test_submittal_apply_is_idempotent_on_second_run() -> None:
    db = _temp_db()
    coord = ProcoreSyncCoordinator(db_path=db)
    _apply_once(coord)
    first = _row_counts(db)
    _apply_once(ProcoreSyncCoordinator(db_path=db))
    second = _row_counts(db)
    assert first == second
    assert second["submittals"] == 3
    assert second["responses"] == 4
    assert second["packages"] == 2


def test_submittal_apply_does_not_persist_raw_comment_text() -> None:
    db = _temp_db()
    coord = ProcoreSyncCoordinator(db_path=db)
    _apply_once(coord)

    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute("SELECT canonical_fields_json FROM procore_synced_entities").fetchall()
    finally:
        conn.close()

    serialized = "".join(row[0] for row in rows if row[0])
    for raw in SUBMITTAL_SAMPLE_PAYLOAD:
        for raw_response in raw["responses"]:
            assert raw_response["comment"] not in serialized
        for raw_package in raw["packages"]:
            description = raw_package.get("description")
            if description:
                assert description not in serialized
