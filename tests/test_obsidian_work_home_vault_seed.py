"""Work/Home vault seed script: dry-run safety, idempotency, marker-gated overwrite, frontmatter.

All tests use TEMP vault paths (never the production vault) with --allow-nonstandard-vault-path.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "seed_obsidian_work_home_vault.py"
_spec = importlib.util.spec_from_file_location("seed_obsidian_work_home_vault", _SCRIPT)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

_REQUIRED = [
    "README.md",
    "Work/00 Dashboard/Work Dashboard.md",
    "Home/00 Dashboard/Home Dashboard.md",
    "MOCs/Work/Work MOC.md",
    "MOCs/Home/Home MOC.md",
    "MOCs/Shared/Shared MOC.md",
    "Templates/Source Cards/source-card-template.md",
    "Templates/Projects/work-project-template.md",
    "Templates/Projects/home-project-template.md",
    "Templates/Meetings/work-meeting-template.md",
    "Templates/Meetings/home-meeting-template.md",
    "Templates/Decisions/decision-log-template.md",
    "Templates/Daily/work-daily-template.md",
    "Templates/Daily/home-daily-template.md",
    "Templates/People/person-template.md",
    "Templates/Companies/company-template.md",
    "Source Notes/Work/README.md",
    "Source Notes/Home/README.md",
    "Source Notes/Shared/README.md",
]


def _vault(tmp_path: Path) -> Path:
    v = tmp_path / "Obsidian Vault"
    v.mkdir()
    return v


def test_dry_run_changes_nothing(tmp_path: Path) -> None:
    v = _vault(tmp_path)
    rc = mod.main(["--vault-path", str(v), "--evidence-dir", str(tmp_path / "ev"),
                   "--allow-nonstandard-vault-path"])
    assert rc == 0
    # Nothing written.
    assert list(v.iterdir()) == []
    plan = json.loads((tmp_path / "ev" / "seed-plan-dry_run.json").read_text())
    assert plan["mode"] == "dry_run"
    assert plan["create_count"] == plan["total_seed_files"] > 0
    assert plan["written_count"] == 0


def test_apply_creates_required_files(tmp_path: Path) -> None:
    v = _vault(tmp_path)
    rc = mod.main(["--vault-path", str(v), "--apply", "--allow-nonstandard-vault-path"])
    assert rc == 0
    for rel in _REQUIRED:
        assert (v / rel).is_file(), rel


def test_unsafe_paths_refused(tmp_path: Path) -> None:
    for bad in ("/", str(Path.home()), str(Path.home() / "Documents"), ""):
        rc = mod.main(["--vault-path", bad, "--allow-nonstandard-vault-path"])
        assert rc == 3, bad


def test_user_authored_files_not_overwritten(tmp_path: Path) -> None:
    v = _vault(tmp_path)
    (v / "Work" / "00 Dashboard").mkdir(parents=True)
    user = v / "Work" / "00 Dashboard" / "Work Dashboard.md"
    user.write_text("# My own dashboard\nhand written", encoding="utf-8")  # no managed marker
    mod.main(["--vault-path", str(v), "--apply", "--allow-nonstandard-vault-path"])
    assert user.read_text() == "# My own dashboard\nhand written"  # untouched


def test_managed_overwrite_only_with_flag(tmp_path: Path) -> None:
    v = _vault(tmp_path)
    mod.main(["--vault-path", str(v), "--apply", "--allow-nonstandard-vault-path"])
    moc = v / "MOCs" / "Work" / "Work MOC.md"
    assert mod.MANAGED_MARKER in moc.read_text()
    moc.write_text(mod.MANAGED_MARKER + "\n# edited managed\n", encoding="utf-8")
    # Without the flag, a managed file is preserved.
    mod.main(["--vault-path", str(v), "--apply", "--allow-nonstandard-vault-path"])
    assert "edited managed" in moc.read_text()
    # With the flag, it is re-seeded.
    mod.main(["--vault-path", str(v), "--apply", "--overwrite-generated", "--allow-nonstandard-vault-path"])
    assert "edited managed" not in moc.read_text()
    assert "Work MOC" in moc.read_text()


def test_only_markdown_files_created(tmp_path: Path) -> None:
    v = _vault(tmp_path)
    mod.main(["--vault-path", str(v), "--apply", "--allow-nonstandard-vault-path"])
    non_md = [p for p in v.rglob("*") if p.is_file() and p.suffix != ".md"]
    assert non_md == [], non_md
    # Every declared seed file is a .md file.
    assert all(rel.endswith(".md") for rel in mod.seed_files())


def test_work_home_frontmatter_present(tmp_path: Path) -> None:
    v = _vault(tmp_path)
    mod.main(["--vault-path", str(v), "--apply", "--allow-nonstandard-vault-path"])
    wp = (v / "Templates/Projects/work-project-template.md").read_text()
    assert "note_type: work_project" in wp and "domain: work" in wp and "- work/project" in wp
    hp = (v / "Templates/Projects/home-project-template.md").read_text()
    assert "note_type: home_project" in hp and "domain: home" in hp and "- home/project" in hp


def test_source_card_template_has_source_metadata(tmp_path: Path) -> None:
    v = _vault(tmp_path)
    mod.main(["--vault-path", str(v), "--apply", "--allow-nonstandard-vault-path"])
    card = (v / "Templates/Source Cards/source-card-template.md").read_text()
    for field in ("note_type: source_card", "source_id:", "source_sha256:", "source_root_key:",
                  "document_type:", "review_status: unreviewed", 'template_version: "source-card-v1"'):
        assert field in card, field


def test_source_notes_domain_readmes_exist(tmp_path: Path) -> None:
    v = _vault(tmp_path)
    mod.main(["--vault-path", str(v), "--apply", "--allow-nonstandard-vault-path"])
    for d in ("Work", "Home", "Shared"):
        assert (v / "Source Notes" / d / "README.md").is_file()


def test_no_external_root_write_targets(tmp_path: Path) -> None:
    """Every seed target is vault-relative; none reference an external/absolute path."""
    for rel in mod.seed_files():
        assert not rel.startswith("/")
        assert "CloudStorage" not in rel and "OneDrive" not in rel and "Synology" not in rel
        assert ".." not in Path(rel).parts
