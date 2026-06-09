"""Tests for construction-agent manifest/receipt projections (Phase 01 Step 5)."""

from __future__ import annotations

import json
import re
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
from hb_assistant.store.connection import get_connection

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
        run_id="r1",
        source_key="tropical-sharepoint",
        drive_id="b!drive-1",
        mode="apply",
        status="ok",
        started_at="2026-05-27T12:00:00+00:00",
        finished_at="2026-05-27T12:00:01+00:00",
        pages_seen=2,
        items_seen=5,
        items_new=4,
        items_updated=1,
        items_deleted=0,
        delta_link_recorded=True,
        sample_items=[],
    )
    svc = ManifestService(ConstructionStore())
    receipt = svc.build_sync_receipt(cr)
    assert receipt.run_id == "r1"
    assert receipt.items_new == 4
    assert receipt.status == "ok"


def test_service_projects_sync_receipt_from_store(populated_store: ConstructionStore) -> None:
    svc = ManifestService(populated_store)
    proj = svc.build_sync_receipt_from_store(
        "tropical-sharepoint",
        run_id="r2",
        started_at="2026-05-27T12:00:00+00:00",
    )
    assert proj.status == "projected"
    assert proj.items_seen == 3  # carried from prior crawl receipt


def test_service_projects_empty_when_no_prior_receipt(tmp_path: Path) -> None:
    db = str(tmp_path / "fresh.sqlite")
    store = ConstructionStore(db)
    svc = ManifestService(store)
    proj = svc.build_sync_receipt_from_store(
        "tropical-sharepoint",
        run_id="r3",
        started_at="2026-05-27T12:00:00+00:00",
    )
    assert proj.status == "projected"
    assert proj.items_seen == 0
    assert proj.error_redacted is not None


