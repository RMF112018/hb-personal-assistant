"""pa_artifact_author — template-based vault-markdown artifact creation (no DB records).

Proves the operator directive: structured-intelligence artifacts are created by instantiating a
vault-resident template into the resolved taxonomy folder (not free-rendered, not DB rows). Built against
a temp vault seeded with the real templates (``scripts/seed_obsidian_work_home_vault.py``) and a migrated
temp DB — never the real vault or prod snapshot.
"""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.nas_mcp.artifact_template_registry import (
    SUPPORTED_ARTIFACT_TYPES,
    ArtifactTemplateError,
    resolve_template,
)
from hb_assistant.nas_mcp.artifact_tools import PA_CANONICAL_WRITE_TOOLS, dispatch_artifact_tool
from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec
from hb_assistant.store.migrator import SQLiteMigrator

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _seed_templates(vault: Path) -> int:
    spec = importlib.util.spec_from_file_location(
        "seed_vault", _REPO_ROOT / "scripts" / "seed_obsidian_work_home_vault.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    n = 0
    for rel, content in mod.seed_files().items():
        p = vault / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        n += 1 if rel.startswith("Templates/") else 0
    return n


@pytest.fixture()
def env(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    _seed_templates(vault)
    db = tmp_path / "db" / "x.sqlite"
    db.parent.mkdir(exist_ok=True)
    SQLiteMigrator(db_path=str(db)).apply()
    support = tmp_path / "sup"
    config = NasMcpConfig(
        db_path=db,
        audit_dir=tmp_path / "audit",
        roots={"vault": RootSpec("vault", vault, "read_write")},
        obsidian=NasObsidianConfig(vault_root=vault, backup_dir=tmp_path / "bk", support_dir=support),
    )
    # ``md_config`` -> ``apply_obsidian_support_env`` sets HB_OBSIDIAN_MCP_SUPPORT_DIR via os.environ;
    # pin it through monkeypatch so the mutation-receipt store stays isolated and reverts after the test.
    monkeypatch.setenv("HB_OBSIDIAN_MCP_SUPPORT_DIR", str(support))
    return {"config": config, "vault": vault, "db": db}


def _author(env, **kw):
    return dispatch_artifact_tool(env["config"], "pa_artifact_author", kw)


def test_author_instantiates_template_into_taxonomy(env):
    r = _author(env, artifact_type="decision", title="Adopt read-only opener", domain="work",
                source_client="chatgpt", sections={"Decision": "Open immutable RO.", "Context": "RO mount."})
    assert r["status"] == "written"
    assert r["relative_path"].startswith("Work/03 Decisions/")
    assert r["template_path"] == "Templates/Decisions/decision-log-template.md"
    assert r["sha256"]
    body = (env["vault"] / r["relative_path"]).read_text(encoding="utf-8")
    # Template-based: the decision heading + section scaffold come from the template, filled with content.
    assert "# Decision: Adopt read-only opener" in body
    assert "Open immutable RO." in body and "RO mount." in body
    # Single merged frontmatter (template note_type + canonical fields), managed marker stripped.
    assert body.count("\n---") == 1
    assert "hb-managed" not in body
    assert "note_type: decision" in body and "artifact_type: decision" in body
    assert "source/chatgpt" in body


def test_author_writes_no_db_rows(env):
    with sqlite3.connect(env["db"]) as c:
        before = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        counts_before = {t: c.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
                         for t in before if t.startswith("pa_")}
    _author(env, artifact_type="person_note", title="Jane Roe", domain="work", source_client="claude")
    with sqlite3.connect(env["db"]) as c:
        counts_after = {t: c.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
                        for t in before if t.startswith("pa_")}
    assert counts_before == counts_after, "pa_artifact_author must not write DB rows"


def test_every_supported_type_has_a_template_and_route(env):
    for at in SUPPORTED_ARTIFACT_TYPES:
        r = _author(env, artifact_type=at, title=f"T {at}", domain="work", source_client="grok")
        assert r["status"] == "written"
        assert (env["vault"] / r["relative_path"]).exists()


def test_unknown_type_fails_closed(env):
    with pytest.raises(ArtifactTemplateError):
        _author(env, artifact_type="preference", title="No template", domain="work")
    # nothing under a taxonomy folder for the unmapped type
    with pytest.raises(ArtifactTemplateError):
        resolve_template("open_loop", "work")


def test_oversize_content_fails_closed(env):
    from hb_assistant.obsidian_mcp.artifact_workspace import ArtifactWorkspaceError
    huge = "x" * 300_000
    with pytest.raises(ArtifactWorkspaceError):
        _author(env, artifact_type="decision", title="Big", domain="work", sections={"Decision": huge})


def test_no_overwrite_on_duplicate(env):
    _author(env, artifact_type="decision", title="Same Title", domain="work", source_client="chatgpt")
    with pytest.raises(Exception):  # noqa: B017 — create_note fails closed (note_already_exists)
        _author(env, artifact_type="decision", title="Same Title", domain="work", source_client="chatgpt")


def test_classified_as_canonical_write():
    assert "pa_artifact_author" in PA_CANONICAL_WRITE_TOOLS


def test_denied_under_safe_mode(env, monkeypatch):
    # Safe mode denies writes at the broker; pa_artifact_author is a canonical write so it must be denied.
    from hb_assistant.nas_mcp.broker import NasMcpBroker
    monkeypatch.setenv("HB_MCP_SAFE_MODE", "1")
    broker = NasMcpBroker(env["config"])
    res = broker.dispatch("pa_artifact_author",
                          {"artifact_type": "decision", "title": "Blocked", "domain": "work"})
    assert res["ok"] is False
    assert "safe_mode" in (res.get("deny_reason") or res.get("error") or "")
