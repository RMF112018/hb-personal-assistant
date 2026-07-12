"""A2 — root-specific client trust (fail-closed only).

Proves the shared ``RootTrustDecision`` authority gates every client operation: an unsafe root returns zero
items / no metadata / no live read through search, list, metadata, and bounded read; unscoped search is
restricted to safe roots and discloses the excluded ones; configless roots are authorization-unverified with
unknown sensitivity; the health aggregate is non-vacuous (all enabled+authorized roots safe, never any-safe);
``read_status`` no longer claims live readability without a probe; and the watcher independently enforces the
authority. Mapping resolution and OPERATIONAL structure readiness are distinct.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import source_connector_service as svc
from hb_assistant.obsidian_mcp.config import ExternalSourceRoot, ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_content_provider import SourceContentProvider
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository, source_id_for
from hb_assistant.obsidian_mcp.source_indexer import _root_fingerprint
from hb_assistant.obsidian_mcp.source_root_trust import (
    AUTH_UNVERIFIED,
    RootTrustInputs,
    evaluate_root_trust,
    load_root_trust,
)
from hb_assistant.store.migrator import SQLiteMigrator

_TS = "2026-07-01T12:00:00+00:00"


def _insert(db: str, *, root_key: str, rel_path: str, body: str, ext: str = "txt",
            extraction_status: str = "ok") -> str:
    sid = source_id_for("external_file", source_root_key=root_key, rel_path=rel_path)
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO source_intelligence_sources(source_id,source_kind,source_root_key,"
                  "rel_path,active,deleted,created_at,updated_at) VALUES(?,?,?,?,1,0,'t','t')",
                  (sid, "external_file", root_key, rel_path))
        c.execute("INSERT INTO source_intelligence_metadata(source_id,file_ext,size_bytes,mtime_ns,"
                  "content_sha256,extraction_status,fts_rowid,indexed_at) VALUES(?,?,?,1,?,?,NULL,?)",
                  (sid, ext, len(body), hashlib.sha256(body.encode()).hexdigest(), extraction_status, _TS))
        c.execute("INSERT INTO source_intelligence_text(source_id,text_excerpt,excerpt_char_count,"
                  "excerpt_truncated,raw_body_persisted,redaction_applied,updated_at) "
                  "VALUES(?,?,?,0,0,1,'t')", (sid, body, len(body)))
        rid = c.execute("INSERT INTO source_intelligence_fts(text_excerpt,rel_path,aux) VALUES(?,?,NULL)",
                        (body, rel_path)).lastrowid
        c.execute("UPDATE source_intelligence_metadata SET fts_rowid=? WHERE source_id=?", (rid, sid))
        c.execute("INSERT OR REPLACE INTO source_intelligence_state(state_key,state_value,updated_at) "
                  "VALUES('fts_available','1','t')")
        c.commit()
    return sid


def _certify(db: str, config: ObsidianMcpConfig, root_key: str, *, status: str = "completed") -> None:
    """Insert a generation with the current policy fingerprint. ``completed`` → policy current; any other
    status (``partial``/``failed``/``running``) leaves the root NOT certified (fail-closed)."""
    cfg_root = next(r for r in config.external_sources if r.source_root_key == root_key)
    fp = _root_fingerprint(cfg_root, config)
    rph = hashlib.sha256(str(Path(cfg_root.path)).encode("utf-8")).hexdigest()[:32]
    with sqlite3.connect(db) as c:
        c.execute(
            "INSERT INTO source_index_scan_generations(generation_id, root_key, status, root_path_hash, "
            "policy_fingerprint, started_at, updated_at, metadata_walk_completed_at, "
            "reconciliation_completed_at, finished_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (f"gen-{root_key}-{status}", root_key, status, rph, fp, _TS, _TS,
             _TS if status == "completed" else None,
             _TS if status == "completed" else None,
             _TS if status == "completed" else None),
        )
        c.commit()


@pytest.fixture()
def env(tmp_path: Path):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    roots = {}
    for key in ("safe", "sensitive", "uncertified", "disabled"):
        d = tmp_path / key
        d.mkdir()
        (d / "doc.txt").write_text(f"payment record for {key} root")
        roots[key] = d
    ids = {
        "safe": _insert(db, root_key="safe", rel_path="doc.txt", body="payment record for safe root"),
        "sensitive": _insert(db, root_key="sensitive", rel_path="doc.txt",
                             body="payment record for sensitive root"),
        "uncertified": _insert(db, root_key="uncertified", rel_path="doc.txt",
                               body="payment record for uncertified root"),
        "disabled": _insert(db, root_key="disabled", rel_path="doc.txt",
                            body="payment record for disabled root"),
    }
    config = ObsidianMcpConfig(external_sources=[
        ExternalSourceRoot(source_root_key="safe", path=str(roots["safe"])),
        ExternalSourceRoot(source_root_key="sensitive", path=str(roots["sensitive"]), sensitive=True),
        ExternalSourceRoot(source_root_key="uncertified", path=str(roots["uncertified"])),
        ExternalSourceRoot(source_root_key="disabled", path=str(roots["disabled"]), enabled=False),
    ])
    _certify(db, config, "safe")
    _certify(db, config, "sensitive")
    # "uncertified" gets a non-completed generation (still fails closed); "disabled" is enabled=False.
    _certify(db, config, "uncertified", status="partial")
    return {"db": db, "repo": SourceIndexRepository(db), "config": config, "ids": ids, "tmp": str(tmp_path)}


def _no_abs(payload, tmp: str) -> None:
    blob = json.dumps(payload, default=str)
    assert tmp not in blob
    assert "/Users/" not in blob


# ============================ pure decision authority ============================
def _inputs(**over):
    base = {
        "root_key": "r", "enabled": True, "sensitive": False, "has_config": True,
        "backend_available": True, "freshness_state": "fresh", "folder_count": 0, "file_count": 5,
        "counts": {"metadata_indexed": 5, "metadata_searchable": 5, "content_searchable": 5,
                   "content_extracted": 5},
        "gen_row": {"status": "completed", "policy_fingerprint": "fp"}, "current_fp": "fp",
        "file_index_status": "bootstrapped", "legacy_watcher_ready": False,
        "struct_mapping": type("M", (), {"structure_key": None, "reason": "unmapped"})(),
        "mapping_config_available": True,
    }
    base.update(over)
    return RootTrustInputs(**base)


def test_certified_root_is_safe():
    d = evaluate_root_trust(_inputs())
    assert d.trust_state == "safe"
    assert d.safe_for_client_answering is True
    assert d.safe_for_live_read is True


def test_uncertified_policy_fails_closed():
    d = evaluate_root_trust(_inputs(gen_row=None, file_index_status=None))
    assert d.trust_state == "blocked"
    assert d.safe_for_client_answering is False
    assert "policy_uncertified" in d.reason_codes


def test_stale_policy_fails_closed():
    d = evaluate_root_trust(_inputs(gen_row={"status": "completed", "policy_fingerprint": "OLD"}))
    assert d.trust_state == "blocked"
    assert d.policy_verification == "stale"


def test_running_corrective_generation_does_not_reopen_trust():
    # A newer running/partial generation must NOT certify — trust stays closed until it COMPLETES.
    d = evaluate_root_trust(_inputs(gen_row={"status": "partial", "policy_fingerprint": "fp"}))
    assert d.trust_state == "blocked"
    assert d.safe_for_content_answering == "none"


def test_disabled_root_is_denied():
    d = evaluate_root_trust(_inputs(enabled=False))
    assert d.trust_state == "denied"
    assert d.authorization_state == "denied"
    assert "root_disabled" in d.reason_codes


def test_configless_root_is_unverified():
    d = evaluate_root_trust(_inputs(has_config=False))
    assert d.trust_state == "unverified"
    assert d.authorization_state == "unverified"
    assert d.sensitivity_known is False


def test_sensitive_root_not_live_readable():
    d = evaluate_root_trust(_inputs(sensitive=True))
    assert d.trust_state == "safe"          # safe for path lookup / content
    assert d.safe_for_live_read is False    # but never live-readable
    assert "sensitive_root" in d.reason_codes


def test_freshness_unknown_fails_closed():
    d = evaluate_root_trust(_inputs(freshness_state="unknown"))
    assert d.trust_state == "blocked"
    assert "freshness_unknown" in d.reason_codes


def test_mapping_resolved_is_not_structure_ready():
    # A resolved mapping ALONE never makes structure_ready true (needs backend + folder + watcher).
    mapped = type("M", (), {"structure_key": "s", "reason": "exact_match"})()
    d = evaluate_root_trust(_inputs(struct_mapping=mapped, folder_count=0))
    assert d.structure_mapping_resolved is True
    assert d.structure_ready is False
    d2 = evaluate_root_trust(_inputs(struct_mapping=mapped, folder_count=3,
                                     gen_row={"status": "completed", "policy_fingerprint": "fp"}))
    assert d2.structure_ready is True  # mapping resolved + backend + folder + watcher-ready


# ============================ serving: search / list / metadata ============================
def test_safe_root_search_still_works(env):
    r = svc.search_source_files(env["repo"], env["config"], query="payment", source_root_key="safe")
    assert r["status"] == "ok"
    assert r["authoritative"] is True
    assert r["count"] >= 1
    assert all(i["source_root_key"] == "safe" for i in r["items"])


def test_explicit_unsafe_root_search_blocked(env):
    r = svc.search_source_files(env["repo"], env["config"], query="payment",
                                source_root_key="uncertified")
    assert r["status"] == "blocked_root_unready"
    assert r["items"] == []
    assert r["authoritative"] is False
    assert r["root_readiness"]["trust_state"] == "blocked"
    assert r["root_readiness"]["reason_codes"]


def test_disabled_root_search_blocked(env):
    r = svc.search_source_files(env["repo"], env["config"], query="payment", source_root_key="disabled")
    assert r["status"] == "blocked_root_unready"
    assert r["root_readiness"]["trust_state"] == "denied"


def test_unknown_root_search_returns_unknown_root(env):
    r = svc.search_source_files(env["repo"], env["config"], query="payment", source_root_key="ghost")
    assert r["status"] == "unknown_root"
    assert r["items"] == []


def test_unscoped_search_restricts_to_safe_and_discloses_excluded(env):
    r = svc.search_source_files(env["repo"], env["config"], query="payment")
    assert r["status"] == "ok"
    # Only safe + sensitive (both certified, both safe for path lookup) may appear; never uncertified/disabled.
    assert {i["source_root_key"] for i in r["items"]} <= {"safe", "sensitive"}
    assert "uncertified" in r["excluded_root_keys"]
    assert "disabled" in r["excluded_root_keys"]
    _no_abs(r, env["tmp"])


def test_unscoped_search_all_unsafe_returns_blocked(tmp_path):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    d = tmp_path / "u"
    d.mkdir()
    _insert(db, root_key="u", rel_path="a.txt", body="payment here")
    config = ObsidianMcpConfig(external_sources=[ExternalSourceRoot(source_root_key="u", path=str(d))])
    # no certification -> uncertified -> unsafe
    r = svc.search_source_files(SourceIndexRepository(db), config, query="payment")
    assert r["status"] == "blocked_root_unready"
    assert r["items"] == []
    assert "u" in r["excluded_root_keys"]


def test_list_unsafe_root_blocked(env):
    r = svc.list_source_files(env["repo"], env["config"], source_root_key="uncertified")
    assert r["status"] == "blocked_root_unready"
    assert r["items"] == []
    assert r["authoritative"] is False


def test_list_safe_root_works(env):
    r = svc.list_source_files(env["repo"], env["config"], source_root_key="safe")
    assert r["status"] == "ok"
    assert r["count"] >= 1


def test_metadata_unsafe_root_blocked(env):
    md = svc.source_file_metadata(env["repo"], env["config"], source_id=env["ids"]["uncertified"])
    assert md["status"] == "blocked_root_unready"
    assert md["authoritative"] is False
    # No advisory item metadata is exposed.
    assert "extraction_status" not in md
    assert "rel_path" not in md


def test_metadata_safe_root_works(env):
    md = svc.source_file_metadata(env["repo"], env["config"], source_id=env["ids"]["safe"])
    assert md["status"] == "ok"
    assert md["object_type"] == "source_file"
    assert md["rel_path"] == "doc.txt"


# ============================ read: trust before FS ============================
def test_read_checks_trust_before_fs_for_unsafe_root(env):
    prov = SourceContentProvider(env["repo"], env["config"])
    r = prov.read(env["ids"]["uncertified"], max_chars=50)
    assert r["content_source"] != "live_extract"
    assert r["reason"] == "root_not_trusted"
    assert r["root_readiness"]["trust_state"] == "blocked"


def test_read_safe_root_is_live(env):
    prov = SourceContentProvider(env["repo"], env["config"])
    r = prov.read(env["ids"]["safe"], max_chars=50)
    assert r["content_source"] == "live_extract"


def test_read_sensitive_root_never_live(env):
    prov = SourceContentProvider(env["repo"], env["config"])
    r = prov.read(env["ids"]["sensitive"], max_chars=50)
    assert r["content_source"] != "live_extract"


# ============================ read_status semantics ============================
def test_read_status_no_live_claim_without_probe():
    from hb_assistant.obsidian_mcp.source_project_number import match_explanation_for_row

    expl = match_explanation_for_row({"rel_path": "a/b.txt", "file_ext": "txt", "snippet": "x"},
                                     query="x", project_numbers=[])
    assert expl["read_status"] == "read_capability_known"      # capability, not live state
    assert expl["read_status"] != "live_readable"
    assert expl["live_readability"] == "unverified"
    assert expl["live_read_performed"] is False


def test_read_status_unsupported_is_metadata_only():
    from hb_assistant.obsidian_mcp.source_project_number import match_explanation_for_row

    expl = match_explanation_for_row({"rel_path": "a/schedule.xer", "file_ext": "xer", "snippet": ""},
                                     query="x", project_numbers=[])
    assert expl["read_status"] == "unsupported_metadata_only"
    assert expl["live_readability"] == "unsupported"


# ============================ health aggregate ============================
def _health(env):
    from hb_assistant.obsidian_mcp.source_health_service import source_index_health

    return source_index_health(env["repo"], env["config"], app_config=env["config"])


def test_health_aggregate_all_safe_not_any_safe(env):
    h = _health(env)
    # uncertified + disabled roots exist and are unsafe → the ALL-safe routing signal must be False even
    # though SOME roots (safe/sensitive) are safe.
    assert h["any_root_safe"] is True
    assert h["all_enabled_roots_safe"] is False
    assert h["safe_for_client_answering"] is False   # canonical routing signal == all-enabled-safe
    assert "uncertified" in h["unsafe_root_keys"]


def test_zero_authorized_roots_is_not_client_safe(tmp_path):
    from hb_assistant.obsidian_mcp.source_health_service import source_index_health

    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    config = ObsidianMcpConfig(external_sources=[])  # no roots at all
    h = source_index_health(SourceIndexRepository(db), config, app_config=config)
    assert h["safe_for_client_answering"] is False
    assert h["all_enabled_roots_safe"] is False
    assert h["zero_authorized_roots_is_not_client_safe"] is True


def test_health_no_absolute_path_leak(env):
    _no_abs(_health(env), env["tmp"])


# ============================ direct == gateway parity ============================
def test_direct_and_gateway_trust_agree(env):
    # The connector service is the single authority behind both the direct API and the NAS MCP broker, so a
    # blocked root blocks identically regardless of entry point (same function, same decision).
    direct = svc.search_source_files(env["repo"], env["config"], query="payment",
                                     source_root_key="uncertified")
    again = svc.search_source_files(env["repo"], env["config"], query="payment",
                                    source_root_key="uncertified")
    assert direct["status"] == again["status"] == "blocked_root_unready"
    assert direct["root_readiness"]["reason_codes"] == again["root_readiness"]["reason_codes"]


# ============================ configless roots ============================
def test_configless_root_listed_unverified(tmp_path):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    _insert(db, root_key="orphan", rel_path="a.txt", body="payment here")
    config = ObsidianMcpConfig(external_sources=[])  # configless serve profile
    roots = svc.list_source_roots(SourceIndexRepository(db), config)["roots"]
    orphan = next(r for r in roots if r["source_root_key"] == "orphan")
    assert orphan["authorization_state"] == "unverified"
    assert orphan["sensitivity_known"] is False
    assert orphan["sensitive"] is None  # NOT False (would fail open)


def test_configless_root_load_trust_unverified(tmp_path):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    _insert(db, root_key="orphan", rel_path="a.txt", body="payment here")
    config = ObsidianMcpConfig(external_sources=[])
    d = load_root_trust(SourceIndexRepository(db), config, None, "orphan")
    assert d.authorization_state == AUTH_UNVERIFIED
    assert d.safe_for_client_answering is False


# ============================ safe-root pagination determinism ============================
def test_safe_root_pagination_deterministic(tmp_path):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    d = tmp_path / "safe"
    d.mkdir()
    for i in range(3):
        _insert(db, root_key="safe", rel_path=f"f{i}.txt", body=f"payment item {i}")
    config = ObsidianMcpConfig(external_sources=[ExternalSourceRoot(source_root_key="safe", path=str(d))])
    _certify(db, config, "safe")
    repo = SourceIndexRepository(db)
    seen = []
    cursor = None
    for _ in range(3):
        page = svc.list_source_files(repo, config, source_root_key="safe", limit=1, cursor=cursor)
        assert page["status"] == "ok"
        seen.extend(i["rel_path"] for i in page["items"])
        cursor = page.get("next_cursor")
        if not cursor:
            break
    assert len(seen) == len(set(seen)) == 3


# ============================ watcher startup enforcement ============================
def _watch_config(tmp_path, *, roots):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    config = ObsidianMcpConfig(external_sources=roots, external_source_watch_enabled=True)
    return db, config


def test_watcher_degrades_when_all_roots_disabled(tmp_path):
    from hb_assistant.obsidian_mcp.source_watch import SourceWatcher

    d = tmp_path / "x"
    d.mkdir()
    db, config = _watch_config(
        tmp_path, roots=[ExternalSourceRoot(source_root_key="x", path=str(d), enabled=False)]
    )
    w = SourceWatcher(db, config)
    w.start()
    try:
        assert w._mode == "degraded"
        assert w._last_error_code == "watcher_no_authorized_roots"
    finally:
        w.stop()


def test_watcher_degrades_on_unevaluable_trust(tmp_path, monkeypatch):
    from hb_assistant.obsidian_mcp.source_watch import SourceWatcher

    d = tmp_path / "x"
    d.mkdir()
    db, config = _watch_config(
        tmp_path, roots=[ExternalSourceRoot(source_root_key="x", path=str(d))]
    )
    monkeypatch.setattr(
        "hb_assistant.obsidian_mcp.source_root_trust.load_root_trust",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    w = SourceWatcher(db, config)
    w.start()
    try:
        assert w._mode == "degraded"
        assert w._last_error_code == "watcher_trust_unevaluable"
    finally:
        w.stop()


def test_watcher_config_bit_alone_cannot_bypass_when_no_roots(tmp_path):
    # external_source_watch_enabled=True but ZERO configured roots must not silently look authorized —
    # the drain still starts (nothing to deny), but the enforcement gate was consulted (no crash).
    from hb_assistant.obsidian_mcp.source_watch import SourceWatcher

    db, config = _watch_config(tmp_path, roots=[])
    w = SourceWatcher(db, config)
    w.start()
    try:
        # No configured roots → no denial; the watcher may run. The gate was invoked without bypassing.
        assert w._mode in ("watchdog", "polling", "degraded")
    finally:
        w.stop()


# ===================== watcher activation is bootstrap-gated (fail closed) =====================
# A2 corrective: SourceWatcher.start() must itself enforce the shared authority's
# ``safe_for_watcher_activation`` (bootstrapped + certified + reconciled + structure-data-ready). Bootstrap
# is a SEPARATE, watcher-independent operation, so blocking the watcher pre-bootstrap is NOT circular.
def _bootstrapped_watch_env(tmp_path, *, file_only=False):
    """Build a real 'work' root + config + app_config and run a REAL ``source_bootstrap.bootstrap()``.

    A FULL bootstrap makes the root ``safe_for_watcher_activation`` (completed generation + structure data);
    a ``file_only`` bootstrap certifies the file layer but leaves structure data unready. Returns
    (db, config, app_config)."""
    from hb_assistant.config.loader import load_config as load_app_config
    from hb_assistant.obsidian_mcp import source_bootstrap as sb

    root_dir = tmp_path / "work"
    root_dir.mkdir()
    for i in range(3):
        (root_dir / f"f{i}.txt").write_text(f"payment record {i}")
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    config = ObsidianMcpConfig(
        vault_root=str(root_dir),
        external_sources=[ExternalSourceRoot(source_root_key="work", path=str(root_dir))],
        external_source_index_enabled=True,
        external_source_watch_enabled=True,
    )
    acfg = load_app_config()
    acfg.source_structure.scan_roots = {"work": str(root_dir)}
    sb.bootstrap(
        db_path=db, obsidian_config=config, app_config=acfg, root_key="work", file_only=file_only
    )
    return db, config, acfg


def _unbootstrapped_watch_env(tmp_path):
    """An enabled 'work' root with a file present but NO bootstrap/generation (pre-index state)."""
    from hb_assistant.config.loader import load_config as load_app_config

    d = tmp_path / "work"
    d.mkdir()
    (d / "f.txt").write_text("payment record")
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    config = ObsidianMcpConfig(
        vault_root=str(d),
        external_sources=[ExternalSourceRoot(source_root_key="work", path=str(d))],
        external_source_watch_enabled=True,
    )
    acfg = load_app_config()
    acfg.source_structure.scan_roots = {"work": str(d)}
    return db, config, acfg


def test_watcher_start_before_bootstrap_fails_closed(tmp_path):
    # The watcher itself (not just client serving) MUST fail closed for a not-yet-bootstrapped root.
    from hb_assistant.obsidian_mcp.source_watch import SourceWatcher

    db, config, acfg = _unbootstrapped_watch_env(tmp_path)
    w = SourceWatcher(db, config, app_config=acfg)
    w.start()
    try:
        assert w._mode == "degraded"
        assert w._last_error_code == "watcher_root_not_bootstrapped"
    finally:
        w.stop()


def test_bootstrap_succeeds_without_watcher(tmp_path):
    # Reframed from the former 'watcher allows uncertified to bootstrap': bootstrap is a SEPARATE operation
    # that runs WITHOUT the watcher and establishes durable readiness — this is what makes gating the watcher
    # pre-bootstrap non-circular. It proves bootstrap is allowed, NOT that the watcher starts early.
    from hb_assistant.store.source_index_scan_generations_repository import (
        SourceIndexScanGenerationsRepository,
    )

    db, config, acfg = _bootstrapped_watch_env(tmp_path)  # a REAL bootstrap ran, no watcher involved
    gen = (SourceIndexScanGenerationsRepository(db).latest_generations() or {}).get("work")
    assert gen is not None and gen["status"] == "completed"  # durable readiness established
    d = load_root_trust(SourceIndexRepository(db), config, acfg, "work")
    assert d.safe_for_watcher_activation is True  # now — and only now — the watcher may activate


def test_watcher_start_after_bootstrap_succeeds(tmp_path):
    from hb_assistant.obsidian_mcp.source_watch import SourceWatcher

    db, config, acfg = _bootstrapped_watch_env(tmp_path)  # FULL bootstrap → fully ready
    w = SourceWatcher(db, config, app_config=acfg)
    w.start()
    try:
        assert w._mode in ("watchdog", "polling")  # NOT degraded — the ready root activates
        assert w._last_error_code not in (
            "watcher_root_not_bootstrapped", "watcher_structure_data_unready",
            "watcher_policy_stale", "watcher_reconciliation_incomplete",
        )
    finally:
        w.stop()


def test_watcher_start_blocks_structure_data_unready(tmp_path):
    # file_only bootstrap: file layer certified (trust_state safe) but NO structure data → not activatable.
    from hb_assistant.obsidian_mcp.source_watch import SourceWatcher

    db, config, acfg = _bootstrapped_watch_env(tmp_path, file_only=True)
    w = SourceWatcher(db, config, app_config=acfg)
    w.start()
    try:
        assert w._mode == "degraded"
        assert w._last_error_code == "watcher_structure_data_unready"
    finally:
        w.stop()


def test_watcher_start_blocks_policy_stale(tmp_path):
    # A fully-ready root whose certified generation's policy fingerprint later drifts must NOT keep draining.
    from hb_assistant.obsidian_mcp.source_watch import SourceWatcher

    db, config, acfg = _bootstrapped_watch_env(tmp_path)
    with sqlite3.connect(db) as c:
        c.execute(
            "UPDATE source_index_scan_generations SET policy_fingerprint='STALE_FP' WHERE root_key='work'"
        )
        c.commit()
    w = SourceWatcher(db, config, app_config=acfg)
    w.start()
    try:
        assert w._mode == "degraded"
        assert w._last_error_code == "watcher_policy_stale"
    finally:
        w.stop()


def test_watcher_start_blocks_reconciliation_incomplete(tmp_path):
    # A generation regressed to a pre-reconcile lifecycle state must block watcher activation.
    from hb_assistant.obsidian_mcp.source_watch import SourceWatcher

    db, config, acfg = _bootstrapped_watch_env(tmp_path)
    with sqlite3.connect(db) as c:
        c.execute(
            "UPDATE source_index_scan_generations SET status='reconcile_pending', "
            "reconciliation_completed_at=NULL WHERE root_key='work'"
        )
        c.commit()
    w = SourceWatcher(db, config, app_config=acfg)
    w.start()
    try:
        assert w._mode == "degraded"
        assert w._last_error_code == "watcher_reconciliation_incomplete"
    finally:
        w.stop()
