"""Phase 10 — consolidated candidate review report (read-only, review-safe, legible).

Proves `build_review_report` / `render_review_report_markdown` group the candidate lifecycle, flag
needs-review, preview the bounded accepted set without persisting, stay source-linked, and never leak
raw content; and that the `second-brain review report` CLI verb emits both JSON and Markdown.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.construction.second_brain.local_ai.candidate_review import (
    build_review_report,
    render_review_report_markdown,
)
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()


def _seed(store: ConstructionStore, cid: str, *, status: str, conf: float, pk: str = "PRJ-1") -> None:
    store.upsert_task_candidate(
        candidate_id=cid, stable_key=f"{pk}:task:{cid}",
        title_redacted=f"Submit inspection report {cid}", project_key=pk,
        assignee_class="me", urgency="high", waiting_state="waiting_on_me",
        safety_category="normal", confidence=conf, reason_redacted="Explicit ask.",
        recommended_next_action="review", review_status=status,
    )
    store.upsert_candidate_source_ref(
        source_ref_id=f"sr-{cid}", candidate_type="task", candidate_id=cid,
        source_family="email_message", source_ref_hash=f"hash-{cid}",
        source_table="email_message_raw_content", source_primary_key_hash=f"hash-{cid}",
        evidence_redacted="Submit inspection report",
    )


def test_review_report_groups_and_previews(tmp_path: Path) -> None:
    store = ConstructionStore(db_path=str(tmp_path / "r.db"))
    _seed(store, "t1", status="pending", conf=0.9)
    _seed(store, "t2", status="pending", conf=0.3)  # low conf -> needs review
    _seed(store, "t3", status="accepted", conf=0.8)
    _seed(store, "t4", status="rejected", conf=0.7)

    report = build_review_report(store, apply_cap=10)
    assert report["counts"]["total"] == 4
    assert report["counts"]["pending"] == 2
    assert report["counts"]["accepted"] == 1
    assert report["counts"]["needs_review"] == 1
    assert report["needs_review"][0]["candidate_id"] == "t2"
    # Preview apply is dry-run and bounded; persists nothing.
    assert report["preview_apply"]["dry_run"] is True
    assert report["preview_apply"]["would_persist_count"] == 1
    assert report["preview_apply"]["would_persist_candidate_ids"] == ["t3"]
    # Source-linked.
    accepted_view = report["groups"]["accepted"][0]
    assert accepted_view["source_refs"] == ["email_message:hash-t3"]

    md = render_review_report_markdown(report)
    assert "# Candidate Review Report" in md
    assert "Needs Bobby's review" in md
    assert "Preview apply (dry-run)" in md
    # No raw content leaks.
    blob = json.dumps(report) + md
    for bad in ("raw_body", "prompt", "response", "signed_url", "download_url", "Bearer "):
        assert bad not in blob


def test_review_report_cli_emits_json_and_markdown(tmp_path: Path) -> None:
    db = str(tmp_path / "r.db")
    store = ConstructionStore(db_path=db)
    _seed(store, "t1", status="pending", conf=0.9)
    md_path = tmp_path / "report.md"
    res = runner.invoke(
        app,
        ["second-brain", "review", "report", "--db", db,
         "--markdown-out", str(md_path), "--json"],
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["command"] == "second-brain review report"
    assert payload["counts"]["total"] == 1
    assert payload["guardrails"]["read_only"] is True
    assert md_path.exists()
    assert "# Candidate Review Report" in md_path.read_text(encoding="utf-8")


def test_review_report_empty_db_is_clean(tmp_path: Path) -> None:
    store = ConstructionStore(db_path=str(tmp_path / "r.db"))
    report = build_review_report(store)
    assert report["ok"] is True
    assert report["counts"]["total"] == 0
    md = render_review_report_markdown(report)
    assert "_None._" in md
