"""N8C-19 action-stage builder: preview/dry-run read-only; apply writes only stage tables + mutates NOTHING
upstream (workflow/feedback/review/source/…); fixed no-execution policy; advisory-execution-verb → blocked;
feedback recommendations become advisory candidates; no execution/external/LLM/source-read. AST/source guards."""

from __future__ import annotations

import ast
import io
import sqlite3
import tokenize
from pathlib import Path

from hb_assistant.obsidian_mcp import action_stage_builder as B
from hb_assistant.obsidian_mcp import action_stage_models as M
from hb_assistant.obsidian_mcp import feedback_service as fs
from hb_assistant.obsidian_mcp.action_stage_repository import ActionStageRepository
from hb_assistant.obsidian_mcp.feedback_repository import FeedbackRepository
from hb_assistant.obsidian_mcp.workflow_router import WorkflowRouter
from hb_assistant.store.migrator import SQLiteMigrator

_SRC = Path(__file__).resolve().parents[1] / "src" / "hb_assistant"
_STAGE_MODULES = [
    _SRC / "obsidian_mcp" / "action_stage_models.py",
    _SRC / "obsidian_mcp" / "action_stage_repository.py",
    _SRC / "obsidian_mcp" / "action_stage_builder.py",
    _SRC / "cli" / "action_stage.py",
]


