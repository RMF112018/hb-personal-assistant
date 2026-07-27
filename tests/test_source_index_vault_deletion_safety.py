"""A1 — vault deletion-safety gate (Phase A).

The lightweight vault scanner (`scan_vault_notes`) must reconcile a deletion ONLY when it has
trustworthy evidence of absence: a certified-complete, untruncated, error-free, uninterrupted traversal
of an available vault root. A truncated / indeterminate / interrupted / empty-observed scan must preserve
every pre-existing active row (source row, its FTS row, and any generated-card state) and perform no
absence-based deletion.

These tests are the A1 prove-red set: they fail against the pre-fix `scan_vault_notes` (which reconciles
deletions unconditionally after a cap-hit `break` or a fail-open walk) and pass against the gated version.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.obsidian_mcp import source_indexer as si
from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import _VAULT_ROOT_KEY, scan_vault_notes
from hb_assistant.store.migrator import SQLiteMigrator


# --------------------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------------------
def _setup(tmp_path: Path, *, max_files: int = 5000):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)  # the autouse isolated_hb_pa_config fixture may pre-create this
    cfg = ObsidianMcpConfig.model_validate(
        {"enabled": True, "vault_root": str(vault), "external_source_scan_max_files": max_files}
    )
    repo = SourceIndexRepository(db)
    return db, vault, cfg, repo


def _note(vault: Path, rel: str, text: str = "# note") -> None:
    p = vault / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _fts_rowid_present(db: str, rowid: int | None) -> bool:
    if rowid is None:
        return False
    with sqlite3.connect(db) as c:
        n = c.execute("SELECT count(*) FROM obsidian_note_fts WHERE rowid=?", (rowid,)).fetchone()[
            0
        ]
    return bool(n)


def _seed_generated_card(db: str, source_id: str, rel_path: str) -> None:
    with sqlite3.connect(db) as c:
        c.execute(
            "INSERT INTO source_intelligence_generated_notes "
            "(generated_note_id, source_entity_id, note_rel_path, generation_status, generated_at, updated_at) "
            "VALUES (?,?,?,?,?,?)",
            (f"gn__{source_id}", source_id, rel_path, "generated", "2026-01-01", "2026-01-01"),
        )
        c.commit()


def _card_status(db: str, source_id: str) -> str | None:
    with sqlite3.connect(db) as c:
        row = c.execute(
            "SELECT generation_status FROM source_intelligence_generated_notes "
            "WHERE source_entity_id=?",
            (source_id,),
        ).fetchone()
    return row[0] if row else None


# --------------------------------------------------------------------------------------------------
# truncation / cap
# --------------------------------------------------------------------------------------------------
def test_vault_over_cap_does_not_delete_unseen_notes(tmp_path: Path) -> None:
    # index all 5 with a high cap, then rescan with a cap of 2 (truncates) — the 3 unseen notes must survive.
    db, vault, cfg, repo = _setup(tmp_path, max_files=5000)
    for i in range(5):
        _note(vault, f"n{i}.md")
    scan_vault_notes(repo, cfg)
    assert len(repo.active_rel_paths(_VAULT_ROOT_KEY)) == 5

    cfg_small = ObsidianMcpConfig.model_validate(
        {"enabled": True, "vault_root": str(vault), "external_source_scan_max_files": 2}
    )
    report = scan_vault_notes(repo, cfg_small)
    assert report.truncated is True
    assert report.deleted == 0
    assert len(repo.active_rel_paths(_VAULT_ROOT_KEY)) == 5


def test_vault_truncated_scan_does_not_delete(tmp_path: Path) -> None:
    db, vault, cfg, repo = _setup(tmp_path, max_files=5000)
    for i in range(4):
        _note(vault, f"n{i}.md")
    scan_vault_notes(repo, cfg)
    cfg_small = ObsidianMcpConfig.model_validate(
        {"enabled": True, "vault_root": str(vault), "external_source_scan_max_files": 1}
    )
    report = scan_vault_notes(repo, cfg_small)
    assert report.truncated is True
    assert report.completeness == "truncated"
    assert report.deletion_reconciliation_allowed is False
    assert report.deleted == 0
    assert len(repo.active_rel_paths(_VAULT_ROOT_KEY)) == 4


# --------------------------------------------------------------------------------------------------
# indeterminate traversal error
# --------------------------------------------------------------------------------------------------
def test_vault_directory_read_error_does_not_delete(tmp_path: Path, monkeypatch) -> None:
    db, vault, cfg, repo = _setup(tmp_path)
    for i in range(3):
        _note(vault, f"n{i}.md")
    scan_vault_notes(repo, cfg)
    assert len(repo.active_rel_paths(_VAULT_ROOT_KEY)) == 3

    real = si.walk_source_tree

    def fake_walk(root_path, config, *, want_dirs=False, error_sink=None):
        # Simulate an unreadable subtree: yield only n0/n1 (n2 lives under the unreadable subtree) and,
        # when the caller opts in to error reporting, record an indeterminate read so it can fail closed.
        if error_sink is not None:
            error_sink.append("redacted:depth=1")
        for kind, abs_path, rel_path in real(root_path, config, want_dirs=want_dirs):
            if rel_path == "n2.md":
                continue
            yield kind, abs_path, rel_path

    monkeypatch.setattr(si, "walk_source_tree", fake_walk)
    report = scan_vault_notes(repo, cfg)
    assert report.walk_error_count >= 1
    assert report.completeness == "walk_errors"
    assert report.deletion_reconciliation_allowed is False
    assert report.deleted == 0
    assert len(repo.active_rel_paths(_VAULT_ROOT_KEY)) == 3


# --------------------------------------------------------------------------------------------------
# root unavailable
# --------------------------------------------------------------------------------------------------
def test_vault_root_unavailable_does_not_delete(tmp_path: Path) -> None:
    db, vault, cfg, repo = _setup(tmp_path)
    for i in range(3):
        _note(vault, f"n{i}.md")
    scan_vault_notes(repo, cfg)
    assert len(repo.active_rel_paths(_VAULT_ROOT_KEY)) == 3

    missing = tmp_path / "gone-vault"
    cfg_missing = ObsidianMcpConfig.model_validate({"enabled": True, "vault_root": str(missing)})
    report = scan_vault_notes(repo, cfg_missing)
    assert report.root_available is False
    assert report.completeness == "root_unavailable"
    assert report.deleted == 0
    assert len(repo.active_rel_paths(_VAULT_ROOT_KEY)) == 3


# --------------------------------------------------------------------------------------------------
# interruption
# --------------------------------------------------------------------------------------------------
def test_vault_interrupted_scan_does_not_delete(tmp_path: Path, monkeypatch) -> None:
    db, vault, cfg, repo = _setup(tmp_path)
    for i in range(3):
        _note(vault, f"n{i}.md")
    scan_vault_notes(repo, cfg)

    real = si.walk_source_tree

    def fake_walk(root_path, config, *, want_dirs=False, error_sink=None):
        for item in real(root_path, config, want_dirs=want_dirs):
            yield item
            raise RuntimeError("scan interrupted mid-traversal")

    monkeypatch.setattr(si, "walk_source_tree", fake_walk)
    report = scan_vault_notes(repo, cfg)
    assert report.interrupted is True
    assert report.completeness == "interrupted"
    assert report.deleted == 0
    assert len(repo.active_rel_paths(_VAULT_ROOT_KEY)) == 3


# --------------------------------------------------------------------------------------------------
# per-file observation error
# --------------------------------------------------------------------------------------------------
def test_vault_per_file_error_does_not_delete(tmp_path: Path, monkeypatch) -> None:
    db, vault, cfg, repo = _setup(tmp_path)
    for name in ("a.md", "b.md", "c.md", "d.md"):
        _note(vault, name)
    scan_vault_notes(repo, cfg)
    # d genuinely removed; a modified so it is re-indexed (and made to raise a per-file error)
    (vault / "d.md").unlink()
    _note(vault, "a.md", "# changed content")

    real_index = si.index_obsidian_note

    def fake_index(abs_path, vault_root, repo_, config, **kw):
        if abs_path.name == "a.md":
            raise RuntimeError("stat/upsert failure on a.md")
        return real_index(abs_path, vault_root, repo_, config, **kw)

    monkeypatch.setattr(si, "index_obsidian_note", fake_index)
    report = scan_vault_notes(repo, cfg)
    assert report.per_file_error_count >= 1
    assert report.completeness == "file_errors"
    assert report.deletion_reconciliation_allowed is False
    assert report.deleted == 0
    # d was genuinely absent but the scan is uncertified, so it MUST be preserved.
    assert "d.md" in repo.active_rel_paths(_VAULT_ROOT_KEY)


# --------------------------------------------------------------------------------------------------
# legitimate complete-scan deletion + preservation
# --------------------------------------------------------------------------------------------------
def test_vault_complete_scan_deletes_confirmed_absent_note(tmp_path: Path) -> None:
    db, vault, cfg, repo = _setup(tmp_path)
    for name in ("a.md", "b.md", "c.md"):
        _note(vault, name)
    scan_vault_notes(repo, cfg)
    (vault / "b.md").unlink()
    report = scan_vault_notes(repo, cfg)
    assert report.completeness == "complete"
    assert report.deletion_reconciliation_allowed is True
    assert report.deleted == 1
    assert repo.active_rel_paths(_VAULT_ROOT_KEY) == {"a.md", "c.md"}


def test_vault_complete_scan_preserves_present_notes(tmp_path: Path) -> None:
    db, vault, cfg, repo = _setup(tmp_path)
    for name in ("a.md", "b.md", "c.md"):
        _note(vault, name)
    scan_vault_notes(repo, cfg)
    report = scan_vault_notes(repo, cfg)
    assert report.deleted == 0
    assert repo.active_rel_paths(_VAULT_ROOT_KEY) == {"a.md", "b.md", "c.md"}


# --------------------------------------------------------------------------------------------------
# uncertified scan leaves FTS + generated-card state intact
# --------------------------------------------------------------------------------------------------
def test_vault_false_delete_does_not_remove_fts(tmp_path: Path) -> None:
    db, vault, cfg, repo = _setup(tmp_path, max_files=5000)
    for i in range(4):
        _note(vault, f"n{i}.md")
    scan_vault_notes(repo, cfg)
    row = repo.lookup_by_path("obsidian_note", "n3.md")
    assert row is not None and _fts_rowid_present(db, row["fts_rowid"])

    cfg_small = ObsidianMcpConfig.model_validate(
        {"enabled": True, "vault_root": str(vault), "external_source_scan_max_files": 1}
    )
    scan_vault_notes(repo, cfg_small)
    row_after = repo.lookup_by_path("obsidian_note", "n3.md")
    assert row_after is not None and row_after["deleted"] is False
    assert _fts_rowid_present(db, row_after["fts_rowid"])


def test_vault_false_delete_does_not_stale_generated_card(tmp_path: Path) -> None:
    db, vault, cfg, repo = _setup(tmp_path, max_files=5000)
    for i in range(4):
        _note(vault, f"n{i}.md")
    scan_vault_notes(repo, cfg)
    sid = repo.lookup_by_path("obsidian_note", "n3.md")["source_id"]
    _seed_generated_card(db, sid, "Source Notes/n3.md")
    assert _card_status(db, sid) == "generated"

    cfg_small = ObsidianMcpConfig.model_validate(
        {"enabled": True, "vault_root": str(vault), "external_source_scan_max_files": 1}
    )
    scan_vault_notes(repo, cfg_small)
    assert _card_status(db, sid) == "generated"


def test_vault_confirmed_delete_updates_source_fts_and_card_state_atomically(
    tmp_path: Path,
) -> None:
    db, vault, cfg, repo = _setup(tmp_path)
    for name in ("a.md", "b.md"):
        _note(vault, name)
    scan_vault_notes(repo, cfg)
    b = repo.lookup_by_path("obsidian_note", "b.md")
    sid = b["source_id"]
    _seed_generated_card(db, sid, "Source Notes/b.md")
    assert _fts_rowid_present(db, b["fts_rowid"])

    (vault / "b.md").unlink()
    report = scan_vault_notes(repo, cfg)
    assert report.deleted == 1
    b_after = repo.get_source_detail(sid)
    # all three side-effects applied consistently: source deactivated, FTS row gone, card staled
    assert b_after["deleted"] is True
    assert not _fts_rowid_present(db, b["fts_rowid"])
    assert _card_status(db, sid) == "stale"


# --------------------------------------------------------------------------------------------------
# streaming + idempotency
# --------------------------------------------------------------------------------------------------
def test_vault_scan_remains_streaming_and_prunes_excluded_subtrees(tmp_path: Path) -> None:
    db, vault, cfg, repo = _setup(tmp_path)
    _note(vault, "Projects/Scope.md", "# scope")
    for pruned in (".git", "node_modules", "node_modules/deep"):
        (vault / pruned).mkdir(parents=True, exist_ok=True)
        (vault / pruned / "buried.md").write_text("# buried", encoding="utf-8")
    report = scan_vault_notes(repo, cfg)
    active = repo.active_rel_paths(_VAULT_ROOT_KEY)
    assert active == {"Projects/Scope.md"}
    assert report.indexed == 1
    assert not any(".git" in p or "node_modules" in p for p in active)


def test_vault_scan_is_idempotent_after_resume_or_retry(tmp_path: Path) -> None:
    db, vault, cfg, repo = _setup(tmp_path)
    for name in ("a.md", "b.md", "c.md"):
        _note(vault, name)
    scan_vault_notes(repo, cfg)
    r2 = scan_vault_notes(repo, cfg)
    assert r2.deleted == 0
    assert r2.indexed == 0
    assert repo.active_rel_paths(_VAULT_ROOT_KEY) == {"a.md", "b.md", "c.md"}


# --------------------------------------------------------------------------------------------------
# empty-root blast-radius guard + one-shot self-scanning recovery
# --------------------------------------------------------------------------------------------------
def test_vault_empty_completed_scan_blocks_mass_delete(tmp_path: Path) -> None:
    db, vault, cfg, repo = _setup(tmp_path)
    for name in ("a.md", "b.md", "c.md"):
        _note(vault, name)
    scan_vault_notes(repo, cfg)
    for name in ("a.md", "b.md", "c.md"):
        (vault / name).unlink()  # vault now scans as empty but the mount is present

    report = scan_vault_notes(repo, cfg)
    assert report.eligible_files_seen == 0
    assert report.active_rows_before_scan == 3
    assert report.completeness == "empty_root_guard"
    assert report.deletion_reconciliation_allowed is False
    assert report.deleted == 0
    assert len(repo.active_rel_paths(_VAULT_ROOT_KEY)) == 3


def test_vault_confirmed_empty_recovery_requires_fresh_selfscan(tmp_path: Path) -> None:
    db, vault, cfg, repo = _setup(tmp_path)
    for name in ("a.md", "b.md", "c.md"):
        _note(vault, name)
    scan_vault_notes(repo, cfg)
    for name in ("a.md", "b.md", "c.md"):
        (vault / name).unlink()

    # default: blocked
    blocked = scan_vault_notes(repo, cfg)
    assert blocked.completeness == "empty_root_guard"
    assert len(repo.active_rel_paths(_VAULT_ROOT_KEY)) == 3

    # explicit one-shot recovery: performs its own certified-complete empty scan, then reconciles
    recovered = scan_vault_notes(repo, cfg, allow_confirmed_empty_recovery=True)
    assert recovered.completeness == "complete"
    assert recovered.deleted == 3
    assert repo.active_rel_paths(_VAULT_ROOT_KEY) == set()


def test_vault_recovery_still_requires_certified_scan(tmp_path: Path, monkeypatch) -> None:
    # Recovery must not delete when its own fresh scan is uncertified (e.g. an indeterminate read).
    db, vault, cfg, repo = _setup(tmp_path)
    for name in ("a.md", "b.md", "c.md"):
        _note(vault, name)
    scan_vault_notes(repo, cfg)
    for name in ("a.md", "b.md", "c.md"):
        (vault / name).unlink()

    def fake_walk(root_path, config, *, want_dirs=False, error_sink=None):
        if error_sink is not None:
            error_sink.append("redacted:depth=1")
        return iter(())

    monkeypatch.setattr(si, "walk_source_tree", fake_walk)
    report = scan_vault_notes(repo, cfg, allow_confirmed_empty_recovery=True)
    assert report.completeness == "walk_errors"
    assert report.deleted == 0
    assert len(repo.active_rel_paths(_VAULT_ROOT_KEY)) == 3


# --------------------------------------------------------------------------------------------------
# operator recovery CLI (local, operator-only, no remote MCP exposure)
# --------------------------------------------------------------------------------------------------
def test_vault_reconcile_cli_requires_both_flags(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from hb_assistant.cli.source_watch import app

    runner = CliRunner()
    # missing both flags
    r0 = runner.invoke(app, ["vault-reconcile", "--db", str(tmp_path / "x.sqlite")])
    assert r0.exit_code == 2 and "requires BOTH" in r0.stdout
    # only one of the two flags
    r1 = runner.invoke(
        app, ["vault-reconcile", "--allow-confirmed-empty", "--db", str(tmp_path / "x.sqlite")]
    )
    assert r1.exit_code == 2


def test_vault_reconcile_cli_recovers_empty_vault_and_writes_receipt(
    tmp_path: Path, monkeypatch
) -> None:
    from typer.testing import CliRunner

    import hb_assistant.cli.source_watch as cli_sw
    from hb_assistant.cli.source_watch import app

    db, vault, cfg, repo = _setup(tmp_path)
    for name in ("a.md", "b.md", "c.md"):
        _note(vault, name)
    scan_vault_notes(repo, cfg)
    for name in ("a.md", "b.md", "c.md"):
        (vault / name).unlink()

    monkeypatch.setattr(cli_sw, "_obsidian_config", lambda: cfg)
    runner = CliRunner()
    res = runner.invoke(
        app, ["vault-reconcile", "--allow-confirmed-empty", "--confirm", "--db", db]
    )
    assert res.exit_code == 0
    assert repo.active_rel_paths(_VAULT_ROOT_KEY) == set()
    # an audit receipt was written locally
    receipts = list((Path(db).parent / "vault_reconcile_receipts").glob("*.json"))
    assert len(receipts) == 1


def test_vault_reconcile_cli_lease_is_os_backed_and_exclusive(tmp_path: Path, monkeypatch) -> None:
    # The recovery lease must be an OS-backed file lock shared across independent open descriptors
    # (fcntl.flock), not an in-memory mutex: a lock held on the same path via a DIFFERENT fd blocks the
    # command's non-blocking acquisition and it must fail closed.
    import fcntl
    import os

    from typer.testing import CliRunner

    import hb_assistant.cli.source_watch as cli_sw
    from hb_assistant.cli.source_watch import app

    db, vault, cfg, repo = _setup(tmp_path)
    monkeypatch.setattr(cli_sw, "_obsidian_config", lambda: cfg)
    op_dir = Path(db).parent
    op_dir.mkdir(parents=True, exist_ok=True)
    held_fd = os.open(str(op_dir / "vault_reconcile.lock"), os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(held_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        res = CliRunner().invoke(
            app, ["vault-reconcile", "--allow-confirmed-empty", "--confirm", "--db", db]
        )
        assert res.exit_code == 2
        assert "holds the local lease" in res.stdout
    finally:
        fcntl.flock(held_fd, fcntl.LOCK_UN)
        os.close(held_fd)
