"""NAS MCP client-readiness remediation (10 defects) — targeted behavior tests.

Covers the fixes that take the connected-client surface to genuine operational readiness:
  * A output workspace: JSON base64 staging, ZIP base64 content-mode alias, archive approval id
  * B tool metadata + manifest: classify_tool wiring, purpose passthrough, startup auto-bootstrap
  * C decision-surface projection: promoted canonical artifacts surface in the read tools
  * D vault tooling: list_directory max_files cap + no absolute-root leak, scoped-search visibility
  * E source live-read: external_sources derived/mapped so prefer_live resolves
  * F freshness: a recently-failed subsystem no longer reads "ok"
"""

from __future__ import annotations

import base64
import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.nas_mcp.client_output_workspace import (
    ClientOutputWorkspaceRepository,
)
from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec
from hb_assistant.store.migrator import SQLiteMigrator
from tests.n8c24_helpers import good_zip_b64, make_env


# ======================================================================================
# A. Output workspace (Defects 2, 3, 4, 10)
# ======================================================================================
def _out_repo(tmp_path: Path) -> ClientOutputWorkspaceRepository:
    env = make_env(tmp_path)
    return ClientOutputWorkspaceRepository(env["config"], env["db"])


def test_json_stage_from_content_text(tmp_path: Path) -> None:
    repo = _out_repo(tmp_path)
    s = repo.stage_output_file({"title": "cfg", "file_type": "json", "content_mode": "json_text",
                                "content_text": '{"a": 1, "b": [2, 3]}'})
    assert s["staged_status"] == "staged" and s["bytes_estimated"] > 0


def test_json_stage_from_content_base64_decodes(tmp_path: Path) -> None:
    # Defect 2: a base64 JSON payload used to hit json.loads(base64) → "invalid json content".
    repo = _out_repo(tmp_path)
    payload = base64.b64encode(b'{"hello": "world"}').decode("ascii")
    s = repo.stage_output_file({"title": "cfg", "file_type": "json", "content_base64": payload})
    r = repo.commit_output_file(output_id=s["output_id"], operator_approval_id=s["operator_approval_id"],
                                idempotency_key=s["idempotency_key"])
    assert r["status"] == "committed"
    excerpt = repo.read_output_excerpt(s["output_id"])["excerpt"]
    assert json.loads(excerpt) == {"hello": "world"}


def test_json_stage_base64_that_is_not_json_is_rejected(tmp_path: Path) -> None:
    from hb_assistant.nas_mcp.client_output_writers import OutputWriteError

    repo = _out_repo(tmp_path)
    payload = base64.b64encode(b"not json at all").decode("ascii")
    with pytest.raises(OutputWriteError, match="invalid json"):
        repo.stage_output_file({"title": "cfg", "file_type": "json", "content_base64": payload})


def test_zip_stage_accepts_bare_base64_content_mode_alias(tmp_path: Path) -> None:
    # Defect 3: content_mode "base64" (the natural client value) folded to base64_binary, not rejected.
    repo = _out_repo(tmp_path)
    s = repo.stage_output_file({"title": "bundle", "file_type": "zip", "content_mode": "base64",
                                "content_base64": good_zip_b64()})
    assert s["staged_status"] == "staged"
    assert s["zip_validation"]["member_count"] >= 1


def test_plan_archive_returns_reusable_operator_approval_id(tmp_path: Path) -> None:
    # Defect 4/10: plan_archive_output now echoes the stage-minted approval so archive is completable.
    repo = _out_repo(tmp_path)
    s = repo.stage_output_file({"title": "doc", "file_type": "md", "content_mode": "markdown_text",
                               "content_text": "# hi\nbody", "destination_state": "final"})
    repo.commit_output_file(output_id=s["output_id"], operator_approval_id=s["operator_approval_id"],
                            idempotency_key=s["idempotency_key"])
    plan = repo.plan_archive_output(s["output_id"])
    assert plan["operator_approval_id"] == s["operator_approval_id"]
    assert plan["deletes"] is False
    done = repo.commit_archive_output(output_id=s["output_id"],
                                      operator_approval_id=plan["operator_approval_id"])
    assert done["status"] == "archived" and done["deletes"] is False
    # path_display must track the archive move, not stay on the stale pending path.
    meta = repo.get_output_metadata(s["output_id"])
    assert meta["relative_path"] == done["archive_relative_path"]
    assert meta["path_display"].endswith(done["archive_relative_path"])


