"""N8C-20 quality EVALUATOR — the guardrail-heavy suite.

Proves the evaluator is a deterministic READ-ONLY advisory layer:
  * ``preview`` and ``build --dry-run`` mutate NOTHING (no quality rows, no upstream rows);
  * ``build --apply`` changes ONLY the five ``assistant_quality_*`` tables — every other N8C table (feedback,
    action-stage, workflow-derived, source, review, draft, packet, context-pack, projection, decision,
    preference, open-loop) is byte-for-byte unchanged (clarification #7);
  * findings are ADVISORY — every finding is no_execution / evaluate_only / requires_operator_review=1 and no
    finding accepts/rejects/defers/disposes/repairs anything;
  * it detects missing_citation / missing_source_ref / execution_language_risk / finality_language_risk /
    policy_mismatch / unknown_target when appropriate;
  * its source imports no execution / external-delivery / LLM / source-file-read / N8D / agent_bridge module,
    and exposes no execute/apply/repair/send entrypoint.
"""

from __future__ import annotations

import ast
import hashlib
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import feedback_service as fs
from hb_assistant.obsidian_mcp import quality_evaluator as E
from hb_assistant.obsidian_mcp.action_stage_repository import ActionStageRepository
from hb_assistant.obsidian_mcp.feedback_repository import FeedbackRepository
from hb_assistant.obsidian_mcp.quality_evaluator import (
    QualityProviders,
    build_quality,
    preview_quality,
)
from hb_assistant.obsidian_mcp.quality_repository import QualityRepository
from hb_assistant.obsidian_mcp.workflow_router import WorkflowRouter
from hb_assistant.store.migrator import SQLiteMigrator

_32HEX = "abcdef0123456789abcdef0123456789"


def _seed_full(db: str) -> str:
    """Populate a realistic DB: one feedback record + one action stage over open-loop triage."""
    from hb_assistant.obsidian_mcp import action_stage_builder as B

    fs.capture_feedback(FeedbackRepository(db), feedback_type="needs_review",
                        targets=[{"target_kind": "open_loop", "target_id": "OL1", "open_loop_id": "OL1"}],
                        apply=True)
    prov = B.ActionStageProviders(router=WorkflowRouter(db), feedback_repo=FeedbackRepository(db))
    out = B.build_action_stage(prov, ActionStageRepository(db),
                               request_inputs={"workflow_type": "open_loop_triage"}, apply=True)
    return out["stage_id"]


def _providers(db: str) -> QualityProviders:
    from hb_assistant.obsidian_mcp.answer_draft_repository import AnswerDraftRepository
    from hb_assistant.obsidian_mcp.research_packet_repository import ResearchPacketRepository
    from hb_assistant.obsidian_mcp.review_repository import ReviewRepository
    from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository

    return QualityProviders(
        action_stage_repo=ActionStageRepository(db), feedback_repo=FeedbackRepository(db),
        draft_repo=AnswerDraftRepository(db), packet_repo=ResearchPacketRepository(db),
        review_repo=ReviewRepository(db), source_repo=SourceIndexRepository(db),
        router=WorkflowRouter(db))


def _snapshot(db: str, *, include_quality: bool) -> dict[str, str]:
    """Content hash of every table (optionally excluding the quality-owned tables)."""
    snap: dict[str, str] = {}
    with sqlite3.connect(db) as c:
        tables = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        for t in sorted(tables):
            if not include_quality and t.startswith("assistant_quality"):
                continue
            rows = c.execute(f"SELECT * FROM {t}").fetchall()  # noqa: S608 (table from sqlite_master)
            snap[t] = hashlib.sha256(repr(rows).encode()).hexdigest()
    return snap


@pytest.fixture()
def seeded(tmp_path: Path):
    db = str(tmp_path / "e.db")
    SQLiteMigrator(db_path=db).apply()
    sid = _seed_full(db)
    return {"db": db, "sid": sid}


# ----- immutability (clarification #7) -----------------------------------------------------------
def test_preview_mutates_nothing(seeded) -> None:
    db = seeded["db"]
    before = _snapshot(db, include_quality=True)
    preview_quality(_providers(db), target_kind="action_stage", target_id=seeded["sid"])
    assert _snapshot(db, include_quality=True) == before


def test_dry_run_mutates_nothing(seeded) -> None:
    db = seeded["db"]
    before = _snapshot(db, include_quality=True)
    build_quality(_providers(db), QualityRepository(db), target_kind="action_stage",
                  target_id=seeded["sid"], apply=False)
    assert _snapshot(db, include_quality=True) == before


def test_apply_changes_only_quality_tables(seeded) -> None:
    db = seeded["db"]
    upstream_before = _snapshot(db, include_quality=False)
    res = build_quality(_providers(db), QualityRepository(db), target_kind="action_stage",
                        target_id=seeded["sid"], apply=True)
    assert res["applied"] is True and res["created"] is True
    # every non-quality table is byte-for-byte unchanged
    assert _snapshot(db, include_quality=False) == upstream_before
    # the quality tables now hold the run
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT COUNT(*) FROM assistant_quality_runs").fetchone()[0] == 1


