"""Phase 10A — candidate review service layer.

Covers list/show/summary/accept/ignore/reject/snooze/edit/export over persisted
V41/V43 candidate rows: status transitions, V43 lifecycle columns, the corrected
candidate_review_events audit insert, ignore->suppressed normalization, edit diff
+ source-ref immutability, enum validation, and no-raw output guarantees.
No Ollama, no network — local DB only.
"""

from __future__ import annotations

import ast
import inspect
import sqlite3
import textwrap
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.local_ai.candidate_review import (
    accept_candidate,
    edit_candidate,
    export_review_queue,
    ignore_candidate,
    list_review_candidates,
    reject_candidate,
    review_summary,
    show_review_candidate,
    snooze_candidate,
)
from hb_assistant.construction.second_brain.local_ai.schema import PHASE_10_GUARD_COLUMNS
from hb_assistant.construction.store import ConstructionStore

_FORBIDDEN_KEYS = {
    "raw_body",
    "body",
    "body_text",
    "prompt",
    "response",
    "raw_prompt",
    "raw_response",
    "signed_url",
    "download_url",
    "token",
    "secret",
}


def _store(tmp_path: Path) -> ConstructionStore:
    return ConstructionStore(db_path=str(tmp_path / "review.db"))


def _seed_task(store: ConstructionStore, pk: str, cid: str = "task-001") -> str:
    store.upsert_task_candidate(
        candidate_id=cid,
        stable_key=f"{pk}:task:{cid}",
        title_redacted="Submit foundation inspection report",
        project_key=pk,
        assignee_class="unknown",
        urgency="high",
        waiting_state="unknown",
        safety_category="normal",
        confidence=0.9,
        reason_redacted="Explicit ask in thread.",
        recommended_next_action="review",
        review_status="pending",
    )
    store.upsert_candidate_source_ref(
        source_ref_id=f"sr-{cid}",
        candidate_type="task",
        candidate_id=cid,
        source_family="email_message_raw_content",
        source_ref_hash="hash-abc",
        source_table="email_message_raw_content",
        source_primary_key_hash="hash-abc",
        evidence_redacted="Submit foundation inspection report",
    )
    return cid


def _seed_commitment(store: ConstructionStore, pk: str, cid: str = "comm-001") -> str:
    store.upsert_commitment_candidate(
        candidate_id=cid,
        stable_key=f"{pk}:commitment:{cid}",
        title_redacted="Vendor will deliver shop drawings",
        project_key=pk,
        commitment_actor_class="other",
        urgency="normal",
        waiting_state="waiting_on_others",
        safety_category="normal",
        confidence=0.8,
        reason_redacted="Promise in thread.",
        recommended_next_action="review",
        review_status="pending",
    )
    return cid


def _audit_rows(store: ConstructionStore, candidate_id: str) -> list[sqlite3.Row]:
    conn = sqlite3.connect(str(store._db_path))
    conn.row_factory = sqlite3.Row
    try:
        return list(
            conn.execute(
                "SELECT * FROM candidate_review_events WHERE candidate_id = ? ORDER BY created_utc",
                (candidate_id,),
            )
        )
    finally:
        conn.close()


def _assert_no_forbidden_keys(obj: object) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert k not in _FORBIDDEN_KEYS, f"forbidden key {k!r} present"
            _assert_no_forbidden_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            _assert_no_forbidden_keys(item)


