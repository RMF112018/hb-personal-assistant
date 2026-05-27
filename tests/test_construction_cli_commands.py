"""Tests for the construction-agent operator CLI surface (Phase 01 Step 9).

Covers three commands added in prompt 08:
- ``construction-agent sources list --json``
- ``construction-agent index status [--source K] --json``
- ``construction-agent validate --json``

Plus a help-shape regression test asserting every shipped sub-app stays
registered on the root command — fails fast if a future change drops one.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from hb_assistant.cli import construction as construction_cli
from hb_assistant.construction.policy.loader import ENV_VAR as REVIEW_RULES_ENV
from hb_assistant.construction.store import ConstructionStore

# ---------------------------------------------------------------------------
# Fixtures (mirrors test_construction_review_policy._patch_store_to_tmp)
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "cli.sqlite")


def _patch_store_to_tmp(monkeypatch: pytest.MonkeyPatch, db_path: str) -> None:
    from hb_assistant.store import connection as conn_mod
    real = conn_mod.get_connection

    def _get(_: str | None = None):
        return real(db_path)

    monkeypatch.setattr(conn_mod, "get_connection", _get)
    from hb_assistant.construction.store import repositories as repo_mod
    from hb_assistant.store import migrator as mig_mod
    monkeypatch.setattr(repo_mod, "get_connection", _get)
    monkeypatch.setattr(mig_mod, "get_connection", _get)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# Root help shape
# ---------------------------------------------------------------------------


_REQUIRED_SUBAPPS = ("sources", "graph", "vault", "review", "classify")
_REQUIRED_TOP_LEVEL = ("sync", "index", "validate")


def test_root_help_exposes_all_subapps_and_commands(runner: CliRunner) -> None:
    r = runner.invoke(construction_cli.app, ["--help"])
    assert r.exit_code == 0, r.output
    for name in _REQUIRED_SUBAPPS + _REQUIRED_TOP_LEVEL:
        assert name in r.output, f"root --help must list {name!r}; got:\n{r.output}"


def test_sources_subapp_lists_list_and_validate(runner: CliRunner) -> None:
    r = runner.invoke(construction_cli.app, ["sources", "--help"])
    assert r.exit_code == 0
    assert "list" in r.output
    assert "validate" in r.output


# ---------------------------------------------------------------------------
# sources list
# ---------------------------------------------------------------------------


def test_sources_list_returns_registered_sources(
    runner: CliRunner,
) -> None:
    r = runner.invoke(construction_cli.app, ["sources", "list", "--json"])
    assert r.exit_code == 0, r.output
    p = json.loads(r.output)
    assert p["command"] == "construction-agent sources list"
    assert p["count"] == len(p["sources"]) >= 1
    keys = {s["source_key"] for s in p["sources"]}
    assert "tropical-sharepoint" in keys
    # Read-only guardrail attested
    assert p["guardrails"]["writeback"] == "none"
    assert p["guardrails"]["external_systems"] == "read_only"


# ---------------------------------------------------------------------------
# index status
# ---------------------------------------------------------------------------


def test_index_status_returns_dashboard(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, db_path: str,
) -> None:
    _patch_store_to_tmp(monkeypatch, db_path)
    r = runner.invoke(construction_cli.app, ["index", "status", "--json"])
    assert r.exit_code == 0, r.output
    p = json.loads(r.output)
    assert p["command"] == "construction-agent index status"
    assert p["schema_version"] >= 4
    # Sections present
    for k in ("summary", "sources", "review_queue", "model_decisions", "policies"):
        assert k in p
    # Empty DB → all zeros
    assert p["review_queue"] == {"open": 0, "resolved": 0, "deferred": 0}
    assert p["model_decisions"] == {"accepted": 0, "review": 0}
    # Policy snapshots populated
    assert p["policies"]["review_rules"]["rule_count"] >= 1
    assert p["policies"]["model_routing"]["default_model"]
    assert set(p["policies"]["model_routing"]["tasks"]) >= {
        "classification", "review_reason",
    }
    # Guardrails
    assert p["guardrails"]["command_role"] == "read_only_dashboard"


def test_index_status_per_source_filter(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, db_path: str,
) -> None:
    _patch_store_to_tmp(monkeypatch, db_path)
    r = runner.invoke(
        construction_cli.app,
        ["index", "status", "--source", "tropical-sharepoint", "--json"],
    )
    assert r.exit_code == 0
    p = json.loads(r.output)
    assert p["summary"]["sources_in_view"] == 1
    assert p["sources"][0]["source_key"] == "tropical-sharepoint"


def test_index_status_unknown_source_returns_not_found(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, db_path: str,
) -> None:
    _patch_store_to_tmp(monkeypatch, db_path)
    r = runner.invoke(
        construction_cli.app,
        ["index", "status", "--source", "does-not-exist", "--json"],
    )
    assert r.exit_code == 1
    p = json.loads(r.output)
    assert p["status"] == "not_found"
    assert "does-not-exist" in p["requested"]


def test_index_status_unsupported_operation(runner: CliRunner) -> None:
    r = runner.invoke(construction_cli.app, ["index", "purge", "--json"])
    assert r.exit_code == 1
    p = json.loads(r.output)
    assert p["status"] == "unsupported_operation"
    assert p["allowed"] == ["status"]


def test_index_status_reflects_review_queue_and_model_decisions(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, db_path: str,
) -> None:
    """End-to-end: seed via the existing review + classify CLIs, then ensure
    index status counts both surfaces."""
    _patch_store_to_tmp(monkeypatch, db_path)
    # Seed inventory + review-evaluate to put rows in the review queue
    store = ConstructionStore()
    store.upsert_inventory_item(
        source_key="tropical-sharepoint", drive_id="d", item_id="seed-1",
        name="Master Agreement.pdf", web_url="https://e/i",
        parent_path="/Tropical/Contracts/Vendors",
        size_bytes=1, is_folder=False, last_modified=None, etag=None,
    )
    r = runner.invoke(
        construction_cli.app,
        ["review", "evaluate", "--source", "tropical-sharepoint",
         "--apply", "--json"],
    )
    assert r.exit_code == 0
    # Seed a model decision
    r = runner.invoke(
        construction_cli.app,
        ["classify", "run", "--fixture", "sample", "--json"],
    )
    assert r.exit_code == 0

    r = runner.invoke(construction_cli.app, ["index", "status", "--json"])
    assert r.exit_code == 0
    p = json.loads(r.output)
    assert p["review_queue"]["open"] > 0
    assert p["model_decisions"]["accepted"] + p["model_decisions"]["review"] > 0


# ---------------------------------------------------------------------------
# top-level validate
# ---------------------------------------------------------------------------


def test_validate_clean_repo_passes(runner: CliRunner) -> None:
    r = runner.invoke(construction_cli.app, ["validate", "--json"])
    assert r.exit_code == 0, r.output
    p = json.loads(r.output)
    assert p["command"] == "construction-agent validate"
    assert p["summary"]["ok"] is True
    assert p["summary"]["failed"] == 0
    names = {c["name"] for c in p["checks"]}
    assert names == {"schema", "source_registry", "review_rules", "model_routing"}
    for c in p["checks"]:
        assert c["ok"] is True
        assert c["error"] is None


def test_validate_reports_failure_with_broken_rules(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Point HB_CONSTRUCTION_REVIEW_RULES at a broken file → validate exits 1
    with the offending check flagged."""
    bad = tmp_path / "broken.yml"
    bad.write_text(
        yaml.safe_dump({
            "rules": [{
                "rule_id": "Bad ID",  # not kebab-case → ValidationError
                "kind": "risk_term", "pattern": "x", "sensitivity": "high",
                "classification_label": "contract",
                "reason": "r", "suggested_action": "review",
            }],
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv(REVIEW_RULES_ENV, str(bad))
    r = runner.invoke(construction_cli.app, ["validate", "--json"])
    assert r.exit_code == 1, r.output
    p = json.loads(r.output)
    assert p["summary"]["ok"] is False
    failing = [c for c in p["checks"] if not c["ok"]]
    assert any(c["name"] == "review_rules" for c in failing)
    rr_check = next(c for c in p["checks"] if c["name"] == "review_rules")
    assert rr_check["error"]


# ---------------------------------------------------------------------------
# Guardrail attestations
# ---------------------------------------------------------------------------


def test_new_commands_never_advertise_writeback(runner: CliRunner) -> None:
    """No new command should ever advertise writeback != 'none' or external
    systems != 'read_only'."""
    targets = [
        ["sources", "list", "--json"],
        ["index", "status", "--json"],
        ["validate", "--json"],
    ]
    for argv in targets:
        r = runner.invoke(construction_cli.app, argv)
        assert r.exit_code in (0, 1), f"{argv} unexpectedly errored: {r.output}"
        try:
            p = json.loads(r.output)
        except json.JSONDecodeError:
            continue  # some failure modes emit non-JSON; skip
        guardrails = p.get("guardrails") or {}
        if "writeback" in guardrails:
            assert guardrails["writeback"] == "none", argv
        if "external_systems" in guardrails:
            assert guardrails["external_systems"] == "read_only", argv
