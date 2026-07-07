"""N8C-14 — citation-safe answer-draft builder behavior.

Proves: the answer_contract GATES the draft (answer_allowed=false → a single insufficient_support section, no
fabricated answer); trusted_answer_draft never admits candidate/deferred/stale support; review_aware labels
candidates; rejected/not_required/superseded and must_not_say targets are excluded-manifest only; every
answer-support section carries ≥1 citation; open loops stay advisory (never tasks); citations preserve the
originating packet_citation_id + provenance and carry read-only source_ref/source_root_key/rel_path (relative,
never absolute); NO live source_file_read happens during drafting; the budget caps sections; and NO
finality-named field is produced anywhere. preview/dry-run never persist or mutate upstream.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import answer_draft_builder as B
from hb_assistant.obsidian_mcp.answer_draft_builder import DraftProviders
from hb_assistant.obsidian_mcp.answer_draft_models import DraftBudget
from hb_assistant.obsidian_mcp.answer_draft_repository import AnswerDraftRepository
from hb_assistant.obsidian_mcp.research_packet_repository import ResearchPacketRepository
from hb_assistant.obsidian_mcp.source_connector_models import decode_source_ref
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository, source_id_for
from hb_assistant.store.migrator import SQLiteMigrator

_FINALITY = ("final_answer", "answer_text", "generated_answer", "authoritative_answer",
             "operator_approved_answer")

# (inclusion_state, answer_role, target_id) rows exercising every routing branch.
_ITEM_SPECS = [
    ("trusted", "primary_support", "C_PRIMARY"),
    ("trusted", "supporting_context", "C_SUPPORT"),
    ("candidate", "candidate_context", "C_CAND"),
    ("deferred", "open_question", "C_OPEN"),
    ("stale", "risk_or_caveat", "C_STALE"),
    ("excluded", "excluded_context", "C_REJECTED"),
    ("not_required", "excluded_context", "C_NOTREQ"),
    ("superseded", "excluded_context", "C_SUPERSEDED"),
]


def _contract(must_not_say: list | None = None) -> tuple[str, str]:
    contract = {"answer_allowed": True, "citation_required": True, "review_labels_required": True,
                "trusted_claims_allowed": True, "candidate_claims_allowed": "with_caveat",
                "must_not_say": must_not_say or [], "unresolved_questions": ["open?"]}
    acj = json.dumps(contract, sort_keys=True, separators=(",", ":"))
    return acj, "d" * 24


def _seed_full_packet(db: str, *, packet_id: str = "PKT", source_id: str | None = None,
                      must_not_say: list | None = None) -> None:
    pr = ResearchPacketRepository(db)
    acj, acd = _contract(must_not_say)
    # inclusion_state → a valid effective_state (the 'excluded' inclusion maps to 'rejected').
    _eff = {"trusted": "accepted", "candidate": "candidate", "deferred": "deferred", "stale": "stale",
            "excluded": "rejected", "not_required": "not_required", "superseded": "superseded"}
    items, cits = [], []
    for i, (inc, role, tid) in enumerate(_ITEM_SPECS):
        included = 0 if inc in ("excluded", "not_required", "superseded") else 1
        item = {"packet_item_id": f"IT{i}", "packet_id": packet_id, "target_kind": "claim",
                "target_id": tid, "effective_state": _eff[inc],
                "inclusion_state": inc, "answer_role": role, "title": f"title-{tid}",
                "summary": f"summary-{tid}", "evidence_excerpt": f"evidence-{tid}", "claim_id": tid,
                "confidence": 0.8, "included": included}
        if i == 0 and source_id:
            item["source_id"] = source_id
        items.append(item)
        if included:
            cits.append({"citation_id": f"PC{i}", "packet_id": packet_id, "packet_item_id": f"IT{i}",
                         "citation_order": 0, "citation_type": "claim", "target_kind": "claim",
                         "target_id": tid, "claim_id": tid,
                         **({"source_id": source_id} if (i == 0 and source_id) else {})})
    pr.upsert_packet(
        {"packet_id": packet_id, "packet_type": "review_aware_answer_context", "answer_contract_json": acj,
         "status": "built", "created_by": "t", "projection_id": "P", "answer_contract_digest": acd,
         "trusted_count": 2, "candidate_count": 1, "excluded_count": 3, "citation_count": len(cits),
         "open_question_count": 1, "item_count": len(items), "truncated": 0, "budget_json": "{}",
         "scope_json": "{}"},
        items, cits,
        {"packet_receipt_id": "R", "packet_id": packet_id, "builder_version": "v", "input_digest": "i",
         "output_digest": "o", "answer_contract_digest": acd})


def _providers(db: str, *, source_repo=None) -> DraftProviders:
    return DraftProviders(packet_repo=ResearchPacketRepository(db), source_repo=source_repo)


def _sections_by_type(export: dict) -> dict[str, list]:
    out: dict[str, list] = {}
    for s in export["sections"]:
        out.setdefault(s["section_type"], []).append(s)
    return out


def test_review_aware_routing_and_labels(tmp_path: Path) -> None:
    db = str(tmp_path / "t.db")
    SQLiteMigrator(db_path=db).apply()
    _seed_full_packet(db)
    repo = AnswerDraftRepository(db)
    # Enable deferred + stale so their advisory routing (open_question / risk) is exercised.
    budget = DraftBudget.for_type("review_aware_answer_draft",
                                  {"include_deferred": True, "include_stale": True})
    res = B.build_answer_draft(_providers(db), repo, packet_id="PKT",
                               draft_type="review_aware_answer_draft", budget=budget, apply=True)
    exp = B.export_answer_draft(repo, draft_id=res["draft_id"])
    by = _sections_by_type(exp)
    assert "direct_answer" in by and "trusted_context" in by
    assert "candidate_context" in by  # candidate surfaced WITH a review label
    assert by["candidate_context"][0]["review_label"] == "candidate — review required"
    assert by["candidate_context"][0]["candidate"] == 1
    assert "open_question" in by and by["open_question"][0]["open_question"] == 1  # deferred → advisory
    assert "risk" in by                                                            # stale → caveat/risk
    # rejected / not_required / superseded → excluded_manifest only (never support), bounded (no body).
    excl_targets = {s["packet_item_id"] for s in by.get("excluded_manifest", [])}
    assert len(excl_targets) == 3
    for s in by["excluded_manifest"]:
        assert s["section_body"] is None and s["excluded"] == 1


def test_trusted_draft_excludes_candidate_and_deferred(tmp_path: Path) -> None:
    db = str(tmp_path / "t.db")
    SQLiteMigrator(db_path=db).apply()
    _seed_full_packet(db)
    repo = AnswerDraftRepository(db)
    res = B.build_answer_draft(_providers(db), repo, packet_id="PKT",
                               draft_type="trusted_answer_draft", apply=True)
    exp = B.export_answer_draft(repo, draft_id=res["draft_id"])
    by = _sections_by_type(exp)
    # No candidate/open-question support sections in a trusted draft.
    assert "candidate_context" not in by and "open_question" not in by
    # Only trusted items are answer-support.
    support = [s for s in exp["sections"] if s["trusted"] == 1]
    assert support and all(s["inclusion_state"] == "trusted" for s in support)


def test_every_support_section_is_cited(tmp_path: Path) -> None:
    db = str(tmp_path / "t.db")
    SQLiteMigrator(db_path=db).apply()
    _seed_full_packet(db)
    repo = AnswerDraftRepository(db)
    res = B.build_answer_draft(_providers(db), repo, packet_id="PKT",
                               draft_type="review_aware_answer_draft", apply=True)
    exp = B.export_answer_draft(repo, draft_id=res["draft_id"])
    support_types = {"direct_answer", "trusted_context", "candidate_context", "source_summary",
                     "implementation_note"}
    for s in exp["sections"]:
        if s["section_type"] in support_types:
            assert s["citation_ids_json"] and json.loads(s["citation_ids_json"]), s["section_type"]


def test_answer_allowed_false_yields_only_insufficient_support(tmp_path: Path) -> None:
    db = str(tmp_path / "t.db")
    SQLiteMigrator(db_path=db).apply()
    pr = ResearchPacketRepository(db)
    contract = {"answer_allowed": False, "trusted_claims_allowed": False,
                "candidate_claims_allowed": False, "must_not_say": [], "unresolved_questions": ["x?"],
                "citation_required": True, "review_labels_required": True}
    acj = json.dumps(contract, sort_keys=True, separators=(",", ":"))
    pr.upsert_packet(
        {"packet_id": "PKT", "packet_type": "trusted_answer_context", "answer_contract_json": acj,
         "status": "built", "created_by": "t", "projection_id": "P", "answer_contract_digest": "d" * 24,
         "trusted_count": 0, "candidate_count": 0, "excluded_count": 1, "budget_json": "{}",
         "scope_json": "{}", "item_count": 1},
        [{"packet_item_id": "IX", "packet_id": "PKT", "target_kind": "claim", "target_id": "X",
          "effective_state": "rejected", "inclusion_state": "excluded", "answer_role": "excluded_context",
          "title": "r", "claim_id": "X", "included": 0}],
        [], {"packet_receipt_id": "R", "packet_id": "PKT", "builder_version": "v", "input_digest": "i",
             "output_digest": "o", "answer_contract_digest": "d" * 24})
    repo = AnswerDraftRepository(db)
    res = B.build_answer_draft(_providers(db), repo, packet_id="PKT",
                               draft_type="trusted_answer_draft", apply=True)
    assert res["answer_allowed"] is False
    exp = B.export_answer_draft(repo, draft_id=res["draft_id"])
    assert [s["section_type"] for s in exp["sections"]] == ["insufficient_support"]
    assert exp["citation_count"] == 0
    # bounded reason metadata, no fabricated direct answer body.
    meta = json.loads(exp["sections"][0]["metadata_json"])
    assert meta["answer_allowed"] is False and meta["unresolved_question_count"] == 1


def test_must_not_say_target_never_support(tmp_path: Path) -> None:
    db = str(tmp_path / "t.db")
    SQLiteMigrator(db_path=db).apply()
    # Force the trusted primary target into must_not_say — it must NOT appear as a support section.
    _seed_full_packet(db, must_not_say=[{"target_kind": "claim", "target_id": "C_PRIMARY",
                                         "inclusion_state": "excluded"}])
    repo = AnswerDraftRepository(db)
    res = B.build_answer_draft(_providers(db), repo, packet_id="PKT",
                               draft_type="review_aware_answer_draft", apply=True)
    exp = B.export_answer_draft(repo, draft_id=res["draft_id"])
    # IT0 is the trusted-primary target that was forced into must_not_say — it must be excluded, not support.
    it0 = [s for s in exp["sections"] if s["packet_item_id"] == "IT0"]
    assert it0 and all(s["section_type"] == "excluded_manifest" for s in it0)
    assert not any(s["trusted"] == 1 and s["packet_item_id"] == "IT0" for s in exp["sections"])


def test_citations_preserve_packet_lineage_and_source_carrythrough(tmp_path: Path) -> None:
    db = str(tmp_path / "t.db")
    SQLiteMigrator(db_path=db).apply()
    sid = source_id_for("external_file", source_root_key="work", rel_path="contracts/a.pdf")
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO source_intelligence_sources(source_id,source_kind,source_root_key,rel_path,"
                  "active,deleted,created_at,updated_at) VALUES(?,?,?,?,1,0,'t','t')",
                  (sid, "external_file", "work", "contracts/a.pdf"))
    _seed_full_packet(db, source_id=sid)
    repo = AnswerDraftRepository(db)
    res = B.build_answer_draft(_providers(db, source_repo=SourceIndexRepository(db)), repo, packet_id="PKT",
                               draft_type="review_aware_answer_draft", apply=True)
    exp = B.export_answer_draft(repo, draft_id=res["draft_id"])
    cite = next(c for c in exp["citations"] if c["source_id"] == sid)
    assert cite["packet_citation_id"] == "PC0"                 # lineage preserved
    assert cite["source_root_key"] == "work"
    assert cite["rel_path"] == "contracts/a.pdf"               # relative
    assert not cite["rel_path"].startswith("/")                # never absolute
    assert decode_source_ref(cite["source_ref"]) == sid


def test_degraded_lineage_marked_when_no_packet_citation(tmp_path: Path) -> None:
    db = str(tmp_path / "t.db")
    SQLiteMigrator(db_path=db).apply()
    pr = ResearchPacketRepository(db)
    acj, acd = _contract()
    # A trusted primary item with NO packet citation manifest → builder synthesizes a citation from the
    # item's own anchor and marks lineage degraded.
    pr.upsert_packet(
        {"packet_id": "PKT", "packet_type": "review_aware_answer_context", "answer_contract_json": acj,
         "status": "built", "created_by": "t", "projection_id": "P", "answer_contract_digest": acd,
         "trusted_count": 1, "budget_json": "{}", "scope_json": "{}", "item_count": 1},
        [{"packet_item_id": "IT", "packet_id": "PKT", "target_kind": "claim", "target_id": "C",
          "effective_state": "accepted", "inclusion_state": "trusted", "answer_role": "primary_support",
          "title": "T", "summary": "S", "claim_id": "C", "projection_item_id": "PJI", "included": 1}],
        [], {"packet_receipt_id": "R", "packet_id": "PKT", "builder_version": "v", "input_digest": "i",
             "output_digest": "o", "answer_contract_digest": acd})
    repo = AnswerDraftRepository(db)
    res = B.build_answer_draft(_providers(db), repo, packet_id="PKT",
                               draft_type="review_aware_answer_draft", apply=True)
    exp = B.export_answer_draft(repo, draft_id=res["draft_id"])
    assert exp["citation_count"] == 1
    cite = exp["citations"][0]
    assert cite["packet_citation_id"] is None
    assert json.loads(cite["metadata_json"])["citation_lineage"] == "degraded"


def test_no_live_source_file_read_during_drafting(tmp_path: Path, monkeypatch) -> None:
    db = str(tmp_path / "t.db")
    SQLiteMigrator(db_path=db).apply()
    sid = source_id_for("external_file", source_root_key="work", rel_path="contracts/a.pdf")
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO source_intelligence_sources(source_id,source_kind,source_root_key,rel_path,"
                  "active,deleted,created_at,updated_at) VALUES(?,?,?,?,1,0,'t','t')",
                  (sid, "external_file", "work", "contracts/a.pdf"))
    _seed_full_packet(db, source_id=sid)
    # Spy: any live bounded read of an original file must raise (drafting must never call it).
    import hb_assistant.obsidian_mcp.source_content_provider as scp

    def _boom(*a, **k):  # noqa: ANN002, ANN003
        raise AssertionError("source_file_read must not be called during draft generation")

    for name in ("read_source_content", "read_bounded", "read_source_file"):
        if hasattr(scp, name):
            monkeypatch.setattr(scp, name, _boom)
    repo = AnswerDraftRepository(db)
    B.build_answer_draft(_providers(db, source_repo=SourceIndexRepository(db)), repo, packet_id="PKT",
                         draft_type="review_aware_answer_draft", apply=True)  # must not raise


def test_budget_caps_sections(tmp_path: Path) -> None:
    db = str(tmp_path / "t.db")
    SQLiteMigrator(db_path=db).apply()
    _seed_full_packet(db)
    repo = AnswerDraftRepository(db)
    budget = DraftBudget(max_sections=2, include_excluded_manifest=False)
    res = B.build_answer_draft(_providers(db), repo, packet_id="PKT",
                               draft_type="review_aware_answer_draft", budget=budget, apply=True)
    exp = B.export_answer_draft(repo, draft_id=res["draft_id"])
    assert len(exp["sections"]) <= 2
    assert res["truncated"] is True


def test_no_finality_fields_and_preview_is_read_only(tmp_path: Path) -> None:
    db = str(tmp_path / "t.db")
    SQLiteMigrator(db_path=db).apply()
    _seed_full_packet(db)
    repo = AnswerDraftRepository(db)
    preview = B.build_answer_draft(_providers(db), repo, packet_id="PKT",
                                   draft_type="review_aware_answer_draft", apply=False)
    # dry-run persists nothing.
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT COUNT(*) FROM assistant_answer_drafts").fetchone()[0] == 0
    # no finality-named key anywhere in the preview payload / rows.
    blob = json.dumps(preview, default=str)
    assert not any(f in blob for f in _FINALITY)
    for s in preview["sections"]:
        assert not (set(_FINALITY) & set(s.keys()))


def test_open_loops_stay_advisory_not_tasks(tmp_path: Path) -> None:
    db = str(tmp_path / "t.db")
    SQLiteMigrator(db_path=db).apply()
    pr = ResearchPacketRepository(db)
    acj, acd = _contract()
    pr.upsert_packet(
        {"packet_id": "PKT", "packet_type": "implementation_research_context",
         "answer_contract_json": acj, "status": "built", "created_by": "t", "projection_id": "P",
         "answer_contract_digest": acd, "trusted_count": 1, "budget_json": "{}", "scope_json": "{}",
         "item_count": 1},
        [{"packet_item_id": "IT", "packet_id": "PKT", "target_kind": "open_loop", "target_id": "OL",
          "effective_state": "accepted", "inclusion_state": "trusted", "answer_role": "implementation_note",
          "title": "Follow up on X", "summary": "advisory", "open_loop_id": "OL", "included": 1}],
        [{"citation_id": "PC", "packet_id": "PKT", "packet_item_id": "IT", "citation_order": 0,
          "citation_type": "open_loop", "target_kind": "open_loop", "target_id": "OL", "open_loop_id": "OL"}],
        {"packet_receipt_id": "R", "packet_id": "PKT", "builder_version": "v", "input_digest": "i",
         "output_digest": "o", "answer_contract_digest": acd})
    repo = AnswerDraftRepository(db)
    res = B.build_answer_draft(
        _providers(db), repo, packet_id="PKT",
        draft_type="implementation_context_draft",
        budget=DraftBudget.for_type("implementation_context_draft"), apply=True)
    exp = B.export_answer_draft(repo, draft_id=res["draft_id"])
    s = exp["sections"][0]
    assert s["section_type"] == "implementation_note"     # advisory, not a task/command/reminder/job
    assert s["open_question"] == 0


def test_unknown_draft_type_rejected(tmp_path: Path) -> None:
    db = str(tmp_path / "t.db")
    SQLiteMigrator(db_path=db).apply()
    _seed_full_packet(db)
    from hb_assistant.obsidian_mcp.answer_draft_models import AnswerDraftValidationError
    with pytest.raises(AnswerDraftValidationError):
        B.preview_answer_draft(_providers(db), packet_id="PKT", draft_type="bogus_type")
