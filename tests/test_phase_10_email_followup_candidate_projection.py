"""Phase 10 — deterministic email follow-up candidate projection tests (offline, raw-safe).

Covers the new ``email_followup_candidate_projection`` slice: deterministic family extraction from the
V49 *structured* email/thread substrate, bounded/redacted output with no raw leakage, idempotent
domain + daily-brief persistence with 100% source-ref coverage, honest project resolution
(review-required, never invented keys), the data-gap card flipping to *populated*, and commitment
routing to ``commitment_candidates``. Fully offline — no Ollama, no network, no raw bodies emitted.

Substrate is seeded the real way: ``upsert_*_raw_content`` + ``projection_engine.reprocess(apply=True)``
(the structured projection layer), then the extractor reads only safe structured fields. Raw bodies
carry obvious sentinels that must never appear in any extractor/persistence/receipt surface.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from hb_assistant.construction.email_calendar import projection_engine as eng
from hb_assistant.construction.second_brain.local_ai.email_followup_candidate_projection import (
    FAM_PROJECT_ACTION_ITEM,
    FAM_RESPONSE_NEEDED,
    FAM_STALE_THREAD_NUDGE,
    FAM_THIRD_PARTY_COMMITMENT,
    FAM_TIME_SENSITIVE_FOLLOWUP,
    FAM_USER_COMMITMENT,
    FAM_WAITING_ON_RESPONSE,
    RESOLUTION_RESOLVED,
    RESOLUTION_REVIEW_REQUIRED,
    OwnerIdentity,
    build_email_followup_candidates,
    extract_email_followup_candidates_from_structured,
    resolve_owner_identity,
)
from hb_assistant.construction.store.repositories import ConstructionStore

# Synthetic raw-content sentinels — must never surface anywhere downstream.
BODY = "EMAIL_FOLLOWUP_BODY_SENTINEL"
HTML = "<p>EMAIL_FOLLOWUP_HTML_SENTINEL</p>"
JOIN = "https://teams.microsoft.com/l/EMAIL_FOLLOWUP_JOIN_SENTINEL"
SIGNED = "https://example.invalid/private/EMAIL_FOLLOWUP_SIGNED_URL_SENTINEL?token=SECRET"
TOKEN = "Bearer EMAIL_FOLLOWUP_TOKEN_SENTINEL"
RECIPIENT = "EMAIL_FOLLOWUP_RECIPIENT_SENTINEL@example.invalid"

_OWNER_ADDR = "bobby@hbconstruction.com"
_OWNER = OwnerIdentity(
    addresses=frozenset({_OWNER_ADDR}), domains=frozenset({"hbconstruction.com"})
)
NOW = "2026-06-11T12:00:00+00:00"


def _store(tmp_path: Path) -> ConstructionStore:
    return ConstructionStore(db_path=str(tmp_path / "efu.sqlite"))


def _seed_message(
    store: ConstructionStore,
    *,
    mid: str,
    conv: str,
    subject: str,
    from_address: str,
    received_at_utc: str,
    project_key: str | None = None,
    body_text: str = BODY,
) -> None:
    store.upsert_email_message_raw_content(
        raw_email_id=f"raw:{mid}",
        message_id_hash=mid,
        conversation_id_hash=conv,
        subject=subject,
        body_text=body_text,
        body_html=HTML,
        from_address=from_address,
        to_recipients_json=json.dumps([{"name": "R", "address": RECIPIENT}]),
        received_at_utc=received_at_utc,
        project_key=project_key,
        source_quality="graph_full_body",
    )


def _seed_all_families(store: ConstructionStore) -> None:
    # response_needed: inbound external direct ask.
    _seed_message(
        store,
        mid="mh_resp",
        conv="c_resp",
        subject="Please confirm the revised sketch by Friday",
        from_address="gc@external.com",
        received_at_utc="2026-06-10T09:00:00Z",
    )
    # user_commitment: outbound first-person promise from Bobby.
    _seed_message(
        store,
        mid="mh_user",
        conv="c_user",
        subject="I will send the RFI response",
        from_address=_OWNER_ADDR,
        received_at_utc="2026-06-11T08:00:00Z",
    )
    # third_party_commitment: inbound first-person promise.
    _seed_message(
        store,
        mid="mh_third",
        conv="c_third",
        subject="We will provide the submittal next week",
        from_address="sub@vendor.com",
        received_at_utc="2026-06-09T08:00:00Z",
    )
    # waiting_on_response: outbound ask awaiting a reply, now stale.
    _seed_message(
        store,
        mid="mh_wait",
        conv="c_wait",
        subject="Following up — any update on the schedule?",
        from_address=_OWNER_ADDR,
        received_at_utc="2026-06-02T08:00:00Z",
        project_key="alton-hilltop-pbg",
    )
    # time_sensitive_followup: inbound due signal, no direct ask wording.
    _seed_message(
        store,
        mid="mh_time",
        conv="c_time",
        subject="Reminder deadline no later than Monday",
        from_address="pm@external.com",
        received_at_utc="2026-06-10T08:00:00Z",
        project_key="alton-hilltop-pbg",
    )
    # project_action_item: inbound, project-tagged, follow-up wording but no direct ask.
    _seed_message(
        store,
        mid="mh_proj",
        conv="c_proj",
        subject="Following up on the Hilltop submittal log",
        from_address="arch@external.com",
        received_at_utc="2026-06-10T08:00:00Z",
        project_key="alton-hilltop-pbg",
    )
    # stale_thread_nudge: a stale structured message in a multi-message thread (no other signal).
    _seed_message(
        store,
        mid="mh_nudge",
        conv="c_nudge",
        subject="Coordination notes",
        from_address="x@external.com",
        received_at_utc="2026-06-01T08:00:00Z",
        project_key="alton-hilltop-pbg",
    )
    store.upsert_email_thread_raw_context(
        raw_thread_context_id="rt_nudge",
        thread_ref="c_nudge",
        conversation_id_hash="c_nudge",
        project_key="alton-hilltop-pbg",
        message_count=4,
        thread_subject="Coordination notes",
        messages_json="[]",
        source_quality="metadata_only",
    )
    eng.reprocess(db_path=store._db_path, apply=True, mode=eng.MODE_ENFORCE)


def _extract(store: ConstructionStore):
    return extract_email_followup_candidates_from_structured(
        messages=store.list_email_message_structured(limit=500),
        threads=store.list_thread_structured(limit=500),
        now_utc=NOW,
        owner=_OWNER,
    )


# --------------------------------------------------------------------------------------------------
# Deterministic extraction (Prompt 03).
# --------------------------------------------------------------------------------------------------
def test_all_seven_families_extracted(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_all_families(store)
    fams = {c.family for c in _extract(store)}
    assert fams == {
        FAM_RESPONSE_NEEDED,
        FAM_USER_COMMITMENT,
        FAM_THIRD_PARTY_COMMITMENT,
        FAM_WAITING_ON_RESPONSE,
        FAM_TIME_SENSITIVE_FOLLOWUP,
        FAM_PROJECT_ACTION_ITEM,
        FAM_STALE_THREAD_NUDGE,
    }


def test_bounded_title_and_reason(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_all_families(store)
    for c in _extract(store):
        assert len(c.title_redacted) <= 120
        assert len(c.reason_redacted) <= 240
        assert len(c.recommended_next_action) <= 160


def test_no_raw_sentinels_in_extractor_output(tmp_path: Path) -> None:
    store = _store(tmp_path)
    # A message whose subject itself embeds URL/token/recipient sentinels → must be scrubbed.
    _seed_message(
        store,
        mid="mh_leak",
        conv="c_leak",
        subject=f"Please confirm {JOIN} {SIGNED} {TOKEN} {RECIPIENT} by Friday",
        from_address="gc@external.com",
        received_at_utc="2026-06-10T09:00:00Z",
    )
    eng.reprocess(db_path=store._db_path, apply=True, mode=eng.MODE_ENFORCE)
    blob = json.dumps([c.__dict__ for c in _extract(store)])
    for sentinel in (
        BODY,
        "EMAIL_FOLLOWUP_HTML_SENTINEL",
        "EMAIL_FOLLOWUP_JOIN_SENTINEL",
        "EMAIL_FOLLOWUP_SIGNED_URL_SENTINEL",
        "EMAIL_FOLLOWUP_TOKEN_SENTINEL",
        "EMAIL_FOLLOWUP_RECIPIENT_SENTINEL",
        "teams.microsoft.com",
        "Bearer",
    ):
        assert sentinel not in blob, sentinel


def test_raw_access_not_used_by_default(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_all_families(store)
    before = store.email_followup_readiness_counts()
    cands = _extract(store)
    assert all(c.raw_access_used is False for c in cands)
    # No raw_content_access_events were written by extraction (metadata-only path).
    conn = sqlite3.connect(store._db_path)
    n = conn.execute("SELECT COUNT(*) FROM raw_content_access_events").fetchone()[0]
    conn.close()
    assert n == 0
    assert before  # readiness counts available (smoke)


def test_deterministic_keys_stable(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_all_families(store)
    a = [c.candidate_key for c in _extract(store)]
    b = [c.candidate_key for c in _extract(store)]
    assert a == b and len(a) == len(set(a))


def test_unknown_owner_degrades_direction_families(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_all_families(store)
    unknown = resolve_owner_identity(addresses=[], domains=[])
    fams = {
        c.family
        for c in extract_email_followup_candidates_from_structured(
            messages=store.list_email_message_structured(limit=500),
            threads=store.list_thread_structured(limit=500),
            now_utc=NOW,
            owner=unknown,
        )
    }
    # Direction-dependent families are suppressed when owner identity is unknown.
    assert FAM_USER_COMMITMENT not in fams
    assert FAM_THIRD_PARTY_COMMITMENT not in fams
    assert FAM_RESPONSE_NEEDED not in fams
    assert FAM_WAITING_ON_RESPONSE not in fams
    # Direction-agnostic families still surface.
    assert fams & {FAM_TIME_SENSITIVE_FOLLOWUP, FAM_PROJECT_ACTION_ITEM, FAM_STALE_THREAD_NUDGE}


# --------------------------------------------------------------------------------------------------
# Persistence + source refs (Prompt 04).
# --------------------------------------------------------------------------------------------------
def test_apply_persists_idempotently_with_full_source_ref_coverage(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_all_families(store)

    def _apply():
        return build_email_followup_candidates(
            store=store, now_utc=NOW, dry_run=False, max_persist=100, owner=_OWNER
        )

    r1 = _apply()
    brief = store.list_daily_brief_action_candidates(brief_date=NOW[:10], limit=1000)
    tasks1 = len(store.list_task_candidates())
    commits1 = len(store.list_commitment_candidates())
    n_brief1 = len(brief)
    assert r1["summary"]["persisted"] == r1["summary"]["generated"] > 0
    # 100% source-ref coverage for every persisted daily-brief candidate.
    for c in brief:
        cid = c["daily_brief_action_candidate_id"]
        refs = store.list_candidate_source_refs(
            candidate_type="daily_brief_action", candidate_id=cid
        )
        assert refs, cid
        assert all(r.get("source_family", "").startswith("email_") for r in refs)

    # Second apply on the same DB → no new rows anywhere (idempotent).
    r2 = _apply()
    assert (
        len(store.list_daily_brief_action_candidates(brief_date=NOW[:10], limit=1000)) == n_brief1
    )
    assert len(store.list_task_candidates()) == tasks1
    assert len(store.list_commitment_candidates()) == commits1
    assert r2["summary"]["generated"] == r1["summary"]["generated"]


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_all_families(store)
    rep = build_email_followup_candidates(store=store, now_utc=NOW, dry_run=True, owner=_OWNER)
    assert rep["summary"]["would_persist"] > 0 and rep["summary"]["persisted"] == 0
    assert store.list_task_candidates() == []
    assert store.list_commitment_candidates() == []
    assert store.list_daily_brief_action_candidates(brief_date=NOW[:10], limit=10) == []


def test_commitments_route_to_commitment_table(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_message(
        store,
        mid="mh_user",
        conv="c_user",
        subject="I will send the RFI response",
        from_address=_OWNER_ADDR,
        received_at_utc="2026-06-11T08:00:00Z",
    )
    _seed_message(
        store,
        mid="mh_third",
        conv="c_third",
        subject="We will provide the submittal next week",
        from_address="sub@vendor.com",
        received_at_utc="2026-06-09T08:00:00Z",
    )
    eng.reprocess(db_path=store._db_path, apply=True, mode=eng.MODE_ENFORCE)
    build_email_followup_candidates(
        store=store, now_utc=NOW, dry_run=False, max_persist=50, owner=_OWNER
    )
    commits = store.list_commitment_candidates()
    actors = {c["commitment_actor_class"] for c in commits}
    assert actors == {"user", "other"}
    # Commitments did not leak into the task table.
    assert store.list_task_candidates() == []
    # Each commitment is source-linked.
    for c in commits:
        refs = store.list_candidate_source_refs(
            candidate_type="commitment", candidate_id=c["candidate_id"]
        )
        assert refs and refs[0]["source_family"].startswith("email_")


# --------------------------------------------------------------------------------------------------
# Project resolution + review queue (Prompt 05).
# --------------------------------------------------------------------------------------------------
def test_project_resolution_honest(tmp_path: Path) -> None:
    store = _store(tmp_path)
    # Explicit project key on the row → resolved (preserved).
    _seed_message(
        store,
        mid="mh_explicit",
        conv="c_explicit",
        subject="Status update for your review",
        from_address=_OWNER_ADDR,
        received_at_utc="2026-06-02T08:00:00Z",
        project_key="alton-hilltop-pbg",
    )
    # Project-like-but-unresolved subject → review_required, never invented.
    _seed_message(
        store,
        mid="mh_review",
        conv="c_review",
        subject="Please confirm the Zephyr Tower mockup by Friday",
        from_address="gc@external.com",
        received_at_utc="2026-06-10T09:00:00Z",
    )
    eng.reprocess(db_path=store._db_path, apply=True, mode=eng.MODE_ENFORCE)
    cands = _extract(store)
    by_status = {c.project_resolution_status for c in cands}
    assert RESOLUTION_RESOLVED in by_status
    assert RESOLUTION_REVIEW_REQUIRED in by_status
    # No invented keys: every resolved key is non-empty; review-required carries None.
    for c in cands:
        if c.project_resolution_status == RESOLUTION_REVIEW_REQUIRED:
            assert c.project_key is None
        if c.project_resolution_status == RESOLUTION_RESOLVED:
            assert c.project_key


def test_builder_receipt_is_raw_free_and_reports_coverage(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_all_families(store)
    rep = build_email_followup_candidates(
        store=store, now_utc=NOW, dry_run=False, max_persist=100, owner=_OWNER
    )
    s = rep["summary"]
    assert {
        "would_persist",
        "persisted",
        "generated",
        "project_key_coverage",
        "review_required_count",
        "raw_access_count",
    } <= set(s)
    assert s["raw_access_count"] == 0
    assert 0.0 <= s["project_key_coverage"] <= 1.0
    blob = json.dumps(rep)
    for sentinel in ("SENTINEL", "Bearer", "teams.microsoft.com"):
        assert sentinel not in blob


def test_data_gap_flips_to_populated_after_apply(tmp_path: Path) -> None:
    from hb_assistant.construction.second_brain.local_ai.email_followup_readiness import (
        build_email_followup_data_gap,
    )

    store = _store(tmp_path)
    _seed_all_families(store)
    # Email rows exist, follow-up layers empty → honest data gap.
    before = build_email_followup_data_gap(store)
    assert before["status"] == "data_gap" and before["data_gap_card"] is not None
    build_email_followup_candidates(
        store=store, now_utc=NOW, dry_run=False, max_persist=100, owner=_OWNER
    )
    after = build_email_followup_data_gap(store)
    assert after["status"] == "populated" and after["data_gap_card"] is None


# --------------------------------------------------------------------------------------------------
# Pipeline integration (Prompt 06): stage ordering, receipt, data-gap flip via the real pipeline.
# --------------------------------------------------------------------------------------------------
def test_pipeline_runs_email_followup_stage_and_flips_data_gap(tmp_path, monkeypatch) -> None:
    from hb_assistant.construction.second_brain.local_ai import pipeline as pl
    from hb_assistant.construction.second_brain.local_ai.email_followup_readiness import (
        build_email_followup_data_gap,
    )

    monkeypatch.setenv("HB_ASSISTANT_OWNER_ADDRESSES", _OWNER_ADDR)
    monkeypatch.setenv("HB_ASSISTANT_OWNER_DOMAINS", "hbconstruction.com")
    store = _store(tmp_path)
    _seed_all_families(store)

    assert build_email_followup_data_gap(store)["status"] == "data_gap"
    # Stage ordering: email_followup_projection runs immediately after email_calendar_projection.
    assert pl.STAGE_ORDER.index("email_followup_projection") == (
        pl.STAGE_ORDER.index("email_calendar_projection") + 1
    )

    result = pl.run_local_agent_pipeline(
        store=store,
        now_utc=NOW,
        db_path=store._db_path,
        dry_run=False,
        max_persist_per_stage=100,
        stages=["email_calendar_projection", "email_followup_projection"],
    )
    stages = {s["stage"]: s for s in result["stages"]}
    receipt = stages["email_followup_projection"]
    assert receipt["status"] == "ok" and receipt["persisted"] > 0
    # Data-gap card is replaced once real follow-up candidates are persisted.
    assert build_email_followup_data_gap(store)["status"] == "populated"
    # Brief candidates landed in executive follow-up/waiting/actions sections, all source-linked.
    brief = store.list_daily_brief_action_candidates(brief_date=NOW[:10], limit=1000)
    assert {c["section"] for c in brief} <= {"follow_up", "waiting", "actions"}
    assert brief and all(
        store.list_candidate_source_refs(
            candidate_type="daily_brief_action", candidate_id=c["daily_brief_action_candidate_id"]
        )
        for c in brief
    )
