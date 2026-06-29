"""A1.9 — source path-exclusion hygiene (node_modules/.venv/dist/build/... never indexed or carded)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import (
    drain_queue,
    index_source_file,
    is_excluded_source_path,
)
from hb_assistant.obsidian_mcp.source_notes import generate_source_card, summarize_source
from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError
from hb_assistant.store.migrator import SQLiteMigrator

BID_PATH = ("25-244-01 WLP - Project Documents/10_Preconstruction/Estimating/"
            "05 Bid Packages/Commercial/Section 275 Bid Package 08-03 Glass Windows and Doors.docx")


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    cfg = tmp_path / "c.yml"
    cfg.write_text(
        f"paths:\n  application_support_root: {str(tmp_path / 'as')!r}\n  obsidian_vault: {vault.as_posix()!r}\n"
    )
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    root = tmp_path / "proj"
    (root / "22-101-00").mkdir(parents=True, exist_ok=True)
    config = ObsidianMcpConfig.model_validate({
        "enabled": True, "vault_root": str(vault), "writes_enabled": True,
        "vault_markdown_write_enabled": True,
        "external_sources": [{"source_root_key": "proj", "path": str(root), "enabled": True}],
    })
    return SourceIndexRepository(db), config, root, vault, db


def _write(root: Path, rel: str, body: str) -> Path:
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")
    return f


def test_helper_excludes_dependency_and_build_paths() -> None:
    config = ObsidianMcpConfig()
    for path in (
        "Apps/foo/node_modules/pkg/index.d.ts",
        ".venv/lib/python/site-packages/x.py",
        "frontend/dist/assets/app.js",
        "frontend/node_modules/react/index.js",
        "build/output/main.js",
        ".next/static/chunk.js",
        "a/__pycache__/m.pyc",
        "x/.pytest_cache/v/cache",
    ):
        assert is_excluded_source_path(path, config) is True, path


def test_helper_does_not_exclude_legitimate_paths() -> None:
    config = ObsidianMcpConfig()
    for path in (
        BID_PATH,
        "22-101-00/A-312-WALL-SECTIONS.pdf",
        "22-101-00/buildings-overview.pdf",   # 'build' is a substring, not a path segment
        "Projects/build.txt",                  # filename only
    ):
        assert is_excluded_source_path(path, config) is False, path


def test_rebuild_scan_skips_excluded_files(env) -> None:
    repo, config, root, _vault, _db = env
    _write(root, "Apps/web/node_modules/@x/icons/Icon.d.ts", "export const x: any;")
    _write(root, "22-101-00/scope.txt", "Project scope of work.")
    repo.enqueue_event(event_type="rebuild", source_root_key="proj")
    while drain_queue(repo, config) > 0:
        pass
    active = repo.active_rel_paths("proj")
    assert not any("node_modules" in p for p in active)
    assert any(p.endswith("scope.txt") for p in active)


def test_queued_excluded_event_is_skipped_without_card(env) -> None:
    repo, config, root, vault, db = env
    rel = "Apps/web/node_modules/@x/icons/Icon.d.ts"
    _write(root, rel, "export const x: any;")
    repo.enqueue_event(event_type="modified", rel_path=rel, source_root_key="proj")
    drain_queue(repo, config)
    rows = sqlite3.connect(db).execute(
        "SELECT status, error_code FROM source_intelligence_events WHERE event_type='modified'"
    ).fetchall()
    assert rows == [("skipped", "excluded_path")]
    # Not indexed and no card written.
    assert repo.lookup_by_path("external_file", rel) is None
    cards = list((vault / "Source Notes").rglob("*")) if (vault / "Source Notes").exists() else []
    assert [c for c in cards if c.is_file()] == []


def test_manual_generate_card_on_excluded_source_raises_and_writes_nothing(env) -> None:
    repo, config, root, vault, _db = env
    bad = _write(root, "Apps/web/node_modules/@x/icons/Icon.d.ts", "export const x: any;")
    # Force-index it (simulating a pre-hygiene indexed row), then attempt a manual card.
    sid = index_source_file(bad, config.external_sources[0], repo, config)
    with pytest.raises(ObsidianMcpToolError) as exc:
        generate_source_card(repo, config, source_id=sid, overwrite=True)
    assert exc.value.code == "source_excluded_path"
    assert not (vault / "Source Notes").exists() or not any(
        p.is_file() for p in (vault / "Source Notes").rglob("*")
    )


def test_manual_summarize_on_excluded_source_does_not_call_model(env) -> None:
    repo, config, root, _vault, _db = env
    bad = _write(root, "Apps/web/node_modules/@x/icons/Icon.d.ts", "export const x: any;")
    sid = index_source_file(bad, config.external_sources[0], repo, config)

    class _Spy:
        calls = 0

        def generate_json(self, *, system: str, prompt: str) -> str:
            _Spy.calls += 1
            return "{}"

    out = summarize_source(repo, config, source_id=sid, backend=_Spy())
    assert out["summarized"] is False
    assert out["reason"] == "excluded_path"
    assert _Spy.calls == 0
