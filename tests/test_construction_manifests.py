"""Tests for construction-agent manifest/receipt projections (Phase 01 Step 5)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli import construction as construction_cli
from hb_assistant.construction.config import SourceLocation
from hb_assistant.construction.graph.delta_crawler import CrawlReceipt
from hb_assistant.construction.manifests import (
    ConstructionVaultWriter,
    ManifestRenderer,
    ManifestService,
    SourceManifest,
    SourceManifestEntry,
    SyncReceipt,
    VaultRootNotConfigured,
)
from hb_assistant.construction.manifests.service import GUARDRAILS_DEFAULT, delta_link_fingerprint
from hb_assistant.construction.manifests.vault_writer import ENV_VAR
from hb_assistant.construction.store import ConstructionStore

# ---------- fixtures -------------------------------------------------------


def _make_source(
    *,
    source_key: str = "tropical-sharepoint",
    project_key: str | None = "tropical",
    kind: str = "sharepoint_site",
    display_name: str = "Tropical SharePoint Site",
    site_url: str | None = "https://contoso.sharepoint.com/sites/Tropical",
) -> SourceLocation:
    return SourceLocation(
        source_key=source_key,
        project_key=project_key,
        kind=kind,  # type: ignore[arg-type]
        display_name=display_name,
        site_url=site_url,
    )


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
    store.set_delta_token(
        source_key="tropical-sharepoint",
        drive_id="b!drive-1",
        delta_link="https://graph.microsoft.com/v1.0/drives/b!drive-1/root/delta?token=ABC123secret",
        page_count=2,
        last_status="ok",
    )
    for i in range(3):
        store.upsert_inventory_item(
            source_key="tropical-sharepoint",
            drive_id="b!drive-1",
            item_id=f"item-{i}",
            name=f"file-{i}.pdf",
            web_url=f"https://x/{i}",
            parent_path="/drives/b!drive-1/root:/Project",
            size_bytes=1000 + i,
            is_folder=False,
            last_modified="2026-05-20T10:00:00Z",
            etag=f"etag-{i}",
        )
    store.insert_crawl_receipt(
        run_id="prior-run",
        source_key="tropical-sharepoint",
        mode="apply",
        started_at="2026-05-20T09:59:00+00:00",
        finished_at="2026-05-20T10:00:00+00:00",
        pages_seen=1,
        items_seen=3,
        items_new=3,
        items_updated=0,
        items_deleted=0,
        delta_link_recorded=True,
        status="ok",
    )
    return store


# ---------- fingerprint ----------------------------------------------------


def test_delta_link_fingerprint_is_short_sha256() -> None:
    fp = delta_link_fingerprint("https://example/delta?token=secret-abc")
    assert fp is not None
    assert fp.startswith("sha256:")
    assert len(fp) == len("sha256:") + 12


def test_delta_link_fingerprint_none_for_empty() -> None:
    assert delta_link_fingerprint(None) is None
    assert delta_link_fingerprint("") is None


# ---------- service --------------------------------------------------------


def test_service_builds_manifest_from_store(populated_store: ConstructionStore) -> None:
    svc = ManifestService(populated_store)
    source = _make_source()
    manifest = svc.build_source_manifest(source, run_id="run-1")
    assert manifest.source_key == "tropical-sharepoint"
    assert manifest.drive_id == "b!drive-1"
    assert manifest.resolution_status == "resolved"
    assert manifest.item_counts == {"active": 3}
    assert len(manifest.sample_entries) == 3
    assert manifest.delta_link_fingerprint is not None
    assert manifest.delta_link_fingerprint.startswith("sha256:")
    assert manifest.guardrails["markdown_role"] == "projection_only"


def test_service_builds_sync_receipt_from_crawl_receipt() -> None:
    cr = CrawlReceipt(
        run_id="r1", source_key="tropical-sharepoint", drive_id="b!drive-1",
        mode="apply", status="ok",
        started_at="2026-05-27T12:00:00+00:00", finished_at="2026-05-27T12:00:01+00:00",
        pages_seen=2, items_seen=5, items_new=4, items_updated=1, items_deleted=0,
        delta_link_recorded=True, sample_items=[],
    )
    svc = ManifestService(ConstructionStore())
    receipt = svc.build_sync_receipt(cr)
    assert receipt.run_id == "r1"
    assert receipt.items_new == 4
    assert receipt.status == "ok"


def test_service_projects_sync_receipt_from_store(populated_store: ConstructionStore) -> None:
    svc = ManifestService(populated_store)
    proj = svc.build_sync_receipt_from_store(
        "tropical-sharepoint", run_id="r2", started_at="2026-05-27T12:00:00+00:00",
    )
    assert proj.status == "projected"
    assert proj.items_seen == 3  # carried from prior crawl receipt


def test_service_projects_empty_when_no_prior_receipt(tmp_path: Path) -> None:
    db = str(tmp_path / "fresh.sqlite")
    store = ConstructionStore(db)
    svc = ManifestService(store)
    proj = svc.build_sync_receipt_from_store(
        "tropical-sharepoint", run_id="r3", started_at="2026-05-27T12:00:00+00:00",
    )
    assert proj.status == "projected"
    assert proj.items_seen == 0
    assert proj.error_redacted is not None


def test_processing_receipt_aggregates_totals_and_errors() -> None:
    svc = ManifestService(ConstructionStore())
    rs = [
        SyncReceipt(
            run_id="r", source_key="a", mode="apply", status="ok",
            started_at="t", pages_seen=1, items_seen=2, items_new=2,
            guardrails=dict(GUARDRAILS_DEFAULT),
        ),
        SyncReceipt(
            run_id="r", source_key="b", mode="apply", status="failed",
            started_at="t", pages_seen=0, items_seen=0,
            error_redacted="graph_503: timeout",
            guardrails=dict(GUARDRAILS_DEFAULT),
        ),
    ]
    pr = svc.build_processing_receipt(
        run_id="r", mode="apply",
        started_at="t0", finished_at="t1", per_source=rs,
    )
    assert pr.source_count == 2
    assert pr.totals["items_seen"] == 2
    assert pr.error_summary == ["b: graph_503: timeout"]


# ---------- renderer determinism -------------------------------------------


def _example_manifest() -> SourceManifest:
    return SourceManifest(
        source_key="tropical-sharepoint",
        project_key="tropical",
        kind="sharepoint_site",
        display_name="Tropical SharePoint Site",
        resolution_status="resolved",
        drive_id="b!drive-1",
        web_url="https://contoso.sharepoint.com/sites/Tropical",
        generated_at="2026-05-27T12:00:00+00:00",
        run_id="run-deterministic",
        item_counts={"active": 3, "deleted": 1},
        sample_entries=[
            SourceManifestEntry(
                item_id="i-1", name="design.pdf", size_bytes=2048,
                is_folder=False, status="active",
                last_modified="2026-05-20T10:00:00Z",
            ),
        ],
        delta_link_fingerprint="sha256:deadbeefcafe",
        last_sync_at="2026-05-20T10:00:00+00:00",
        guardrails=dict(GUARDRAILS_DEFAULT),
    )


def test_renderer_is_byte_deterministic() -> None:
    m = _example_manifest()
    out1 = ManifestRenderer.render_source_manifest(m)
    out2 = ManifestRenderer.render_source_manifest(m)
    assert out1 == out2


def test_render_never_leaks_full_delta_link(populated_store: ConstructionStore) -> None:
    svc = ManifestService(populated_store)
    m = svc.build_source_manifest(_make_source(), run_id="run-x")
    rendered = ManifestRenderer.render_source_manifest(m)
    assert "ABC123secret" not in rendered  # the raw delta_link must never appear
    assert "sha256:" in rendered  # only the fingerprint should


def test_render_never_carries_body_or_text_fields() -> None:
    m = _example_manifest()
    rendered = ManifestRenderer.render_source_manifest(m)
    forbidden = ["full_text:", "body:", "content:", "excerpt:"]
    for needle in forbidden:
        assert needle.lower() not in rendered.lower()


def test_manifest_sample_size_cap_respected() -> None:
    m = SourceManifest(
        source_key="x", kind="sharepoint_site", display_name="x",
        generated_at="t", run_id="r", sample_size_cap=2,
        sample_entries=[
            SourceManifestEntry(item_id=f"i-{i}") for i in range(5)
        ],
        guardrails=dict(GUARDRAILS_DEFAULT),
    )
    rendered = ManifestRenderer.render_source_manifest(m)
    # Capped: i-0, i-1 visible; i-2..i-4 must not be in the rendered table
    assert "`i-0`" in rendered
    assert "`i-1`" in rendered
    assert "`i-2`" not in rendered


# ---------- store read addition --------------------------------------------


def test_list_inventory_changed_since(populated_store: ConstructionStore) -> None:
    rows = populated_store.list_inventory_changed_since(
        "tropical-sharepoint", since_iso="1970-01-01T00:00:00+00:00",
    )
    assert len(rows) == 3
    rows_none = populated_store.list_inventory_changed_since(
        "tropical-sharepoint", since_iso="2099-01-01T00:00:00+00:00",
    )
    assert rows_none == []


# ---------- vault writer ---------------------------------------------------


def test_apply_requires_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_VAR, raising=False)
    writer = ConstructionVaultWriter()
    assert writer.configured is False
    with pytest.raises(VaultRootNotConfigured):
        writer.write_source_manifest(source_key="x", rendered="content")


def test_apply_writes_to_expected_subdirectories(tmp_path: Path) -> None:
    writer = ConstructionVaultWriter(vault_root=tmp_path)
    writer.write_source_manifest(source_key="tropical-sharepoint", rendered="hello manifest")
    writer.write_sync_receipt(
        source_key="tropical-sharepoint", run_id="abcdef123456",
        started_at="2026-05-27T12:00:00+00:00", rendered="hello sync",
    )
    writer.write_processing_receipt(
        run_id="abcdef123456", started_at="2026-05-27T12:00:00+00:00",
        rendered="hello processing",
    )
    assert (tmp_path / "10_Source_Manifests" / "tropical-sharepoint.manifest.md").exists()
    sync_files = list((tmp_path / "11_Sync_Receipts").glob("*.sync.md"))
    assert len(sync_files) == 1
    proc_files = list((tmp_path / "12_Processing_Receipts").glob("*.processing.md"))
    assert len(proc_files) == 1


def test_apply_is_marker_bounded_and_preserves_user_text(tmp_path: Path) -> None:
    writer = ConstructionVaultWriter(vault_root=tmp_path)
    target = writer.manifest_path("tropical-sharepoint")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "# My personal notes\n\nthis text must be preserved.\n", encoding="utf-8"
    )
    writer.write_source_manifest(source_key="tropical-sharepoint", rendered="GENERATED V1")
    content_after_first = target.read_text(encoding="utf-8")
    assert "this text must be preserved." in content_after_first
    assert "GENERATED V1" in content_after_first

    writer.write_source_manifest(source_key="tropical-sharepoint", rendered="GENERATED V2")
    content_after_second = target.read_text(encoding="utf-8")
    assert "this text must be preserved." in content_after_second
    assert "GENERATED V2" in content_after_second
    assert "GENERATED V1" not in content_after_second


# ---------- CLI ------------------------------------------------------------


def test_cli_sync_dry_run_from_receipts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Force CLI to use isolated app-support so it sees an empty fresh store.
    monkeypatch.setenv("HB_PA_CONFIG", "")
    runner = CliRunner()
    result = runner.invoke(
        construction_cli.app,
        ["sync", "--dry-run", "--source-from-receipts-only", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "construction-agent sync"
    assert payload["mode"] == "dry_run"
    assert "processing_receipt" in payload
    assert "rendered" in payload
    assert "processing_receipt_md" in payload["rendered"]
    assert payload["written"] == []
    assert payload["guardrails"]["markdown_role"] == "projection_only"


def test_cli_sync_apply_without_env_var_returns_structured_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ENV_VAR, raising=False)
    runner = CliRunner()
    result = runner.invoke(
        construction_cli.app,
        ["sync", "--apply", "--source-from-receipts-only", "--json"],
    )
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["status"] == "vault_root_not_configured"
    assert "HB_CONSTRUCTION_VAULT_ROOT" in payload["error"]


def test_cli_sync_apply_with_env_var_writes_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv(ENV_VAR, str(tmp_path / "construction-vault"))
    runner = CliRunner()
    result = runner.invoke(
        construction_cli.app,
        ["sync", "--apply", "--source-from-receipts-only", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["mode"] == "apply"
    assert payload["written"], "should have written at least one file"
    kinds = {w["kind"] for w in payload["written"]}
    assert "source_manifest" in kinds
    assert "sync_receipt" in kinds
    assert "processing_receipt" in kinds


def test_cli_sync_changed_only_skips_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    result = runner.invoke(
        construction_cli.app,
        ["sync", "--dry-run", "--changed-only", "--source-from-receipts-only", "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    # With a fresh store and no inventory rows, every source should be skipped.
    assert {s["source_key"] for s in payload["skipped"]} >= {
        "tropical-sharepoint", "hilltop-sharepoint", "bobby-onedrive"
    }
    assert payload["processing_receipt"]["source_count"] == 0


# =====================================================================
# Baseline comparison tests (Phase 02 Prompt 04).
# =====================================================================


def _make_tropical_canonical(**overrides) -> SourceLocation:
    from hb_assistant.construction.config import BaselineSnapshot

    defaults = dict(
        source_key="sp_2023projects_23_435_01_tropical_sl",
        project_key="tropical",
        kind="sharepoint_project_drive_folder",
        display_name="Tropical canonical",
        baseline=BaselineSnapshot(
            baseline_status="complete",
            baseline_unique_item_count=8921,
            baseline_file_count=7208,
            baseline_folder_count=1713,
            baseline_file_size_gb=39.78,
        ),
    )
    defaults.update(overrides)
    return SourceLocation(**defaults)  # type: ignore[arg-type]


def _seed_inventory(
    store: ConstructionStore,
    source_key: str,
    *,
    file_count: int,
    folder_count: int,
    bytes_per_file: int = 1_000_000,
) -> None:
    """Helper: write N file + M folder rows to construction_drive_item_inventory."""
    for i in range(file_count):
        store.upsert_inventory_item(
            source_key=source_key,
            drive_id="drv-test",
            item_id=f"file-{i}",
            name=f"file-{i}.txt",
            web_url=None,
            parent_path="/Test",
            size_bytes=bytes_per_file,
            is_folder=False,
            last_modified=None,
            etag=None,
        )
    for i in range(folder_count):
        store.upsert_inventory_item(
            source_key=source_key,
            drive_id="drv-test",
            item_id=f"folder-{i}",
            name=f"folder-{i}",
            web_url=None,
            parent_path="/Test",
            size_bytes=None,
            is_folder=True,
            last_modified=None,
            etag=None,
        )


def test_compute_baseline_comparison_never_crawled(tmp_path: Path) -> None:
    from hb_assistant.construction.baseline import compute_baseline_comparison

    store = ConstructionStore(str(tmp_path / "c.sqlite"))
    src = _make_tropical_canonical()
    cmp = compute_baseline_comparison(src, store)

    assert cmp.status == "never_crawled"
    assert cmp.historic["unique_item_count"] == 8921
    assert cmp.historic["file_count"] == 7208
    assert cmp.historic["folder_count"] == 1713
    assert cmp.historic["file_size_gb"] == 39.78
    assert cmp.current["unique_item_count"] == 0
    assert cmp.current["file_count"] == 0
    assert cmp.current["folder_count"] == 0
    assert cmp.current["file_size_gb"] == 0
    assert cmp.drift["unique_item_count"] == -8921
    assert cmp.drift_pct["unique_item_count"] == -100.0
    assert cmp.guardrails["source_documents_copied"] is False


def test_compute_baseline_comparison_no_baseline_recorded(tmp_path: Path) -> None:
    from hb_assistant.construction.baseline import compute_baseline_comparison

    store = ConstructionStore(str(tmp_path / "c.sqlite"))
    src = SourceLocation(
        source_key="legacy-no-baseline",
        kind="sharepoint_site",  # type: ignore[arg-type]
        display_name="Legacy",
    )
    cmp = compute_baseline_comparison(src, store)
    assert cmp.status == "no_baseline_recorded"
    assert all(v is None for v in cmp.historic.values())
    assert all(v is None for v in cmp.drift.values())


def test_compute_baseline_comparison_matches_when_current_equals_historic(
    tmp_path: Path,
) -> None:
    from hb_assistant.construction.baseline import compute_baseline_comparison

    store = ConstructionStore(str(tmp_path / "c.sqlite"))
    from hb_assistant.construction.config import BaselineSnapshot

    src = _make_tropical_canonical(
        baseline=BaselineSnapshot(
            baseline_status="complete",
            baseline_unique_item_count=4,  # 3 files + 1 folder
            baseline_file_count=3,
            baseline_folder_count=1,
            baseline_file_size_gb=0.3,  # 3 files × 100MB = 300MB = 0.3 GB
        )
    )
    _seed_inventory(
        store, src.source_key, file_count=3, folder_count=1, bytes_per_file=100_000_000
    )
    cmp = compute_baseline_comparison(src, store)
    assert cmp.status == "matches", cmp.model_dump()
    assert cmp.current["file_count"] == 3
    assert cmp.current["folder_count"] == 1


def test_compute_baseline_comparison_within_tolerance(tmp_path: Path) -> None:
    from hb_assistant.construction.baseline import compute_baseline_comparison
    from hb_assistant.construction.config import BaselineSnapshot

    store = ConstructionStore(str(tmp_path / "c.sqlite"))
    # Historic 100/100/0/0.1; seed 102 files + 0 folders → 2% drift on files,
    # but unique_item_count drift will be (102 - 100)/100 = 2% too.
    src = _make_tropical_canonical(
        baseline=BaselineSnapshot(
            baseline_status="complete",
            baseline_unique_item_count=100,
            baseline_file_count=100,
            baseline_folder_count=0,
            baseline_file_size_gb=0.1,
        )
    )
    _seed_inventory(store, src.source_key, file_count=102, folder_count=0)
    cmp = compute_baseline_comparison(src, store)
    assert cmp.status == "within_tolerance", cmp.model_dump()
    assert abs(cmp.drift_pct["unique_item_count"]) <= 5.0


def test_compute_baseline_comparison_drift_detected(tmp_path: Path) -> None:
    from hb_assistant.construction.baseline import compute_baseline_comparison
    from hb_assistant.construction.config import BaselineSnapshot

    store = ConstructionStore(str(tmp_path / "c.sqlite"))
    src = _make_tropical_canonical(
        baseline=BaselineSnapshot(
            baseline_status="complete",
            baseline_unique_item_count=100,
            baseline_file_count=100,
            baseline_folder_count=0,
            baseline_file_size_gb=0.1,
        )
    )
    # Seed only 50 files — 50% drift on the file metric.
    _seed_inventory(store, src.source_key, file_count=50, folder_count=0)
    cmp = compute_baseline_comparison(src, store)
    assert cmp.status == "drift_detected"
    assert cmp.drift_pct["file_count"] == -50.0


def test_manifest_service_build_baseline_comparison_uses_registry(
    tmp_path: Path,
) -> None:
    from hb_assistant.construction.config import ProjectIdentity, SourceRegistry

    store = ConstructionStore(str(tmp_path / "c.sqlite"))
    src = _make_tropical_canonical()
    registry = SourceRegistry(
        projects=[ProjectIdentity(project_key="tropical", display_name="Tropical")],
        sources=[src],
    )

    svc = ManifestService(store)
    cmp = svc.build_baseline_comparison(registry, src.source_key)
    assert cmp.status == "never_crawled"
    assert cmp.historic["unique_item_count"] == 8921


def test_manifest_service_build_baseline_comparison_unknown_source_raises(
    tmp_path: Path,
) -> None:
    from hb_assistant.construction.config import SourceRegistry

    store = ConstructionStore(str(tmp_path / "c.sqlite"))
    svc = ManifestService(store)
    registry = SourceRegistry(projects=[], sources=[])
    with pytest.raises(KeyError):
        svc.build_baseline_comparison(registry, "nope")
