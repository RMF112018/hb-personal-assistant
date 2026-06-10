"""Phase 10 Daily Brief Quality Correction — routing, local-model synthesis, content quality, safety.

Covers the corrective checkpoint:
- Obsidian routing → governed ``Work/Daily Brief`` (never legacy Phase 08A), scheduler pin, status.
- Local-model executive synthesis (schema-enforced, fail-closed/degraded, no raw persistence).
- Project alias inference, calendar noise classification, hybrid brief structure, empty states.
- Raw-content boundary (raw in Obsidian/browser/model-context only; never status/rows/logs).

Synthesis is exercised offline via ``StaticOutputClient`` (no Ollama daemon, deterministic).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.local_ai import run_daily_local_agent
from hb_assistant.construction.second_brain.local_ai.calendar_classify import (
    classify_calendar_event,
)
from hb_assistant.construction.second_brain.local_ai.daily_brief_context_packet import (
    build_daily_brief_context_packet,
)
from hb_assistant.construction.second_brain.local_ai.daily_brief_llm_synthesis import (
    render_synthesis_markdown,
    synthesize_daily_brief,
)
from hb_assistant.construction.second_brain.local_ai.daily_brief_synthesis_schema import (
    DailyBriefSynthesis,
)
from hb_assistant.construction.second_brain.local_ai.daily_brief_window import (
    compute_daily_brief_window,
)
from hb_assistant.construction.second_brain.local_ai.daily_run_scheduler import (
    DailyRunLaunchdManager,
)
from hb_assistant.construction.second_brain.local_ai.project_aliases import (
    resolve_project,
    summarize_unresolved_tokens,
)
from hb_assistant.construction.second_brain.local_ai.structured_output import StaticOutputClient
from hb_assistant.construction.second_brain.local_ai.vault_brief_policy import (
    LEGACY_OVERRIDE_ENV,
    VaultBriefPolicyError,
    assert_not_legacy,
    governed_brief_dir,
)
from hb_assistant.construction.store import ConstructionStore

MON = "2026-06-15T05:00:00-04:00"  # Monday
FRI = "2026-06-19T05:00:00-04:00"  # Friday

_GUARD_COLUMNS = (
    "raw_email_body_persisted",
    "raw_document_text_persisted",
    "raw_calendar_payload_persisted",
    "raw_procore_payload_persisted",
    "raw_prompt_persisted",
    "raw_response_persisted",
    "signed_url_persisted",
    "download_url_persisted",
    "external_writeback_performed",
    "graph_writeback_performed",
    "procore_writeback_performed",
    "email_send_performed",
    "calendar_mutation_performed",
)

# A complete, schema-valid synthesized brief (canned model output for offline tests).
GOOD_SYNTH = json.dumps(
    {
        "executive_summary": ["Tropical submittal review is today's critical path."],
        "what_changed_since_last_brief": [
            {
                "text": "New RFI opened on Tropical over the weekend",
                "source_id": "abc",
                "project": "tropical",
            }
        ],
        "critical_due_today": [{"text": "Submittal log due 4pm", "source_id": "d1"}],
        "open_commitments_follow_ups": [
            {
                "text": "GC owes submittal response (stale 4d)",
                "source_id": "w1",
                "project": "the-wellington",
            }
        ],
        "todays_meetings": [
            {
                "local_time": "Mon 11:00 AM",
                "title": "TWN OAC Coordination",
                "project": "tropical",
                "why_it_matters": "open RFI on the critical path",
                "prep": "pull latest submittal log",
                "open_questions": ["status of RFI #214?"],
                "source_id": "cal1",
                "recommended_next_action": "prepare_packet",
            }
        ],
        "project_signals": [
            {
                "project": "tropical",
                "summary": "2 overdue RFIs",
                "items": [{"text": "RFI overdue 3d"}],
            }
        ],
        "recommended_next_actions": ["Resolve Tropical submittal first"],
        "fyi_low_priority": ["IT maintenance Saturday"],
        "needs_review_data_gaps": ["1 calendar item unassigned"],
    }
)


def _seed(
    db: str,
    *,
    events: list[tuple[str, str, str | None]] | None = None,
    raw_subject: str | None = None,
) -> ConstructionStore:
    """Seed calendar events as (event_id, subject_redacted, project_key|None) on Monday 2026-06-15."""
    s = ConstructionStore(db_path=db)
    conn = sqlite3.connect(db)
    events = events or [("ev0", "TWN OAC Coordination", None)]
    for eid, subject, proj in events:
        conn.execute(
            """INSERT INTO calendar_event_index
               (event_index_id, source_id, graph_event_id_hash, start_datetime_utc,
                end_datetime_utc, subject_redacted, organizer_domain, is_online_meeting,
                is_cancelled, is_private, project_key)
               VALUES (?, 'src1', ?, '2026-06-15T15:00:00.0000000',
                       '2026-06-15T16:00:00.0000000', ?, 'hb.com', 0, 0, 0, ?)""",
            (eid, f"gh-{eid}", subject, proj),
        )
    if raw_subject is not None:
        conn.execute(
            """INSERT INTO calendar_event_raw_content
               (raw_calendar_event_id, event_index_id, graph_event_id_hash, source_ref_hash,
                subject, location_display, organizer_name, start_datetime_utc, end_datetime_utc)
               VALUES ('raw0', 'ev0', 'gh-ev0', 'srh0', ?, 'Room 1', 'Jane Doe',
                       '2026-06-15T15:00:00.0000000', '2026-06-15T16:00:00.0000000')""",
            (raw_subject,),
        )
    conn.commit()
    conn.close()
    return s


def _dirs(tmp_path: Path) -> dict[str, str]:
    return {
        "browser_output_dir": str(tmp_path / "html"),
        "status_dir": str(tmp_path / "status"),
        "vault_brief_dir": str(tmp_path / "vault"),
    }


def _win(now: str = MON) -> object:
    return compute_daily_brief_window(datetime.fromisoformat(now), "America/New_York")


# =============================================================================
# 1-4 — PATH / ROUTING
# =============================================================================


def test_1_scheduled_daily_run_routes_to_work_daily_brief(tmp_path: Path) -> None:
    # The governed scheduled-run folder resolves to Work/Daily Brief (never Phase 08A).
    assert governed_brief_dir().as_posix().endswith("Work/Daily Brief")
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = run_daily_local_agent(
        store=s, now_utc=MON, db_path=db, dry_run=True,
        browser_output_dir=str(tmp_path / "html"), status_dir=str(tmp_path / "status"),
    )  # no explicit vault_brief_dir → defaults to the governed policy folder
    # (the redacted form may collapse to the basename when the vault root is outside $HOME)
    assert "Daily Brief" in out["outputs"]["vault_brief_dir_redacted"]
    assert "Phase 08A" not in out["outputs"]["vault_brief_dir_redacted"]


def test_2_legacy_phase_08a_folder_guarded_and_refused(tmp_path: Path) -> None:
    # The governed folder is never the legacy Phase 08A folder.
    assert "Phase 08A" not in governed_brief_dir().as_posix()
    # The guard raises on a legacy path.
    with pytest.raises(VaultBriefPolicyError):
        assert_not_legacy("/v/Construction Intelligence/Phase 08A Daily Briefs/x.md")
    # A scheduled run pointed at the legacy folder fails closed (no silent fallback).
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = run_daily_local_agent(
        store=s, now_utc=MON, db_path=db, dry_run=True,
        vault_brief_dir="/tmp/x/Construction Intelligence/Phase 08A Daily Briefs",
        browser_output_dir=str(tmp_path / "html"), status_dir=str(tmp_path / "status"),
    )
    assert out["status"] == "failure" and out["error"] == "vault_brief_dir_refused"


def test_2b_legacy_override_env_allows_explicit_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LEGACY_OVERRIDE_ENV, "1")
    # override only suppresses the guard; it does not raise
    assert_not_legacy("/v/Construction Intelligence/Phase 08A Daily Briefs/x.md")


def test_3_scheduler_pins_governed_vault_dir() -> None:
    mgr = DailyRunLaunchdManager(label="com.hb.test.route", apply_mode=True)
    args = mgr.render_plist()["ProgramArguments"]
    assert "--vault-brief-dir" in args
    pinned = args[args.index("--vault-brief-dir") + 1]
    assert pinned == str(governed_brief_dir())
    assert pinned.endswith("Work/Daily Brief")
    assert "Phase 08A" not in pinned


def test_4_status_reports_effective_vault_dir(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = run_daily_local_agent(store=s, now_utc=MON, db_path=db, dry_run=True, **_dirs(tmp_path))
    assert "vault_brief_dir_redacted" in out["outputs"]
    assert out["guardrails"]["vault_brief_folder_pinned"] is True
    # scheduler status surfaces it too
    st = DailyRunLaunchdManager(label="com.hb.test.route2").status()
    assert "Daily Brief" in st["vault_brief_dir_redacted"]
    assert "Phase 08A" not in st["vault_brief_dir_redacted"]


# =============================================================================
# 5-9 — MODEL SYNTHESIS
# =============================================================================


def test_5_synthesis_calls_local_model_when_enabled(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    client = StaticOutputClient(GOOD_SYNTH)
    out = run_daily_local_agent(
        store=s,
        now_utc=MON,
        db_path=db,
        dry_run=False,
        max_persist_per_stage=10,
        synthesize_brief=True,
        synthesis_backend=client,
        **_dirs(tmp_path),
    )
    assert client.call_count >= 1
    assert out["synthesis"] is not None and out["synthesis"]["status"] == "ok"
    assert out["synthesis_degraded"] is False
    assert out["status"] == "success"


def test_6_context_packet_is_bounded_and_source_linked(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(
        db,
        events=[
            ("ev0", "TWN OAC Coordination", None),  # prep keyword → visible
            ("ev1", "Bobby PTO", None),  # excluded
            ("ev2", "Weekly team huddle", None),  # fyi
        ],
    )
    packet = build_daily_brief_context_packet(
        store=s, brief_date="2026-06-15", window=_win(), now_utc=MON, db_path=db
    )
    cal = packet["calendar"]
    titles = [m["title"] for m in cal["meetings"]]
    assert "TWN OAC Coordination" in titles  # prep-worthy surfaced
    assert cal["excluded_count"] >= 1  # PTO excluded pre-model
    assert all("title" in m and "id" in m and "local_time" in m for m in cal["meetings"])
    assert "caps" in packet and packet["caps"]["max_meetings"] == 15


def test_7_malformed_model_output_fails_closed(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    r = synthesize_daily_brief(
        store=s,
        brief_date="2026-06-15",
        window=_win(),
        now_utc=MON,
        db_path=db,
        backend=StaticOutputClient("not json {"),
        dry_run=True,
    )
    assert r.degraded is True and r.synthesis is None and r.schema_valid is False


def test_8_low_quality_empty_output_is_degraded_not_success(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    r = synthesize_daily_brief(
        store=s,
        brief_date="2026-06-15",
        window=_win(),
        now_utc=MON,
        db_path=db,
        backend=StaticOutputClient("{}"),
        dry_run=True,
    )
    assert r.degraded is True and r.degraded_reason == "empty_synthesis_low_quality"


def test_9_raw_prompt_and_response_not_persisted(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    synthesize_daily_brief(
        store=s,
        brief_date="2026-06-15",
        window=_win(),
        now_utc=MON,
        db_path=db,
        backend=StaticOutputClient(GOOD_SYNTH),
        dry_run=False,  # writes a receipt
    )
    receipts = s.list_local_model_run_receipts(limit=10)
    assert receipts, "a hash-only receipt should be written on apply"
    blob = json.dumps(receipts, default=str)
    # only hashes + metadata — never the packet body or model prose
    assert "executive_summary" not in blob and "Tropical" not in blob
    assert "CONTEXT_PACKET" not in blob


# =============================================================================
# 10-19 — CONTENT QUALITY
# =============================================================================


def _render_good() -> str:
    syn = DailyBriefSynthesis.model_validate(json.loads(GOOD_SYNTH))
    return render_synthesis_markdown(
        syn,
        brief_date="2026-06-15",
        window=_win(),
        model_metadata={"model_name": "m", "profile_id": "brief_synthesis", "status": "ok"},
        generated_label="2026-06-15T05:00:00",
    )


def test_10_to_13_required_sections_and_meeting_prep_present() -> None:
    md = _render_good()
    assert "## Executive Summary" in md
    assert "What Changed Since Last Brief" in md
    assert "## Open Commitments & Follow-Ups" in md
    assert "## Today's Meetings" in md
    assert "Mon 11:00 AM" in md and "Prep:" in md  # local time + prep notes


def test_12_open_commitments_empty_state() -> None:
    empty = DailyBriefSynthesis.model_validate({"executive_summary": ["x"]})
    md = render_synthesis_markdown(
        empty,
        brief_date="2026-06-15",
        window=_win(),
        model_metadata={"model_name": "m", "profile_id": "p", "status": "ok"},
        generated_label="t",
    )
    assert "No open commitments or follow-up items found" in md
    assert "No critical due-today actions found" in md
    assert "No meeting-prep items required attention" in md


def test_14_calendar_noise_is_filtered_or_demoted() -> None:
    assert classify_calendar_event(title="Bobby PTO").klass == "excluded"
    assert classify_calendar_event(title="IT maintenance window").klass == "excluded"
    assert classify_calendar_event(title="Weekly huddle", attendee_count=8).klass == "fyi"
    assert (
        classify_calendar_event(title="TWN OAC Coordination", has_project=True).klass
        == "requires_prep"
    )


def test_15_technical_relationship_rows_not_in_main_body() -> None:
    md = _render_good()
    assert "↔" not in md  # no raw relationship technical rows
    assert "raw_context" not in md and "raw_content" not in md
    assert "## Related Context" not in md


def test_16_project_alias_assigns_known_tokens() -> None:
    assert resolve_project("TWN OAC Coordination") == "tropical"
    assert resolve_project("PGA The Modern review") == "pga-modern-garage"
    assert resolve_project("Alton Hilltop punch") == "alton-hilltop-pbg"
    assert resolve_project("The Wellington Homes kickoff") == "the-wellington"
    assert resolve_project("Generic weekly sync") is None


def test_17_unassigned_items_grouped_not_inline(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    # Prep-worthy (RFI keyword → visible) but no project alias match → stays unassigned.
    s = _seed(db, events=[("ev0", "Mystery RFI submittal review", None)])
    packet = build_daily_brief_context_packet(
        store=s, brief_date="2026-06-15", window=_win(), now_utc=MON, db_path=db
    )
    # unassigned calendar items are surfaced as a project-review signal, not project:__unassigned__
    assert packet["calendar"]["unassigned"] >= 1
    assert any("could not be assigned to a project" in g for g in packet["data_gaps"])
    md = _render_good()
    assert "project:__unassigned__" not in md


def test_18_empty_source_families_render_clear_empty_states() -> None:
    empty = DailyBriefSynthesis.model_validate({"executive_summary": ["x"]})
    md = render_synthesis_markdown(
        empty,
        brief_date="2026-06-15",
        window=_win(),
        model_metadata={"model_name": "m", "profile_id": "p", "status": "ok"},
        generated_label="t",
    )
    assert "No Procore project signals were generated in this run." in md


def test_19_friday_and_monday_window_labels_render() -> None:
    mon = _render_good()  # built with Monday window
    assert "Prior Week / Weekend Carryover" in mon
    syn = DailyBriefSynthesis.model_validate(json.loads(GOOD_SYNTH))
    fri = render_synthesis_markdown(
        syn,
        brief_date="2026-06-19",
        window=_win(FRI),
        model_metadata={"model_name": "m", "profile_id": "p", "status": "ok"},
        generated_label="t",
    )
    assert "Next Week Prep" in fri


# =============================================================================
# 20-30 — SAFETY / REDACTION / DEGRADED / EGRESS
# =============================================================================


def _candidate_titles(db: str) -> list[str]:
    conn = sqlite3.connect(db)
    rows = [r[0] for r in conn.execute("SELECT title_redacted FROM daily_brief_action_candidates")]
    conn.close()
    return rows


def test_20_21_22_raw_only_in_private_outputs_not_status_or_rows(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db, raw_subject="ZEBRAQUARTERLY review")
    run_daily_local_agent(
        store=s,
        now_utc=MON,
        db_path=db,
        dry_run=False,
        max_persist_per_stage=10,
        include_raw=True,
        synthesize_brief=True,
        synthesis_backend=StaticOutputClient(GOOD_SYNTH),
        write_obsidian=True,
        confirm_vault_write=True,
        **_dirs(tmp_path),
    )
    obsidian = (tmp_path / "vault" / "2026-06-15_daily_brief.md").read_text()
    browser = (tmp_path / "html" / "daily-brief-2026-06-15.html").read_text()
    status = (tmp_path / "status" / "latest-status.json").read_text()
    assert "ZEBRAQUARTERLY" in obsidian  # raw allowed in governed Obsidian note
    assert "ZEBRAQUARTERLY" in browser  # raw allowed in private browser brief
    assert "ZEBRAQUARTERLY" not in status  # never in status JSON
    assert all("ZEBRAQUARTERLY" not in t for t in _candidate_titles(db))  # persisted rows redacted


def test_23_guard_columns_zero_after_apply(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    run_daily_local_agent(
        store=s,
        now_utc=MON,
        db_path=db,
        dry_run=False,
        max_persist_per_stage=10,
        synthesize_brief=True,
        synthesis_backend=StaticOutputClient(GOOD_SYNTH),
        **_dirs(tmp_path),
    )
    conn = sqlite3.connect(db)
    cols = ", ".join(_GUARD_COLUMNS)
    rows = conn.execute(f"SELECT {cols} FROM daily_brief_action_candidates").fetchall()
    conn.close()
    assert rows and all(all(v == 0 for v in row) for row in rows)


def test_24_25_no_external_or_source_mutation(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = run_daily_local_agent(
        store=s,
        now_utc=MON,
        db_path=db,
        dry_run=False,
        max_persist_per_stage=10,
        synthesize_brief=True,
        synthesis_backend=StaticOutputClient(GOOD_SYNTH),
        **_dirs(tmp_path),
    )
    assert out["guardrails"]["no_external_writeback"] is True
    # calendar table unchanged (no mutation)
    conn = sqlite3.connect(db)
    n = conn.execute("SELECT COUNT(*) FROM calendar_event_index").fetchone()[0]
    conn.close()
    assert n == 1


def test_26_27_degraded_preserves_last_good_and_is_marked(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    d = _dirs(tmp_path)
    # 1) a successful synthesized run establishes last-good
    run_daily_local_agent(
        store=s,
        now_utc=MON,
        db_path=db,
        dry_run=False,
        max_persist_per_stage=10,
        synthesize_brief=True,
        synthesis_backend=StaticOutputClient(GOOD_SYNTH),
        **d,
    )
    latest = tmp_path / "html" / "daily-brief-latest.html"
    good = latest.read_bytes()
    pointer = json.loads((tmp_path / "status" / "last-successful.json").read_text())
    # 2) a degraded run (model unavailable) must NOT clobber last-good and must mark partial
    out = run_daily_local_agent(
        store=s,
        now_utc=MON,
        db_path=db,
        dry_run=False,
        max_persist_per_stage=10,
        synthesize_brief=True,
        synthesis_backend=StaticOutputClient(raise_unavailable=True),
        **d,
    )
    # A deterministic-useful brief with degraded synthesis is an operator-usable fallback, NOT a
    # generic partial/unusable run: explicit status, no partial:false contradiction, fallback marked.
    assert out["status"] == "deterministic_success_synthesis_degraded"
    assert out["synthesis_degraded"] is True
    assert out["partial"] is False
    assert out["deterministic_fallback_used"] is True
    assert out["operator_usable"] is True
    assert latest.read_bytes() == good  # daily-brief-latest.html reserved for full success (preserved)
    pointer2 = json.loads((tmp_path / "status" / "last-successful.json").read_text())
    assert pointer2["updated"] == pointer["updated"]  # full-success pointer not advanced
    # Option A: the deterministic fallback publishes its own stable path, clearly marked operator-usable.
    det_latest = (tmp_path / "html" / "daily-brief-latest-deterministic.html").read_text()
    assert "Deterministic source-linked brief published" in det_latest
    assert "NOT counted as successful" not in det_latest
    attempted = (tmp_path / "html" / "daily-brief-latest-attempted.html").read_text()
    assert "Deterministic source-linked brief published" in attempted


def test_28_browser_html_egress_scan_clean(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db, raw_subject="Sync https://evil.com/x?sig=tok teams.microsoft.com/l/m a@b.com")
    out = run_daily_local_agent(
        store=s,
        now_utc=MON,
        db_path=db,
        dry_run=False,
        max_persist_per_stage=10,
        include_raw=True,
        synthesize_brief=True,
        synthesis_backend=StaticOutputClient(GOOD_SYNTH),
        **_dirs(tmp_path),
    )
    assert out["egress_scan"]["clean"] is True
    html = (tmp_path / "html" / "daily-brief-2026-06-15.html").read_text()
    for forbidden in ("https://", "evil.com", "teams.microsoft.com", "sig=tok", "a@b.com"):
        assert forbidden not in html


def test_29_no_repo_contained_output_paths(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    repo = str(Path(__file__).resolve().parents[1] / "scratch_x")
    out = run_daily_local_agent(
        store=s,
        now_utc=MON,
        db_path=db,
        dry_run=True,
        browser_output_dir=repo,
        status_dir=str(tmp_path / "s"),
    )
    assert out["status"] == "failure" and out["error"] == "output_path_inside_repo_refused"


def test_30_unresolved_token_diagnostics_for_alias_coverage() -> None:
    diag = summarize_unresolved_tokens(["Acme Tower kickoff", "Acme Tower review"], top=5)
    assert diag and diag[0]["token"] == "Acme Tower" and diag[0]["count"] == 2


def test_status_json_carries_safe_model_metadata_only(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    run_daily_local_agent(
        store=s,
        now_utc=MON,
        db_path=db,
        dry_run=False,
        max_persist_per_stage=10,
        synthesize_brief=True,
        synthesis_backend=StaticOutputClient(GOOD_SYNTH),
        **_dirs(tmp_path),
    )
    status = json.loads((tmp_path / "status" / "latest-status.json").read_text())
    syn = status["synthesis"]
    assert set(syn) >= {"profile_id", "model_name", "status", "degraded"}
    assert "prompt" not in json.dumps(syn) and "response" not in json.dumps(syn)


def test_scheduler_emits_synthesize_flag() -> None:
    args = DailyRunLaunchdManager(label="com.hb.test.syn").render_plist()["ProgramArguments"]
    assert "--synthesize" in args
