"""Phase 06A — project-aware file matching (deterministic + heuristic).

Emphasis on false-positive prevention: exact project-number equality, ambiguous
multi-project signals → low_confidence, no signal → unmatched (never force-matched
to the queried project). Pure SQLite + registry; no Graph.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.graph import app
from hb_assistant.construction.config import load_source_registry
from hb_assistant.construction.graph.file_project_matcher import FileProjectMatcher
from hb_assistant.construction.source_projection import (
    project_registry_to_v5_source_locations,
)
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()

# Seed sources from the live registry: a project-bound SharePoint source (tropical)
# and an UNBOUND source (no project_key) for heuristic-only matching.
_BOUND = "sp_2023projects_23_435_01_tropical_sl"  # project_key = tropical
_UNBOUND = "od_business_bobby_hedrickbrothers"  # project_key = None


def _store(tmp_path: Path) -> ConstructionStore:
    store = ConstructionStore(str(tmp_path / "pm.sqlite"))
    project_registry_to_v5_source_locations(load_source_registry(), store)
    return store


def _add(store: ConstructionStore, source_id: str, item_id: str, name: str, path: str) -> None:
    store.upsert_drive_item(
        source_id=source_id, drive_id="D", drive_item_id=item_id,
        name=name, path=path, parent_reference_path=path, is_file=True,
    )


def _by_id(report) -> dict:
    return {r.drive_item_id: r for r in report.items}


# --- deterministic source binding ---------------------------------------------


def test_source_bound_item_matches_high_to_source_project(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add(store, _BOUND, "f1", "RFI Log.xlsx", "/drive/root:/Shared Documents/07-RFI")
    rep = FileProjectMatcher(store).match(dry_run=True)
    r = _by_id(rep)["f1"]
    assert r.project_key == "tropical" and r.match_confidence == "high"
    assert r.match_status == "matched" and not r.review_required
    assert "source_registry_project_key" in r.reason_codes


# --- heuristic on an unbound source -------------------------------------------


def test_exact_path_project_number_matches_high(tmp_path: Path) -> None:
    store = _store(tmp_path)
    # 23-435-01 is the tropical project number; on an UNBOUND source it must match by number.
    _add(store, _UNBOUND, "f2", "log.xlsx", "/OneDrive/Projects/23-435-01 Tropical/RFI")
    rep = FileProjectMatcher(store).match(dry_run=True)
    r = _by_id(rep)["f2"]
    assert r.match_confidence == "high" and r.project_key == "tropical"
    assert any(c.endswith("project_number") for c in r.reason_codes)


def test_different_project_number_does_not_false_positive(tmp_path: Path) -> None:
    store = _store(tmp_path)
    # Path carries a DIFFERENT project's number (25-244-01 = the-wellington), not tropical.
    _add(store, _UNBOUND, "f3", "doc.pdf", "/OneDrive/Projects/25-244-01 The Wellington/x")
    rep = FileProjectMatcher(store).match(dry_run=True)  # no target filter — see all results
    r = _by_id(rep)["f3"]
    # Must match the-wellington (its real number), NEVER force-matched to tropical.
    assert r.project_key == "the-wellington"
    assert r.project_key != "tropical"


def test_ambiguous_multiple_numbers_is_low_confidence(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add(store, _UNBOUND, "f4", "mix.pdf", "/OneDrive/23-435-01 and 25-244-01 combined/x")
    rep = FileProjectMatcher(store).match(dry_run=True)
    r = _by_id(rep)["f4"]
    assert r.match_status == "low_confidence" and r.review_required
    assert r.project_key is None
    assert "ambiguous_multiple_project_numbers" in r.reason_codes


def test_no_signal_is_unmatched_and_routed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add(store, _UNBOUND, "f5", "misc.pdf", "/OneDrive/Personal/Misc/notes")
    rep = FileProjectMatcher(store).match(target_project="tropical", dry_run=True)
    r = _by_id(rep)["f5"]
    assert r.match_status == "unmatched" and r.review_required
    assert r.review_reason == "unmatched_no_project"
    assert r.project_key is None  # never forced to the queried target


# --- persistence --------------------------------------------------------------


def test_dry_run_writes_no_match_fields(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add(store, _BOUND, "f1", "a.pdf", "/x")
    FileProjectMatcher(store).match(dry_run=True)
    row = store.get_drive_item(source_id=_BOUND, drive_item_id="f1")
    assert row.get("project_key") is None and row.get("match_status") is None


def test_apply_persists_match_fields(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add(store, _BOUND, "f1", "a.pdf", "/Shared Documents/07-RFI")
    _add(store, _UNBOUND, "f5", "misc.pdf", "/Personal/notes")
    FileProjectMatcher(store).match(dry_run=False)
    matches = {m["drive_item_id"]: m for m in store.list_drive_item_project_matches()}
    assert matches["f1"]["project_key"] == "tropical"
    assert matches["f1"]["match_status"] == "matched"
    assert matches["f5"]["review_required"] is True
    f1_signals = json.loads(matches["f1"]["match_signals_json"])
    assert isinstance(f1_signals, list) and "source_registry_project_key" in f1_signals


# --- CLI (offline, no token) --------------------------------------------------


def test_cli_project_match_offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = str(tmp_path / "pm.sqlite")
    seed = ConstructionStore(db)
    project_registry_to_v5_source_locations(load_source_registry(), seed)
    seed.upsert_drive_item(source_id=_BOUND, drive_id="D", drive_item_id="f1",
                           name="a.pdf", path="/Shared Documents/07-RFI", is_file=True)
    monkeypatch.setattr("hb_assistant.cli.graph.ConstructionStore", lambda *a, **k: ConstructionStore(db))
    result = runner.invoke(app, ["files", "project-match", "--project", "tropical", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "graph files project-match"
    assert payload["guardrails"]["graph_calls"] == "none"
    assert payload["result"]["mode"] == "dry_run"