def test_apply_is_idempotent(seeded) -> None:
    db = seeded["db"]
    repo = QualityRepository(db)
    build_quality(_providers(db), repo, target_kind="action_stage", target_id=seeded["sid"], apply=True)
    after_first = _snapshot(db, include_quality=True)
    build_quality(_providers(db), repo, target_kind="action_stage", target_id=seeded["sid"], apply=True)
    assert _snapshot(db, include_quality=True) == after_first


# ----- advisory posture --------------------------------------------------------------------------
def test_run_and_findings_are_advisory(seeded) -> None:
    db = seeded["db"]
    plan = preview_quality(_providers(db), target_kind="action_stage", target_id=seeded["sid"])
    assert plan["run"]["status"] == "evaluated"
    assert plan["run"]["action_policy"] == "no_execution"
    assert plan["run"]["execution_policy"] == "evaluate_only"
    assert plan["run"]["requires_operator_review"] == 1
    for f in plan["findings"]:
        assert f["execution_policy"] == "evaluate_only"
        assert f["requires_operator_review"] == 1
        # no finding carries a disposition/repair field
        for forbidden in ("accepted", "rejected", "deferred", "disposed", "repaired", "executed"):
            assert forbidden not in f


# ----- detection ---------------------------------------------------------------------------------
def _insert_stage_with_items(db: str) -> None:
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO assistant_action_stages (stage_id, stage_type, status) "
                  "VALUES ('DS','mixed_actions','staged')")
        # item with provenance but NO citation -> missing_citation
        c.execute("INSERT INTO assistant_action_stage_items "
                  "(stage_item_id, stage_id, action_kind, target_id) "
                  "VALUES ('DI1','DS','human_follow_up','OL9')")
        # item whose advisory text reads like execution -> execution_language_risk
        c.execute("INSERT INTO assistant_action_stage_items "
                  "(stage_item_id, stage_id, action_kind, title) "
                  "VALUES ('DI2','DS','human_follow_up','Please send email to the client now')")
        # item referencing a source id absent from the index -> missing_source_ref
        c.execute("INSERT INTO assistant_action_stage_items "
                  "(stage_item_id, stage_id, action_kind, source_id) "
                  f"VALUES ('DI3','DS','human_follow_up','{_32HEX}')")
        c.commit()


def test_detects_defects_in_crafted_stage(tmp_path: Path) -> None:
    db = str(tmp_path / "d.db")
    SQLiteMigrator(db_path=db).apply()
    _insert_stage_with_items(db)
    plan = preview_quality(_providers(db), target_kind="action_stage", target_id="DS")
    types = {f["finding_type"] for f in plan["findings"]}
    assert "missing_citation" in types
    assert "execution_language_risk" in types
    assert "missing_source_ref" in types


def test_unknown_target_when_absent(tmp_path: Path) -> None:
    db = str(tmp_path / "u.db")
    SQLiteMigrator(db_path=db).apply()
    plan = preview_quality(_providers(db), target_kind="action_stage", target_id="does-not-exist")
    assert {f["finding_type"] for f in plan["findings"]} == {"unknown_target"}


def test_policy_mismatch_helper() -> None:
    # The pure policy check flags any deviation from the expected fixed policy.
    assert E._policy_mismatch({"action_policy": "no_execution"}, {"action_policy": "no_execution"}) == []
    assert E._policy_mismatch({"action_policy": "execute"},
                              {"action_policy": "no_execution"}) == ["policy_mismatch"]


def test_text_risk_detection() -> None:
    assert "execution_language_risk" in E._text_risks("we should send email to them")
    assert "finality_language_risk" in E._text_risks("this is the final answer, guaranteed")
    assert E._text_risks("a bounded advisory observation") == []


def test_unknown_target_kind_rejected(seeded) -> None:
    from hb_assistant.obsidian_mcp.quality_models import QualityValidationError

    with pytest.raises(QualityValidationError):
        preview_quality(_providers(seeded["db"]), target_kind="not_a_kind", target_id="x")


# ----- source-level guardrails -------------------------------------------------------------------
def _evaluator_source() -> str:
    return Path(E.__file__).read_text()


def test_evaluator_imports_no_forbidden_module() -> None:
    src = _evaluator_source()
    tree = ast.parse(src)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        elif isinstance(node, ast.Import):
            imported += [a.name for a in node.names]
    forbidden = ("agent_bridge", "ollama", "requests", "httpx", "smtplib", "subprocess",
                 "source_content_provider")
    for mod in imported:
        assert not any(bad in mod for bad in forbidden), mod


def test_evaluator_has_no_execution_entrypoint() -> None:
    tree = ast.parse(_evaluator_source())
    funcs = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    banned = ("execute", "apply_action", "repair", "send", "dispatch", "schedule",
              "accept", "reject", "defer", "dispose", "write_back")
    for fn in funcs:
        assert not any(b in fn for b in banned), fn


def test_evaluator_never_calls_source_file_read() -> None:
    src = _evaluator_source()
    for banned in ("source_file_read", "read_file_absolute", "SourceContentProvider", "def _repair",
                   "UPDATE ", "DELETE ", "INSERT INTO"):
        assert banned not in src, banned