def test_processing_receipt_aggregates_totals_and_errors() -> None:
    svc = ManifestService(ConstructionStore())
    rs = [
        SyncReceipt(
            run_id="r",
            source_key="a",
            mode="apply",
            status="ok",
            started_at="t",
            pages_seen=1,
            items_seen=2,
            items_new=2,
            guardrails=dict(GUARDRAILS_DEFAULT),
        ),
        SyncReceipt(
            run_id="r",
            source_key="b",
            mode="apply",
            status="failed",
            started_at="t",
            pages_seen=0,
            items_seen=0,
            error_redacted="graph_503: timeout",
            guardrails=dict(GUARDRAILS_DEFAULT),
        ),
    ]
    pr = svc.build_processing_receipt(
        run_id="r",
        mode="apply",
        started_at="t0",
        finished_at="t1",
        per_source=rs,
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
                item_id="i-1",
                name="design.pdf",
                size_bytes=2048,
                is_folder=False,
                status="active",
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


# ---------- Phase 02: all-output guardrails -------------------------------

ALL_OUTPUT_KINDS = (
    "source_manifest",
    "sync_receipt",
    "processing_receipt",
    "registry_overview",
    "project_card",
    "review_required",
    "document_card",
)


def _build_all_renders(populated_store: ConstructionStore) -> dict[str, str]:
    """Build all 7 rendered outputs from a populated store + canonical seed.

    The ``populated_store`` fixture seeds a raw delta_link containing the
    sentinel ``ABC123secret`` in SQLite, so the no-raw-delta-link guardrail
    test can prove the renderer never surfaces that token.
    """
    from hb_assistant.construction.config import load_source_registry

    reg = load_source_registry()
    svc = ManifestService(populated_store)
    source = next(s for s in reg.sources if s.source_key == "tropical-sharepoint")

    manifest = svc.build_source_manifest(source, run_id="run-x")
    sync_receipt = svc.build_sync_receipt_from_store(
        "tropical-sharepoint",
        run_id="r1",
        started_at="2026-05-27T12:00:00+00:00",
    )
    processing_receipt = svc.build_processing_receipt(
        run_id="r1",
        mode="apply",
        started_at="2026-05-27T11:59:00+00:00",
        finished_at="2026-05-27T12:00:00+00:00",
        per_source=[sync_receipt],
    )
    overview = svc.build_registry_overview(reg)
    card = svc.build_project_card(reg, "tropical")
    review_note = svc.build_review_required_note()
    document_card = svc.build_document_card(
        source=source,
        item_id="item-0",
        policy_reason="manual review",
    )

    return {
        "source_manifest": ManifestRenderer.render_source_manifest(manifest),
        "sync_receipt": ManifestRenderer.render_sync_receipt(sync_receipt),
        "processing_receipt": ManifestRenderer.render_processing_receipt(processing_receipt),
        "registry_overview": ManifestRenderer.render_registry_overview(overview),
        "project_card": ManifestRenderer.render_project_card(card),
        "review_required": ManifestRenderer.render_review_required(review_note),
        "document_card": ManifestRenderer.render_document_card(document_card),
    }


@pytest.fixture
def all_renders(populated_store: ConstructionStore) -> dict[str, str]:
    return _build_all_renders(populated_store)


@pytest.mark.parametrize("kind", ALL_OUTPUT_KINDS)
def test_render_never_carries_body_or_text_fields_all_kinds(
    all_renders: dict[str, str],
    kind: str,
) -> None:
    forbidden = ["body:", "content:", "text:", "excerpt:", "full_text:"]
    lower = all_renders[kind].lower()
    for needle in forbidden:
        assert needle not in lower, f"{kind} unexpectedly contains {needle!r}"


@pytest.mark.parametrize("kind", ALL_OUTPUT_KINDS)
def test_render_never_leaks_raw_delta_link_all_kinds(
    all_renders: dict[str, str],
    kind: str,
) -> None:
    rendered = all_renders[kind]
    # The populated_store fixture seeded delta_link with ABC123secret. No
    # rendered output may carry the raw token; only the SHA256 fingerprint.
    assert "ABC123secret" not in rendered, f"{kind} leaked raw delta token"
    # Graph delta endpoint URLs must never appear verbatim.
    assert "/root/delta?token=" not in rendered, f"{kind} leaked delta URL"


_RENDERER_BY_KIND = {
    "source_manifest": ("build_source_manifest", "render_source_manifest"),
    "sync_receipt": ("build_sync_receipt_from_store", "render_sync_receipt"),
    "processing_receipt": ("build_processing_receipt", "render_processing_receipt"),
    "registry_overview": ("build_registry_overview", "render_registry_overview"),
    "project_card": ("build_project_card", "render_project_card"),
    "review_required": ("build_review_required_note", "render_review_required"),
    "document_card": ("build_document_card", "render_document_card"),
}


@pytest.mark.parametrize("kind", ALL_OUTPUT_KINDS)
def test_render_is_byte_identical_on_repeat(
    populated_store: ConstructionStore,
    kind: str,
) -> None:
    """Renderer is a pure function: rendering the same model instance twice
    must produce byte-identical Markdown. The service layer stamps
    generated_at at build time and is intentionally not part of this check."""
    rendered_map = _build_all_renders(populated_store)
    # Re-render the same model instance — model objects are cached via the
    # all_renders pipeline; this test guards the renderer itself.
    from hb_assistant.construction.config import load_source_registry

    reg = load_source_registry()
    svc = ManifestService(populated_store)
    source = next(s for s in reg.sources if s.source_key == "tropical-sharepoint")

    if kind == "source_manifest":
        m = svc.build_source_manifest(source, run_id="run-x")
        a = ManifestRenderer.render_source_manifest(m)
        b = ManifestRenderer.render_source_manifest(m)
    elif kind == "sync_receipt":
        m = svc.build_sync_receipt_from_store(
            "tropical-sharepoint",
            run_id="r1",
            started_at="2026-05-27T12:00:00+00:00",
        )
        a = ManifestRenderer.render_sync_receipt(m)
        b = ManifestRenderer.render_sync_receipt(m)
    elif kind == "processing_receipt":
        sync = svc.build_sync_receipt_from_store(
            "tropical-sharepoint",
            run_id="r1",
            started_at="2026-05-27T12:00:00+00:00",
        )
        m = svc.build_processing_receipt(
            run_id="r1",
            mode="apply",
            started_at="2026-05-27T11:59:00+00:00",
            finished_at="2026-05-27T12:00:00+00:00",
            per_source=[sync],
        )
        a = ManifestRenderer.render_processing_receipt(m)
        b = ManifestRenderer.render_processing_receipt(m)
    elif kind == "registry_overview":
        m = svc.build_registry_overview(reg)
        a = ManifestRenderer.render_registry_overview(m)
        b = ManifestRenderer.render_registry_overview(m)
    elif kind == "project_card":
        m = svc.build_project_card(reg, "tropical")
        a = ManifestRenderer.render_project_card(m)
        b = ManifestRenderer.render_project_card(m)
    elif kind == "review_required":
        m = svc.build_review_required_note()
        a = ManifestRenderer.render_review_required(m)
        b = ManifestRenderer.render_review_required(m)
    else:  # document_card
        m = svc.build_document_card(
            source=source,
            item_id="item-0",
            policy_reason="manual review",
        )
        a = ManifestRenderer.render_document_card(m)
        b = ManifestRenderer.render_document_card(m)
    assert a == b, f"{kind} render is non-deterministic across repeated calls"
    # Sanity: each kind has at least one render visible in the all-renders map.
    assert kind in rendered_map


_TOKEN_SHAPE_REGEXES: tuple[re.Pattern[str], ...] = (
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}"),
    re.compile(r"eyJ[A-Za-z0-9._\-]{20,}"),
    re.compile(r"\b(access|refresh)_token\s*[=:]\s*\S+"),
    re.compile(r"client_secret\s*[=:]\s*\S+"),
    re.compile(r"api_key\s*[=:]\s*\S+"),
    re.compile(r"Authorization:\s*Bearer\b"),
)


