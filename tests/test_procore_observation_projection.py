"""Phase 04B observation + safety enrichment projection tests."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

from hb_assistant.security.text_vault import decrypt_text
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_observation_projection import project_observation

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")

_NOW = "2026-05-29T00:00:00Z"

# Open safety observation (type=incident, subtype=injury), high priority, due soon,
# with assignee+vendor, created_by, location hierarchy, and a trade.
_SAFETY_OBS: Dict[str, Any] = {
    "id": "obs-501",
    "number": "OBS-501",
    "title": "Worker near-miss at scaffold",
    "type": "incident",
    "subtype": "injury",
    "status": "open",
    "priority": "high",
    "severity": "high",
    "personal": False,
    "date_notified": "2026-05-28T08:00:00Z",
    "due_date": "2026-05-31",  # within 3 days of _NOW -> due_soon
    "closed_at": None,
    "description": "Scaffold guardrail missing; worker nearly fell. Corrective action issued.",
    "location": {"id": 22001, "name": "Tower A>Level 5", "parent_id": 22000},
    "trade": {"id": 7, "name": "05 - structural steel"},
    "assignee": {"id": 31, "login": "super@example.test", "name": "Site Super", "vendor": {"id": 900, "name": "Acme Safety"}},
    "created_by": {"id": 12, "login": "pm@example.test", "name": "Project Manager", "company_name": "HB Construction"},
}

# Benign, closed, low-priority observation — no safety signal.
_BENIGN_OBS: Dict[str, Any] = {
    "id": "obs-502",
    "number": "OBS-502",
    "title": "Housekeeping at loading dock",
    "type": "general",
    "subtype": "housekeeping",
    "status": "closed",
    "priority": "normal",
    "closed_at": "2026-05-22T00:00:00Z",
    "description": "Keep the dock clear of pallets.",
    "assignee_id": "user-31",
    "created_by_id": "user-12",
}


def _db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        path = Path(tf.name)
    SQLiteMigrator(db_path=str(path)).apply()
    return path


def _conn(db: Path) -> sqlite3.Connection:
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row
    return c


def _signals(db: Path) -> set[str]:
    return {r[0] for r in _conn(db).execute("SELECT signal_type FROM procore_action_signals")}


def test_observation_safety_classification_and_priority() -> None:
    db = _db()
    project_observation(_SAFETY_OBS, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    sigs = _signals(db)
    assert {"observation_open_safety", "observation_high_priority", "observation_due_soon"} <= sigs
    assert "observation_closed" not in sigs


def test_observation_location_trade_vendor_edges_hashed() -> None:
    db = _db()
    project_observation(_SAFETY_OBS, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    c = _conn(db)
    edges = {r[0] for r in c.execute("SELECT edge_type FROM procore_record_edges")}
    assert {"at_location", "trade", "vendor", "assignee", "created_by"} <= edges
    people = c.execute("SELECT * FROM procore_people_entities").fetchall()
    pblob = "|".join(str(x) for r in people for x in r)
    assert "super@example.test" not in pblob and "Site Super" not in pblob
    loc = c.execute("SELECT * FROM procore_location_entities").fetchone()
    assert loc["parent_location_id"] == "22000"
    vendor = c.execute(
        "SELECT name_redacted FROM procore_company_entities WHERE name_redacted='Acme Safety'"
    ).fetchone()
    assert vendor is not None


def test_observation_description_text_intelligence_encrypted() -> None:
    db = _db()
    project_observation(_SAFETY_OBS, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    row = _conn(db).execute(
        "SELECT * FROM procore_text_intelligence WHERE source_field_path='description'"
    ).fetchone()
    assert row is not None and decrypt_text(row["encrypted_full_text_ref"]) == _SAFETY_OBS["description"]


def test_observation_closed_signal_no_safety() -> None:
    db = _db()
    project_observation(_BENIGN_OBS, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    sigs = _signals(db)
    assert "observation_closed" in sigs
    assert "observation_open_safety" not in sigs
    assert "observation_high_priority" not in sigs


def test_observation_projection_idempotent() -> None:
    db = _db()
    project_observation(_SAFETY_OBS, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    project_observation(_SAFETY_OBS, project_key="tropical", sync_run_id="r2", now_utc=_NOW, db_path=db)
    assert _conn(db).execute(
        "SELECT COUNT(*) FROM procore_text_intelligence WHERE source_field_path='description'"
    ).fetchone()[0] == 1
