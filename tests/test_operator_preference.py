"""Phase 08A Prompt 10 — Operator Preference Agent (A08) against a temp DB.

Proves: preferences are captured as reviewable records (never auto-accepted); sensitive
preferences route to Tier 3; the unique (scope, scope_key, preference_key) upsert
increments signal_count; guard columns stay 0; and accepted preferences can never override
safety policy / review-tier routing.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.memory import (
    apply_operator_preferences,
    build_operator_preference_proof,
    capture_preference,
)
from hb_assistant.construction.store import ConstructionStore


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    db = str(tmp_path / "pref.sqlite")
    ConstructionStore(db)
    return db


def test_low_risk_preference_is_tier_2_pending(db_path: str) -> None:
    p = capture_preference(
        scope="global",
        preference_key="detail_level",
        preference_value_redacted="concise",
        preference_type="detail_level",
        db_path=db_path,
        emit=True,
    )
    assert p.review_tier == 2
    assert p.review_status == "pending_review"


def test_sensitive_preference_routes_tier_3(db_path: str) -> None:
    p = capture_preference(
        scope="project",
        scope_key="P1",
        preference_key="personnel_emphasis",
        preference_value_redacted="[redacted]",
        preference_type="personnel",
        db_path=db_path,
        emit=True,
    )
    assert p.review_tier == 3
    assert p.review_tier_reason_code == "T3_SENSITIVE_HIGH_IMPACT"
    assert p.review_status == "pending_review"


def test_upsert_increments_signal_count_and_guards_zero(db_path: str) -> None:
    capture_preference(
        scope="global",
        preference_key="terminology",
        preference_value_redacted="RFI",
        preference_type="terminology",
        db_path=db_path,
        emit=True,
    )
    capture_preference(
        scope="global",
        preference_key="terminology",
        preference_value_redacted="RFI",
        preference_type="terminology",
        db_path=db_path,
        emit=True,
    )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM second_brain_operator_preference_profiles WHERE preference_key='terminology'"
    ).fetchall()
    assert len(rows) == 1  # deduped by UNIQUE(scope, scope_key, preference_key)
    row = dict(rows[0])
    assert row["signal_count"] == 2  # insert=1, then the conflicting upsert increments to 2
    for col in (c for c in row if c.endswith("_persisted")):
        assert row[col] == 0
    conn.close()


def test_accepted_preferences_cannot_override_safety() -> None:
    applied, dropped = apply_operator_preferences(
        [
            {
                "preference_key": "executive_summary_style",
                "preference_value_redacted": "brief",
                "review_status": "accepted",
            },
            {
                "preference_key": "bypass_review_tier",
                "preference_value_redacted": "1",
                "review_status": "accepted",
            },
        ]
    )
    assert applied == {"executive_summary_style": "brief"}
    assert any("bypass_review_tier" in d for d in dropped)


def test_proof_passes() -> None:
    assert build_operator_preference_proof()["proof_passed"] is True
