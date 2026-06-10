"""Phase 10 — follow-up watch report grouped by operator action (deterministic, review-safe).

Proves items bucket into the right operator-action group, that quality gates route no-source-ref /
contradictory items to needs-review, that the report uses no model (so model availability never
affects it), stays source-linked + raw-free, and that the CLI verb emits JSON + Markdown.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.construction.second_brain.local_ai.follow_up_watch import (
    build_follow_up_watch_report,
    operator_action_for,
    render_follow_up_watch_report_markdown,
    run_follow_up_watch_scan,
    watch_quality_flags,
)
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()
NOW = "2026-06-09T00:00:00+00:00"


def _seed(db: str, cid: str, *, waiting_state: str, status: str = "open",
          due_at_utc: str | None = None, accepted_utc: str = "2026-06-01T00:00:00+00:00",
          completed_utc: str | None = None, with_source_ref: bool = True) -> None:
    s = ConstructionStore(db_path=db)
    s.upsert_task_candidate(
        candidate_id=cid, stable_key=f"PRJ:task:{cid}", title_redacted=f"Task {cid}",
        project_key="PRJ", assignee_class="user", waiting_state=waiting_state,
        safety_category="normal", confidence=0.9, review_status="accepted",
    )
    if with_source_ref:
        s.upsert_candidate_source_ref(
            source_ref_id=f"sr-{cid}", candidate_type="task", candidate_id=cid,
            source_family="email_message", source_ref_hash=f"hash-{cid}",
            source_table="email_message", evidence_redacted=f"evidence {cid}",
        )
    s.insert_accepted_task(
        candidate_id=cid, title_redacted=f"Task {cid}", waiting_state=waiting_state,
        safety_category="normal", project_key="PRJ", status=status,
        due_at_utc=due_at_utc, accepted_utc=accepted_utc,
    )
    if completed_utc:
        s.update_accepted_task_status(accepted_task_id=s.accepted_task_id_for(cid),
                                      status=status, completed_utc=completed_utc)


def test_quality_gates_and_action_mapping() -> None:
    # No source ref -> insufficient evidence -> needs review.
    flags = watch_quality_flags(status="open", waiting_state="waiting_on_me",
                                completed_utc=None, has_source_ref=False)
    assert "insufficient_evidence" in flags
    assert operator_action_for("waiting_on_me", flags) == "needs_review"
    # Terminal status + active waiting + no completion -> contradictory -> needs review.
    contra = watch_quality_flags(status="done", waiting_state="waiting_on_others",
                                 completed_utc=None, has_source_ref=True)
    assert "contradictory" in contra
    assert operator_action_for("closed", contra) == "needs_review"
    # Clean mappings.
    assert operator_action_for("waiting_on_me", []) == "needs_bobby_action"
    assert operator_action_for("waiting_on_others", []) == "waiting_on_others"
    assert operator_action_for("stale", []) == "stale_no_response"
    assert operator_action_for("closed", []) == "closed_resolved"
    assert operator_action_for("open", []) == "monitor_only"


def test_report_buckets_and_is_raw_free(tmp_path: Path) -> None:
    db = str(tmp_path / "w.db")
    _seed(db, "needbobby", waiting_state="waiting_on_me")
    _seed(db, "others", waiting_state="waiting_on_others")
    _seed(db, "stale1", waiting_state="unknown", accepted_utc="2026-01-01T00:00:00+00:00")
    _seed(db, "openmon", waiting_state="unknown")
    _seed(db, "nosrc", waiting_state="waiting_on_me", with_source_ref=False)

    store = ConstructionStore(db_path=db)
    report = build_follow_up_watch_report(store=store, now_utc=NOW)
    g = report["groups"]
    assert any(i["accepted_id"].endswith("needbobby") for i in g["needs_bobby_action"])
    assert any(i["accepted_id"].endswith("others") for i in g["waiting_on_others"])
    assert any(i["accepted_id"].endswith("stale1") for i in g["stale_no_response"])
    assert any(i["accepted_id"].endswith("openmon") for i in g["monitor_only"])
    # No-source-ref item routes to needs_review and is flagged non-actionable.
    nr = g["needs_review"]
    assert any("insufficient_evidence" in i["quality_flags"] for i in nr)
    assert all(i["persistable_as_actionable"] is False for i in nr)
    assert report["counts"]["total"] == 5

    md = render_follow_up_watch_report_markdown(report)
    blob = json.dumps(report) + md
    import re as _re
    # Precise forbidden patterns (avoid false positives like the group key "stale_no_response").
    assert '"raw_body"' not in blob
    assert '"prompt"' not in blob and '"raw_prompt"' not in blob
    assert '"raw_response"' not in blob
    assert "signed_url" not in blob and "download_url" not in blob
    assert "Bearer " not in blob
    assert not _re.search(r"https?://", blob)
    assert not _re.search(r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}", blob)
    assert report["guardrails"]["deterministic_no_model"] is True


def test_scan_does_not_persist_quality_flagged_items(tmp_path: Path) -> None:
    # A source-linked but CONTRADICTORY item (terminal status + active waiting + no completion)
    # must be quality-gated out of persistence, consistent with the report's needs-review bucket.
    db = str(tmp_path / "scan.db")
    _seed(db, "contra", waiting_state="waiting_on_others", status="done", completed_utc=None,
          with_source_ref=True)
    store = ConstructionStore(db_path=db)

    res = run_follow_up_watch_scan(store=store, now_utc=NOW, dry_run=False, max_persist=5)
    summary = res["summary"]
    assert summary["scanned"] == 1
    assert summary["skipped_quality_flags"] == 1
    assert summary["persisted"] == 0
    assert summary["status_events_written"] == 0

    # The result entry is flagged contradictory and marked skipped for quality.
    entry = next(e for e in res["results"] if e["accepted_id"].endswith("contra"))
    assert "contradictory" in entry["quality_flags"]
    assert entry["skipped_reason"] == "quality_flags"
    assert entry["persisted"] is False
    assert res["guardrails"]["quality_gated"] is True

    # Nothing was written to the watch table.
    assert store.list_follow_up_watch_items(limit=100) == []


def test_cli_emits_json_and_markdown(tmp_path: Path) -> None:
    db = str(tmp_path / "w.db")
    _seed(db, "x1", waiting_state="waiting_on_me")
    md_path = tmp_path / "watch.md"
    res = runner.invoke(app, ["second-brain", "follow-up-watch", "report", "--db", db,
                              "--as-of", NOW, "--markdown-out", str(md_path), "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["command"] == "second-brain follow-up-watch report"
    assert payload["counts"]["total"] == 1
    assert md_path.exists()
    assert "Follow-up Watch Report" in md_path.read_text(encoding="utf-8")
