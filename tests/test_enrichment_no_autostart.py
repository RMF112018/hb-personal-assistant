"""N8C-5 — boundary proofs: no auto-start, no remote MCP write surface, no raw/import mutation.

These pin the guardrails that make the enrichment layer safe: the worker is CLI/service-only (never
started by the backend lifespan / scheduler / watcher), the remote MCP surface is unchanged (still
exactly the 12 read-only assistant_* nav tools, no enrichment write tool), the repository only ever
writes its own two tables, and the model-provider module keeps ``requests`` out of its import graph.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import hb_assistant

SRC = Path(hb_assistant.__file__).parent


def test_importing_worker_modules_writes_nothing() -> None:
    # Importing the queue/worker/provider must not run extraction or touch a DB.
    for mod in (
        "hb_assistant.store.assistant_enrichment_tables",
        "hb_assistant.obsidian_mcp.enrichment_models",
        "hb_assistant.obsidian_mcp.enrichment_repository",
        "hb_assistant.obsidian_mcp.enrichment_model_provider",
        "hb_assistant.obsidian_mcp.qwen_worker",
    ):
        importlib.import_module(mod)  # no side effects / exceptions


def test_backend_startup_enqueues_no_jobs(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from hb_assistant.construction.analytics.api import create_app
    from hb_assistant.obsidian_mcp.enrichment_repository import EnrichmentRepository
    from hb_assistant.store.migrator import SQLiteMigrator

    monkeypatch.setenv("HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS", "1")
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    with TestClient(create_app(db_path=db)):
        pass  # lifespan runs on enter/exit
    assert EnrichmentRepository(db).count_jobs() == 0  # startup created no jobs


def test_worker_not_referenced_by_lifespan_or_automation() -> None:
    # The qwen enrichment worker is CLI-driven only; no backend path imports it. api.py may reference
    # EnrichmentRepository (the read-only GET routes) but must never import the worker itself.
    api = (SRC / "construction" / "analytics" / "api.py").read_text(encoding="utf-8")
    assert "qwen_worker" not in api

    # The watcher / automation paths must not touch the enrichment layer at all (no auto-enqueue,
    # no auto-run). (The unrelated schedule *quality* worker also exposes poll_and_process, so we
    # pin the enrichment-specific names rather than that generic symbol.)
    watched = [SRC / "obsidian_mcp" / "source_watch.py"]
    watched += list((SRC / "automation").glob("*.py"))
    for path in watched:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for ref in ("qwen_worker", "enrichment_repository", "EnrichmentRepository", "enrichment_jobs"):
            assert ref not in text, f"{path.name} unexpectedly references {ref}"


def test_remote_mcp_has_no_enrichment_write_tool() -> None:
    from hb_assistant.nas_mcp.broker import ASSISTANT_CONTEXT_PACK_TOOLS, ASSISTANT_NAV_TOOLS

    assert len(ASSISTANT_NAV_TOOLS) == 12
    assert not any("enrichment" in name for name in ASSISTANT_NAV_TOOLS)
    # N8C-6 adds ONE read-only enrichment-review tool remotely (reads receipts via the read-only
    # snapshot); it is NOT a queue write. No nas_mcp module may call an enrichment WRITE method, so
    # the queue lifecycle (enqueue/claim/complete/fail) stays CLI/service-only and off the remote
    # surface — ``ai_outputs_card_upsert`` remains the only sanctioned remote write.
    assert "assistant_list_enrichment_review_items" in ASSISTANT_CONTEXT_PACK_TOOLS
    write_methods = ("queue_job", "claim_next_job", "mark_running", "complete_job", "fail_job",
                     "heartbeat_job", "release_expired_leases")
    for path in (SRC / "nas_mcp").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for method in write_methods:
            assert method not in text, f"{path.name} references enrichment write method {method}"


def test_repository_writes_only_enrichment_tables() -> None:
    text = (SRC / "obsidian_mcp" / "enrichment_repository.py").read_text(encoding="utf-8")
    import re

    targets = set(re.findall(r"(?:INSERT INTO|UPDATE|DELETE FROM)\s+([a-z_]+)", text))
    assert targets <= {"assistant_enrichment_jobs", "assistant_enrichment_receipts"}, targets


def test_provider_module_has_no_toplevel_requests_import() -> None:
    text = (SRC / "obsidian_mcp" / "enrichment_model_provider.py").read_text(encoding="utf-8")
    # requests is imported lazily inside OllamaModelProvider.generate, never at module top level.
    assert "\nimport requests" not in text
    assert "\nfrom requests" not in text