@pytest.mark.parametrize("kind", ALL_OUTPUT_KINDS)
def test_rendered_markdown_contains_no_token_shaped_secrets(
    all_renders: dict[str, str],
    kind: str,
) -> None:
    rendered = all_renders[kind]
    for rx in _TOKEN_SHAPE_REGEXES:
        match = rx.search(rendered)
        assert match is None, (
            f"{kind} contains token-shaped substring {match.group()!r} matching {rx.pattern!r}"
        )


def test_sync_receipt_renders_raw_delta_link_redacted_proof(
    populated_store: ConstructionStore,
) -> None:
    svc = ManifestService(populated_store)
    receipt = svc.build_sync_receipt_from_store(
        "tropical-sharepoint",
        run_id="r1",
        started_at="2026-05-27T12:00:00+00:00",
    )
    rendered = ManifestRenderer.render_sync_receipt(receipt)
    assert "raw_delta_link_redacted: true" in rendered


def test_processing_receipt_renders_raw_delta_link_redacted_proof() -> None:
    svc = ManifestService(ConstructionStore())
    sync = SyncReceipt(
        run_id="r",
        source_key="a",
        mode="apply",
        status="ok",
        started_at="2026-05-27T12:00:00+00:00",
        guardrails=dict(GUARDRAILS_DEFAULT),
    )
    pr = svc.build_processing_receipt(
        run_id="r",
        mode="apply",
        started_at="2026-05-27T11:59:00+00:00",
        finished_at="2026-05-27T12:00:00+00:00",
        per_source=[sync],
    )
    rendered = ManifestRenderer.render_processing_receipt(pr)
    assert "raw_delta_link_redacted: true" in rendered


def test_manifest_sample_size_cap_respected() -> None:
    m = SourceManifest(
        source_key="x",
        kind="sharepoint_site",
        display_name="x",
        generated_at="t",
        run_id="r",
        sample_size_cap=2,
        sample_entries=[SourceManifestEntry(item_id=f"i-{i}") for i in range(5)],
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
        "tropical-sharepoint",
        since_iso="1970-01-01T00:00:00+00:00",
    )
    assert len(rows) == 3
    rows_none = populated_store.list_inventory_changed_since(
        "tropical-sharepoint",
        since_iso="2099-01-01T00:00:00+00:00",
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
        source_key="tropical-sharepoint",
        run_id="abcdef123456",
        started_at="2026-05-27T12:00:00+00:00",
        rendered="hello sync",
    )
    writer.write_processing_receipt(
        run_id="abcdef123456",
        started_at="2026-05-27T12:00:00+00:00",
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
    target.write_text("# My personal notes\n\nthis text must be preserved.\n", encoding="utf-8")
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
    # Use the autouse isolated HB_PA_CONFIG fixture from tests/conftest.py.
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
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
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
        "tropical-sharepoint",
        "hilltop-sharepoint",
        "bobby-onedrive",
    }
    assert payload["processing_receipt"]["source_count"] == 0


# =====================================================================
# Baseline comparison tests (Phase 02 Prompt 04).
# =====================================================================


def _make_tropical_canonical(**overrides) -> SourceLocation:
    from hb_assistant.construction.config import BaselineSnapshot

    defaults = {
        "source_key": "sp_2023projects_23_435_01_tropical_sl",
        "project_key": "tropical",
        "kind": "sharepoint_project_drive_folder",
        "display_name": "Tropical canonical",
        "baseline": BaselineSnapshot(
            baseline_status="complete",
            baseline_unique_item_count=8921,
            baseline_file_count=7208,
            baseline_folder_count=1713,
            baseline_file_size_gb=39.78,
        ),
    }
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
    _seed_inventory(store, src.source_key, file_count=3, folder_count=1, bytes_per_file=100_000_000)
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
    unique_drift = cmp.drift_pct["unique_item_count"]
    assert unique_drift is not None
    assert abs(unique_drift) <= 5.0


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


