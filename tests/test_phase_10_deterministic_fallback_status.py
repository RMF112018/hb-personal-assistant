"""Phase 10 — deterministic-fallback run-state semantics (daily-brief usefulness follow-up).

Proves that a source-linked deterministic brief that passes the usefulness gate but has degraded
local-model synthesis is reported and published as an operator-usable DETERMINISTIC FALLBACK, not as
a generic partial/unusable run:

- usefulness passed + synthesis ok            -> success (writes daily-brief-latest.html)
- usefulness passed + synthesis degraded      -> deterministic_success_synthesis_degraded
  (writes daily-brief-latest-deterministic.html; does NOT overwrite daily-brief-latest.html)
- usefulness FAILED + synthesis degraded      -> degraded (publishes neither stable path)
- egress failure                              -> failure (publishes neither stable path)
- no status=partial / partial=false contradiction
- Model Enriched Intelligence is never available/degraded=false when synthesis degraded

Offline: synthesis + MEI backends are injected (no Ollama).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai import daily_run as daily_run_mod
from hb_assistant.construction.second_brain.local_ai.daily_brief_candidate_writer import (
    persist_candidate_with_refs,
)
from hb_assistant.construction.second_brain.local_ai.daily_run import (
    STATUS_DETERMINISTIC_FALLBACK,
    run_daily_local_agent,
)
from hb_assistant.construction.second_brain.local_ai.structured_output import StaticOutputClient
from hb_assistant.construction.store import ConstructionStore

MON = "2026-06-15T05:00:00-04:00"  # Monday
BRIEF_DATE = "2026-06-15"
_PRESENT = {"mistral-nemo:12b"}
GOOD_SYNTH = json.dumps({"executive_summary": ["Respond to the RFI today."]})


def _dirs(tmp_path: Path) -> dict[str, str]:
    return {
        "browser_output_dir": str(tmp_path / "html"),
        "status_dir": str(tmp_path / "status"),
        "vault_brief_dir": str(tmp_path / "vault"),
    }


def _seed_linked_action(store: ConstructionStore) -> None:
    """One source-linked executive (actions) candidate → usefulness gate can pass."""
    persist_candidate_with_refs(
        store,
        brief_date=BRIEF_DATE,
        section="actions",
        title_redacted="Respond to the RFI",
        confidence=0.9,
        project_key="tropical",
        priority=10,
        reason_redacted="Due today",
        recommended_next_action="Send the response",
        group_key="g1",
        source_refs=[{"source_family": "email_message", "source_ref": "g1"}],
    )


def _seed_calendar(store: ConstructionStore, *, raw_subject: str) -> None:
    conn = sqlite3.connect(store._db_path)
    conn.execute(
        """INSERT INTO calendar_event_index
           (event_index_id, source_id, graph_event_id_hash, start_datetime_utc, end_datetime_utc,
            subject_redacted, organizer_domain, is_online_meeting, is_cancelled, is_private, project_key)
           VALUES ('e1','src1','gh1','2026-06-16T15:00:00+00:00','2026-06-16T16:00:00+00:00',
                   'redacted-hash-1','hb.com',0,0,0,NULL)""",
    )
    conn.execute(
        """INSERT INTO calendar_event_raw_content
           (raw_calendar_event_id, event_index_id, graph_event_id_hash, subject, location_display,
            start_datetime_utc, end_datetime_utc)
           VALUES ('raw-e1','e1','gh1', ?, 'Room', '2026-06-16T15:00:00+00:00','2026-06-16T16:00:00+00:00')""",
        (raw_subject,),
    )
    conn.commit()
    conn.close()


def _mei_mock() -> str:
    return json.dumps({
        "executive_catchup": ["One advisory item today."],
        "top_priorities": [{"text": "Respond to the RFI", "source_ids": ["c1"],
                            "confidence": 0.9, "reason_code": "due_today"}],
        "open_loops": [], "waiting_on_me": [], "waiting_on_others": [],
        "meeting_prep": [], "project_risk": [],
    })


# --- success vs deterministic fallback -----------------------------------------


def test_synthesis_ok_is_full_success(tmp_path: Path) -> None:
    s = ConstructionStore(db_path=str(tmp_path / "t.sqlite"))
    _seed_linked_action(s)
    out = run_daily_local_agent(
        store=s, now_utc=MON, db_path=s._db_path, dry_run=False, max_persist_per_stage=10,
        synthesize_brief=True, synthesis_backend=StaticOutputClient(GOOD_SYNTH), **_dirs(tmp_path),
    )
    assert out["status"] == "success"
    assert out["synthesis_degraded"] is False
    assert out["operator_usable"] is True
    assert (tmp_path / "html" / "daily-brief-latest.html").exists()
    assert (tmp_path / "html" / "daily-brief-latest-deterministic.html").exists()


def test_synthesis_degraded_is_deterministic_fallback(tmp_path: Path) -> None:
    s = ConstructionStore(db_path=str(tmp_path / "t.sqlite"))
    _seed_linked_action(s)
    out = run_daily_local_agent(
        store=s, now_utc=MON, db_path=s._db_path, dry_run=False, max_persist_per_stage=10,
        synthesize_brief=True, synthesis_backend=StaticOutputClient(raise_unavailable=True),
        **_dirs(tmp_path),
    )
    assert out["status"] == STATUS_DETERMINISTIC_FALLBACK
    assert out["ok"] is True
    assert out["partial"] is False
    assert out["synthesis_degraded"] is True
    assert out["synthesis_status"] == "degraded"
    assert out["deterministic_fallback_used"] is True
    assert out["operator_usable"] is True
    df = out["deterministic_fallback"]
    assert df["used"] is True and df["published"] is True
    assert df["usefulness_gate_passed"] is True
    assert df["reason"].startswith("synthesis_degraded:")
    assert df["stable_path"] and "deterministic" in df["stable_path"]


def test_no_status_partial_partial_false_contradiction(tmp_path: Path) -> None:
    s = ConstructionStore(db_path=str(tmp_path / "t.sqlite"))
    _seed_linked_action(s)
    out = run_daily_local_agent(
        store=s, now_utc=MON, db_path=s._db_path, dry_run=False, max_persist_per_stage=10,
        synthesize_brief=True, synthesis_backend=StaticOutputClient(raise_unavailable=True),
        **_dirs(tmp_path),
    )
    # Invariant: top-level partial must equal (status == "partial").
    assert out["partial"] == (out["status"] == "partial")
    status = json.loads((tmp_path / "status" / "latest-status.json").read_text())
    assert (status["status"] == "partial") == (out["partial"])


# --- Option A publishing -------------------------------------------------------


def test_fallback_publishes_deterministic_not_latest(tmp_path: Path) -> None:
    s = ConstructionStore(db_path=str(tmp_path / "t.sqlite"))
    _seed_linked_action(s)
    out = run_daily_local_agent(
        store=s, now_utc=MON, db_path=s._db_path, dry_run=False, max_persist_per_stage=10,
        synthesize_brief=True, synthesis_backend=StaticOutputClient(raise_unavailable=True),
        **_dirs(tmp_path),
    )
    assert out["status"] == STATUS_DETERMINISTIC_FALLBACK
    det = tmp_path / "html" / "daily-brief-latest-deterministic.html"
    latest = tmp_path / "html" / "daily-brief-latest.html"
    assert det.exists()  # deterministic fallback published to its own stable path
    assert not latest.exists()  # daily-brief-latest.html reserved for full synthesis success
    body = det.read_text()
    assert "Deterministic source-linked brief published" in body
    assert "NOT counted as successful" not in body


# --- usefulness failure stays degraded; publishes neither stable path ----------


def test_usefulness_failed_is_degraded_not_fallback(tmp_path: Path) -> None:
    s = ConstructionStore(db_path=str(tmp_path / "t.sqlite"))
    # Project-looking but unresolvable meeting → calendar all unresolved → usefulness gate fails.
    _seed_calendar(s, raw_subject="Mystery Tower Coordination")
    out = run_daily_local_agent(
        store=s, now_utc=MON, db_path=s._db_path, dry_run=False, max_persist_per_stage=10,
        synthesize_brief=True, synthesis_backend=StaticOutputClient(raise_unavailable=True),
        **_dirs(tmp_path),
    )
    assert out["status"] == "degraded"
    assert out["deterministic_fallback_used"] is False
    assert out["operator_usable"] is False
    assert "calendar_project_like_all_unresolved" in out["usefulness_gate"]["failed_reasons"]
    assert not (tmp_path / "html" / "daily-brief-latest.html").exists()
    assert not (tmp_path / "html" / "daily-brief-latest-deterministic.html").exists()
    assert not (tmp_path / "status" / "last-successful.json").exists()


# --- egress failure stays failure; publishes nothing ---------------------------


def test_egress_failure_is_failure_no_publish(tmp_path: Path, monkeypatch) -> None:
    s = ConstructionStore(db_path=str(tmp_path / "t.sqlite"))
    _seed_linked_action(s)
    # Force the fail-closed egress scan to report an external-asset hit.
    monkeypatch.setattr(daily_run_mod, "scan_daily_run_html", lambda _html: ["external_asset"])
    out = run_daily_local_agent(
        store=s, now_utc=MON, db_path=s._db_path, dry_run=False, max_persist_per_stage=10,
        synthesize_brief=True, synthesis_backend=StaticOutputClient(raise_unavailable=True),
        **_dirs(tmp_path),
    )
    assert out["status"] == "failure"
    assert out["ok"] is False
    assert out["egress_scan"]["clean"] is False
    assert out["deterministic_fallback"]["published"] is False
    assert not (tmp_path / "html" / "daily-brief-latest.html").exists()
    assert not (tmp_path / "html" / "daily-brief-latest-deterministic.html").exists()


# --- Model Enriched Intelligence never healthy when synthesis degraded ---------


def test_mei_withheld_when_synthesis_degraded(tmp_path: Path) -> None:
    s = ConstructionStore(db_path=str(tmp_path / "t.sqlite"))
    _seed_linked_action(s)  # one linked actions candidate → MEI alias c1, usefulness passes
    out = run_daily_local_agent(
        store=s, now_utc=MON, db_path=s._db_path, dry_run=False, max_persist_per_stage=10,
        synthesize_brief=True, synthesis_backend=StaticOutputClient(raise_unavailable=True),
        model_enriched_intelligence=True, model_enriched_backend=StaticOutputClient(_mei_mock()),
        model_enriched_present_models=_PRESENT,
        **_dirs(tmp_path),
    )
    assert out["status"] == STATUS_DETERMINISTIC_FALLBACK
    mei = out["model_enriched_intelligence"]
    # Never displayed as available/healthy while synthesis degraded.
    assert not (mei["available"] is True and mei["degraded"] is False)
    assert mei["available"] is False
    assert mei["degraded"] is True
    assert str(mei["withheld_reason"]).startswith("synthesis_degraded:")
    assert mei["label"] == "Source-Linked Deterministic Brief"
