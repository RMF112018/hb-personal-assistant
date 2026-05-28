"""Phase 04 Prompt 08 — Daily log sync SQLite idempotency tests.

``list-daily-logs`` is already ``official_docs_verified`` /
``is_live_eligible: true`` in the active contract — no contract patching
is needed. The mocked HTTP client returns the synthetic fixture; apply()
demultiplexes it into per-section canonical rows.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from hb_assistant.construction.fixtures.procore import DAILY_LOG_SAMPLE_PAYLOAD
from hb_assistant.procore.sync import ProcoreSyncCoordinator


def _temp_db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        return Path(tf.name)


def _apply_once(coord: ProcoreSyncCoordinator) -> dict:
    with patch.object(coord, "auditor") as mock_auditor, \
         patch("hb_assistant.procore.sync.ProcoreHTTPClient") as mock_client_cls:
        mock_auditor.audit_endpoints_for_pilots.return_value = {"daily-log": "available"}
        mock_client = MagicMock()
        mock_client.paginate.return_value = list(DAILY_LOG_SAMPLE_PAYLOAD)
        mock_client_cls.return_value = mock_client
        return coord.apply(project_key="tropical", endpoints=["list-daily-logs"])  # type: ignore[return-value]


def _row_counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(str(db_path))
    try:
        out: dict[str, int] = {}
        for category in (
            "daily_log_counts",
            "daily_log_weather",
            "daily_log_manpower",
            "daily_log_dcr",
            "daily_log_delivery",
            "daily_log_notes",
            "daily_log_accident_review",
            "daily_log_injury_review",
            "daily_log_delay_review",
            "daily_log_safety_review",
        ):
            row = conn.execute(
                "SELECT COUNT(*) FROM procore_synced_entities WHERE category = ?",
                (category,),
            ).fetchone()
            out[category] = row[0] if row else 0
        return out
    finally:
        conn.close()


def test_daily_log_apply_persists_records_across_every_section_category() -> None:
    db = _temp_db()
    coord = ProcoreSyncCoordinator(db_path=db)
    receipt = _apply_once(coord)
    entry = next(e for e in receipt["per_endpoint"] if e["endpoint_id"] == "list-daily-logs")
    assert entry["status"] == "success"
    assert entry["records_by_category"] == {
        "daily_log_counts": 3,
        "daily_log_weather": 2,
        "daily_log_manpower": 3,
        "daily_log_dcr": 2,
        "daily_log_delivery": 2,
        "daily_log_notes": 2,
        "daily_log_accident_review": 1,
        "daily_log_injury_review": 1,
        "daily_log_delay_review": 1,
        "daily_log_safety_review": 1,
    }
    # Notes (2) + accident + injury + delay + safety (4) = 6 review-required rows.
    assert entry["review_required_count"] == 6
    # Only the routed-to-review buckets fire safety_route (4 rows).
    assert entry["safety_route_count"] == 4
    counts = _row_counts(db)
    assert sum(counts.values()) == sum(entry["records_by_category"].values())


def test_daily_log_apply_is_idempotent_on_second_run() -> None:
    db = _temp_db()
    coord = ProcoreSyncCoordinator(db_path=db)
    _apply_once(coord)
    first = _row_counts(db)
    _apply_once(ProcoreSyncCoordinator(db_path=db))
    second = _row_counts(db)
    assert first == second


def test_daily_log_apply_never_persists_raw_section_body_text() -> None:
    db = _temp_db()
    coord = ProcoreSyncCoordinator(db_path=db)
    _apply_once(coord)

    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT canonical_fields_json FROM procore_synced_entities"
        ).fetchall()
    finally:
        conn.close()

    serialized = "".join(row[0] for row in rows if row[0])
    for raw_log in DAILY_LOG_SAMPLE_PAYLOAD:
        for key in (
            "notes_logs",
            "accident_logs",
            "injury_logs",
            "delay_logs",
            "safety_violation_logs",
        ):
            for item in raw_log.get(key, []):
                for text_field in ("description", "note", "narrative", "body", "comment"):
                    raw_text = item.get(text_field)
                    if isinstance(raw_text, str) and raw_text.strip():
                        assert raw_text not in serialized, (
                            f"raw {text_field!r} from {key!r} leaked into canonical_fields_json"
                        )