# =====================================================================
# Phase 03 Prompt 07: canonical V5 read-model path
# =====================================================================


_CANONICAL_SOURCE_ID = "sp_2023projects_23_435_01_tropical_sl"


def _seed_v5_source_with_drive_items(
    store: ConstructionStore,
    *,
    source_id: str = _CANONICAL_SOURCE_ID,
    project_key: str | None = "tropical",
) -> None:
    """Seed a V5 ``construction_source_locations`` row and two V5
    ``construction_drive_items`` rows for canonical-path tests."""
    store.upsert_source_location(
        source_id=source_id,
        source_system="sharepoint",
        source_scope="sharepoint_project_drive_folder",
        source_name="Tropical canonical",
        project_key=project_key,
    )
    store.upsert_drive_item(
        source_id=source_id,
        drive_id="drv-canonical",
        drive_item_id="canon-item-1",
        name="design.pdf",
        path="/Tropical/Design",
        web_url="https://x/canon-1",
        is_file=True,
        size_bytes=4096,
        mime_type="application/pdf",
        last_modified_datetime="2026-05-27T10:00:00Z",
    )
    store.upsert_drive_item(
        source_id=source_id,
        drive_id="drv-canonical",
        drive_item_id="canon-item-2",
        name="spec.docx",
        path="/Tropical/Design",
        web_url="https://x/canon-2",
        is_file=True,
        size_bytes=1024,
        last_modified_datetime="2026-05-27T11:00:00Z",
    )


def test_document_card_renders_from_canonical_v5_source_id(tmp_path: Path) -> None:
    store = ConstructionStore(str(tmp_path / "canon.sqlite"))
    _seed_v5_source_with_drive_items(store)
    svc = ManifestService(store)
    card = svc.build_document_card_from_source_id(
        source_id=_CANONICAL_SOURCE_ID,
        item_id="canon-item-1",
        policy_reason="manual review",
    )
    rendered = ManifestRenderer.render_document_card(card)
    assert rendered  # non-empty
    assert "canon-item-1" in rendered
    assert "design.pdf" in rendered


def test_document_card_source_key_and_source_id_parity(tmp_path: Path) -> None:
    """Canonical path: frontmatter exposes both source_key (V2 alias) and
    source_id (V5 canonical) as distinct fields, populated from the V5
    source_locations row."""
    import yaml

    store = ConstructionStore(str(tmp_path / "canon.sqlite"))
    _seed_v5_source_with_drive_items(store)
    svc = ManifestService(store)
    card = svc.build_document_card_from_source_id(
        source_id=_CANONICAL_SOURCE_ID,
        item_id="canon-item-1",
        policy_reason="manual review",
    )
    rendered = ManifestRenderer.render_document_card(card)
    end = rendered.index("\n---\n", 4)
    fm = yaml.safe_load(rendered[4:end])
    assert fm["source_key"] == _CANONICAL_SOURCE_ID
    assert fm["source_id"] == _CANONICAL_SOURCE_ID
    # Both keys must be present as distinct fields, even though their
    # current canonical values match.
    assert "source_key" in fm and "source_id" in fm


def test_canonical_render_carries_no_body_or_token_or_raw_delta(tmp_path: Path) -> None:
    """Re-run the existing forbidden-substring scanners against the
    canonical-path render output."""
    store = ConstructionStore(str(tmp_path / "canon.sqlite"))
    _seed_v5_source_with_drive_items(store)
    # Seed a raw delta-link sentinel in the legacy V2 token storage to
    # prove the canonical path doesn't accidentally surface it either.
    store.set_delta_token(
        source_key=_CANONICAL_SOURCE_ID,
        drive_id="drv-canonical",
        delta_link=(
            "https://graph.microsoft.com/v1.0/drives/drv/root/delta?"
            "token=CANONsecretXYZ&skiptoken=Bearer eyJabcdefghijklmnopqrstuvwxyz"
        ),
        page_count=1,
        last_status="ok",
    )
    svc = ManifestService(store)
    card = svc.build_document_card_from_source_id(
        source_id=_CANONICAL_SOURCE_ID,
        item_id="canon-item-1",
        policy_reason="manual review",
    )
    rendered = ManifestRenderer.render_document_card(card)
    forbidden_body = ["body:", "content:", "text:", "excerpt:", "full_text:"]
    for needle in forbidden_body:
        assert needle not in rendered.lower(), f"canonical render leaked {needle!r}"
    # Token / delta-link forbidden substrings.
    for forbidden in (
        "@odata.deltaLink",
        "@odata.nextLink",
        "skiptoken",
        "Bearer ",
        "eyJ",
        "access_token=",
        "CANONsecretXYZ",
        "/root/delta?token=",
    ):
        assert forbidden not in rendered, (
            f"canonical render unexpectedly contains forbidden substring {forbidden!r}"
        )
    for rx in _TOKEN_SHAPE_REGEXES:
        assert rx.search(rendered) is None, (
            f"canonical render matched forbidden token shape {rx.pattern!r}"
        )


