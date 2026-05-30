"""Phase 06 (Files) Prompt 03 — canonical source-registry projection.

Complements the existing projection coverage in test_construction_sources.py by
locking in the Prompt 03 deliverables: dry-run (zero writes), apply idempotency,
the `graph files sources` CLI surface, classification buckets, and invalid
read_only/policy rejection.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from hb_assistant.cli.graph import _classify_source, _sources_summary, app
from hb_assistant.construction.config import load_source_registry
from hb_assistant.construction.config.models import (
    DefaultPolicies,
    FolderPolicies,
    SourceLocation,
)
from hb_assistant.construction.source_projection import (
    project_registry_to_v5_source_locations,
)
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()


@pytest.fixture
def v5_store(tmp_path: Path) -> ConstructionStore:
    return ConstructionStore(str(tmp_path / "v5_projection.sqlite"))


# --- projection dry-run / apply ------------------------------------------------


def test_projection_dry_run_writes_zero_rows(v5_store: ConstructionStore) -> None:
    reg = load_source_registry()
    report = project_registry_to_v5_source_locations(reg, v5_store, dry_run=True)
    assert report.total == 14
    assert report.projected + report.compat_projected == 14
    # Dry-run must not touch SQLite.
    assert v5_store.list_source_locations(limit=10000) == []


def test_projection_dry_run_needs_no_store() -> None:
    reg = load_source_registry()
    report = project_registry_to_v5_source_locations(reg, dry_run=True)
    assert report.total == 14


def test_projection_apply_without_store_raises() -> None:
    reg = load_source_registry()
    with pytest.raises(ValueError, match="requires a store when dry_run=False"):
        project_registry_to_v5_source_locations(reg, dry_run=False)


def test_projection_apply_is_idempotent(v5_store: ConstructionStore) -> None:
    reg = load_source_registry()
    project_registry_to_v5_source_locations(reg, v5_store)
    first = v5_store.list_source_locations(limit=10000)
    # Re-apply: same identities, no duplicates.
    project_registry_to_v5_source_locations(reg, v5_store)
    second = v5_store.list_source_locations(limit=10000)
    assert len(first) == 14
    assert len(second) == 14
    assert {r["source_id"] for r in first} == {r["source_id"] for r in second}


# --- classification ------------------------------------------------------------


def test_classification_buckets_match_seed() -> None:
    reg = load_source_registry()
    rows = [_classify_source(s) for s in reg.sources]
    summary = _sources_summary(rows)
    assert summary["total"] == 14
    assert summary["enabled"] == 14
    assert summary["disabled"] == 0
    # Exactly the two unmatched Wellington sources route to review.
    assert summary["unmatched"] == 2
    assert summary["review_required"] == 2
    # 7 carry drive/site identifiers (pre-resolved), 7 are still pending.
    assert summary["pre_resolved"] == 7
    assert summary["pending"] == 7
    assert summary["pre_resolved"] + summary["pending"] == summary["total"]


def test_classification_marks_tropical_graph_delta_ready() -> None:
    reg = load_source_registry()
    rows = {r["source_id"]: r for r in (_classify_source(s) for s in reg.sources)}
    tropical = rows["sp_2023projects_23_435_01_tropical_sl"]
    assert tropical["resolution_status"] == "graph_delta_ready"
    assert tropical["pre_resolved"] is True
    assert tropical["pending"] is False


# --- invalid read_only / policy rejection -------------------------------------


def test_source_location_rejects_read_only_false() -> None:
    with pytest.raises(ValidationError):
        SourceLocation(
            source_key="sp_bad",
            kind="sharepoint_project_drive_folder",
            display_name="bad",
            read_only=False,  # type: ignore[arg-type]
        )


def test_default_policies_reject_vault_copy_and_full_text() -> None:
    with pytest.raises(ValidationError):
        DefaultPolicies(copy_originals_to_vault=True)
    with pytest.raises(ValidationError):
        DefaultPolicies(store_full_text_in_vault_notes=True)


def test_folder_policies_reject_review_deep_index_overlap() -> None:
    with pytest.raises(ValidationError):
        FolderPolicies(deep_index_allowed=["Contracts"], review_required=["contracts"])


def test_store_upsert_rejects_read_only_false(v5_store: ConstructionStore) -> None:
    with pytest.raises(ValueError, match="read_only must be True"):
        v5_store.upsert_source_location(
            source_id="sp_forbidden",
            source_system="sharepoint",
            source_scope="sharepoint_project_drive_folder",
            source_name="forbidden",
            read_only=False,
        )


# --- CLI surface ---------------------------------------------------------------


def test_cli_sources_dry_run_writes_nothing() -> None:
    result = runner.invoke(app, ["files", "sources", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "graph files sources"
    assert payload["mode"] == "dry_run"
    assert payload["ok"] is True
    assert payload["persisted_source_location_count"] is None
    assert payload["summary"]["total"] == 14
    assert payload["guardrails"]["writeback"] == "none"
    assert payload["guardrails"]["permission_tightening"] == "deferred"


def test_cli_sources_apply_persists_isolated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = str(tmp_path / "apply.sqlite")
    monkeypatch.setattr(
        "hb_assistant.cli.graph.ConstructionStore", lambda *a, **k: ConstructionStore(db)
    )
    result = runner.invoke(app, ["files", "sources", "--apply", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["mode"] == "apply"
    assert payload["ok"] is True
    assert payload["persisted_source_location_count"] == 14
    # Confirm the rows actually landed in the isolated DB.
    assert len(ConstructionStore(db).list_source_locations(limit=10000)) == 14
