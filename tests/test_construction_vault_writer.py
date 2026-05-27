"""Tests for the Obsidian construction-vault writer (Phase 01 Step 6)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from typer.testing import CliRunner

from hb_assistant.cli import construction as construction_cli
from hb_assistant.construction.manifests import (
    ConstructionVaultWriter,
    DocumentCardPolicyError,
    ManifestRenderer,
    ManifestService,
    VaultRootNotConfigured,
)
from hb_assistant.construction.manifests.vault_writer import (
    ENV_VAR,
    _atomic_write_text,
)
from hb_assistant.construction.store import ConstructionStore

# ---------- fixtures ----------------------------------------------------


@pytest.fixture
def vault_root(tmp_path: Path) -> Path:
    root = tmp_path / "construction-vault"
    return root


@pytest.fixture
def populated_store(tmp_path: Path) -> ConstructionStore:
    db = str(tmp_path / "c.sqlite")
    store = ConstructionStore(db)
    store.upsert_resolution(
        source_key="tropical-sharepoint",
        kind="sharepoint_site",
        site_id="contoso.sharepoint.com,site-1",
        drive_id="b!drive-1",
        web_url="https://contoso.sharepoint.com/sites/Tropical",
        resolution_status="resolved",
    )
    store.upsert_inventory_item(
        source_key="tropical-sharepoint",
        drive_id="b!drive-1",
        item_id="item-1",
        name="design.pdf",
        web_url="https://x/item-1",
        parent_path="/drives/b!drive-1/root:/Project",
        size_bytes=2048,
        is_folder=False,
        last_modified="2026-05-20T10:00:00Z",
        etag="etag-1",
    )
    return store


# ---------- vault root resolution precedence ----------------------------


def test_ctor_arg_takes_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV_VAR, str(tmp_path / "env-root"))
    explicit = tmp_path / "explicit"
    w = ConstructionVaultWriter(vault_root=explicit)
    assert w.root == explicit


def test_env_var_used_when_no_ctor_arg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_root = tmp_path / "env-root"
    monkeypatch.setenv(ENV_VAR, str(env_root))
    w = ConstructionVaultWriter()
    assert w.root == env_root


def test_config_used_when_env_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ENV_VAR, raising=False)
    cfg_root = tmp_path / "cfg-root"

    fake_cfg = type("PFake", (), {})()
    fake_cfg.paths = type("X", (), {"construction_vault_root": str(cfg_root)})()

    def fake_load_config() -> object:
        return fake_cfg

    with patch(
        "hb_assistant.construction.manifests.vault_writer._resolve_root_from_config",
        return_value=str(cfg_root),
    ):
        w = ConstructionVaultWriter()
    assert w.root == cfg_root


def test_unset_raises_on_apply(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_VAR, raising=False)
    with patch(
        "hb_assistant.construction.manifests.vault_writer._resolve_root_from_config",
        return_value=None,
    ):
        w = ConstructionVaultWriter()
        assert w.configured is False
        with pytest.raises(VaultRootNotConfigured):
            w.write_registry_overview(rendered="hello")


# ---------- bootstrap ---------------------------------------------------


def test_bootstrap_dry_run_lists_seven_subdirs(vault_root: Path) -> None:
    w = ConstructionVaultWriter(vault_root=vault_root)
    results = w.bootstrap_folders(dry_run=True)
    subdirs = {r.subdir for r in results}
    expected = {
        "00_Registry", "01_Projects", "02_Review_Queue", "03_Document_Cards",
        "10_Source_Manifests", "11_Sync_Receipts", "12_Processing_Receipts",
    }
    assert subdirs == expected
    for r in results:
        assert r.created is False
        assert r.existed_before is False
        assert not r.path.exists()


def test_bootstrap_apply_creates_all_subdirs_idempotently(vault_root: Path) -> None:
    w = ConstructionVaultWriter(vault_root=vault_root)
    r1 = w.bootstrap_folders(dry_run=False)
    assert all(r.created for r in r1)
    for r in r1:
        assert r.path.is_dir()

    r2 = w.bootstrap_folders(dry_run=False)
    assert all(r.created is False for r in r2)
    assert all(r.existed_before is True for r in r2)


# ---------- atomic write -----------------------------------------------


def test_atomic_write_failure_preserves_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "x.md"
    target.write_text("ORIGINAL CONTENTS\n", encoding="utf-8")

    with patch(
        "hb_assistant.construction.manifests.vault_writer.os.replace",
        side_effect=OSError("simulated failure"),
    ), pytest.raises(OSError):
        _atomic_write_text(target, "NEW CONTENTS\n")

    assert target.read_text(encoding="utf-8") == "ORIGINAL CONTENTS\n"
    leftover = list(tmp_path.glob(".x.md.*.tmp"))
    assert leftover == [], "temp file must be cleaned up on failure"


def test_atomic_write_success_replaces_atomically(tmp_path: Path) -> None:
    target = tmp_path / "y.md"
    target.write_text("OLD\n", encoding="utf-8")
    n = _atomic_write_text(target, "NEW CONTENTS\n")
    assert target.read_text(encoding="utf-8") == "NEW CONTENTS\n"
    assert n == len(b"NEW CONTENTS\n")
    leftover = list(tmp_path.glob(".y.md.*.tmp"))
    assert leftover == []


# ---------- frontmatter -------------------------------------------------


def _split_frontmatter(text: str) -> dict:
    assert text.startswith("---\n"), "expected leading YAML frontmatter"
    end = text.index("\n---\n", 4)
    return yaml.safe_load(text[4:end])


def test_registry_overview_frontmatter_is_valid(populated_store: ConstructionStore) -> None:
    from hb_assistant.construction.config import load_source_registry
    reg = load_source_registry()
    svc = ManifestService(populated_store)
    overview = svc.build_registry_overview(reg)
    rendered = ManifestRenderer.render_registry_overview(overview)
    fm = _split_frontmatter(rendered)
    assert fm["type"] == "construction-registry-overview"
    assert fm["domain"] == "construction"
    assert "owner" in fm
    assert "generated" in fm
    assert isinstance(fm["tags"], list)


def test_project_card_frontmatter_is_valid(populated_store: ConstructionStore) -> None:
    from hb_assistant.construction.config import load_source_registry
    reg = load_source_registry()
    svc = ManifestService(populated_store)
    card = svc.build_project_card(reg, "tropical")
    rendered = ManifestRenderer.render_project_card(card)
    fm = _split_frontmatter(rendered)
    assert fm["type"] == "construction-project-card"
    assert fm["project_key"] == "tropical"
    assert fm["domain"] == "construction"


# ---------- no-full-text policy -----------------------------------------


@pytest.mark.parametrize("kind", ["registry", "project", "review", "document"])
def test_render_never_carries_body_or_text_fields(
    populated_store: ConstructionStore, kind: str,
) -> None:
    from hb_assistant.construction.config import load_source_registry
    reg = load_source_registry()
    svc = ManifestService(populated_store)
    if kind == "registry":
        rendered = ManifestRenderer.render_registry_overview(svc.build_registry_overview(reg))
    elif kind == "project":
        rendered = ManifestRenderer.render_project_card(svc.build_project_card(reg, "tropical"))
    elif kind == "review":
        rendered = ManifestRenderer.render_review_required(svc.build_review_required_note())
    else:
        src = next(s for s in reg.sources if s.source_key == "tropical-sharepoint")
        rendered = ManifestRenderer.render_document_card(
            svc.build_document_card(source=src, item_id="item-1", policy_reason="manual review"),
        )
    forbidden = ["body:", "content:", "text:", "excerpt:", "full_text:"]
    lower = rendered.lower()
    for needle in forbidden:
        assert needle not in lower


# ---------- document card policy ---------------------------------------


def test_document_card_requires_non_empty_policy_reason(
    populated_store: ConstructionStore,
) -> None:
    from hb_assistant.construction.config import load_source_registry
    reg = load_source_registry()
    src = next(s for s in reg.sources if s.source_key == "tropical-sharepoint")
    svc = ManifestService(populated_store)
    with pytest.raises(DocumentCardPolicyError):
        svc.build_document_card(source=src, item_id="item-1", policy_reason="")
    with pytest.raises(DocumentCardPolicyError):
        svc.build_document_card(source=src, item_id="item-1", policy_reason="   ")


def test_document_card_requires_known_item(populated_store: ConstructionStore) -> None:
    from hb_assistant.construction.config import load_source_registry
    reg = load_source_registry()
    src = next(s for s in reg.sources if s.source_key == "tropical-sharepoint")
    svc = ManifestService(populated_store)
    with pytest.raises(ValueError):
        svc.build_document_card(source=src, item_id="missing", policy_reason="manual review")


# ---------- marker-bounded re-runs --------------------------------------


def test_registry_overview_marker_bounded_preserves_user_text(vault_root: Path) -> None:
    w = ConstructionVaultWriter(vault_root=vault_root)
    target = w.registry_overview_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# My personal note\n\nstay here.\n", encoding="utf-8")
    w.write_registry_overview(rendered="GEN_V1")
    after_v1 = target.read_text(encoding="utf-8")
    assert "stay here." in after_v1 and "GEN_V1" in after_v1
    w.write_registry_overview(rendered="GEN_V2")
    after_v2 = target.read_text(encoding="utf-8")
    assert "stay here." in after_v2
    assert "GEN_V2" in after_v2 and "GEN_V1" not in after_v2


def test_project_card_marker_bounded(vault_root: Path) -> None:
    w = ConstructionVaultWriter(vault_root=vault_root)
    target = w.project_card_path("tropical")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("user content above\n", encoding="utf-8")
    w.write_project_card(project_key="tropical", rendered="PCARD V1")
    assert "user content above" in target.read_text(encoding="utf-8")


# ---------- service aggregation -----------------------------------------


def test_project_card_aggregates_totals(populated_store: ConstructionStore) -> None:
    from hb_assistant.construction.config import load_source_registry
    reg = load_source_registry()
    svc = ManifestService(populated_store)
    card = svc.build_project_card(reg, "tropical")
    assert card.totals == {"active": 1}
    # The tropical project now has both the Phase 01 legacy source
    # (tropical-sharepoint) and the Phase 02 canonical source
    # (sp_2023projects_23_435_01_tropical_sl) attached.
    assert "tropical-sharepoint" in card.source_keys
    assert "sp_2023projects_23_435_01_tropical_sl" in card.source_keys
    assert card.source_count == 2


def test_registry_overview_lists_unresolved(populated_store: ConstructionStore) -> None:
    from hb_assistant.construction.config import load_source_registry
    reg = load_source_registry()
    svc = ManifestService(populated_store)
    overview = svc.build_registry_overview(reg)
    assert "hilltop-sharepoint" in overview.unresolved_sources
    assert "bobby-onedrive" in overview.unresolved_sources
    assert "tropical-sharepoint" not in overview.unresolved_sources


def test_review_required_empty_state(populated_store: ConstructionStore) -> None:
    svc = ManifestService(populated_store)
    note = svc.build_review_required_note()
    rendered = ManifestRenderer.render_review_required(note)
    assert "no items currently flagged for review" in rendered


# ---------- CLI ---------------------------------------------------------


def test_cli_vault_bootstrap_dry_run_lists_seven(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv(ENV_VAR, str(tmp_path / "v"))
    runner = CliRunner()
    result = runner.invoke(construction_cli.app, ["vault", "bootstrap", "--dry-run", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["mode"] == "dry_run"
    assert len(payload["subdirs"]) == 7


def test_cli_vault_bootstrap_apply_creates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    root = tmp_path / "v"
    monkeypatch.setenv(ENV_VAR, str(root))
    runner = CliRunner()
    result = runner.invoke(construction_cli.app, ["vault", "bootstrap", "--apply", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["mode"] == "apply"
    for sub in payload["subdirs"]:
        assert Path(sub["path"]).is_dir()


def test_cli_vault_preview_dry_run_renders_all_default_kinds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    result = runner.invoke(construction_cli.app, ["vault", "preview", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["mode"] == "dry_run"
    assert payload["registry_overview"]["project_count"] >= 2
    assert "tropical" in payload["project_cards"]
    assert payload["review_required"] is not None
    assert payload["document_card"] is None
    assert payload["written"] == []
    assert payload["rendered"]["registry_overview_md"].startswith("---\n")
    assert payload["guardrails"]["document_card_policy"] == "opt_in_only"


def test_cli_vault_preview_apply_writes_expected_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    root = tmp_path / "v"
    monkeypatch.setenv(ENV_VAR, str(root))
    runner = CliRunner()
    result = runner.invoke(
        construction_cli.app,
        ["vault", "preview", "--apply", "--no-include-review-required", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    kinds = {w["kind"] for w in payload["written"]}
    # at minimum registry_overview + project cards
    assert "registry_overview" in kinds
    assert "project_card" in kinds
    assert "document_card" not in kinds
    # files actually exist
    assert (root / "00_Registry" / "registry-overview.md").exists()
    assert (root / "01_Projects" / "tropical.project.md").exists()
    assert (root / "01_Projects" / "hilltop.project.md").exists()
    # No document cards directory was populated (opt-in only)
    doc_cards = list((root / "03_Document_Cards").glob("*.md")) if (root / "03_Document_Cards").exists() else []
    assert doc_cards == []


def test_cli_vault_preview_document_card_requires_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    result = runner.invoke(
        construction_cli.app, ["vault", "preview", "--include-document-cards", "--json"],
    )
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["status"] == "document_card_requires_item_and_policy"


def test_cli_vault_preview_apply_without_env_returns_structured_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ENV_VAR, raising=False)
    with patch(
        "hb_assistant.construction.manifests.vault_writer._resolve_root_from_config",
        return_value=None,
    ):
        runner = CliRunner()
        result = runner.invoke(construction_cli.app, ["vault", "preview", "--apply", "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["status"] == "vault_root_not_configured"
