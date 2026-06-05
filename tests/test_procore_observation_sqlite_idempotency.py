"""Phase 04 Prompt 06 — Observation sync SQLite idempotency tests.

The active contract ships ``list-observations`` as ``verification_status:
candidate`` → ``is_live_eligible: false``, so apply() would normally emit
``skipped_not_live_eligible``. These tests patch the loaded contract so the
observation endpoint is treated as ``official_docs_verified`` for the
duration of the test, documenting what apply() will do when the endpoint is
promoted in a future prompt.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from hb_assistant.construction.fixtures.procore import OBSERVATION_SAMPLE_PAYLOAD
from hb_assistant.procore.loader import load_endpoint_contract
from hb_assistant.procore.sync import ProcoreSyncCoordinator


def _temp_db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        return Path(tf.name)


def _promoted_contract():
    contract = load_endpoint_contract()
    for ep in contract.endpoints:
        if ep.endpoint_id == "list-observations":
            # Bypass Pydantic frozen-ness by direct attribute assignment via
            # object.__setattr__ since pydantic v2 models permit it on default
            # configuration but ``computed_field`` is evaluated on access.
            object.__setattr__(ep, "verification_status", "official_docs_verified")
    return contract


def _apply_once(coord: ProcoreSyncCoordinator) -> dict:
    contract = _promoted_contract()
    with (
        patch.object(coord, "auditor") as mock_auditor,
        patch("hb_assistant.procore.sync.ProcoreHTTPClient") as mock_client_cls,
        patch("hb_assistant.procore.sync.load_endpoint_contract", return_value=contract),
    ):
        mock_auditor.audit_endpoints_for_pilots.return_value = {"observation": "available"}
        mock_client = MagicMock()
        mock_client.paginate.return_value = list(OBSERVATION_SAMPLE_PAYLOAD)
        mock_client_cls.return_value = mock_client
        result = coord.apply(project_key="tropical", endpoints=["list-observations"])
    return result  # type: ignore[return-value]


def _row_counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(str(db_path))
    try:
        observations = conn.execute(
            "SELECT COUNT(*) FROM procore_synced_entities WHERE category = 'observations'"
        ).fetchone()[0]
        comments = conn.execute(
            "SELECT COUNT(*) FROM procore_synced_entities WHERE category = 'observation_comments'"
        ).fetchone()[0]
        watermarks = conn.execute(
            "SELECT COUNT(*) FROM procore_sync_watermarks WHERE endpoint_id = 'list-observations'"
        ).fetchone()[0]
        return {
            "observations": observations,
            "comments": comments,
            "watermarks": watermarks,
        }
    finally:
        conn.close()


def test_observation_apply_persists_parents_and_comments_separately() -> None:
    db = _temp_db()
    coord = ProcoreSyncCoordinator(db_path=db)
    receipt = _apply_once(coord)

    assert receipt["mode"] == "apply"
    assert receipt["persisted_to_sqlite"] is True
    entry = next(e for e in receipt["per_endpoint"] if e["endpoint_id"] == "list-observations")
    assert entry["status"] == "success"
    assert entry["observation_records_written"] == 3
    assert entry["comment_records_written"] == 3
    # Two of three fixture observations fire the safety heuristic.
    assert entry["safety_route_count"] == 2
    counts = _row_counts(db)
    assert counts["observations"] == 3
    assert counts["comments"] == 3
    assert counts["watermarks"] == 1


def test_observation_apply_is_idempotent_on_second_run() -> None:
    db = _temp_db()
    coord = ProcoreSyncCoordinator(db_path=db)
    _apply_once(coord)
    first = _row_counts(db)
    _apply_once(ProcoreSyncCoordinator(db_path=db))
    second = _row_counts(db)
    assert first == second
    assert second["observations"] == 3
    assert second["comments"] == 3


def test_observation_apply_does_not_persist_raw_body_text() -> None:
    db = _temp_db()
    coord = ProcoreSyncCoordinator(db_path=db)
    _apply_once(coord)

    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute("SELECT canonical_fields_json FROM procore_synced_entities").fetchall()
    finally:
        conn.close()

    serialized = "".join(row[0] for row in rows if row[0])
    for raw in OBSERVATION_SAMPLE_PAYLOAD:
        assert raw["description"] not in serialized
        for raw_comment in raw["comments"]:
            assert raw_comment["body"] not in serialized
