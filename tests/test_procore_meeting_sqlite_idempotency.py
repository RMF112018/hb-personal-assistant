"""Phase 04 Prompt 07 — Meeting + meeting-topic SQLite idempotency tests.

Both endpoints ship as ``verification_status: candidate`` →
``is_live_eligible: false``, so ``apply()`` would normally emit
``skipped_not_live_eligible``. These tests patch the loaded contract so the
endpoints are treated as ``official_docs_verified`` for the duration of the
test, documenting what apply() will do once they're promoted.

The meeting-topic endpoint's path template carries a ``{meeting_id}``
placeholder that ``sync.apply()`` does not supply (it formats with
``company_id`` and ``project_id`` only). For the topic idempotency test we
also patch the path template to a single-param shape so the format call
succeeds; the mock client returns the fixture verbatim regardless of path.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from hb_assistant.construction.fixtures.procore import (
    MEETING_SAMPLE_PAYLOAD,
    MEETING_TOPIC_SAMPLE_PAYLOAD,
)
from hb_assistant.procore.loader import load_endpoint_contract
from hb_assistant.procore.sync import ProcoreSyncCoordinator


def _temp_db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        return Path(tf.name)


def _promoted_contract(*, also_strip_topic_meeting_id: bool = False):
    contract = load_endpoint_contract()
    for ep in contract.endpoints:
        if ep.endpoint_id == "list-meetings":
            object.__setattr__(ep, "verification_status", "official_docs_verified")
        if ep.endpoint_id == "list-meeting-topics":
            object.__setattr__(ep, "verification_status", "official_docs_verified")
            if also_strip_topic_meeting_id:
                object.__setattr__(
                    ep,
                    "path_template",
                    "/rest/v1.0/projects/{project_id}/meeting_topics",
                )
    return contract


def _apply_once_meetings(coord: ProcoreSyncCoordinator) -> dict:
    contract = _promoted_contract()
    with (
        patch.object(coord, "auditor") as mock_auditor,
        patch("hb_assistant.procore.sync.ProcoreHTTPClient") as mock_client_cls,
        patch("hb_assistant.procore.sync.load_endpoint_contract", return_value=contract),
    ):
        mock_auditor.audit_endpoints_for_pilots.return_value = {"meeting": "available"}
        mock_client = MagicMock()
        mock_client.paginate.return_value = list(MEETING_SAMPLE_PAYLOAD)
        mock_client_cls.return_value = mock_client
        return coord.apply(project_key="tropical", endpoints=["list-meetings"])  # type: ignore[return-value]


def _apply_once_topics(coord: ProcoreSyncCoordinator) -> dict:
    contract = _promoted_contract(also_strip_topic_meeting_id=True)
    with (
        patch.object(coord, "auditor") as mock_auditor,
        patch("hb_assistant.procore.sync.ProcoreHTTPClient") as mock_client_cls,
        patch("hb_assistant.procore.sync.load_endpoint_contract", return_value=contract),
    ):
        mock_auditor.audit_endpoints_for_pilots.return_value = {"meeting-topic": "available"}
        mock_client = MagicMock()
        mock_client.paginate.return_value = list(MEETING_TOPIC_SAMPLE_PAYLOAD)
        mock_client_cls.return_value = mock_client
        return coord.apply(project_key="tropical", endpoints=["list-meeting-topics"])  # type: ignore[return-value]


def _row_counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(str(db_path))
    try:
        meetings = conn.execute(
            "SELECT COUNT(*) FROM procore_synced_entities WHERE category = 'meetings'"
        ).fetchone()[0]
        topics = conn.execute(
            "SELECT COUNT(*) FROM procore_synced_entities WHERE category = 'meeting_topics'"
        ).fetchone()[0]
        return {"meetings": meetings, "meeting_topics": topics}
    finally:
        conn.close()


def test_meeting_apply_persists_meeting_rows_idempotently() -> None:
    db = _temp_db()
    coord = ProcoreSyncCoordinator(db_path=db)
    receipt = _apply_once_meetings(coord)
    entry = next(e for e in receipt["per_endpoint"] if e["endpoint_id"] == "list-meetings")
    assert entry["status"] == "success"
    assert entry["meeting_records_written"] == 3
    counts_first = _row_counts(db)
    assert counts_first["meetings"] == 3
    # Re-apply with a fresh coord on the same DB → still 3 (idempotent).
    _apply_once_meetings(ProcoreSyncCoordinator(db_path=db))
    counts_second = _row_counts(db)
    assert counts_second["meetings"] == 3


def test_meeting_topic_apply_persists_topic_rows_with_safety_counts() -> None:
    db = _temp_db()
    coord = ProcoreSyncCoordinator(db_path=db)
    receipt = _apply_once_topics(coord)
    entry = next(e for e in receipt["per_endpoint"] if e["endpoint_id"] == "list-meeting-topics")
    assert entry["status"] == "success"
    assert entry["meeting_topic_records_written"] == 4
    # Only topic #2 (injury body trigger) routes safety.
    assert entry["safety_route_count"] == 1
    counts_first = _row_counts(db)
    assert counts_first["meeting_topics"] == 4
    _apply_once_topics(ProcoreSyncCoordinator(db_path=db))
    counts_second = _row_counts(db)
    assert counts_second["meeting_topics"] == 4


def test_meeting_topic_apply_does_not_persist_raw_body_text() -> None:
    db = _temp_db()
    coord = ProcoreSyncCoordinator(db_path=db)
    _apply_once_topics(coord)

    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT canonical_fields_json FROM procore_synced_entities WHERE category = 'meeting_topics'"
        ).fetchall()
    finally:
        conn.close()

    serialized = "".join(row[0] for row in rows if row[0])
    for raw in MEETING_TOPIC_SAMPLE_PAYLOAD:
        description = raw.get("description")
        if description:
            assert description not in serialized
        action_items = raw.get("action_items")
        if isinstance(action_items, str):
            assert action_items not in serialized
        elif isinstance(action_items, list):
            for item in action_items:
                assert item not in serialized