# ======================================================================================
# B. Tool metadata + manifest (Defects 1, 9)
# ======================================================================================
def test_assistant_tool_meta_uses_real_safety_class(tmp_path: Path) -> None:
    # Defect 9: staged/canonical writes must not be labelled read_only_advisory.
    from hb_assistant.nas_mcp.tool_registration import _assistant_tool_meta

    stage = _assistant_tool_meta("pa_output_stage", {})
    assert stage["safety_class"] == "staged_write_requires_review"
    assert stage["read_write_class"] == "staged_write"
    capture = _assistant_tool_meta("pa_session_capture_stage", {})
    assert capture["safety_class"] == "staged_write_requires_review"
    # A genuine read stays a bounded/safe read.
    nav = _assistant_tool_meta("assistant_list_decisions", {})
    assert nav["read_write_class"] == "read_only"


def test_build_manifest_carries_purpose(tmp_path: Path) -> None:
    from hb_assistant.obsidian_mcp.client_tool_manifest import build_manifest

    idx = {"assistant_list_decisions": {"group": "decision_memory", "purpose": "List decisions",
                                        "required_args": [], "optional_args": ["limit"], "limits": {"limit": 25}}}
    m = build_manifest(idx, runtime_commit="vT", now="2026-07-08T00:00:00+00:00")
    entry = next(e for e in m["entries"] if e["tool_name"] == "assistant_list_decisions")
    assert entry["purpose"] == "List decisions"
    assert entry["optional_args"] == ["limit"] and entry["limits"] == {"limit": 25}


def test_manifest_bootstrap_is_gated_off_when_not_readonly(tmp_path: Path) -> None:
    from hb_assistant.nas_mcp.artifact_tools import bootstrap_persisted_manifest

    out = bootstrap_persisted_manifest(make_env(tmp_path)["config"])
    assert out["bootstrapped"] is False and out["reason"] == "not_nas_readonly_profile"


def test_manifest_bootstrap_persists_and_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    # Defect 1: server self-materializes a persisted active manifest under the read-only NAS profile,
    # so pa_tool_manifest_get returns persisted:true; a no-change re-run is a no-op.
    from hb_assistant.nas_mcp.artifact_tools import (
        bootstrap_persisted_manifest,
        dispatch_manifest_tool,
    )

    monkeypatch.setenv("HB_ASSISTANT_DB_READONLY", "1")
    monkeypatch.setenv("HB_ASSISTANT_WORKSPACE_DB", str(tmp_path / "workspace" / "db" / "ws.sqlite"))
    (tmp_path / "workspace" / "db").mkdir(parents=True, exist_ok=True)

    # Build a vault-backed config (promote writes the manifest md/json pair into 99 System/Manifests).
    from tests.n8c23_helpers import make_env as n8c23_make_env

    config = n8c23_make_env(tmp_path)["config"]

    first = bootstrap_persisted_manifest(config, runtime_commit="vBoot")
    assert first["bootstrapped"] is True and first["manifest_id"]

    got = dispatch_manifest_tool(config, "pa_tool_manifest_get", {}, runtime_commit="vBoot")
    assert got.get("persisted") is True
    assert got["manifest_status"] == "active" and got["tool_count"] > 0

    second = bootstrap_persisted_manifest(config, runtime_commit="vBoot")
    assert second["bootstrapped"] is False and second["reason"] == "already_active"


# ======================================================================================
# C. Decision-surface projection (Defect 5)
# ======================================================================================
def _seed_canonical(db: str, *, canonical_id: str, artifact_type: str, title: str, summary: str,
                    status: str = "canonical") -> None:
    with sqlite3.connect(db) as c:
        c.execute(
            "INSERT INTO pa_canonical_artifacts (canonical_id, artifact_type, title, summary, domain, "
            "status, vault_path, content_hash, promoted_at, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (canonical_id, artifact_type, title, summary, "work", status,
             "Work/03 Decisions/x.md", "hash1", "2026-07-08T00:00:00+00:00",
             "2026-07-08T00:00:00+00:00", "2026-07-08T00:00:00+00:00"))


