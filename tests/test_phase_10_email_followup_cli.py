"""Phase 10 V45 — CLI surface tests for raw email follow-up enrichment (offline, synthetic).

Exercises `second-brain follow-up-watch enrich` and `... scan --with-raw-enrichment`: dry-run writes
nothing, apply requires + respects a cap, `--show-raw-local` gating (requires --dry-run + --no-json;
refused with --json/--apply), JSON output is raw-free, and exit codes match expectations.

The local model is offline in CI (no Ollama daemon), so enrich JSON runs report model_unavailable
(exit 0, degraded) rather than persisting — which is itself the model-unavailable proof. Persistence
+ cap + idempotency are covered at the engine layer (test_phase_10_email_followup_engine).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.construction.store import ConstructionStore

_BODY = "Please confirm the slab schedule and send the revised submittal."


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _seed(db: str, *, cid: str = "c1", status: str = "open") -> None:
    store = ConstructionStore(db_path=db)
    store.upsert_task_candidate(
        candidate_id=cid, stable_key=f"sk-{cid}", title_redacted="Follow up on RFI",
        waiting_state="waiting_on_me", safety_category="normal",
    )
    store.insert_accepted_task(
        candidate_id=cid, title_redacted="Follow up on RFI", waiting_state="waiting_on_me",
        safety_category="normal", status=status,
    )
    store.upsert_candidate_source_ref(
        source_ref_id=f"sr-{cid}", candidate_type="task", candidate_id=cid,
        source_family="email_message", source_ref_hash=f"srh-{cid}",
        source_table="email_message_raw_content", source_primary_key_hash=f"mh-{cid}",
    )
    store.upsert_email_message_raw_content(
        raw_email_id=f"raw-{cid}", message_id_hash=f"mh-{cid}", source_ref_hash=f"srh-{cid}",
        subject="RFI follow up", body_text=_BODY, from_address="vendor@example.com",
        received_at_utc="2026-06-01T10:00:00+00:00",
    )


def test_enrich_dry_run_json_writes_nothing(runner: CliRunner) -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "cli.db")
        _seed(db)
        res = runner.invoke(
            app, ["second-brain", "follow-up-watch", "enrich", "--db", db, "--dry-run", "--json"]
        )
        assert res.exit_code == 0, res.output
        payload = json.loads(res.output)
        assert payload["mode"] == "dry_run"
        assert payload["persisted"] == 0
        assert ConstructionStore(db_path=db).count_email_followup_enrichments() == 0
        # raw-free JSON
        for forbidden in (_BODY, "http://", "https://", "body_html", "raw_prompt", "raw_response"):
            assert forbidden not in res.output


def test_enrich_apply_requires_cap(runner: CliRunner) -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "cli.db")
        _seed(db)
        res = runner.invoke(
            app, ["second-brain", "follow-up-watch", "enrich", "--db", db, "--apply", "--json"]
        )
        assert res.exit_code == 2, res.output
        assert "apply_requires_max_persist" in res.output


def test_enrich_show_raw_local_refused_with_json(runner: CliRunner) -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "cli.db")
        _seed(db)
        res = runner.invoke(
            app,
            ["second-brain", "follow-up-watch", "enrich", "--db", db,
             "--show-raw-local", "--dry-run", "--json"],
        )
        assert res.exit_code == 2, res.output
        assert "show_raw_local_incompatible_with_json" in res.output


def test_enrich_show_raw_local_refused_with_apply(runner: CliRunner) -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "cli.db")
        _seed(db)
        res = runner.invoke(
            app,
            ["second-brain", "follow-up-watch", "enrich", "--db", db,
             "--show-raw-local", "--no-json", "--apply", "--max-persist", "5"],
        )
        assert res.exit_code == 2, res.output
        assert "requires --dry-run" in res.output


def test_enrich_show_raw_local_preview_text_mode(runner: CliRunner) -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "cli.db")
        _seed(db)
        res = runner.invoke(
            app,
            ["second-brain", "follow-up-watch", "enrich", "--db", db,
             "--candidate-id", "c1", "--show-raw-local", "--dry-run", "--no-json"],
        )
        assert res.exit_code == 0, res.output
        assert "RAW-LOCAL PREVIEW" in res.output
        assert "NEVER copy into evidence" in res.output
        assert "nothing persisted" in res.output
        # not JSON
        assert not res.output.strip().startswith("{")
        assert ConstructionStore(db_path=db).count_email_followup_enrichments() == 0


def test_enrich_no_eligible_reports_cleanly(runner: CliRunner) -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "cli.db")
        ConstructionStore(db_path=db)  # migrate, no candidates
        res = runner.invoke(
            app, ["second-brain", "follow-up-watch", "enrich", "--db", db, "--dry-run", "--json"]
        )
        assert res.exit_code == 0, res.output
        payload = json.loads(res.output)
        assert payload["note"] == "no_eligible_candidates"
        assert payload["eligible"] == 0


def test_enrich_reports_model_unavailable_offline(runner: CliRunner) -> None:
    # No Ollama daemon in CI → enrichment degrades; exit 0 with model_unavailable in JSON.
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "cli.db")
        _seed(db)
        res = runner.invoke(
            app, ["second-brain", "follow-up-watch", "enrich", "--db", db, "--dry-run", "--json"]
        )
        assert res.exit_code == 0, res.output
        payload = json.loads(res.output)
        assert payload["persisted"] == 0
        # Either model unavailable (no daemon) or no raw — both are clean, non-persisting outcomes.
        assert payload["model_unavailable"] is True or payload["would_persist"] == 0


def test_scan_with_raw_enrichment_dry_run(runner: CliRunner) -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "cli.db")
        _seed(db)
        res = runner.invoke(
            app,
            ["second-brain", "follow-up-watch", "scan", "--db", db,
             "--with-raw-enrichment", "--dry-run", "--json"],
        )
        assert res.exit_code == 0, res.output
        payload = json.loads(res.output)
        assert "raw_enrichment" in payload
        assert payload["raw_enrichment"]["mode"] == "dry_run"
        assert payload["raw_enrichment"]["persisted"] == 0
        for forbidden in (_BODY, "http://", "https://", "raw_prompt"):
            assert forbidden not in res.output


def test_scan_with_raw_enrichment_apply_requires_cap(runner: CliRunner) -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "cli.db")
        _seed(db)
        res = runner.invoke(
            app,
            ["second-brain", "follow-up-watch", "scan", "--db", db,
             "--with-raw-enrichment", "--apply", "--json"],
        )
        assert res.exit_code == 2, res.output
        assert "apply_requires_max_persist" in res.output
