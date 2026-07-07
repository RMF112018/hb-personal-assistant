"""N8C-18 feedback service: capture writes ONLY feedback tables and mutates NOTHING upstream; recommendations
are advisory + operator-review-required with no accept/reject/defer/dispose; no action staging, no execution,
no external system, no source_file_read, no LLM, no raw-body persistence. Includes AST/source guards."""

from __future__ import annotations

import ast
import io
import sqlite3
import tokenize
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import feedback_service as fs
from hb_assistant.obsidian_mcp.feedback_models import FeedbackValidationError
from hb_assistant.obsidian_mcp.feedback_repository import FeedbackRepository
from hb_assistant.store.migrator import SQLiteMigrator

_SRC = Path(__file__).resolve().parents[1] / "src" / "hb_assistant"
_FEEDBACK_MODULES = [
    _SRC / "obsidian_mcp" / "feedback_models.py",
    _SRC / "obsidian_mcp" / "feedback_repository.py",
    _SRC / "obsidian_mcp" / "feedback_service.py",
    _SRC / "cli" / "feedback.py",
]


def _code_only(path: Path) -> str:
    """Source with comments and string/docstring literals stripped — so prose negations like
    'no source_file_read' in a docstring never trip a code-symbol guard."""
    out: list[str] = []
    for tok in tokenize.generate_tokens(io.StringIO(path.read_text()).readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        out.append(tok.string)
    # Join with "" so dotted attribute access (os.system, requests.post) survives as a contiguous string.
    return "".join(out)


def _db(tmp_path: Path) -> str:
    db = tmp_path / "fb.db"
    SQLiteMigrator(db_path=str(db)).apply()
    return str(db)


def _targets(tid: str = "ol-1") -> list[dict]:
    return [{"target_kind": "open_loop", "target_id": tid, "open_loop_id": tid}]


# ---- preview / capture behavior --------------------------------------------------------
def test_preview_is_read_only_and_not_applied(tmp_path: Path) -> None:
    plan = fs.preview_feedback(feedback_type="needs_review", targets=_targets(), note="x")
    assert plan["applied"] is False
    # preview never needs a DB; nothing is persisted.
    assert plan["feedback"]["feedback_id"]
    assert plan["counts"]["targets"] == 1


def test_preview_rejects_unknown_type() -> None:
    with pytest.raises(FeedbackValidationError):
        fs.preview_feedback(feedback_type="accepted", targets=_targets())


def test_preview_requires_a_target() -> None:
    with pytest.raises(FeedbackValidationError):
        fs.preview_feedback(feedback_type="needs_review", targets=[])


def test_capture_without_apply_persists_nothing(tmp_path: Path) -> None:
    repo = FeedbackRepository(_db(tmp_path))
    out = fs.capture_feedback(repo, feedback_type="needs_review", targets=_targets(), apply=False)
    assert out["applied"] is False
    assert repo.count() == 0


def test_capture_with_apply_persists_and_is_advisory(tmp_path: Path) -> None:
    repo = FeedbackRepository(_db(tmp_path))
    out = fs.capture_feedback(repo, feedback_type="needs_review", targets=_targets(), apply=True)
    assert out["applied"] is True
    fid = out["feedback"]["feedback_id"]
    recs = repo.list_recommendations(fid)
    assert recs and all(r["requires_operator_review"] == 1 for r in recs)
    assert all(r["review_policy"] == "advisory_review_loop" for r in recs)


def test_source_related_feedback_without_source_ref_warns() -> None:
    plan = fs.preview_feedback(feedback_type="wrong_source", targets=_targets())
    assert "missing_source_ref" in plan["warnings"]


def test_source_related_feedback_with_source_ref_no_warning() -> None:
    plan = fs.preview_feedback(
        feedback_type="wrong_source",
        targets=[{"target_kind": "citation", "target_id": "c1", "source_ref": "sr-1"}])
    assert "missing_source_ref" not in plan["warnings"]


def test_export_is_bounded_and_read_only(tmp_path: Path) -> None:
    repo = FeedbackRepository(_db(tmp_path))
    out = fs.capture_feedback(repo, feedback_type="needs_review", targets=_targets(), apply=True)
    exported = fs.export_feedback(repo, feedback_id=out["feedback"]["feedback_id"])
    assert exported["format"] == "feedback_export_v1"
    assert exported["feedback"]["feedback_id"] == out["feedback"]["feedback_id"]
    # No raw body / payload leaks in the export (bounded metadata + ids only).
    blob = str(exported).lower()
    for leak in ("claim_text", "evidence_excerpt", "email_body", "raw_response", "prompt"):
        assert leak not in blob


def test_apply_mutates_no_upstream_table(tmp_path: Path) -> None:
    db = _db(tmp_path)
    repo = FeedbackRepository(db)
    with sqlite3.connect(db) as c:
        other = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'assistant_feedback%' AND name NOT LIKE 'sqlite_%'")]
        before = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in other}
    fs.capture_feedback(repo, feedback_type="wrong_review_label", targets=_targets(), apply=True)
    with sqlite3.connect(db) as c:
        after = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in other}
    assert before == after


# ---- source / AST guards ---------------------------------------------------------------
def test_no_execution_or_external_or_llm_symbols_in_source() -> None:
    forbidden = (
        "action_stage", "assistant_action", "subprocess", "smtplib", "sendmail",
        "send_email", "calendar", "reminder", "requests.post", "httpx.post", "urllib.request",
        "ollama", "openai", "anthropic", "agent_bridge", "SourceContentProvider", "source_file_read",
        "reindex", "os.system",
    )
    for path in _FEEDBACK_MODULES:
        text = _code_only(path)
        for bad in forbidden:
            assert bad not in text, f"{path.name} references forbidden symbol {bad!r}"


def test_repository_only_writes_feedback_tables() -> None:
    # Every INSERT/UPDATE/DELETE literal in the repository targets an assistant_feedback_* table.
    text = (_SRC / "obsidian_mcp" / "feedback_repository.py").read_text().lower()
    for verb in ("insert into ", "update ", "delete from "):
        idx = 0
        while (idx := text.find(verb, idx)) != -1:
            tail = text[idx + len(verb): idx + len(verb) + 40].lstrip()
            assert tail.startswith("assistant_feedback") or tail.startswith("{table}"), tail
            idx += len(verb)


def test_service_never_writes_review_disposition_words() -> None:
    text = (_SRC / "obsidian_mcp" / "feedback_service.py").read_text().lower()
    for bad in ("accept", "reject", "defer", "dispose"):
        # These review-disposition verbs must not appear as write operations in the service.
        assert bad not in text, f"service references disposition verb {bad!r}"


def test_modules_parse_and_define_no_execution_entrypoint() -> None:
    # Guard: no function name in the feedback modules implies execution/dispatch/staging.
    banned_names = ("execute", "dispatch", "send", "stage_action", "schedule", "run_action")
    for path in _FEEDBACK_MODULES:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert not any(b in node.name for b in banned_names), (path.name, node.name)