# ---------------------------------------------------------------------------
# Read-only
# ---------------------------------------------------------------------------
def test_summary_counts(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    _seed_task(s, pk)
    _seed_commitment(s, pk)
    rep = review_summary(s, project_key=pk)
    assert rep["ok"] is True
    assert rep["task"]["pending"] == 1
    assert rep["task"]["total"] == 1
    assert rep["commitment"]["pending"] == 1
    assert rep["combined"]["pending"] == 2
    assert rep["combined"]["total"] == 2


def test_list_and_status_filter_and_enum_reject(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    tid = _seed_task(s, pk)
    _seed_commitment(s, pk)
    out = list_review_candidates(s, project_key=pk)
    assert out["count"] == 2
    assert {c["candidate_type"] for c in out["candidates"]} == {"task", "commitment"}

    accept_candidate(s, candidate_id=tid, candidate_type="task")
    accepted = list_review_candidates(s, status="accepted", project_key=pk)
    assert accepted["count"] == 1
    assert accepted["candidates"][0]["candidate_id"] == tid

    with pytest.raises(ValueError):
        list_review_candidates(s, status="ignored")  # not a valid stored status


def test_show_found_and_not_found_with_source_refs(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    tid = _seed_task(s, pk)
    shown = show_review_candidate(s, candidate_id=tid)
    assert shown["ok"] is True
    assert shown["candidate_type"] == "task"
    assert shown["candidate"]["candidate_id"] == tid
    assert len(shown["source_refs"]) == 1
    assert shown["source_refs"][0]["source_ref_hash"] == "hash-abc"

    missing = show_review_candidate(s, candidate_id="nope")
    assert missing["ok"] is False
    assert missing["error"] == "candidate_not_found"


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------
def test_accept_sets_lifecycle_columns_and_audit(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    tid = _seed_task(s, pk)
    res = accept_candidate(
        s, candidate_id=tid, candidate_type="task", reviewer="bobby", note="looks right"
    )
    assert res["ok"] is True
    assert res["prior_review_status"] == "pending"
    assert res["new_review_status"] == "accepted"
    assert res["review_event_id"]

    row = [r for r in s.list_task_candidates(project_key=pk) if r["candidate_id"] == tid][0]
    assert row["review_status"] == "accepted"
    assert row["reviewed_by"] == "bobby"
    assert row["reviewed_utc"]
    assert row["review_note_redacted"] == "looks right"

    audits = _audit_rows(s, tid)
    assert len(audits) == 1
    assert audits[0]["action"] == "accept"
    assert audits[0]["prior_status"] == "pending"
    assert audits[0]["new_status"] == "accepted"
    assert audits[0]["reviewer_ref"] == "bobby"
    assert audits[0]["user_note_redacted"] == "looks right"


def test_reject_and_missing_candidate(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    tid = _seed_task(s, pk)
    res = reject_candidate(s, candidate_id=tid, candidate_type="task", note="bad extraction")
    assert res["new_review_status"] == "rejected"

    missing = reject_candidate(s, candidate_id="ghost", candidate_type="task")
    assert missing["ok"] is False
    assert missing["error"] == "candidate_not_found"


def test_ignore_normalizes_to_suppressed(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    tid = _seed_task(s, pk)
    res = ignore_candidate(s, candidate_id=tid, candidate_type="task")
    assert res["action"] == "ignore"
    assert res["new_review_status"] == "suppressed"
    row = [r for r in s.list_task_candidates(project_key=pk) if r["candidate_id"] == tid][0]
    assert row["review_status"] == "suppressed"
    assert _audit_rows(s, tid)[0]["action"] == "ignore"


def test_snooze_persists_until_and_rejects_bad_timestamp(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    cid = _seed_commitment(s, pk)
    until = "2026-06-12T09:00:00-04:00"
    res = snooze_candidate(s, candidate_id=cid, candidate_type="commitment", until=until)
    assert res["new_review_status"] == "snoozed"
    assert res["snoozed_until_utc"] == until
    row = [r for r in s.list_commitment_candidates(project_key=pk) if r["candidate_id"] == cid][0]
    assert row["review_status"] == "snoozed"
    assert row["snoozed_until_utc"] == until
    assert _audit_rows(s, cid)[0]["snoozed_until_utc"] == until

    with pytest.raises(ValueError):
        snooze_candidate(s, candidate_id=cid, candidate_type="commitment", until="not-a-date")


def test_edit_updates_fields_records_diff_preserves_refs_and_status(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    tid = _seed_task(s, pk)
    res = edit_candidate(
        s,
        candidate_id=tid,
        candidate_type="task",
        title="Submit revised inspection report",
        assignee="user",
        waiting_state="waiting_on_me",
    )
    assert res["ok"] is True
    assert res["review_status"] == "pending"  # edit does not change review decision
    assert res["changes"]["assignee_class"] == {"from": "unknown", "to": "user"}

    row = [r for r in s.list_task_candidates(project_key=pk) if r["candidate_id"] == tid][0]
    assert row["title_redacted"] == "Submit revised inspection report"
    assert row["assignee_class"] == "user"
    assert row["waiting_state"] == "waiting_on_me"
    assert row["review_status"] == "pending"

    # source refs untouched
    refs = s.list_candidate_source_refs(candidate_id=tid)
    assert len(refs) == 1 and refs[0]["source_ref_hash"] == "hash-abc"

    audit = _audit_rows(s, tid)[0]
    assert audit["action"] == "edit"
    assert audit["changes_json_redacted"] and "assignee_class" in audit["changes_json_redacted"]


def test_edit_validates_enums_and_no_edits(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    tid = _seed_task(s, pk)
    with pytest.raises(ValueError):
        edit_candidate(s, candidate_id=tid, candidate_type="task", assignee="nobody")
    with pytest.raises(ValueError):
        edit_candidate(s, candidate_id=tid, candidate_type="task", waiting_state="someday")
    none = edit_candidate(s, candidate_id=tid, candidate_type="task")
    assert none["ok"] is False and none["error"] == "no_edits"


def test_edit_commitment_maps_actor_class(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    cid = _seed_commitment(s, pk)
    res = edit_candidate(s, candidate_id=cid, candidate_type="commitment", assignee="user")
    assert res["changes"]["commitment_actor_class"] == {"from": "other", "to": "user"}
    row = [r for r in s.list_commitment_candidates(project_key=pk) if r["candidate_id"] == cid][0]
    assert row["commitment_actor_class"] == "user"


# ---------------------------------------------------------------------------
# Export + no-raw guarantee
# ---------------------------------------------------------------------------
def test_export_returns_safe_items_with_refs(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    _seed_task(s, pk)
    _seed_commitment(s, pk)
    out = export_review_queue(s, project_key=pk)
    assert out["count"] == 2
    assert all("source_refs" in it for it in out["items"])
    with pytest.raises(ValueError):
        export_review_queue(s, status="bogus")


def test_no_forbidden_keys_in_any_output(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    tid = _seed_task(s, pk)
    _seed_commitment(s, pk)
    _assert_no_forbidden_keys(review_summary(s, project_key=pk))
    _assert_no_forbidden_keys(list_review_candidates(s, project_key=pk))
    _assert_no_forbidden_keys(show_review_candidate(s, candidate_id=tid))
    _assert_no_forbidden_keys(accept_candidate(s, candidate_id=tid, candidate_type="task"))
    _assert_no_forbidden_keys(export_review_queue(s, project_key=pk))


# ---------------------------------------------------------------------------
# Store-layer methods (Prompt 03)
# ---------------------------------------------------------------------------
def test_store_getters_found_and_none(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    tid = _seed_task(s, pk)
    cid = _seed_commitment(s, pk)
    t = s.get_task_candidate(tid)
    assert t is not None and t["candidate_id"] == tid
    assert "snoozed_until_utc" in t and "reviewed_by" in t  # V43 columns projected
    c = s.get_commitment_candidate(cid)
    assert c is not None and c["commitment_actor_class"] == "other"
    assert s.get_task_candidate("missing") is None
    assert s.get_commitment_candidate("missing") is None


def test_store_get_candidate_resolves_type(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    tid = _seed_task(s, pk)
    cid = _seed_commitment(s, pk)
    auto_t = s.get_candidate(tid)
    assert auto_t is not None and auto_t["candidate_type"] == "task"
    auto_c = s.get_candidate(cid)
    assert auto_c is not None and auto_c["candidate_type"] == "commitment"
    # explicit type that doesn't match -> not found
    assert s.get_candidate(tid, candidate_type="commitment") is None
    assert s.get_candidate("ghost") is None


def test_store_list_review_candidates_merge_and_filters(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    tid = _seed_task(s, pk)
    _seed_commitment(s, pk)
    merged = s.list_review_candidates(project_key=pk)
    assert len(merged) == 2
    assert {r["candidate_type"] for r in merged} == {"task", "commitment"}

    s.update_candidate_review_state(
        candidate_type="task", candidate_id=tid, review_status="accepted"
    )
    accepted = s.list_review_candidates(status="accepted", project_key=pk)
    assert len(accepted) == 1 and accepted[0]["candidate_id"] == tid
    assert s.list_review_candidates(project_key="OTHER") == []


def test_store_update_candidate_review_state_sets_lifecycle_columns(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    tid = _seed_task(s, pk)
    ok = s.update_candidate_review_state(
        candidate_type="task",
        candidate_id=tid,
        review_status="snoozed",
        reviewed_utc="2026-06-08T00:00:00+00:00",
        reviewed_by="bobby",
        review_note_redacted="later",
        snoozed_until_utc="2026-06-12T09:00:00-04:00",
    )
    assert ok is True
    row = s.get_task_candidate(tid)
    assert row is not None
    assert row["review_status"] == "snoozed"
    assert row["reviewed_by"] == "bobby"
    assert row["snoozed_until_utc"] == "2026-06-12T09:00:00-04:00"
    assert row["review_note_redacted"] == "later"
    # unknown candidate -> no row updated
    assert (
        s.update_candidate_review_state(
            candidate_type="task", candidate_id="ghost", review_status="accepted"
        )
        is False
    )


def test_store_update_candidate_fields_whitelist(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    tid = _seed_task(s, pk)
    original = s.get_task_candidate(tid)
    assert original is not None
    # Mix of allowed (title_redacted) and disallowed (stable_key, review_status) keys.
    ok = s.update_candidate_fields(
        candidate_type="task",
        candidate_id=tid,
        fields={
            "title_redacted": "Edited title",
            "stable_key": "HACKED",
            "review_status": "accepted",
        },
    )
    assert ok is True
    row = s.get_task_candidate(tid)
    assert row is not None
    assert row["title_redacted"] == "Edited title"  # allowed key applied
    assert row["stable_key"] == original["stable_key"]  # disallowed key ignored
    assert row["review_status"] == "pending"  # disallowed key ignored
    # all-disallowed -> no update
    assert (
        s.update_candidate_fields(
            candidate_type="task", candidate_id=tid, fields={"stable_key": "x"}
        )
        is False
    )


def test_store_insert_candidate_review_event_propagates(tmp_path: Path) -> None:
    """The audit insert must not silently swallow failures (action is NOT NULL)."""
    s = _store(tmp_path)
    pk = "PRJ-1"
    tid = _seed_task(s, pk)
    rid = s.insert_candidate_review_event(
        candidate_type="task", candidate_id=tid, decision="accept", new_status="accepted"
    )
    assert isinstance(rid, str) and rid
    with pytest.raises(sqlite3.IntegrityError):
        s.insert_candidate_review_event(
            candidate_type="task", candidate_id=tid, decision=None  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# List sorting / snooze visibility / guardrail-columns-zero
# ---------------------------------------------------------------------------
def test_list_sorting_by_created_utc_desc(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-SORT"
    for cid in ("t1", "t2", "t3"):
        _seed_task(s, pk, cid=cid)
    # upsert stamps CURRENT_TIMESTAMP (collides within a second) — set distinct values.
    conn = sqlite3.connect(str(s._db_path))
    try:
        for cid, ts in (
            ("t1", "2026-01-01T00:00:00+00:00"),
            ("t2", "2026-02-01T00:00:00+00:00"),
            ("t3", "2026-03-01T00:00:00+00:00"),
        ):
            conn.execute(
                "UPDATE task_candidates SET created_utc = ? WHERE candidate_id = ?", (ts, cid)
            )
        conn.commit()
    finally:
        conn.close()
    order = [r["candidate_id"] for r in s.list_task_candidates(project_key=pk)]
    assert order == ["t3", "t2", "t1"]  # newest-first (ORDER BY created_utc DESC)


def test_snooze_visibility_in_list_and_summary(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-SNZ"
    tid = _seed_task(s, pk)
    until = "2026-06-12T09:00:00-04:00"
    snooze_candidate(s, candidate_id=tid, candidate_type="task", until=until)

    snoozed = list_review_candidates(s, status="snoozed", project_key=pk)
    assert snoozed["count"] == 1
    assert snoozed["candidates"][0]["candidate_id"] == tid
    assert snoozed["candidates"][0]["snoozed_until_utc"] == until

    summ = review_summary(s, project_key=pk)
    assert summ["combined"]["snoozed"] == 1
    assert summ["task"]["snoozed"] == 1


def _guard_sum(db_path: str, table: str) -> int:
    expr = " + ".join(f"COALESCE(SUM({g}),0)" for g in PHASE_10_GUARD_COLUMNS)
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute(f"SELECT {expr} FROM {table}").fetchone()[0])
    finally:
        conn.close()


def test_guardrail_columns_stay_zero_after_review_ops(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-GUARD"
    tid = _seed_task(s, pk)
    cid = _seed_commitment(s, pk)
    # Exercise row updates + audit inserts across all three review-bearing tables.
    accept_candidate(s, candidate_id=tid, candidate_type="task", note="ok")
    edit_candidate(s, candidate_id=tid, candidate_type="task", title="New", assignee="user")
    snooze_candidate(
        s, candidate_id=cid, candidate_type="commitment", until="2026-06-12T09:00:00-04:00"
    )
    assert len(PHASE_10_GUARD_COLUMNS) == 13
    for table in ("task_candidates", "commitment_candidates", "candidate_review_events"):
        assert _guard_sum(str(s._db_path), table) == 0, f"{table} guard columns nonzero"


# ---------------------------------------------------------------------------
# No-raw / no-writeback proofs (Prompt 08)
# ---------------------------------------------------------------------------
# External-write / raw-exposure module-name substrings the review surface must not
# import: Graph (mail/calendar), Procore, generic network/email SDKs, MCP raw
# exposure, and the raw-content packet builders.
_FORBIDDEN_IMPORT_SUBSTRINGS = (
    "graph",
    "procore",
    "msal",
    "requests",
    "httpx",
    "urllib",
    "smtplib",
    "aiohttp",
    "boto",
    "mcp",
    "packet_builders",
)


def _imported_module_names(func: object) -> set[str]:
    """Collect every module name imported within a function/module's own source (AST)."""
    src = textwrap.dedent(inspect.getsource(func))  # type: ignore[arg-type]
    tree = ast.parse(src)
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(n.name for n in node.names)
        elif isinstance(node, ast.ImportFrom):
            mods.add(node.module or "")
    return mods


def test_candidate_review_and_cli_import_no_external_write_surface() -> None:
    """The review service + CLI path import no external-write / raw-exposure surface.

    AST-imports (not raw text), so guardrail prose like 'no_graph_or_procore_writeback'
    and the docstring's 'Procore'/'calendar' never false-positive.
    """
    from hb_assistant.cli import second_brain as cli
    from hb_assistant.construction.second_brain.local_ai import candidate_review

    targets: list[object] = [candidate_review]
    cli_funcs = [
        "review_list",
        "review_show",
        "review_summary_cmd",
        "review_accept",
        "review_ignore",
        "review_reject",
        "review_snooze",
        "review_edit",
        "review_export",
        "_run_review_action",
        "_run_review_batch",
        "_dispatch_review_action",
    ]
    targets.extend(getattr(cli, name) for name in cli_funcs)

    offenders: list[str] = []
    for target in targets:
        for mod in _imported_module_names(target):
            low = mod.lower()
            for bad in _FORBIDDEN_IMPORT_SUBSTRINGS:
                if bad in low:
                    label = getattr(target, "__name__", str(target))
                    offenders.append(f"{label}:{mod}")
    assert offenders == [], f"review surface imports external-write surface: {offenders}"


def test_no_raw_persisted_in_candidate_review_tables(tmp_path: Path) -> None:
    """Review actions persist no raw bodies / prompts / responses / URLs / tokens."""
    s = _store(tmp_path)
    pk = "PRJ-RAW"
    tid = _seed_task(s, pk)
    cid = _seed_commitment(s, pk)
    accept_candidate(s, candidate_id=tid, candidate_type="task", note="reviewed ok")
    edit_candidate(s, candidate_id=tid, candidate_type="task", title="Edited", assignee="user")
    snooze_candidate(
        s, candidate_id=cid, candidate_type="commitment", until="2026-06-12T09:00:00-04:00"
    )
    markers = ("http://", "https://", "-----begin", "private key", "access_token", "bearer ")
    conn = sqlite3.connect(str(s._db_path))
    try:
        for table in (
            "task_candidates",
            "commitment_candidates",
            "candidate_review_events",
            "candidate_source_refs",
        ):
            for row in conn.execute(f"SELECT * FROM {table}"):
                for cell in row:
                    if isinstance(cell, str):
                        low = cell.lower()
                        for m in markers:
                            assert m not in low, f"{table} cell contains raw marker {m!r}"
    finally:
        conn.close()