def test_canonical_render_is_byte_deterministic(tmp_path: Path) -> None:
    store = ConstructionStore(str(tmp_path / "canon.sqlite"))
    _seed_v5_source_with_drive_items(store)
    svc = ManifestService(store)
    card = svc.build_document_card_from_source_id(
        source_id=_CANONICAL_SOURCE_ID,
        item_id="canon-item-1",
        policy_reason="manual review",
    )
    a = ManifestRenderer.render_document_card(card)
    b = ManifestRenderer.render_document_card(card)
    assert a == b


def test_canonical_path_fails_closed_when_source_missing(tmp_path: Path) -> None:
    from hb_assistant.construction.manifests import CanonicalSourceNotFound

    store = ConstructionStore(str(tmp_path / "canon.sqlite"))
    svc = ManifestService(store)
    with pytest.raises(CanonicalSourceNotFound):
        svc.build_document_card_from_source_id(
            source_id="not-in-source-locations",
            item_id="x",
            policy_reason="manual review",
        )


def test_canonical_path_requires_non_empty_policy_reason(tmp_path: Path) -> None:
    from hb_assistant.construction.manifests.service import DocumentCardPolicyError

    store = ConstructionStore(str(tmp_path / "canon.sqlite"))
    _seed_v5_source_with_drive_items(store)
    svc = ManifestService(store)
    with pytest.raises(DocumentCardPolicyError):
        svc.build_document_card_from_source_id(
            source_id=_CANONICAL_SOURCE_ID,
            item_id="canon-item-1",
            policy_reason="   ",
        )


def test_canonical_path_unknown_item_raises(tmp_path: Path) -> None:
    store = ConstructionStore(str(tmp_path / "canon.sqlite"))
    _seed_v5_source_with_drive_items(store)
    svc = ManifestService(store)
    with pytest.raises(ValueError):
        svc.build_document_card_from_source_id(
            source_id=_CANONICAL_SOURCE_ID,
            item_id="missing-item",
            policy_reason="manual review",
        )


def test_project_card_includes_procore_sync_summary_totals(
    populated_store: ConstructionStore,
) -> None:
    # Seed the CANONICAL procore_live_* path (the tables the daily source-refresh
    # now writes); the legacy procore_sync_* path is retired. The real V6 schema
    # is already present, so insert full rows (NOT NULL columns satisfied,
    # raw_body_persisted=0 honored).
    conn = get_connection(populated_store._db_path)  # noqa: SLF001
    rec_cols = (
        "project_key, procore_project_id, endpoint_id, procore_record_id, "
        "canonical_json_redacted, review_required, first_seen_at_utc, "
        "last_seen_at_utc, last_sync_run_id, raw_body_persisted"
    )
    now = "2026-05-28T00:00:00+00:00"
    conn.execute(
        """
        INSERT INTO procore_live_sync_runs
        (sync_run_id, endpoint_id, command_endpoint, project_key, procore_project_id,
         company_id, mode, started_at_utc, status, state)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "run-1",
            "rfis",
            "rfis",
            "tropical",
            "111",
            "5280",
            "live_apply",
            now,
            "success",
            "success",
        ),
    )
    conn.execute(
        f"INSERT INTO procore_live_records ({rec_cols}) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("tropical", "111", "rfis", "rfi-1", "{}", 0, now, now, "run-1", 0),
    )
    conn.execute(
        f"INSERT INTO procore_live_records ({rec_cols}) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("tropical", "111", "subcontractor-invoices", "inv-1", "{}", 1, now, now, "run-1", 0),
    )
    conn.execute(
        """
        INSERT INTO procore_live_sync_watermarks
        (company_id, project_key, procore_project_id, endpoint_id, last_success_at_utc)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("5280", "tropical", "111", "rfis", now),
    )
    conn.commit()

    from hb_assistant.construction.config import load_source_registry

    reg = load_source_registry()
    svc = ManifestService(populated_store)
    card = svc.build_project_card(reg, "tropical")

    assert card.totals["procore_entities_total"] == 2
    assert card.totals["procore_review_required_total"] == 1
    assert card.totals["procore_watermark_count"] == 1
