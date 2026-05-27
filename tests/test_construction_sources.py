"""Tests for the construction-agent source registry (Phase 01 Step 2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from typer.testing import CliRunner

from hb_assistant.cli import construction as construction_cli
from hb_assistant.construction.config import (
    ProjectIdentity,
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


def test_seed_loads_with_expected_projects_and_sources() -> None:
    reg = load_source_registry()

    project_keys = {p.project_key for p in reg.projects}
    assert {"tropical", "hilltop"}.issubset(project_keys)

    source_keys = {s.source_key for s in reg.sources}
    assert {"tropical-sharepoint", "hilltop-sharepoint", "bobby-onedrive"}.issubset(source_keys)


def test_seed_sources_are_all_read_only_and_pending() -> None:
    reg = load_source_registry()
    assert reg.sources, "seed must contain at least one source"
    for src in reg.sources:
        assert src.read_only is True, f"{src.source_key} must remain read-only"
        assert src.resolution_status == "pending", (
            f"{src.source_key} must be pending at seed time (no fabricated IDs)"
        )
        assert src.site_id is None, f"{src.source_key} must not carry a fabricated site_id"
        assert src.drive_id is None, f"{src.source_key} must not carry a fabricated drive_id"


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


def test_non_kebab_key_is_rejected() -> None:
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


def test_validate_cli_emits_expected_json() -> None:
    runner = CliRunner()
    result = runner.invoke(construction_cli.app, ["sources", "validate", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["implemented"] is True
    assert payload["step"] == "2-source-registry"
    assert payload["summary"]["project_count"] >= 2
    assert payload["summary"]["source_count"] >= 3
    assert payload["summary"]["ok"] is True
    assert payload["summary"]["blocking"] is False
    assert payload["summary"]["pending_count"] == payload["summary"]["source_count"]
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