def test_projection_maps_canonical_onto_record_shape(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from hb_assistant.nas_mcp import canonical_decision_projection as proj

    db = str(tmp_path / "c.sqlite")
    SQLiteMigrator(db_path=db).apply()
    _seed_canonical(db, canonical_id="CANON-D-1", artifact_type="decision",
                    title="Use staged promotion", summary="Promote via staging")
    with sqlite3.connect(db) as c:
        c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    cfg = SimpleNamespace(db_path=db)
    recs = proj.project_canonical_records(cfg, "decision", limit=10)
    assert len(recs) == 1
    r = recs[0]
    assert r["decision_id"] == "CANON-D-1" and r["record_source"] == "canonical_artifact"
    assert r["decision_text"] == "Promote via staging" and r["note_rel_path"] == "Work/03 Decisions/x.md"


def test_merge_dedup_and_status_filter() -> None:
    from hb_assistant.nas_mcp import canonical_decision_projection as proj

    native = [{"decision_id": "N1"}]
    projected = [{"decision_id": "N1"}, {"decision_id": "C1", "status": "canonical"}]
    merged = proj.merge_records(native, projected, pk="decision_id", status=None, limit=50)
    assert [m["decision_id"] for m in merged] == ["N1", "C1"]  # N1 not duplicated, C1 appended
    # A non-canonical status filter drops projected canonical rows.
    filtered = proj.merge_records(native, projected, pk="decision_id", status="candidate", limit=50)
    assert [m["decision_id"] for m in filtered] == ["N1"]


def test_broker_list_decisions_includes_promoted_canonical(tmp_path: Path, monkeypatch) -> None:
    # End-to-end: a promoted canonical decision appears via assistant_list_decisions / assistant_get_decision.
    monkeypatch.setenv("HB_MCP_PROFILE", "remote_cloudflare")
    from hb_assistant.nas_mcp.broker import NasMcpBroker

    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    _seed_canonical(db, canonical_id="CANON-D-9", artifact_type="decision",
                    title="Canonical decision", summary="A promoted decision")
    with sqlite3.connect(db) as c:
        c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    cfg = NasMcpConfig(db_path=Path(db), audit_dir=tmp_path / "audit",
                       roots={"vault": RootSpec("vault", vault, "read_write")},
                       obsidian=NasObsidianConfig(vault_root=vault, backup_dir=tmp_path / "bk",
                                                  support_dir=tmp_path / "sup"))
    broker = NasMcpBroker(cfg)
    listed = broker.dispatch("assistant_list_decisions", {})
    assert listed["ok"] is True, listed
    ids = [d["decision_id"] for d in listed["result"]["decisions"]]
    assert "CANON-D-9" in ids
    got = broker.dispatch("assistant_get_decision", {"decision_id": "CANON-D-9"})
    assert got["ok"] is True and got["result"]["decision"]["record_source"] == "canonical_artifact"


# ======================================================================================
# D. Vault tooling (Defect 7)
# ======================================================================================
def _vault_config(tmp_path: Path, n_files: int = 12):
    from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig

    vault = tmp_path / "vault"
    (vault / "Notes").mkdir(parents=True)
    for i in range(n_files):
        (vault / "Notes" / f"n{i:02d}.md").write_text(f"# note {i}\nbody", encoding="utf-8")
    return ObsidianMcpConfig(vault_root=str(vault)), vault


def test_list_directory_caps_and_hides_absolute_root(tmp_path: Path) -> None:
    from hb_assistant.obsidian_mcp.tools import list_directory

    config, _ = _vault_config(tmp_path, n_files=12)
    result = list_directory(config, path="Notes", recursive=True, extensions=["md"], max_files=5)
    assert result["file_count"] == 5 and result["truncated"] is True
    assert "root" not in result  # absolute /mnt/vault-style root no longer leaked
    assert result["path_display"] == "Notes"


def test_list_directory_default_cap_untruncated_small_dir(tmp_path: Path) -> None:
    from hb_assistant.obsidian_mcp.tools import list_directory

    config, _ = _vault_config(tmp_path, n_files=3)
    result = list_directory(config, path="Notes", recursive=True, extensions=["md"])
    assert result["file_count"] == 3 and result["truncated"] is False


def test_search_by_properties_reports_scope_and_truncation(tmp_path: Path) -> None:
    from hb_assistant.obsidian_mcp.frontmatter import search_by_properties

    config, vault = _vault_config(tmp_path, n_files=2)
    (vault / "Notes" / "tagged.md").write_text("---\nkind: decision\n---\n# t\nbody", encoding="utf-8")
    res = search_by_properties(config, root_path="Notes", filters={"kind": "decision"})
    assert res["scope"] == "Notes" and res["scoped"] is True
    assert "truncated" in res
    assert all(r["path"].startswith("Notes/") for r in res["results"])


def test_dataview_query_documents_sole_scope(tmp_path: Path) -> None:
    from hb_assistant.obsidian_mcp.frontmatter import dataview_query

    config, _ = _vault_config(tmp_path, n_files=2)
    res = dataview_query(config, root_path="", where=[{"field": "path", "op": "exists"}])
    assert res["scope"] == "(entire vault)" and res["scoped"] is False
    assert "FROM is unsupported" in res["scope_note"]


# ======================================================================================
# E. Source live-read enablement (Defect 8)
# ======================================================================================
def _nas_cfg_with_roots(tmp_path: Path, *, external_sources=()):
    home = tmp_path / "roots" / "home"
    work = tmp_path / "roots" / "work"
    vault = tmp_path / "vault"
    for p in (home, work, vault):
        p.mkdir(parents=True, exist_ok=True)
    return NasMcpConfig(
        db_path=tmp_path / "db.sqlite", audit_dir=tmp_path / "audit",
        roots={"vault": RootSpec("vault", vault, "read_write"),
               "home": RootSpec("home", home, "read_only"),
               "work": RootSpec("work", work, "read_only")},
        obsidian=NasObsidianConfig(vault_root=vault, backup_dir=tmp_path / "bk", support_dir=tmp_path / "sup",
                                   external_sources=external_sources))


def test_live_read_external_sources_derived_from_roots(tmp_path: Path) -> None:
    from hb_assistant.nas_mcp.obsidian_config import obsidian_config_from_nas

    ob = obsidian_config_from_nas(_nas_cfg_with_roots(tmp_path))
    keys = {r.source_root_key: r for r in ob.external_sources}
    assert set(keys) == {"syn-home", "syn-work"}
    assert keys["syn-work"].enabled is True and keys["syn-work"].sensitive is False  # live enabled
    assert keys["syn-work"].path.endswith("/roots/work")


def test_live_read_explicit_config_overrides_derivation(tmp_path: Path) -> None:
    from hb_assistant.nas_mcp.obsidian_config import obsidian_config_from_nas

    ext = ({"source_root_key": "syn-work", "path": str(tmp_path / "roots" / "work"), "sensitive": True},)
    ob = obsidian_config_from_nas(_nas_cfg_with_roots(tmp_path, external_sources=ext))
    keys = {r.source_root_key: r for r in ob.external_sources}
    assert set(keys) == {"syn-work"}  # only the explicit entry
    assert keys["syn-work"].sensitive is True  # operator kept it indexed-only


# ======================================================================================
# F. Freshness headline hardening (Defect 6)
# ======================================================================================
def test_freshness_recent_but_failed_is_degraded_not_ok() -> None:
    from hb_assistant.nas_mcp import freshness

    info = {"status": freshness.STATUS_OK, "last": "2026-07-08T00:00:00+00:00", "age_seconds": 30}
    out = freshness._apply_last_status(dict(info), "failed")
    assert out["status"] == freshness.STATUS_DEGRADED and out["last_status"] == "failed"


def test_freshness_recent_and_success_stays_ok() -> None:
    from hb_assistant.nas_mcp import freshness

    info = {"status": freshness.STATUS_OK, "last": "2026-07-08T00:00:00+00:00", "age_seconds": 30}
    out = freshness._apply_last_status(dict(info), "success")
    assert out["status"] == freshness.STATUS_OK and out["last_status"] == "success"


def test_freshness_future_anomaly_not_overridden_by_status() -> None:
    from hb_assistant.nas_mcp import freshness

    info = {"status": freshness.STATUS_FUTURE, "last": "2099-01-01T00:00:00+00:00", "age_seconds": -1000}
    out = freshness._apply_last_status(dict(info), "failed")
    assert out["status"] == freshness.STATUS_FUTURE  # anomaly wins; not downgraded to degraded
