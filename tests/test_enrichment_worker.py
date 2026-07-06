"""N8C-5 — enrichment worker end-to-end with the FakeModelProvider (no live Ollama).

Proves: run_once completes source_summary (stored_only) and claim_extraction (candidate/unreviewed
claims via the N8C-4 future_qwen seam); dry_run is read-only; source digest drift / deleted / an
ambiguous card link ⇒ stale_rejected (no ingest); oversized model output fails (no truncate-ingest);
backlink jobs store a receipt only and never touch the vault.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import qwen_worker as qw
from hb_assistant.obsidian_mcp import source_card_identity as identity
from hb_assistant.obsidian_mcp.claim_repository import ClaimRepository
from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.enrichment_model_provider import FakeModelProvider
from hb_assistant.obsidian_mcp.enrichment_models import RESULT_MAX_CHARS
from hb_assistant.obsidian_mcp.enrichment_repository import EnrichmentRepository
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import index_source_file
from hb_assistant.store.migrator import SQLiteMigrator

TEXT = (
    "We decided to keep MCP read-only.\n"
    "Kickoff is scheduled for next week.\n"
    "Warranty expires March 4, 2027.\n"
)
REL = "docs/note.txt"


@pytest.fixture()
def seeded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    cfg = tmp_path / "c.yml"
    cfg.write_text(
        f"paths:\n  application_support_root: {str(tmp_path / 'as')!r}\n"
        f"  obsidian_vault: {vault.as_posix()!r}\n"
    )
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    root = tmp_path / "proj"
    (root / "docs").mkdir(parents=True)
    (root / REL).write_text(TEXT, encoding="utf-8")
    config = ObsidianMcpConfig.model_validate({
        "enabled": True, "vault_root": str(vault), "writes_enabled": True,
        "vault_markdown_write_enabled": True,
        "external_sources": [{"source_root_key": "proj", "path": str(root), "enabled": True}],
    })
    repo = SourceIndexRepository(db)
    sid = index_source_file(root / REL, config.external_sources[0], repo, config)
    detail = repo.get_source_detail(sid)
    return {"db": db, "repo": repo, "config": config, "sid": sid, "root": root, "vault": vault,
            "digest": detail["content_sha256"], "file": root / REL}


def _vault_files(vault: Path) -> set[str]:
    return {p.name for p in vault.rglob("*") if p.is_file()}


def test_run_once_source_summary_stored_only(seeded: dict) -> None:
    enrich = EnrichmentRepository(seeded["db"])
    enrich.queue_job(job_type="source_summary", source_id=seeded["sid"], source_digest=seeded["digest"])
    out = qw.poll_and_process(db_path=seeded["db"], provider=FakeModelProvider(), worker_id="w1", limit=1)
    assert out[0]["status"] == "completed" and out[0]["applied_status"] == "stored_only"
    receipts = enrich.list_receipts()
    assert len(receipts) == 1
    r = receipts[0]
    assert r["runtime"] == "fake" and r["model_name"] == "qwen2.5:14b"
    assert r["prompt_version"] == "source_summary-v1"
    assert r["input_digest"] and r["output_digest"]
    assert ClaimRepository(seeded["db"]).count_claims() == 0  # summary never creates claims


def test_run_once_claim_extraction_ingests_candidate_unreviewed(seeded: dict) -> None:
    enrich = EnrichmentRepository(seeded["db"])
    enrich.queue_job(job_type="claim_extraction", source_id=seeded["sid"], source_digest=seeded["digest"])
    out = qw.poll_and_process(db_path=seeded["db"], provider=FakeModelProvider(), worker_id="w1", limit=1)
    assert out[0]["applied_status"] == "candidate_claims_ingested"
    claims = ClaimRepository(seeded["db"]).list_claims()
    assert len(claims) >= 1
    for c in claims:
        assert c["status"] == "candidate"
        assert c["review_state"] == "unreviewed"
        assert c["extracted_by"] == "future_qwen"
        assert c["model_name"] == "qwen2.5:14b"
        assert c["source_id"] == seeded["sid"]  # source-backed provenance


def test_dry_run_is_read_only(seeded: dict) -> None:
    enrich = EnrichmentRepository(seeded["db"])
    q = enrich.queue_job(job_type="source_summary", source_id=seeded["sid"], source_digest=seeded["digest"])
    out = qw.poll_and_process(db_path=seeded["db"], provider=FakeModelProvider(), worker_id="w1",
                              dry_run=True)
    assert out[0]["dry_run"] is True and out[0]["outcome"] == "would_complete"
    # nothing persisted: still queued, unleased, no receipts, no claims
    job = enrich.get_job(q["job_id"])
    assert job["status"] == "queued" and job["lease_owner"] is None
    assert enrich.list_receipts() == []
    assert ClaimRepository(seeded["db"]).count_claims() == 0


def test_source_digest_drift_marks_stale_no_ingest(seeded: dict) -> None:
    enrich = EnrichmentRepository(seeded["db"])
    enrich.queue_job(job_type="claim_extraction", source_id=seeded["sid"], source_digest=seeded["digest"])
    # source content changes AFTER enqueue -> re-index bumps content_sha256 -> digest drift
    seeded["file"].write_text(TEXT + "New unexpected content added.\n", encoding="utf-8")
    index_source_file(seeded["file"], seeded["config"].external_sources[0], seeded["repo"], seeded["config"])
    out = qw.poll_and_process(db_path=seeded["db"], provider=FakeModelProvider(), worker_id="w1", limit=1)
    assert out[0]["status"] == "stale" and out[0]["applied_status"] == "stale_rejected"
    assert out[0]["reason"] == "source_digest_drift"
    assert ClaimRepository(seeded["db"]).count_claims() == 0  # stale output never ingested


def test_deleted_source_marks_stale(seeded: dict) -> None:
    enrich = EnrichmentRepository(seeded["db"])
    enrich.queue_job(job_type="claim_extraction", source_id=seeded["sid"], source_digest=seeded["digest"])
    detail = seeded["repo"].get_source_detail(seeded["sid"])
    seeded["repo"].mark_deleted(detail["source_kind"], detail["rel_path"],
                                source_root_key=detail["source_root_key"])
    out = qw.poll_and_process(db_path=seeded["db"], provider=FakeModelProvider(), worker_id="w1", limit=1)
    assert out[0]["applied_status"] == "stale_rejected"
    assert ClaimRepository(seeded["db"]).count_claims() == 0


def test_ambiguous_card_link_marks_stale(seeded: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    enrich = EnrichmentRepository(seeded["db"])
    enrich.queue_job(job_type="claim_extraction", source_id=seeded["sid"], note_rel_path=REL,
                     source_digest=seeded["digest"])
    ambiguous = identity.ReverseLookup(REL, [{"source_id": "a"}, {"source_id": "b"}], "ambiguous", None)
    monkeypatch.setattr(identity, "get_source_for_card", lambda *a, **k: ambiguous)
    out = qw.poll_and_process(db_path=seeded["db"], provider=FakeModelProvider(), worker_id="w1", limit=1)
    assert out[0]["applied_status"] == "stale_rejected"
    assert out[0]["reason"] == "ambiguous_source_card_link"
    assert ClaimRepository(seeded["db"]).count_claims() == 0


def test_oversized_output_fails_no_ingest(seeded: dict) -> None:
    enrich = EnrichmentRepository(seeded["db"])
    enrich.queue_job(job_type="claim_extraction", source_id=seeded["sid"],
                     source_digest=seeded["digest"], max_attempts=1)
    huge = FakeModelProvider(responder=lambda p: '{"claims": ["' + "y" * (RESULT_MAX_CHARS + 10) + '"]}')
    out = qw.poll_and_process(db_path=seeded["db"], provider=huge, worker_id="w1", limit=1)
    assert out[0]["reason"] == "oversized_model_output"
    assert enrich.get_job(out[0]["job_id"])["status"] == "failed"
    receipts = enrich.list_receipts()
    assert receipts and receipts[0]["applied_status"] == "failed"
    assert ClaimRepository(seeded["db"]).count_claims() == 0  # no truncate-and-ingest


def test_backlink_stores_receipt_no_vault_mutation(seeded: dict) -> None:
    enrich = EnrichmentRepository(seeded["db"])
    enrich.queue_job(job_type="backlink_suggestions", source_id=seeded["sid"], source_digest=seeded["digest"])
    before = _vault_files(seeded["vault"])
    out = qw.poll_and_process(db_path=seeded["db"], provider=FakeModelProvider(), worker_id="w1", limit=1)
    assert out[0]["applied_status"] == "stored_only"
    assert enrich.list_receipts()[0]["job_type"] == "backlink_suggestions"
    assert _vault_files(seeded["vault"]) == before  # no link/file written to the vault
    assert ClaimRepository(seeded["db"]).count_claims() == 0


def test_reserved_job_type_fails_cleanly(seeded: dict) -> None:
    enrich = EnrichmentRepository(seeded["db"])
    # claim_validation is a reserved (schema-valid) but unimplemented type: the worker refuses it.
    enrich.queue_job(job_type="claim_validation", source_id=seeded["sid"], source_digest=seeded["digest"])
    out = qw.poll_and_process(db_path=seeded["db"], provider=FakeModelProvider(), worker_id="w1", limit=1)
    assert out[0]["reason"] == "unsupported_job_type"
