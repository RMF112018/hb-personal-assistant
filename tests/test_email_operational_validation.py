"""Prompt 13 operational validation chain tests."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.construction.email.operational_validation import run_operational_validation
from hb_assistant.construction.store import ConstructionStore

_RUNNER = CliRunner()


def _seed(db: str) -> None:
    store = ConstructionStore(db)
    store.upsert_email_source_location(
        source_id="sx",
        mailbox_owner_hash="h",
        folder_role="inbox",
        folder_id="f1",
        include_in_sync=True,
    )
    store.upsert_email_message(
        message_id="m1",
        thread_key="t1",
        source_id="sx",
        subject_redacted="tropical schedule",
        body_preview_excerpt_redacted="safe preview",
        full_body_persisted=False,
    )
    store.upsert_email_project_match(
        match_id="pm1",
        message_id="m1",
        match_signal="project_name_in_subject",
        confidence=0.9,
        project_key="tropical",
    )
    store.upsert_email_relationship_candidate(
        candidate_id="rc1",
        message_id="m1",
        candidate_type="meeting",
        match_signal="metadata",
        confidence=0.8,
        project_key="tropical",
    )
    store.enqueue_email_review_item(
        review_id="rv1",
        message_id="m1",
        category="contracts",
        sensitivity="high",
        reason="sensitive",
        suggested_action="manual_review",
        confidence=0.8,
        project_key="tropical",
    )


def test_run_operational_validation_aggregates_and_writes_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    db = str(tmp_path / "db.sqlite")
    _seed(db)
    monkeypatch.setenv("HB_APP_SUPPORT_DIR", str(tmp_path / "app"))
    monkeypatch.setenv("HB_CONSTRUCTION_VAULT_ROOT", str(tmp_path / "vault"))

    def fake_run(name: str, argv: list[str]):
        payload = {"ok": True, "command": name}
        if "discover" in name:
            payload["messages_scanned"] = 1
        if "obsidian" in name:
            payload["notes_written"] = 5
        if "mail_status" in name:
            payload["guard_self_test"] = {"passed": True, "mutation_attempts_blocked": 6}
            payload["guardrails"] = {"no_mail_write_scopes_requested": True}
            payload["forbidden_mail_scopes_requested"] = []
        from hb_assistant.construction.email.operational_validation import CommandReceipt

        receipt = CommandReceipt(
            name=name,
            argv=argv,
            exit_code=0,
            ok=True,
            payload=payload,
            started_utc="2026-05-30T00:00:00+00:00",
            completed_utc="2026-05-30T00:00:01+00:00",
        )

        class _R:
            def __init__(self):
                self.receipt = receipt
                self.raw_stdout = json.dumps(payload)

        return _R()

    monkeypatch.setattr(
        "hb_assistant.construction.email.operational_validation._run_cmd",
        fake_run,
    )
    report = run_operational_validation(
        project_key="tropical",
        lookback_days=30,
        include_live_index=True,
        write_evidence=True,
        db_path=db,
    )
    assert report.metrics.messages_indexed >= 1
    assert report.metrics.messages_discovered == 1
    assert report.metrics.plaintext_bodies_persisted == 0
    assert report.metrics.mailbox_mutations_attempted == 0
    assert report.metrics.validation_ok is True

    # Evidence writes to repo root; resolve using PathPolicy.
    from hb_assistant.config.path_policy import PathPolicy

    repo_ev = (
        PathPolicy().resolve_repo_root()
        / "docs"
        / "evidence"
        / "construction-intelligence-phase-06-email"
    )
    assert (repo_ev / "13-operational-workflow-pilot-dry-run.json").exists()
    assert (repo_ev / "13-operational-workflow-pilot-index-proof.md").exists()
    assert (repo_ev / "13-operational-workflow-encrypted-body-proof.md").exists()
    assert (repo_ev / "13-operational-review-queue-proof.md").exists()
    assert (repo_ev / "13-operational-obsidian-preview.md").exists()


def test_graph_mail_operational_validate_cli_parses(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HB_APP_SUPPORT_DIR", str(tmp_path / "app"))

    class _Report:
        def __init__(self):
            self.metrics = type("M", (), {"validation_ok": True})()

        def model_dump(self):
            return {
                "prompt": 13,
                "project_key": "tropical",
                "lookback_days": 30,
                "generated_at": "2026-05-30T00:00:00+00:00",
                "command_receipts": [],
                "endpoint_methods_used": ["GET"],
                "endpoint_path_families": ["/me/messages"],
                "runtime_no_mutation_proof": {"mailbox_mutation_endpoints_blocked": True},
                "scopes_requested": ["Mail.Read"],
                "metrics": {"validation_ok": True},
            }

    monkeypatch.setattr(
        "hb_assistant.cli.graph.run_operational_validation",
        lambda **_: _Report(),
    )

    res = _RUNNER.invoke(
        app,
        [
            "graph",
            "mail",
            "operational-validate",
            "--project",
            "tropical",
            "--lookback-days",
            "30",
            "--no-live-index",
            "--json",
        ],
        catch_exceptions=False,
    )
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["command"] == "graph mail operational-validate"
    assert payload["ok"] is True
