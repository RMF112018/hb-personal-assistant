"""Checkpoint FINAL — A4 quarantine trust-integration lifecycle (end-to-end, real shared authority).

Proves the full A4 lifecycle through the REAL shared trust authority (`load_root_trust` /
`evaluate_root_trust`), the REAL serving layer (`source_connector_service` search / list / read), the REAL
generation gate (`begin_generation_pass`), and the REAL watcher-activation predicate — not isolated mocks:

    unresolved quarantine
      -> root trust blocked
      -> source search / list / read blocked
      -> reconciliation (next generation pass) blocked
      -> watcher activation blocked
    operator retry resolves the final quarantine
      -> root REMAINS non-authoritative (no completed generation yet)
    a normal validating pass completes
      -> reconciliation completes
      -> root trust becomes safe
      -> serving answers again
      -> watcher activation is no longer quarantine-blocked

Scratch SQLite + temp roots only; no live/production DB, NAS, or remote MCP surface is touched.
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.obsidian_mcp import source_connector_service as svc
from hb_assistant.obsidian_mcp import source_indexer as si
from hb_assistant.obsidian_mcp.config import ExternalSourceRoot, ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_connector_models import CONTENT_LIVE_EXTRACT
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_quarantine_ops import retry_quarantine
from hb_assistant.obsidian_mcp.source_root_mapping import REASON_EXACT_MATCH, StructureRootMapping
from hb_assistant.obsidian_mcp.source_root_trust import (
    RC_QUARANTINE_UNRESOLVED,
    TRUST_SAFE,
    RootTrustInputs,
    evaluate_root_trust,
    load_root_trust,
)
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.source_index_scan_generations_repository import (
    SourceIndexScanGenerationsRepository,
)
from hb_assistant.store.source_index_scan_quarantine_repository import (
    SourceIndexScanQuarantineRepository,
)

_TEMPLATE_DB: str | None = None


def _template_db() -> str:
    global _TEMPLATE_DB
    if _TEMPLATE_DB is None:
        import os

        path = os.path.join(tempfile.mkdtemp(prefix="a4life_"), "template.db")
        SQLiteMigrator(db_path=path).apply()
        _TEMPLATE_DB = path
    return _TEMPLATE_DB


def _db(tmp_path: Path) -> str:
    db = str(tmp_path / "life.db")
    shutil.copy(_template_db(), db)
    return db


def _cfg(root_dir: Path, *, threshold: int = 2) -> ObsidianMcpConfig:
    return ObsidianMcpConfig(
        vault_root=str(root_dir),
        external_sources=[
            ExternalSourceRoot(source_root_key="work", path=str(root_dir), enabled=True)
        ],
        external_source_index_enabled=True,
        source_index_quarantine_retry_threshold=threshold,
    )


def _poison(name: str):
    orig = si._index_source_metadata

    def _flaky(abs_path, *a, **k):
        if abs_path.name == name:
            raise RuntimeError("permanent upsert error")
        return orig(abs_path, *a, **k)

    return _flaky


def _run_to_completion(r, repo, cfg, *, cap: int = 20):
    rep = None
    for _ in range(cap):
        rep = si.scan_source_root(r, repo, cfg)
        if rep.generation_status == "completed":
            return rep
    raise AssertionError(f"did not complete; last={rep.generation_status if rep else None}")


def test_quarantine_lifecycle_blocks_serving_and_reconcile_then_recovers(tmp_path, monkeypatch):
    root_dir = tmp_path / "work"
    root_dir.mkdir()
    (root_dir / "alpha.txt").write_text("payment schedule alpha for the contract")
    (root_dir / "beta.txt").write_text("payment invoice beta due now")
    (root_dir / "gamma.txt").write_text("payment poison gamma record")  # the poison file
    (root_dir / "delta.txt").write_text("payment note delta follow up")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir), enabled=True)
    cfg = _cfg(root_dir, threshold=2)
    genrepo = SourceIndexScanGenerationsRepository(db)
    # The root_path_hash the scan uses — a generation block matches on it, so mirror it exactly.
    rph = hashlib.sha256(str(root_dir).encode("utf-8")).hexdigest()[:32]

    # ---- Drive c.txt to a blocking quarantine via a REAL scan (pass1 holds < threshold; pass2 quarantines). ----
    monkeypatch.setattr(si, "_index_source_metadata", _poison("gamma.txt"))
    rep1 = si.scan_source_root(r, repo, cfg)
    assert rep1.generation_status == "partial"
    rep2 = si.scan_source_root(r, repo, cfg)
    assert rep2.generation_status == "failed"
    assert rep2.error_code == "quarantine_unresolved"

    qrepo = SourceIndexScanQuarantineRepository(db)
    assert qrepo.has_blocking("work") is True

    # ---- BLOCKED everywhere through the real shared authority. ----
    d_blocked = load_root_trust(repo, cfg, None, "work")
    assert d_blocked.trust_state != TRUST_SAFE
    assert RC_QUARANTINE_UNRESOLVED in d_blocked.reason_codes
    assert d_blocked.safe_for_client_answering is False
    assert d_blocked.safe_for_watcher_activation is False

    search_blocked = svc.search_source_files(
        repo, cfg, query="delta", source_root_key="work", limit=10
    )
    assert search_blocked["status"] == "blocked_root_unready"
    assert search_blocked["items"] == []
    assert search_blocked["authoritative"] is False

    list_blocked = svc.list_source_files(repo, cfg, source_root_key="work")
    assert list_blocked["status"] == "blocked_root_unready"
    assert list_blocked["authoritative"] is False

    # A readable, indexed file may not be live-read while its root is untrusted.
    a_row = repo.lookup_by_path("external_file", "alpha.txt")
    assert a_row is not None
    read_blocked = svc.read_source_file(repo, cfg, source_id=a_row["source_id"])
    assert read_blocked.get("reason") == "root_not_trusted"
    assert read_blocked.get("content_source") != CONTENT_LIVE_EXTRACT

    # Reconciliation / the next automatic generation pass is BLOCKED (no new infinite loop).
    blocked_gen = genrepo.begin_generation_pass(
        "work",
        "auto-run",
        policy_fingerprint=si._root_fingerprint(r, cfg),
        root_path_hash=rph,
    )
    assert blocked_gen.get("blocked") is True
    assert blocked_gen.get("last_error_code") == "quarantine_unresolved"

    # ---- Operator retry resolves the quarantine (c.txt is readable again once the fault is gone). ----
    monkeypatch.undo()
    out = retry_quarantine(db, cfg, root_key="work", max_items=5)
    assert out["resolved"] == 1
    assert qrepo.has_blocking("work") is False

    # Root REMAINS non-authoritative: resolving the quarantine did not itself certify a generation.
    d_after_retry = load_root_trust(repo, cfg, None, "work")
    assert d_after_retry.trust_state != TRUST_SAFE
    still_blocked = svc.search_source_files(
        repo, cfg, query="delta", source_root_key="work", limit=10
    )
    assert still_blocked["status"] == "blocked_root_unready"

    # ---- A normal validating pass now completes (c.txt indexes; the walk finalizes; reconciliation runs). ----
    rep_done = _run_to_completion(r, repo, cfg)
    assert rep_done.generation_status == "completed"
    n = (
        sqlite3.connect(db)
        .execute(
            "SELECT COUNT(*) FROM source_intelligence_sources WHERE source_root_key='work' AND deleted=0"
        )
        .fetchone()[0]
    )
    assert n == 4  # every file, including the once-poisoned c.txt, is now indexed

    # ---- SAFE again through the real authority; serving answers. ----
    d_safe = load_root_trust(repo, cfg, None, "work")
    assert d_safe.trust_state == TRUST_SAFE
    assert RC_QUARANTINE_UNRESOLVED not in d_safe.reason_codes
    assert d_safe.safe_for_client_answering is True

    search_ok = svc.search_source_files(repo, cfg, query="delta", source_root_key="work", limit=10)
    assert search_ok["status"] == "ok"
    assert search_ok["authoritative"] is True
    assert len(search_ok["items"]) > 0

    list_ok = svc.list_source_files(repo, cfg, source_root_key="work")
    assert list_ok["status"] == "ok"

    # A trusted root permits the live bounded read again.
    read_ok = svc.read_source_file(repo, cfg, source_id=a_row["source_id"])
    assert read_ok.get("reason") != "root_not_trusted"

    # The next generation pass is no longer blocked.
    ok_gen = genrepo.begin_generation_pass(
        "work",
        "auto-run-2",
        policy_fingerprint=si._root_fingerprint(r, cfg),
        root_path_hash=rph,
    )
    assert not ok_gen.get("blocked")


def _safe_watcher_inputs(*, quarantine: int) -> RootTrustInputs:
    """Fully watcher-activatable inputs (authorized, fresh, policy-current, reconciled, structure-ready),
    parameterized ONLY by the unresolved-quarantine count — so `evaluate_root_trust` isolates the quarantine
    as the deciding factor for `safe_for_watcher_activation`, independent of the watchdog install state."""
    fp = "fp-current"
    gen = {"status": "completed", "policy_fingerprint": fp}
    return RootTrustInputs(
        root_key="work",
        enabled=True,
        sensitive=False,
        has_config=True,
        backend_available=True,  # structure readiness requires a live backend; forced so the toggle is isolated
        freshness_state="fresh",
        folder_count=3,
        file_count=10,
        counts={"metadata_indexed": 10, "metadata_searchable": 10, "content_searchable": 10},
        gen_row=gen,
        current_fp=fp,
        file_index_status="bootstrapped",
        legacy_watcher_ready=True,
        struct_mapping=StructureRootMapping("work", "work", REASON_EXACT_MATCH),
        mapping_config_available=True,
        unresolved_quarantine_count=quarantine,
    )


def test_quarantine_toggles_watcher_activation_via_shared_authority():
    """The watcher-activation predicate integrates the quarantine blocker through the real pure authority."""
    safe = evaluate_root_trust(_safe_watcher_inputs(quarantine=0))
    assert safe.trust_state == TRUST_SAFE
    assert safe.safe_for_watcher_activation is True
    assert safe.watcher_activation_block_reason is None

    blocked = evaluate_root_trust(_safe_watcher_inputs(quarantine=1))
    assert blocked.trust_state != TRUST_SAFE
    assert RC_QUARANTINE_UNRESOLVED in blocked.reason_codes
    assert blocked.safe_for_watcher_activation is False
    # The block reason is surfaced (sanitized) so the watcher degrades with a deterministic code.
    assert blocked.watcher_activation_block_reason is not None


def test_quarantined_root_fails_watcher_start_closed(tmp_path, monkeypatch):
    """End-to-end fail-closed direction: a real SourceWatcher.start() on a root holding a blocking quarantine
    does NOT activate the drain (it degrades/stops) — the config bit + lease alone cannot start it."""
    from hb_assistant.obsidian_mcp.source_watch import SourceWatcher

    root_dir = tmp_path / "work"
    root_dir.mkdir()
    (root_dir / "a.txt").write_text("payment alpha")
    db = _db(tmp_path)
    cfg = ObsidianMcpConfig(
        vault_root=str(root_dir),
        external_sources=[
            ExternalSourceRoot(source_root_key="work", path=str(root_dir), enabled=True)
        ],
        external_source_index_enabled=True,
        external_source_watch_enabled=True,
        source_index_quarantine_retry_threshold=1,
    )
    # A real blocking quarantine for the root.
    SourceIndexScanQuarantineRepository(db).record_failure(
        root_key="work",
        rel_path="a.txt",
        source_id=None,
        generation_id="g1",
        failure_stage="metadata_stat",
        error_code="stat_failed",
        threshold=1,
    )
    w = SourceWatcher(db, cfg, app_config=cfg)
    w.start()
    try:
        st = w.status()
        # Fail closed: never watchdog/polling for a quarantined root.
        assert st["mode"] not in ("watchdog", "polling")
        assert st["running"] is False
    finally:
        w.stop()