def _code_only(path: Path) -> str:
    """Source with comments and string/docstring literals stripped (so docstring prose never trips a guard)."""
    out: list[str] = []
    for tok in tokenize.generate_tokens(io.StringIO(path.read_text()).readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        out.append(tok.string)
    return "".join(out)


def _db(tmp_path: Path) -> str:
    db = tmp_path / "as.db"
    SQLiteMigrator(db_path=str(db)).apply()
    return str(db)


def _providers(db: str, *, with_feedback: bool = True) -> B.ActionStageProviders:
    return B.ActionStageProviders(router=WorkflowRouter(db),
                                  feedback_repo=FeedbackRepository(db) if with_feedback else None)


def _seed_feedback(db: str) -> None:
    fs.capture_feedback(FeedbackRepository(db), feedback_type="needs_review",
                        targets=[{"target_kind": "open_loop", "target_id": "OL1", "open_loop_id": "OL1"}],
                        apply=True)


# ---- preview / build behavior ----------------------------------------------------------
def test_preview_is_read_only(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _seed_feedback(db)
    plan = B.preview_action_stage(_providers(db), request_inputs={"workflow_type": "open_loop_triage"})
    assert plan["applied"] is False
    assert ActionStageRepository(db).count() == 0
    assert plan["stage"]["action_policy"] == "no_execution"
    assert plan["stage"]["execution_policy"] == "staged_only"


def test_build_dry_run_persists_nothing(tmp_path: Path) -> None:
    db = _db(tmp_path)
    out = B.build_action_stage(_providers(db), ActionStageRepository(db),
                               request_inputs={"workflow_type": "open_loop_triage"}, apply=False)
    assert out["applied"] is False
    assert ActionStageRepository(db).count() == 0


def test_build_apply_persists_non_executing_items(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _seed_feedback(db)
    repo = ActionStageRepository(db)
    out = B.build_action_stage(_providers(db), repo,
                               request_inputs={"workflow_type": "open_loop_triage"}, apply=True)
    assert out["applied"] is True
    for it in repo.list_items(out["stage_id"]):
        assert it["execution_status"] == "not_executed"
        assert it["external_system"] == "none"
        assert it["external_ref"] is None
        assert it["requires_operator_review"] == 1
        assert it["staged_state"] in ("candidate", "blocked")


def test_apply_is_idempotent(tmp_path: Path) -> None:
    db = _db(tmp_path)
    repo = ActionStageRepository(db)
    a = B.build_action_stage(_providers(db), repo, request_inputs={"workflow_type": "open_loop_triage"},
                             apply=True)
    b = B.build_action_stage(_providers(db), repo, request_inputs={"workflow_type": "open_loop_triage"},
                             apply=True)
    assert a["created"] is True and b["reused"] is True and b["created"] is False


def test_execution_like_advisory_is_blocked_never_active(tmp_path: Path) -> None:
    # An advisory step that reads like an execution instruction stages BLOCKED with an explicit block_reason.
    item = B._item_from_advisory("Send an email to the client about the RFI", "wf1")
    assert item.staged_state == M.STATE_BLOCKED
    assert item.block_reason == "execution_like_advisory"
    # A pure review/navigation advisory step stays a candidate.
    item2 = B._item_from_advisory("Review the candidate items before the meeting", "wf1")
    assert item2.staged_state == M.STATE_CANDIDATE


def test_feedback_recommendation_becomes_advisory_candidate(tmp_path: Path) -> None:
    rec = {"recommendation_type": "suggest_source_check", "target_kind": "citation", "target_id": "C1",
           "feedback_id": "F1", "recommendation_id": "R1"}
    item = B._item_from_recommendation(rec)
    assert item.action_kind == "source_review"
    assert item.staged_state == M.STATE_CANDIDATE
    assert item.anchors.get("feedback_id") == "F1"


def test_trusted_context_sections_are_not_actions() -> None:
    # trusted_facts / trusted_updates / project_scope carry established knowledge — never a follow-up.
    for section in ("trusted_facts", "trusted_updates", "trusted_items", "project_scope"):
        assert B._SECTION_MAP.get(section) is None


def test_terminal_sections_are_blocked_only() -> None:
    for section in ("stale_or_superseded", "excluded_items"):
        mapped = B._SECTION_MAP[section]
        assert mapped is not None and mapped[1] == M.STATE_BLOCKED


def test_apply_mutates_no_upstream_table(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _seed_feedback(db)
    repo = ActionStageRepository(db)
    with sqlite3.connect(db) as c:
        other = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'assistant_action_stage%' AND name NOT LIKE 'sqlite_%'")]
        before = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in other}
    B.build_action_stage(_providers(db), repo, request_inputs={"workflow_type": "daily_brief_context"},
                         apply=True)
    with sqlite3.connect(db) as c:
        after = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in other}
    assert before == after


def test_export_is_bounded_and_read_only(tmp_path: Path) -> None:
    db = _db(tmp_path)
    repo = ActionStageRepository(db)
    out = B.build_action_stage(_providers(db), repo,
                               request_inputs={"workflow_type": "open_loop_triage"}, apply=True)
    exported = B.export_action_stage(repo, stage_id=out["stage_id"])
    assert exported["format"] == "action_stage_export_v1"
    blob = str(exported).lower()
    for leak in ("claim_text", "evidence_excerpt", "email_body", "raw_response", "prompt"):
        assert leak not in blob


# ---- source / AST guards ---------------------------------------------------------------
def test_no_execution_external_or_llm_symbols_in_source() -> None:
    forbidden = (
        "subprocess", "os.system", "smtplib", "sendmail", "send_email", "requests.post", "httpx.post",
        "urllib.request", "ollama", "openai", "anthropic", "agent_bridge", "SourceContentProvider",
        "source_file_read", "reindex", "calendar", "reminder",
    )
    for path in _STAGE_MODULES:
        text = _code_only(path)
        for bad in forbidden:
            assert bad not in text, f"{path.name} references forbidden symbol {bad!r}"


def test_repository_only_writes_stage_tables() -> None:
    text = (_SRC / "obsidian_mcp" / "action_stage_repository.py").read_text().lower()
    for verb in ("insert into ", "update ", "delete from "):
        idx = 0
        while (idx := text.find(verb, idx)) != -1:
            tail = text[idx + len(verb): idx + len(verb) + 40].lstrip()
            assert tail.startswith("assistant_action_stage") or tail.startswith("{table}"), tail
            idx += len(verb)


def test_modules_define_no_execution_entrypoint() -> None:
    banned = ("execute", "dispatch", "send", "schedule", "run_action", "deliver", "remind")
    for path in _STAGE_MODULES:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert not any(b in node.name for b in banned), (path.name, node.name)
