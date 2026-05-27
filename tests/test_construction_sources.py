"""Tests for the construction-agent source registry (Phase 01 + Phase 02 bridge)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import get_args

import pytest
import yaml
from pydantic import ValidationError
from typer.testing import CliRunner

from hb_assistant.cli import construction as construction_cli
from hb_assistant.construction.config import (
    BaselinePolicy,
    BaselineSnapshot,
    DefaultPolicies,
    FolderPolicies,
    ProjectIdentity,
    ResolutionStatus,
    SourceKind,
    SourceLocation,
    SourceRegistry,
    load_source_registry,
)
from hb_assistant.construction.config.loader import (
    ENV_VAR,
    SourceRegistryError,
)


def _write_yaml(path: Path, data: dict) -> Path:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _minimal_override(tmp_path: Path) -> Path:
    return _write_yaml(
        tmp_path / "override.yml",
        {
            "projects": [{"project_key": "alpha", "display_name": "Alpha"}],
            "sources": [
                {
                    "source_key": "alpha-sharepoint",
                    "project_key": "alpha",
                    "kind": "sharepoint_site",
                    "display_name": "Alpha SharePoint Site",
                    "read_only": True,
                    "resolution_status": "pending",
                }
            ],
        },
    )


# ---------------------------------------------------------------------------
# Seed-shape tests (Phase 01 + Phase 02 hybrid).
# ---------------------------------------------------------------------------


def test_seed_loads_with_expected_projects_and_sources() -> None:
    reg = load_source_registry()

    project_keys = {p.project_key for p in reg.projects}
    # Phase 01 compatibility records.
    assert {"tropical", "hilltop"}.issubset(project_keys)
    # Phase 02 canonical projects.
    assert {
        "pga-modern-garage",
        "alton-hilltop-pbg",
        "the-wellington",
        "hilltop-gardens",
    }.issubset(project_keys)

    source_keys = {s.source_key for s in reg.sources}
    # Phase 01 compatibility records.
    assert {"tropical-sharepoint", "hilltop-sharepoint", "bobby-onedrive"}.issubset(source_keys)
    # Phase 02 canonical sources (sampled).
    assert {
        "sp_2023projects_23_435_01_tropical_sl",
        "sp_hilltop_gardens_projecthome",
        "od_business_bobby_hedrickbrothers",
        "od_personal_bobby",
        "od_shared_libraries_cloudtemp",
    }.issubset(source_keys)


def test_seed_sources_are_all_read_only() -> None:
    reg = load_source_registry()
    assert reg.sources, "seed must contain at least one source"
    for src in reg.sources:
        assert src.read_only is True, f"{src.source_key} must remain read-only"


def test_seed_resolution_statuses_are_in_allowed_set() -> None:
    reg = load_source_registry()
    allowed = set(get_args(ResolutionStatus))
    for src in reg.sources:
        assert src.resolution_status in allowed


def test_seed_legacy_compat_sources_have_no_fabricated_ids() -> None:
    reg = load_source_registry()
    legacy_keys = {"tropical-sharepoint", "hilltop-sharepoint", "bobby-onedrive"}
    for src in reg.sources:
        if src.source_key in legacy_keys:
            assert src.resolution_status == "pending"
            assert src.site_id is None
            assert src.drive_id is None


def test_seed_default_policies_enforce_safe_defaults() -> None:
    reg = load_source_registry()
    assert reg.default_policies is not None
    assert reg.default_policies.read_only is True
    assert reg.default_policies.copy_originals_to_vault is False
    assert reg.default_policies.store_full_text_in_vault_notes is False


# ---------------------------------------------------------------------------
# Phase 01 model-level guardrails.
# ---------------------------------------------------------------------------


def test_invalid_writeback_flag_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SourceLocation(
            source_key="x",
            kind="sharepoint_site",
            display_name="X",
            read_only=False,  # type: ignore[arg-type]
        )


def test_unknown_source_kind_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SourceLocation(
            source_key="x",
            kind="ftp_server",  # type: ignore[arg-type]
            display_name="X",
        )


def test_non_kebab_or_snake_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ProjectIdentity(project_key="Tropical Pointe", display_name="x")
    with pytest.raises(ValidationError):
        SourceLocation(
            source_key="Tropical_Site",
            kind="sharepoint_site",
            display_name="x",
        )


def test_extra_fields_are_forbidden() -> None:
    with pytest.raises(ValidationError):
        SourceLocation(
            source_key="x",
            kind="sharepoint_site",
            display_name="X",
            secret_token="leak",  # type: ignore[call-arg]
        )


def test_orphan_source_project_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SourceRegistry.model_validate(
            {
                "projects": [{"project_key": "alpha", "display_name": "Alpha"}],
                "sources": [
                    {
                        "source_key": "stray",
                        "project_key": "nonexistent",
                        "kind": "sharepoint_site",
                        "display_name": "Stray",
                    }
                ],
            }
        )


def test_duplicate_source_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SourceRegistry.model_validate(
            {
                "projects": [],
                "sources": [
                    {
                        "source_key": "dup",
                        "kind": "sharepoint_site",
                        "display_name": "A",
                    },
                    {
                        "source_key": "dup",
                        "kind": "sharepoint_site",
                        "display_name": "B",
                    },
                ],
            }
        )


def test_duplicate_site_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SourceRegistry.model_validate(
            {
                "projects": [],
                "sources": [
                    {
                        "source_key": "a",
                        "kind": "sharepoint_site",
                        "display_name": "A",
                        "site_id": "shared-site-id",
                        "resolution_status": "resolved",
                    },
                    {
                        "source_key": "b",
                        "kind": "sharepoint_site",
                        "display_name": "B",
                        "site_id": "shared-site-id",
                        "resolution_status": "resolved",
                    },
                ],
            }
        )


def test_explicit_override_replaces_seed(tmp_path: Path) -> None:
    override = _minimal_override(tmp_path)
    reg = load_source_registry(override_path=override)
    assert [p.project_key for p in reg.projects] == ["alpha"]
    assert [s.source_key for s in reg.sources] == ["alpha-sharepoint"]


def test_env_var_override_is_respected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    override = _minimal_override(tmp_path)
    monkeypatch.setenv(ENV_VAR, str(override))
    reg = load_source_registry()
    assert [p.project_key for p in reg.projects] == ["alpha"]


def test_missing_seed_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from hb_assistant.construction.config import loader as loader_mod

    monkeypatch.setattr(loader_mod, "_resolve_seed_path", lambda: tmp_path / "missing.yaml")
    monkeypatch.setattr(loader_mod, "_resolve_repo_override_path", lambda: tmp_path / "absent.yml")
    monkeypatch.delenv(ENV_VAR, raising=False)
    with pytest.raises(SourceRegistryError):
        load_source_registry()


# ---------------------------------------------------------------------------
# Phase 02 compatibility-bridge tests.
# ---------------------------------------------------------------------------


def test_legacy_phase1_yaml_shape_still_loads() -> None:
    src = SourceLocation.model_validate(
        {
            "source_key": "legacy-one",
            "kind": "sharepoint_site",
            "display_name": "Legacy One",
            "root_path": "/legacy/path",
        }
    )
    assert src.source_key == "legacy-one"
    assert src.kind == "sharepoint_site"
    assert src.display_name == "Legacy One"
    assert src.root_path == "/legacy/path"


def test_canonical_phase2_yaml_shape_loads() -> None:
    src = SourceLocation.model_validate(
        {
            "source_id": "sp_canon_one",
            "source_scope": "sharepoint_project_drive_folder",
            "source_name": "Canonical One",
            "folder_path": "/canon/path",
            "source_system": "sharepoint",
            "enabled": True,
        }
    )
    assert src.source_key == "sp_canon_one"
    assert src.kind == "sharepoint_project_drive_folder"
    assert src.display_name == "Canonical One"
    assert src.root_path == "/canon/path"
    assert src.source_system == "sharepoint"
    assert src.enabled is True


def test_mixed_legacy_and_canonical_seed_loads() -> None:
    reg = SourceRegistry.model_validate(
        {
            "projects": [
                {"project_key": "alpha", "display_name": "Alpha"},
                {"project_key": "beta", "project_name": "Beta Canonical"},
            ],
            "sources": [
                {
                    "source_key": "alpha-legacy",
                    "project_key": "alpha",
                    "kind": "sharepoint_site",
                    "display_name": "Alpha legacy",
                },
                {
                    "source_id": "sp_beta_canon",
                    "project_key": "beta",
                    "source_scope": "sharepoint_project_drive_folder",
                    "source_name": "Beta canonical",
                },
            ],
        }
    )
    assert [p.project_key for p in reg.projects] == ["alpha", "beta"]
    assert reg.projects[1].display_name == "Beta Canonical"
    assert [s.source_key for s in reg.sources] == ["alpha-legacy", "sp_beta_canon"]


def test_conflicting_source_alias_pair_raises() -> None:
    with pytest.raises(ValidationError) as excinfo:
        SourceLocation.model_validate(
            {
                "source_key": "phase1",
                "source_id": "phase2",
                "kind": "sharepoint_site",
                "display_name": "Conflict",
            }
        )
    assert "conflicting alias" in str(excinfo.value)


def test_conflicting_kind_alias_pair_raises() -> None:
    with pytest.raises(ValidationError) as excinfo:
        SourceLocation.model_validate(
            {
                "source_key": "x",
                "kind": "sharepoint_site",
                "source_scope": "sharepoint_project_drive_folder",
                "display_name": "Conflict",
            }
        )
    assert "conflicting alias" in str(excinfo.value)


def test_conflicting_project_name_alias_pair_raises() -> None:
    with pytest.raises(ValidationError) as excinfo:
        ProjectIdentity.model_validate(
            {
                "project_key": "alpha",
                "display_name": "Alpha One",
                "project_name": "Alpha Two",
            }
        )
    assert "conflicting alias" in str(excinfo.value)


def test_identical_alias_pair_is_accepted() -> None:
    src = SourceLocation.model_validate(
        {
            "source_key": "same",
            "source_id": "same",
            "kind": "sharepoint_site",
            "display_name": "Same",
        }
    )
    assert src.source_key == "same"


def test_canonical_source_ids_are_unique_in_registry() -> None:
    with pytest.raises(ValidationError):
        SourceRegistry.model_validate(
            {
                "projects": [],
                "sources": [
                    {
                        "source_id": "sp_dup",
                        "source_scope": "sharepoint_project_drive_folder",
                        "source_name": "Dup A",
                    },
                    {
                        "source_id": "sp_dup",
                        "source_scope": "sharepoint_project_drive_folder",
                        "source_name": "Dup B",
                    },
                ],
            }
        )


def test_underscore_canonical_source_id_accepted() -> None:
    src = SourceLocation.model_validate(
        {
            "source_id": "sp_2023projects_23_435_01_tropical_sl",
            "source_scope": "sharepoint_project_drive_folder",
            "source_name": "Tropical",
        }
    )
    assert src.source_key == "sp_2023projects_23_435_01_tropical_sl"


def test_new_source_scopes_accepted() -> None:
    new_scopes = [
        "sharepoint_project_drive_folder",
        "sharepoint_site_page",
        "onedrive_business_root",
        "onedrive_personal_root",
        "onedrive_shared_library",
    ]
    for scope in new_scopes:
        src = SourceLocation.model_validate(
            {
                "source_id": f"sp_test_{scope}",
                "source_scope": scope,
                "source_name": scope,
            }
        )
        assert src.kind == scope


def test_new_resolution_statuses_accepted() -> None:
    new_statuses = [
        "graph_delta_ready",
        "pending_graph_resolution",
        "pending_drive_resolution",
        "pending_source_resolution",
    ]
    for status in new_statuses:
        src = SourceLocation.model_validate(
            {
                "source_id": f"sp_status_{status}",
                "source_scope": "sharepoint_project_drive_folder",
                "source_name": "x",
                "resolution_status": status,
            }
        )
        assert src.resolution_status == status


def test_legacy_sources_can_omit_phase02_fields() -> None:
    src = SourceLocation.model_validate(
        {
            "source_key": "legacy-min",
            "kind": "sharepoint_site",
            "display_name": "Legacy Minimal",
        }
    )
    assert src.baseline is None
    assert src.baseline_policy is None
    assert src.folder_policies is None
    assert src.source_system is None
    assert src.tenant_id is None
    assert src.enabled is True


def test_duplicate_folder_item_id_rejected() -> None:
    with pytest.raises(ValidationError):
        SourceRegistry.model_validate(
            {
                "projects": [],
                "sources": [
                    {
                        "source_id": "sp_a",
                        "source_scope": "sharepoint_project_drive_folder",
                        "source_name": "A",
                        "folder_item_id": "01SAMEID",
                    },
                    {
                        "source_id": "sp_b",
                        "source_scope": "sharepoint_project_drive_folder",
                        "source_name": "B",
                        "folder_item_id": "01SAMEID",
                    },
                ],
            }
        )


def test_drive_id_reuse_is_allowed() -> None:
    # Multiple folder-scoped sources can legitimately share the same drive_id
    # (Phase 02 canonical seed: 2025Projects + 2026Projects drives).
    reg = SourceRegistry.model_validate(
        {
            "projects": [],
            "sources": [
                {
                    "source_id": "sp_a",
                    "source_scope": "sharepoint_project_drive_folder",
                    "source_name": "A",
                    "drive_id": "shared-drive",
                    "folder_item_id": "01FOLDERA",
                },
                {
                    "source_id": "sp_b",
                    "source_scope": "sharepoint_project_drive_folder",
                    "source_name": "B",
                    "drive_id": "shared-drive",
                    "folder_item_id": "01FOLDERB",
                },
            ],
        }
    )
    assert len(reg.sources) == 2


# ---------------------------------------------------------------------------
# Typed-policy tests.
# ---------------------------------------------------------------------------


def test_canonical_baseline_policy_loads() -> None:
    policy = BaselinePolicy.model_validate(
        {
            "mode": "inventory_first",
            "deep_index_default": False,
            "classify_project_matches": True,
            "graph_delta_required": True,
            "local_folder_watcher": "secondary_signal_only",
            "require_review_for_sensitive": True,
        }
    )
    assert policy.mode == "inventory_first"
    assert policy.local_folder_watcher == "secondary_signal_only"
    assert policy.require_review_for_sensitive is True


def test_canonical_baseline_snapshot_loads() -> None:
    snap = BaselineSnapshot.model_validate(
        {
            "baseline_status": "complete",
            "baseline_unique_item_count": 8921,
            "baseline_file_count": 7208,
            "baseline_folder_count": 1713,
            "baseline_file_size_gb": 39.78,
        }
    )
    assert snap.baseline_status == "complete"
    assert snap.baseline_unique_item_count == 8921


def test_canonical_folder_policies_load() -> None:
    fp = FolderPolicies.model_validate(
        {
            "deep_index_allowed": ["07-RFI", "15-Submittal"],
            "metadata_only": ["00-Est", "12-Accounting"],
            "review_required": ["00-Est", "12-Accounting", "contracts"],
        }
    )
    assert "07-RFI" in fp.deep_index_allowed
    assert "00-Est" in fp.review_required


def test_invalid_baseline_mode_fails() -> None:
    with pytest.raises(ValidationError):
        BaselinePolicy.model_validate({"mode": "no_such_mode"})


def test_invalid_indexing_depth_fails() -> None:
    with pytest.raises(ValidationError):
        SourceLocation.model_validate(
            {
                "source_id": "sp_x",
                "source_scope": "sharepoint_site_page",
                "source_name": "X",
                "indexing_depth": "not_a_real_depth",
            }
        )


def test_folder_policy_review_required_cannot_be_deep_indexed() -> None:
    with pytest.raises(ValidationError) as excinfo:
        FolderPolicies.model_validate(
            {
                "deep_index_allowed": ["00-Est"],
                "review_required": ["00-Est"],
            }
        )
    assert "review_required and deep_index_allowed" in str(excinfo.value)


def test_default_policies_rejects_copy_originals_true() -> None:
    with pytest.raises(ValidationError) as excinfo:
        DefaultPolicies.model_validate({"copy_originals_to_vault": True})
    assert "copy_originals_to_vault" in str(excinfo.value)


def test_default_policies_rejects_full_text_in_vault_notes_true() -> None:
    with pytest.raises(ValidationError) as excinfo:
        DefaultPolicies.model_validate({"store_full_text_in_vault_notes": True})
    assert "store_full_text_in_vault_notes" in str(excinfo.value)


def test_default_policies_rejects_read_only_false() -> None:
    with pytest.raises(ValidationError):
        DefaultPolicies.model_validate({"read_only": False})


def test_default_policies_safe_defaults_when_empty() -> None:
    dp = DefaultPolicies()
    assert dp.read_only is True
    assert dp.copy_originals_to_vault is False
    assert dp.store_full_text_in_vault_notes is False
    assert dp.require_review_for_sensitive is True


def test_source_kind_literal_contains_phase01_and_phase02_values() -> None:
    kinds = set(get_args(SourceKind))
    # Phase 01.
    assert {"sharepoint_site", "sharepoint_library", "onedrive_personal", "onedrive_shared"}.issubset(kinds)
    # Phase 02.
    assert {
        "sharepoint_project_drive_folder",
        "sharepoint_site_page",
        "onedrive_business_root",
        "onedrive_personal_root",
        "onedrive_shared_library",
    }.issubset(kinds)


# ---------------------------------------------------------------------------
# CLI behavior.
# ---------------------------------------------------------------------------


def test_validate_cli_emits_expected_json() -> None:
    runner = CliRunner()
    result = runner.invoke(construction_cli.app, ["sources", "validate", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["implemented"] is True
    assert payload["step"] == "2-source-registry"
    # Phase 02 canonical expansion: at least 6 projects and 14 sources after the
    # legacy + canonical merge.
    assert payload["summary"]["project_count"] >= 6
    assert payload["summary"]["source_count"] >= 14
    assert payload["summary"]["ok"] is True
    assert payload["summary"]["blocking"] is False
    assert payload["guardrails"]["all_read_only"] is True
    assert payload["guardrails"]["no_writeback_paths"] is True


def test_validate_cli_reports_schema_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = _write_yaml(
        tmp_path / "bad.yml",
        {
            "projects": [],
            "sources": [
                {
                    "source_key": "x",
                    "kind": "ftp_server",
                    "display_name": "X",
                }
            ],
        },
    )
    monkeypatch.setenv(ENV_VAR, str(bad))
    runner = CliRunner()
    result = runner.invoke(construction_cli.app, ["sources", "validate", "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["summary"]["ok"] is False
    assert payload["error"] == "schema_validation_failed"
