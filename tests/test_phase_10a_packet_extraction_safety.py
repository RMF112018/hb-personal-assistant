"""Phase 10A — packet extraction safety: dry-run zero writes, triage no-persist, linkage."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.second_brain import app
from hb_assistant.construction.second_brain.local_ai import (
    build_email_thread_action_packet,
    build_related_context_action_packet,
    build_triage_batch_packet,
    extract_actions_for_packet,
)
from hb_assistant.construction.second_brain.local_ai.schema import PHASE_10_GUARD_COLUMNS
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()

_RAW_TABLES = ("task_candidates", "commitment_candidates", "candidate_source_refs",
               "local_model_run_receipts")


def _seed_thread(store: ConstructionStore, *, thread_ref: str = "t1", msg_id: str = "m1") -> None:
    store.upsert_email_thread_raw_context(
        raw_thread_context_id=f"rtc-{thread_ref}", thread_ref=thread_ref, project_key="P",
        message_count=1, thread_subject="RFI 42 follow-up",
        messages_json=json.dumps([{"id": msg_id, "subject": "RFI 42 follow-up",
                                   "body_text": "Please submit the revised RFI 42 sketch by Friday.",
                                   "sent_at_utc": "2026-06-07T12:00:00+00:00"}]),
        source_refs_json="[]", model_ready=1,
    )


def _candidate(source_ref: str = "m1") -> str:
    return json.dumps([{
        "candidate_type": "task", "title": "Submit revised RFI 42 sketch by Friday",
        "project_key": "P", "assignee": "user", "due_at": None, "urgency": "normal",
        "waiting_state": "waiting_on_me", "source_refs": [source_ref], "confidence": 0.85,
        "reason": "Email asks to submit the revised RFI 42 sketch by Friday.",
        "safety_category": "normal", "recommended_next_action": "review",
        "review_status": "pending", "external_action_requires_approval": True,
    }])


def _counts(store: ConstructionStore) -> dict:
    return {
        "task": len(store.list_task_candidates()),
        "commitment": len(store.list_commitment_candidates()),
        "refs": len(store.list_candidate_source_refs(candidate_type="task")),
        "receipts": len(store.list_local_model_run_receipts()),
    }


def test_dry_run_extraction_writes_nothing() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "x.db"))
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        rep = extract_actions_for_packet(packet=pkt, store=s, dry_run=True, mock_output=_candidate())
        assert rep["extracted"] is True and rep["accepted"] == 1 and rep["persisted"] == 0
        assert _counts(s) == {"task": 0, "commitment": 0, "refs": 0, "receipts": 0}


def test_triage_packet_cannot_persist_candidates() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "x2.db"))
        _seed_thread(s)
        triage = build_triage_batch_packet(store=s)
        # Even on apply, a triage packet never persists task/commitment candidates.
        rep = extract_actions_for_packet(packet=triage, store=s, dry_run=False, mock_output=_candidate())
        assert rep["extracted"] is False
        assert rep["persisted"] == 0
        assert rep["note"] == "purpose_does_not_allow_candidate_actions"
        assert _counts(s) == {"task": 0, "commitment": 0, "refs": 0, "receipts": 0}


def test_apply_persists_after_validation_with_linkage() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "x3.db")
        s = ConstructionStore(db_path=db)
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        rep = extract_actions_for_packet(packet=pkt, store=s, dry_run=False, mock_output=_candidate())
        assert rep["persisted"] == 1
        tasks = s.list_task_candidates()
        refs = s.list_candidate_source_refs(candidate_type="task")
        assert len(tasks) == 1 and len(refs) == 1
        assert refs[0]["candidate_id"] == tasks[0]["candidate_id"]  # linkage to persisted id
        assert refs[0]["source_ref_hash"] == "m1"  # resolves back to the raw message
        conn = sqlite3.connect(db)
        expr = " + ".join(f"COALESCE(SUM({g}),0)" for g in PHASE_10_GUARD_COLUMNS)
        for table in ("task_candidates", "candidate_source_refs"):
            assert int(conn.execute(f"SELECT {expr} FROM {table}").fetchone()[0]) == 0
        conn.close()


def test_apply_rejects_generic_candidate() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "x4.db"))
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        generic = json.dumps([{
            "candidate_type": "task", "title": "Analyze the data and clean up the fields",
            "project_key": "P", "assignee": "user", "due_at": None, "urgency": "low",
            "waiting_state": "unknown", "source_refs": ["m1"], "confidence": 0.6,
            "reason": "Perform data analysis and normalize the spreadsheet fields.",
            "safety_category": "normal", "recommended_next_action": "review",
            "review_status": "pending", "external_action_requires_approval": True,
        }])
        rep = extract_actions_for_packet(packet=pkt, store=s, dry_run=False, mock_output=generic)
        assert rep["accepted"] == 0 and rep["persisted"] == 0
        assert s.list_task_candidates() == []


def _seed_strong_pair(store: ConstructionStore) -> None:
    """A strongly-related thread + event (same project, RFI 42, participant + time overlap)."""
    store.upsert_email_thread_raw_context(
        raw_thread_context_id="rtc-t1", thread_ref="t1", project_key="HILL", message_count=1,
        thread_subject="Hilltop RFI 42 coordination",
        messages_json=json.dumps([{"id": "m1", "subject": "Hilltop RFI 42 coordination",
                                   "from_address": "pm@sub.com", "to_recipients": ["bob@hbcd.com"],
                                   "body_text": "Confirm the revised RFI 42 sketch before the meeting.",
                                   "sent_at_utc": "2026-06-07T12:00:00+00:00"}]),
        source_refs_json="[]", model_ready=1,
    )
    store.upsert_calendar_event_raw_content(
        raw_calendar_event_id="raw:e1", event_index_id="e1", graph_event_id_hash="gh1",
        project_key="HILL", subject="Hilltop RFI 42 coordination", body_text="Discuss RFI 42",
        organizer_name="PM", organizer_email="pm@sub.com",
        attendees_json=json.dumps([{"email": "bob@hbcd.com"}]),
        start_datetime_utc="2026-06-08T09:00:00+00:00", end_datetime_utc="2026-06-08T09:30:00+00:00",
    )


def test_blocked_related_packet_never_calls_model() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "blk.db"))
        # Unrelated thread + event → related packet does not compile.
        s.upsert_email_thread_raw_context(
            raw_thread_context_id="rtc-t1", thread_ref="t1", project_key="A", message_count=1,
            thread_subject="Lunch order",
            messages_json=json.dumps([{"id": "m1", "body_text": "sandwiches"}]),
            source_refs_json="[]", model_ready=1,
        )
        s.upsert_calendar_event_raw_content(
            raw_calendar_event_id="raw:e1", event_index_id="e1", graph_event_id_hash="gh1",
            project_key="B", subject="Budget review", body_text="numbers",
            organizer_email="z@c.com", attendees_json="[]",
            start_datetime_utc="2026-06-08T09:00:00+00:00", end_datetime_utc="2026-06-08T09:30:00+00:00",
        )
        packet = build_related_context_action_packet(thread_ref="t1", store=s)
        assert packet["compiled"] is False
        # A mock that WOULD produce a candidate; the blocked packet must ignore it (no model call).
        rep = extract_actions_for_packet(packet=packet, store=s, dry_run=False, mock_output=_candidate())
        assert rep["extracted"] is False and rep["blocked"] is True and rep["persisted"] == 0
        assert rep["candidates"] == []
        assert rep["note"] == "no_strong_or_moderate_relationship"
        assert "best_confidence" in rep
        assert _counts(s) == {"task": 0, "commitment": 0, "refs": 0, "receipts": 0}


def test_related_packet_per_ref_source_family_attribution() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "fam.db"))
        _seed_strong_pair(s)
        packet = build_related_context_action_packet(thread_ref="t1", store=s)
        assert packet["compiled"] is True and packet["content"]["events"]
        # Candidate cites BOTH the email message ref and the calendar event ref.
        cand = json.dumps([{
            "candidate_type": "task", "title": "Confirm revised RFI 42 sketch before the meeting",
            "project_key": "HILL", "assignee": "user", "due_at": None, "urgency": "normal",
            "waiting_state": "waiting_on_me", "source_refs": ["m1", "e1"], "confidence": 0.85,
            "reason": "Email asks to confirm RFI 42 sketch before the coordination meeting.",
            "safety_category": "normal", "recommended_next_action": "review",
            "review_status": "pending", "external_action_requires_approval": True,
        }])
        rep = extract_actions_for_packet(packet=packet, store=s, dry_run=False, mock_output=cand)
        assert rep["persisted"] == 1
        refs = s.list_candidate_source_refs(candidate_type="task")
        fam = {r["source_ref_hash"]: r["source_family"] for r in refs}
        assert fam["m1"] == "email_message_raw_content"
        assert fam["e1"] == "calendar_event_raw_content"  # not inferred as email


def test_no_client_returns_explicit_diagnostic_not_no_output() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "diag.db"))
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        # No mock + no client → NO model called → explicit no_client_constructed diagnostic.
        rep = extract_actions_for_packet(packet=pkt, store=s, dry_run=True, mock_output=None)
        assert rep["note"] == "no_model_client"
        assert rep["note"] != "model returned no output"
        diag = rep["diagnostics"]
        assert diag["reason"] == "no_client_constructed"
        assert diag["prompt_char_count"] > 0
        assert diag["endpoint_reachable"] is None
        assert diag["model_name"] is None
        assert diag["error_class_redacted"] is None
        assert "http" not in json.dumps(diag).lower()


def test_thread_ref_citation_persists_email_thread_family() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "tr.db"))
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        # Candidate cites the THREAD ref (in packet source_refs as email_thread_raw_context).
        cand = json.dumps([{
            "candidate_type": "task", "title": "Submit revised RFI 42 sketch by Friday",
            "project_key": "P", "assignee": "user", "due_at": None, "urgency": "normal",
            "waiting_state": "waiting_on_me", "source_refs": ["t1"], "confidence": 0.85,
            "reason": "Email asks to submit the revised RFI 42 sketch by Friday.",
            "safety_category": "normal", "recommended_next_action": "review",
            "review_status": "pending", "external_action_requires_approval": True,
        }])
        rep = extract_actions_for_packet(packet=pkt, store=s, dry_run=False, mock_output=cand)
        assert rep["persisted"] == 1
        refs = s.list_candidate_source_refs(candidate_type="task")
        assert refs[0]["source_ref_hash"] == "t1"
        assert refs[0]["source_family"] == "email_thread_raw_context"  # not calendar


def test_event_ref_citation_persists_calendar_family() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "er.db"))
        s.upsert_calendar_event_raw_content(
            raw_calendar_event_id="raw:e1", event_index_id="e1", graph_event_id_hash="gh1",
            project_key="P", subject="Coordination", body_text="Discuss RFI 42 before pour",
            organizer_email="pm@sub.com", attendees_json="[]",
            start_datetime_utc="2026-06-08T09:00:00+00:00", end_datetime_utc="2026-06-08T09:30:00+00:00",
        )
        from hb_assistant.construction.second_brain.local_ai import (
            build_calendar_event_action_packet,
        )
        pkt = build_calendar_event_action_packet(event_index_id="e1", store=s)
        cand = json.dumps([{
            "candidate_type": "task", "title": "Confirm RFI 42 status before the pour",
            "project_key": "P", "assignee": "user", "due_at": None, "urgency": "normal",
            "waiting_state": "waiting_on_me", "source_refs": ["e1"], "confidence": 0.8,
            "reason": "Event agenda asks to confirm RFI 42 before the pour.",
            "safety_category": "normal", "recommended_next_action": "review",
            "review_status": "pending", "external_action_requires_approval": True,
        }])
        rep = extract_actions_for_packet(packet=pkt, store=s, dry_run=False, mock_output=cand)
        assert rep["persisted"] == 1
        refs = s.list_candidate_source_refs(candidate_type="task")
        assert refs[0]["source_family"] == "calendar_event_raw_content"


def test_unknown_source_ref_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "ur.db"))
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        cand = json.dumps([{
            "candidate_type": "task", "title": "Do the thing referenced nowhere in the packet",
            "project_key": "P", "assignee": "user", "due_at": None, "urgency": "normal",
            "waiting_state": "waiting_on_me", "source_refs": ["totally-unknown-ref"], "confidence": 0.8,
            "reason": "Cites a source ref not present in the packet.",
            "safety_category": "normal", "recommended_next_action": "review",
            "review_status": "pending", "external_action_requires_approval": True,
        }])
        rep = extract_actions_for_packet(packet=pkt, store=s, dry_run=False, mock_output=cand)
        assert rep["accepted"] == 0 and rep["persisted"] == 0
        assert any(r.get("reason") == "source_alias_not_in_packet" for r in rep["rejections"])
        assert s.list_task_candidates() == []


def _valid_object_root() -> str:
    return json.dumps({"candidates": [json.loads(_candidate())[0]]})


def test_object_root_output_is_accepted_and_persists() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "obj.db"))
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        rep = extract_actions_for_packet(
            packet=pkt, store=s, dry_run=False, mock_output=_valid_object_root()
        )
        assert rep["produced"] == 1 and rep["accepted"] == 1 and rep["persisted"] == 1
        assert rep["diagnostics"]["root_type"] == "object"
        assert rep["diagnostics"]["has_candidates_key"] is True
        assert rep["diagnostics"]["parsed_candidate_count"] == 1
        assert len(s.list_task_candidates()) == 1


def test_raw_array_output_still_accepted_for_backward_compat() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "arr.db"))
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        rep = extract_actions_for_packet(packet=pkt, store=s, dry_run=False, mock_output=_candidate())
        assert rep["accepted"] == 1 and rep["persisted"] == 1
        assert rep["diagnostics"]["root_type"] == "array"


def _obj_candidate(source_refs: list) -> str:
    base = json.loads(_candidate())[0]
    base["source_refs"] = source_refs
    return json.dumps({"candidates": [base]})


class _PromptCapturingClient:
    """Fake live client that records the prompt and returns object-root empty output."""

    model = "mistral-nemo:12b"

    def __init__(self) -> None:
        self.system = ""
        self.prompt = ""

    def generate_json(self, *, system: str, prompt: str) -> str:
        self.system = system
        self.prompt = prompt
        return '{"candidates":[]}'


def test_alias_src1_resolves_to_thread_ref_family() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "a1.db"))
        _seed_thread(s)  # packet source_refs: [thread t1, message m1] → src_1=t1
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        rep = extract_actions_for_packet(
            packet=pkt, store=s, dry_run=False, mock_output=_obj_candidate(["src_1"])
        )
        assert rep["accepted"] == 1 and rep["persisted"] == 1
        refs = s.list_candidate_source_refs(candidate_type="task")
        assert refs[0]["source_ref_hash"] == "t1"  # alias resolved to canonical thread ref
        assert refs[0]["source_family"] == "email_thread_raw_context"
        assert rep["diagnostics"]["candidate_refs_resolved_count"] == 1


def test_alias_calendar_resolves_to_calendar_family() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "a2.db"))
        s.upsert_calendar_event_raw_content(
            raw_calendar_event_id="raw:e1", event_index_id="e1", graph_event_id_hash="gh1",
            project_key="P", subject="Coordination", body_text="Discuss RFI 42 before pour",
            organizer_email="pm@sub.com", attendees_json="[]",
            start_datetime_utc="2026-06-08T09:00:00+00:00", end_datetime_utc="2026-06-08T09:30:00+00:00",
        )
        from hb_assistant.construction.second_brain.local_ai import (
            build_calendar_event_action_packet,
        )
        pkt = build_calendar_event_action_packet(event_index_id="e1", store=s)
        rep = extract_actions_for_packet(
            packet=pkt, store=s, dry_run=False, mock_output=_obj_candidate(["src_1"])
        )
        assert rep["persisted"] == 1
        refs = s.list_candidate_source_refs(candidate_type="task")
        assert refs[0]["source_ref_hash"] == "e1"
        assert refs[0]["source_family"] == "calendar_event_raw_content"


def test_mixed_related_packet_aliases_preserve_per_ref_family() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "a3.db"))
        _seed_strong_pair(s)  # related packet: src_1=thread, src_2=m1(message), src_3=e1(event)
        pkt = build_related_context_action_packet(thread_ref="t1", store=s)
        assert pkt["compiled"] is True
        rep = extract_actions_for_packet(
            packet=pkt, store=s, dry_run=False, mock_output=_obj_candidate(["src_2", "src_3"])
        )
        assert rep["persisted"] == 1
        fam = {r["source_ref_hash"]: r["source_family"]
               for r in s.list_candidate_source_refs(candidate_type="task")}
        assert fam["m1"] == "email_message_raw_content"
        assert fam["e1"] == "calendar_event_raw_content"


def test_excerpt_label_alias_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "a4.db"))
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        rep = extract_actions_for_packet(
            packet=pkt, store=s, dry_run=False, mock_output=_obj_candidate(["<excerpt1>"])
        )
        assert rep["accepted"] == 0 and rep["persisted"] == 0
        assert any(r.get("reason") == "source_alias_not_in_packet" for r in rep["rejections"])
        assert s.list_task_candidates() == []


def test_unknown_alias_src999_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "a5.db"))
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        rep = extract_actions_for_packet(
            packet=pkt, store=s, dry_run=False, mock_output=_obj_candidate(["src_999"])
        )
        assert rep["accepted"] == 0 and rep["persisted"] == 0
        assert any(r.get("reason") == "source_alias_not_in_packet" for r in rep["rejections"])


def test_alias_dry_run_resolves_but_writes_nothing() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "a6.db"))
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        rep = extract_actions_for_packet(
            packet=pkt, store=s, dry_run=True, mock_output=_obj_candidate(["src_1"])
        )
        assert rep["accepted"] == 1 and rep["persisted"] == 0
        assert _counts(s) == {"task": 0, "commitment": 0, "refs": 0, "receipts": 0}


def test_prompt_includes_allowed_source_aliases_and_no_placeholder() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "a7.db"))
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        fake = _PromptCapturingClient()
        extract_actions_for_packet(packet=pkt, store=s, dry_run=True, mock_output=None, client=fake)
        assert "allowed_source_aliases" in fake.prompt
        assert "src_1" in fake.prompt
        assert "source_alias:" in fake.prompt
        assert "<ref-from-excerpt>" not in fake.prompt
        assert "ref=" not in fake.prompt  # no canonical-ref leakage in the excerpt header
        assert "allowed_source_aliases" in fake.system or "alias" in fake.system


def _prompt_aliases(prompt: str) -> tuple[list[str], set]:
    import re

    shown = re.findall(r"source_alias: (\S+)", prompt)
    allowed = json.loads(prompt.split("allowed_source_aliases:\n", 1)[1])["allowed_source_aliases"]
    return shown, {a["alias"] for a in allowed}


def test_multimessage_thread_prompt_shows_only_registered_aliases() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "mm.db"))
        # Six messages with NO id/message_id_hash → packet messages have id=None (the live failure case).
        msgs = [
            {"subject": f"msg {n}", "body_text": f"please review item {n} by Friday",
             "sent_at_utc": "2026-06-07T12:00:00+00:00"}
            for n in range(6)
        ]
        s.upsert_email_thread_raw_context(
            raw_thread_context_id="r1", thread_ref="THREAD-XYZ", project_key="P", message_count=6,
            thread_subject="RFI thread", messages_json=json.dumps(msgs), source_refs_json="[]",
            model_ready=1,
        )
        pkt = build_email_thread_action_packet(thread_ref="THREAD-XYZ", store=s)
        fake = _PromptCapturingClient()
        extract_actions_for_packet(packet=pkt, store=s, dry_run=True, mock_output=None, client=fake)
        shown, allowed = _prompt_aliases(fake.prompt)
        assert shown, "expected source_alias lines in the prompt"
        # Every displayed alias is registered — no index-based src_2.. leak.
        assert all(a in allowed for a in shown), (shown, allowed)
        # Thread-level: all message excerpts share the one thread alias.
        assert set(shown) == {"src_1"}
        assert "src_2" not in fake.prompt.split("allowed_source_aliases", 1)[0]


def test_displayed_alias_resolves_not_rejected() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "mm2.db"))
        msgs = [{"subject": f"m{n}", "body_text": f"review item {n}",
                 "sent_at_utc": "2026-06-07T12:00:00+00:00"} for n in range(4)]
        s.upsert_email_thread_raw_context(
            raw_thread_context_id="r1", thread_ref="THREAD-ABC", project_key="P", message_count=4,
            thread_subject="thread", messages_json=json.dumps(msgs), source_refs_json="[]",
            model_ready=1,
        )
        pkt = build_email_thread_action_packet(thread_ref="THREAD-ABC", store=s)
        # The model cites the displayed alias (src_1) → resolves to the canonical thread ref, accepted.
        rep = extract_actions_for_packet(
            packet=pkt, store=s, dry_run=False, mock_output=_obj_candidate(["src_1"])
        )
        assert rep["accepted"] == 1 and rep["persisted"] == 1
        refs = s.list_candidate_source_refs(candidate_type="task")
        assert refs[0]["source_ref_hash"] == "THREAD-ABC"
        assert refs[0]["source_family"] == "email_thread_raw_context"
        assert not any(r.get("reason") == "source_alias_not_in_packet" for r in rep["rejections"])


def _candidate_with(**overrides) -> str:
    """Object-root candidate citing src_1 with field overrides (assignee/waiting_state/etc.)."""
    base = json.loads(_candidate())[0]
    base["source_refs"] = ["src_1"]
    base.update(overrides)
    return json.dumps({"candidates": [base]})


def _extract_one(store, packet, mock):
    return extract_actions_for_packet(packet=packet, store=store, dry_run=True, mock_output=mock)


def test_assignee_waiting_state_quality_cases() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "q.db"))
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)

        # "Peter asks Bobby to confirm..." → user / waiting_on_me → accepted.
        r = _extract_one(s, pkt, _candidate_with(
            title="Confirm the revised RFI sketch issuance", assignee="user",
            waiting_state="waiting_on_me"))
        assert r["accepted"] == 1, r["rejections"]

        # "Bobby asks Andrew to add..." → other / waiting_on_others → accepted.
        r = _extract_one(s, pkt, _candidate_with(
            title="Andrew to add the revised detail to the set", assignee="other",
            waiting_state="waiting_on_others"))
        assert r["accepted"] == 1, r["rejections"]

        # "Ryan asks Bobby to forward..." → user / waiting_on_me → accepted.
        r = _extract_one(s, pkt, _candidate_with(
            title="Forward the OAC agenda to the design team", assignee="user",
            waiting_state="waiting_on_me"))
        assert r["accepted"] == 1, r["rejections"]


def test_assignee_waiting_state_inconsistencies_rejected() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "qi.db"))
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)

        # user + waiting_on_others (not a follow-up title) → rejected.
        r = _extract_one(s, pkt, _candidate_with(
            title="Confirm the revised RFI sketch issuance", assignee="user",
            waiting_state="waiting_on_others"))
        assert r["accepted"] == 0
        assert any(x.get("reason") == "assignee_waiting_state_inconsistent" for x in r["rejections"])

        # other + waiting_on_me (not a follow-up title) → rejected.
        r = _extract_one(s, pkt, _candidate_with(
            title="Confirm the revised RFI sketch issuance", assignee="other",
            waiting_state="waiting_on_me"))
        assert r["accepted"] == 0
        assert any(x.get("reason") == "assignee_waiting_state_inconsistent" for x in r["rejections"])

        # follow-up exception: user + waiting_on_others with a "Follow up with..." title → accepted.
        r = _extract_one(s, pkt, _candidate_with(
            title="Follow up with Andrew on the shop drawings", assignee="user",
            waiting_state="waiting_on_others"))
        assert r["accepted"] == 1, r["rejections"]

        # task + not_applicable → rejected.
        r = _extract_one(s, pkt, _candidate_with(
            title="Confirm the revised RFI sketch issuance", waiting_state="not_applicable"))
        assert r["accepted"] == 0
        assert any(x.get("reason") == "task_waiting_state_not_applicable" for x in r["rejections"])


def test_high_stakes_accept_action_normalized_to_review() -> None:
    # A high-stakes candidate the model marks accept/prepare_packet is normalized to review
    # BEFORE validation (so _high_stakes_routing passes), then accepted if otherwise valid.
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "hs.db"))
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        for category, action in (("schedule", "accept"), ("financial", "prepare_packet")):
            r = _extract_one(s, pkt, _candidate_with(
                title="Review the change order pricing impact", safety_category=category,
                recommended_next_action=action))
            assert r["accepted"] == 1, (category, action, r["rejections"])
            assert r["candidates"][0]["recommended_next_action"] == "review"
        # The same high-stakes candidate already marked review is still accepted.
        r = _extract_one(s, pkt, _candidate_with(
            title="Review the change order pricing impact", safety_category="financial",
            recommended_next_action="review"))
        assert r["accepted"] == 1, r["rejections"]
        assert r["candidates"][0]["recommended_next_action"] == "review"


def test_direct_bobby_ask_corrected_to_user_waiting_on_me() -> None:
    # The model mislabels a direct ask TO Bobby as other/waiting_on_others; it is corrected to
    # user/waiting_on_me before validation (and not rejected as inconsistent).
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "ask.db"))
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)

        r = _extract_one(s, pkt, _candidate_with(
            title="Antonio asked Bobby to send draft certification",
            reason="Antonio asked Bobby to send the draft certification to the owner.",
            assignee="other", waiting_state="waiting_on_others"))
        assert r["accepted"] == 1, r["rejections"]
        assert r["candidates"][0]["assignee"] == "user"
        assert r["candidates"][0]["waiting_state"] == "waiting_on_me"

        # High-stakes (financial) direct ask with model action=accept → corrected + normalized.
        r = _extract_one(s, pkt, _candidate_with(
            title="Rob asked Bobby to resend financial statement",
            reason="Rob asked Bobby to resend the financial statement for the draw.",
            assignee="other", waiting_state="waiting_on_others",
            safety_category="financial", recommended_next_action="accept"))
        assert r["accepted"] == 1, r["rejections"]
        c = r["candidates"][0]
        assert c["assignee"] == "user" and c["waiting_state"] == "waiting_on_me"
        assert c["recommended_next_action"] == "review"


def test_followup_title_direct_ask_not_overcorrected() -> None:
    # A "Follow up with [person]" delegation legitimately stays user/waiting_on_others even when the
    # text mentions Bobby — the follow-up exception suppresses the direct-ask correction.
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "fu.db"))
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        r = _extract_one(s, pkt, _candidate_with(
            title="Follow up with Antonio on the draft certification",
            reason="Bobby is asked to keep this moving; follow up with Antonio.",
            assignee="user", waiting_state="waiting_on_others"))
        assert r["accepted"] == 1, r["rejections"]
        assert r["candidates"][0]["assignee"] == "user"
        assert r["candidates"][0]["waiting_state"] == "waiting_on_others"


def test_invented_src3_alias_still_rejected() -> None:
    # Pre-validation normalization must not weaken source-alias enforcement: an invented src_3 over a
    # single-source seeded thread is still rejected.
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "s3.db"))
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        r = _extract_one(s, pkt, _obj_candidate(["src_3"]))
        assert r["accepted"] == 0 and r["persisted"] == 0
        assert any(x.get("reason") == "source_alias_not_in_packet" for x in r["rejections"])


def test_diagnostic_reasons_distinguish_failure_modes() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "dr.db"))
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        # Object-root empty + raw-array empty → valid empty result, NOT empty_model_output.
        obj_empty = extract_actions_for_packet(
            packet=pkt, store=s, dry_run=True, mock_output='{"candidates":[]}'
        )
        assert obj_empty["produced"] == 0 and obj_empty["diagnostics"]["reason"] == "no_candidates"
        arr_empty = extract_actions_for_packet(packet=pkt, store=s, dry_run=True, mock_output="[]")
        assert arr_empty["diagnostics"]["reason"] == "no_candidates"
        # Object without candidates/items → invalid envelope (not empty_model_output).
        envelope = extract_actions_for_packet(packet=pkt, store=s, dry_run=True, mock_output="{}")
        assert envelope["diagnostics"]["reason"] == "invalid_output_envelope"
        # Truly empty raw output → empty_model_output.
        truly_empty = extract_actions_for_packet(packet=pkt, store=s, dry_run=True, mock_output="")
        assert truly_empty["diagnostics"]["reason"] == "empty_model_output"
        # Unparseable → invalid_json_output.
        bad = extract_actions_for_packet(packet=pkt, store=s, dry_run=True, mock_output="{not json")
        assert bad["diagnostics"]["reason"] == "invalid_json_output"
        # Parsed but all rejected → schema_rejected_output.
        generic = json.dumps({"candidates": [{
            "candidate_type": "task", "title": "Analyze the data and clean up the fields",
            "project_key": "P", "assignee": "user", "due_at": None, "urgency": "low",
            "waiting_state": "unknown", "source_refs": ["m1"], "confidence": 0.6,
            "reason": "Perform data analysis and normalize the spreadsheet fields.",
            "safety_category": "normal", "recommended_next_action": "review",
            "review_status": "pending", "external_action_requires_approval": True,
        }]})
        rejected = extract_actions_for_packet(packet=pkt, store=s, dry_run=True, mock_output=generic)
        assert rejected["diagnostics"]["reason"] == "schema_rejected_output"
        # Diagnostics never carry raw response/body/URL.
        assert "http" not in json.dumps(envelope["diagnostics"]).lower()


def test_cli_live_attempt_reports_model_name_not_null() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "live.db")
        s = ConstructionStore(db_path=db)
        _seed_thread(s)
        # No --mock-output, no --no-client → constructs a live Ollama client (default mistral-nemo:12b).
        res = runner.invoke(
            app,
            ["phase-10", "extract-packet", "--thread-ref", "t1", "--timeout-seconds", "1",
             "--db", db, "--json"],
        )
        assert res.exit_code == 0, res.output
        body = json.loads(res.output)
        assert body["model_name"] == "mistral-nemo:12b"
        diag = body["report"].get("diagnostics", {})
        # A live attempt never reports no_client_constructed; model_name is set even when unreachable.
        assert diag.get("reason") != "no_client_constructed"
        assert diag.get("model_name") == "mistral-nemo:12b"


def test_cli_no_client_mode_is_explicit_diagnostic() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "nc.db")
        s = ConstructionStore(db_path=db)
        _seed_thread(s)
        res = runner.invoke(
            app,
            ["phase-10", "extract-packet", "--thread-ref", "t1", "--no-client", "--db", db, "--json"],
        )
        assert res.exit_code == 0, res.output
        body = json.loads(res.output)
        assert body["report"]["diagnostics"]["reason"] == "no_client_constructed"
        assert body["report"]["note"] == "no_model_client"


def test_cli_extract_packet_dry_run_is_default_and_writes_nothing() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "cli.db")
        ConstructionStore(db_path=db)  # migrate
        s = ConstructionStore(db_path=db)
        _seed_thread(s)
        # Default (no flag) is dry-run; --mock-output is the offline path.
        res = runner.invoke(
            app,
            ["phase-10", "extract-packet", "--thread-ref", "t1", "--mock-output", _candidate(),
             "--db", db, "--json"],
        )
        assert res.exit_code == 0, res.output
        body = json.loads(res.output)
        assert body["applied"] is False and body["guardrails"]["dry_run"] is True
        assert s.list_task_candidates() == []
        # Explicit --dry-run behaves the same.
        res2 = runner.invoke(
            app,
            ["phase-10", "extract-packet", "--thread-ref", "t1", "--mock-output", _candidate(),
             "--dry-run", "--db", db, "--json"],
        )
        assert res2.exit_code == 0
        assert json.loads(res2.output)["applied"] is False
        assert s.list_task_candidates() == []


# --- Phase 10A persistence hardening: force review + traceability defaults ----------------------


def _obj_candidate_action(action: str) -> str:
    """Object-root mock candidate (citing src_1) with a chosen recommended_next_action, and with
    traceability fields omitted (null) so persistence defaults are exercised."""
    base = json.loads(_candidate())[0]
    base["source_refs"] = ["src_1"]
    base["recommended_next_action"] = action
    base["model_profile_id"] = None
    base["prompt_template_version"] = None
    base["model_name"] = None
    base["input_window_hash"] = None
    return json.dumps({"candidates": [base]})


def test_live_accept_candidate_persisted_as_review() -> None:
    # A non-high-stakes candidate the model marks `accept` must persist as `review`.
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "force_review.db"))
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        rep = extract_actions_for_packet(
            packet=pkt, store=s, dry_run=False, mock_output=_obj_candidate_action("accept")
        )
        assert rep["accepted"] == 1 and rep["persisted"] == 1
        tasks = s.list_task_candidates()
        assert len(tasks) == 1
        assert tasks[0]["recommended_next_action"] == "review"
        assert rep["candidates"][0]["recommended_next_action"] == "review"


def test_persisted_candidate_has_nonnull_traceability_defaults() -> None:
    # Model omits model_profile_id / prompt_template_version → persisted with Phase 10A defaults.
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "trace.db")
        s = ConstructionStore(db_path=db)
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        rep = extract_actions_for_packet(
            packet=pkt, store=s, dry_run=False, mock_output=_obj_candidate_action("accept")
        )
        assert rep["persisted"] == 1
        tasks = s.list_task_candidates()
        assert tasks[0]["model_profile_id"] == "default_extract"
        assert tasks[0]["prompt_template_version"] == "phase10a-action-extraction-v1.2.7"
        # Reporting-only traceability (no table columns): carried on the candidate dump.
        cand = rep["candidates"][0]
        assert cand["model_name"] == "mock"
        assert cand["input_window_hash"]  # non-null, non-empty
        # No raw-content / no-writeback guard columns remain zero.
        conn = sqlite3.connect(db)
        expr = " + ".join(f"COALESCE(SUM({g}),0)" for g in PHASE_10_GUARD_COLUMNS)
        for table in ("task_candidates", "candidate_source_refs"):
            assert int(conn.execute(f"SELECT {expr} FROM {table}").fetchone()[0]) == 0
        conn.close()
