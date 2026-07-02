"""Phase 10L-C: singleton folder-README upsert — in-place update, no sha suffix, marker-protected.

Proves the six folder READMEs are upserted by exact path (never ``README__<sha>.md``), an existing
generated README is updated in place (with backup), a manual README lacking the generated marker is
never overwritten, duplicate generated-README variants are reported count-only, and folder READMEs are
excluded from source-card indexing.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from hb_assistant.obsidian_mcp.source_indexer import is_email_archive_path, is_source_notes_path

_REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "obsidian_folder_readme_upsert", _REPO / "scripts" / "obsidian_folder_readme_upsert.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    for rel, *_ in _load()._TARGETS:
        (vault / Path(rel).parent).mkdir(parents=True, exist_ok=True)
    return vault


def test_dry_run_plans_create_and_apply_creates_singletons(tmp_path: Path) -> None:
    mod = _load()
    vault = _vault(tmp_path)
    assert mod.main(["--vault-path", str(vault)]) == 0  # dry-run: no writes
    for rel, *_ in mod._TARGETS:
        assert not (vault / rel).exists()

    rc = mod.main(["--vault-path", str(vault), "--apply", "--confirm-vault-path", str(vault),
                   "--backup-dir", str(tmp_path / "bak")])
    assert rc == 0
    for rel, *_ in mod._TARGETS:
        target = vault / rel
        assert target.is_file()
        assert mod.GENERATED_MARKER in target.read_text(encoding="utf-8")
        # No sha/id-suffixed README variant was created anywhere.
        assert not list(target.parent.glob("README__*.md"))


def test_update_in_place_with_backup_and_noop_second_run(tmp_path: Path) -> None:
    mod = _load()
    vault = _vault(tmp_path)
    target = vault / "Source Notes/Work/README.md"
    target.write_text(mod.GENERATED_MARKER + "\n# stale\n\nold body\n", encoding="utf-8")

    rc = mod.main(["--vault-path", str(vault), "--apply", "--confirm-vault-path", str(vault),
                   "--backup-dir", str(tmp_path / "bak")])
    assert rc == 0
    assert "old body" not in target.read_text(encoding="utf-8")
    assert (tmp_path / "bak" / "Source Notes/Work/README.md").is_file()  # backup captured
    # Second apply is a no-op (idempotent content).
    plan2 = mod.plan(vault)
    actions = {a["rel"]: a["action"] for a in plan2["actions"]}
    assert actions["Source Notes/Work/README.md"] == "noop"


def test_manual_readme_without_marker_is_protected(tmp_path: Path) -> None:
    mod = _load()
    vault = _vault(tmp_path)
    target = vault / "Source Notes/Home/README.md"
    target.write_text("# Hand-written\n\nBobby's notes — keep me.\n", encoding="utf-8")

    rc = mod.main(["--vault-path", str(vault), "--apply", "--confirm-vault-path", str(vault),
                   "--backup-dir", str(tmp_path / "bak")])
    assert rc == 0
    assert target.read_text(encoding="utf-8") == "# Hand-written\n\nBobby's notes — keep me.\n"
    actions = {a["rel"]: a["action"] for a in mod.plan(vault)["actions"]}
    assert actions["Source Notes/Home/README.md"] == "protected_manual"


def test_duplicate_generated_readme_variants_reported_countonly(tmp_path: Path) -> None:
    mod = _load()
    vault = _vault(tmp_path)
    folder = vault / "Source Notes/Work"
    (folder / "README__abcdef012345.md").write_text("dup card\n", encoding="utf-8")
    (folder / "README (1).md").write_text("dup copy\n", encoding="utf-8")
    plan = mod.plan(vault)
    dv = {d["folder_rel"]: d["variants"] for d in plan["duplicate_variants"]}
    assert set(dv["Source Notes/Work"]) == {"README__abcdef012345.md", "README (1).md"}
    summary = mod._safe_summary("dry_run", plan, {"created": 0, "updated": 0, "noop": 0,
                                                  "protected_skipped": 0})
    assert summary["duplicate_variant_total"] == 2


def test_apply_requires_backup_and_confirm(tmp_path: Path) -> None:
    mod = _load()
    vault = _vault(tmp_path)
    assert mod.main(["--vault-path", str(vault), "--apply", "--confirm-vault-path", str(vault)]) == 3
    assert mod.main(["--vault-path", str(vault), "--apply", "--confirm-vault-path", "/wrong",
                     "--backup-dir", str(tmp_path / "bak")]) == 3


def test_folder_readmes_excluded_from_source_card_indexing() -> None:
    config = SimpleNamespace(source_notes_folder="Source Notes")
    assert is_source_notes_path("Source Notes/Work/README.md", config)
    assert is_email_archive_path("Email Archive/Work/README.md")
