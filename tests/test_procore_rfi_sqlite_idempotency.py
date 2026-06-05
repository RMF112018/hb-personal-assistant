"""Phase 04 Prompt 04 — RFI sync SQLite idempotency tests.

Mocks the audit gate and Procore HTTP client; the real assertion is that
``coord.apply()`` writes RFI parent rows and RFI reply rows into the
caller-supplied temp SQLite, and that re-running the same apply does not
duplicate any row.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from hb_assistant.construction.fixtures.procore import RFI_SAMPLE_PAYLOAD
from hb_assistant.procore.sync import ProcoreSyncCoordinator


def _temp_db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        return Path(tf.name)


def _apply_once(coord: ProcoreSyncCoordinator) -> dict:
    with (
        patch.object(coord, "auditor") as mock_auditor,
        patch("hb_assistant.procore.sync.ProcoreHTTPClient") as mock_client_cls,
    ):
        mock_auditor.audit_endpoints_for_pilots.return_value = {"rfi": "available"}
        mock_client = MagicMock()
        mock_client.paginate.return_value = list(RFI_SAMPLE_PAYLOAD)
        mock_client_cls.return_value = mock_client
        result = coord.apply(project_key="tropical", endpoints=["list-rfis"])
    # ``apply`` returns the redacted receipt as a plain dict (``redact_for_evidence``
    # over ``SyncReceipt.__dict__``); the type stub still advertises ``SyncReceipt``.
    return result  # type: ignore[return-value]


def _row_counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(str(db_path))
    try:
        rfis = conn.execute(
            "SELECT COUNT(*) FROM procore_synced_entities WHERE category = 'rfis'"
        ).fetchone()[0]
        replies = conn.execute(
            "SELECT COUNT(*) FROM procore_synced_entities WHERE category = 'rfi_replies'"
        ).fetchone()[0]
        watermarks = conn.execute(
            "SELECT COUNT(*) FROM procore_sync_watermarks WHERE endpoint_id = 'list-rfis'"
        ).fetchone()[0]
        return {"rfis": rfis, "replies": replies, "watermarks": watermarks}
    finally:
        conn.close()


def test_rfi_apply_persists_parents_and_replies_as_separate_rows() -> None:
    db = _temp_db()
    coord = ProcoreSyncCoordinator(db_path=db)
    receipt = _apply_once(coord)

    assert receipt["mode"] == "apply"
    assert receipt["persisted_to_sqlite"] is True
    entry = next(e for e in receipt["per_endpoint"] if e["endpoint_id"] == "list-rfis")
    assert entry["status"] == "success"
    assert entry["rfi_records_written"] == 3
    assert entry["reply_records_written"] == 5
    counts = _row_counts(db)
    assert counts["rfis"] == 3
    assert counts["replies"] == 5
    assert counts["watermarks"] == 1


def test_rfi_apply_is_idempotent_on_second_run() -> None:
    db = _temp_db()
    coord = ProcoreSyncCoordinator(db_path=db)
    _apply_once(coord)
    first = _row_counts(db)
    _apply_once(ProcoreSyncCoordinator(db_path=db))  # fresh coordinator, same DB
    second = _row_counts(db)
    assert first == second
    assert second["rfis"] == 3
    assert second["replies"] == 5


def test_rfi_apply_does_not_persist_raw_body_text() -> None:
    db = _temp_db()
    coord = ProcoreSyncCoordinator(db_path=db)
    _apply_once(coord)

    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute("SELECT canonical_fields_json FROM procore_synced_entities").fetchall()
    finally:
        conn.close()

    serialized = "".join(row[0] for row in rows if row[0])
    for raw in RFI_SAMPLE_PAYLOAD:
        for raw_reply in raw["replies"]:
            assert raw_reply["body"] not in serialized
