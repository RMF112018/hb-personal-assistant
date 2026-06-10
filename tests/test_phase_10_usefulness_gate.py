"""Phase 10 — daily-run usefulness gate (daily-brief usefulness repair).

Proves a run may stay `success` only when it is operator-useful: at least one non-empty deterministic
section, 100% executive source-ref coverage, project-like calendar not all unresolved, Procore top
rows not aggregate sludge, and no synthesis/deterministic contradiction. Also proves the full
apply-run integration downgrades a non-useful run to `partial` and preserves the last successful brief.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai.daily_brief_candidate_writer import (
    persist_candidate_with_refs,
)
from hb_assistant.construction.second_brain.local_ai.daily_run import run_daily_local_agent
from hb_assistant.construction.second_brain.local_ai.usefulness_gate import (
    evaluate_usefulness_gate,
)
from hb_assistant.construction.store import ConstructionStore

BRIEF_DATE = "2026-06-08"
NOW = "2026-06-08T00:00:00+00:00"


def _cand(
    s: ConstructionStore,
    *,
    section: str,
    project_key: str,
    group_key: str,
    linked: bool = True,
) -> None:
    if linked:
        persist_candidate_with_refs(
            s,
            brief_date=BRIEF_DATE,
            section=section,
            title_redacted=f"{section} {group_key}",
            confidence=0.9,
            project_key=project_key,
            priority=10,
            reason_redacted="why",
            group_key=group_key,
            source_refs=[{"source_family": f"{section}_src", "source_ref": group_key}],
        )
    else:
        s.insert_daily_brief_action_candidate(
            brief_date=BRIEF_DATE,
            section=section,
            title_redacted=f"{section} {group_key}",
            confidence=0.5,
            project_key=project_key,
            priority=30,
            group_key=group_key,
        )


def _gate(s: ConstructionStore, **over: object):
    kwargs: dict = {"synthesis_present": False, "synthesis_degraded": False}
    kwargs.update(over)
    return evaluate_usefulness_gate(store=s, brief_date=BRIEF_DATE, **kwargs)  # type: ignore[arg-type]


def test_useful_run_passes(tmp_path: Path) -> None:
    s = ConstructionStore(db_path=str(tmp_path / "t.sqlite"))
    _cand(s, section="calendar", project_key="tropical", group_key="c1")
    _cand(s, section="procore", project_key="the-wellington", group_key="p1")
    r = _gate(s)
    assert r.passed is True
    assert r.verdict == "useful"
    assert r.metrics["deterministic_section_count"] >= 1
    assert r.metrics["procore_aggregate_sludge_selected"] == 0


def test_empty_sections_degraded(tmp_path: Path) -> None:
    s = ConstructionStore(db_path=str(tmp_path / "t.sqlite"))
    r = _gate(s)
    assert r.passed is False
    assert "no_useful_deterministic_section" in r.failed_reasons


def test_zero_source_ref_coverage_degraded(tmp_path: Path) -> None:
    s = ConstructionStore(db_path=str(tmp_path / "t.sqlite"))
    _cand(s, section="calendar", project_key="tropical", group_key="c1", linked=False)
    r = _gate(s)
    assert r.passed is False
    assert "executive_source_ref_coverage_below_100" in r.failed_reasons
    assert r.metrics["executive_source_ref_coverage"] == 0.0


def test_all_calendar_unresolved_degraded(tmp_path: Path) -> None:
    s = ConstructionStore(db_path=str(tmp_path / "t.sqlite"))
    _cand(s, section="calendar", project_key="__needs_review__", group_key="c1")
    _cand(s, section="calendar", project_key="__needs_review__", group_key="c2")
    r = _gate(s)
    assert r.passed is False
    assert "calendar_project_like_all_unresolved" in r.failed_reasons
    assert r.metrics["calendar_project_resolution_rate"] == 0.0


def test_contradiction_synthesis_without_candidates(tmp_path: Path) -> None:
    s = ConstructionStore(db_path=str(tmp_path / "t.sqlite"))
    r = _gate(s, synthesis_present=True, synthesis_degraded=False)
    assert r.passed is False
    assert "synthesis_without_deterministic_candidates" in r.failed_reasons


def test_internal_only_calendar_does_not_trip_unresolved(tmp_path: Path) -> None:
    # Internal events (PTO/training/company) are NOT project-like, so an all-internal calendar is fine.
    s = ConstructionStore(db_path=str(tmp_path / "t.sqlite"))
    _cand(s, section="calendar", project_key="__internal_time_off__", group_key="c1")
    _cand(s, section="procore", project_key="tropical", group_key="p1")
    r = _gate(s)
    assert "calendar_project_like_all_unresolved" not in r.failed_reasons
    assert r.passed is True


# --- integration: apply run downgrade + last-successful preservation ------------


def _seed_event(db: str, *, subject_redacted: str, raw_subject: str) -> ConstructionStore:
    s = ConstructionStore(db_path=db)
    conn = sqlite3.connect(db)
    conn.execute(
        """INSERT INTO calendar_event_index
           (event_index_id, source_id, graph_event_id_hash, start_datetime_utc, end_datetime_utc,
            subject_redacted, organizer_domain, is_online_meeting, is_cancelled, is_private, project_key)
           VALUES ('e1','src1','gh1','2026-06-09T15:00:00+00:00','2026-06-09T16:00:00+00:00',
                   ?, 'hb.com', 0, 0, 0, NULL)""",
        (subject_redacted,),
    )
    conn.execute(
        """INSERT INTO calendar_event_raw_content
           (raw_calendar_event_id, event_index_id, graph_event_id_hash, subject, location_display,
            start_datetime_utc, end_datetime_utc)
           VALUES ('raw-e1','e1','gh1', ?, 'Room', '2026-06-09T15:00:00+00:00','2026-06-09T16:00:00+00:00')""",
        (raw_subject,),
    )
    conn.commit()
    conn.close()
    return s


def test_apply_run_with_unresolved_calendar_downgrades_and_preserves(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    # A project-looking but unknown meeting → persisted as needs_review → calendar all unresolved.
    s = _seed_event(db, subject_redacted="redacted-hash-1", raw_subject="Mystery Tower Coordination")
    dirs = {
        "browser_output_dir": str(tmp_path / "html"),
        "status_dir": str(tmp_path / "status"),
        "vault_brief_dir": str(tmp_path / "vault"),
    }
    out = run_daily_local_agent(
        store=s, now_utc=NOW, db_path=db, dry_run=False, max_persist_per_stage=10, **dirs
    )
    assert out["status"] in {"partial", "degraded"}
    assert any("usefulness_gate_failed" in w for w in out["warnings"])
    assert "calendar_project_like_all_unresolved" in out["usefulness_gate"]["failed_reasons"]
    # latest.html is NOT written as a fresh success; last-successful pointer not created.
    assert "browser_latest_path" not in out["outputs"]
    assert not (tmp_path / "status" / "last-successful.json").exists()
    # status JSON carries the usefulness_gate block.
    status = json.loads((tmp_path / "status" / "latest-status.json").read_text())
    assert status["usefulness_gate"]["verdict"] == "degraded"
