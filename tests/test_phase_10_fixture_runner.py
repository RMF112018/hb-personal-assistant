"""Phase 10 Prompt 06 — action candidate fixture-runner & validation-failure harness tests.

Covers the six-scenario matrix the prompt requires (success, blocked/high-risk routing, unavailable
dependency, invalid schema, stale schema, no-raw/no-writeback), a schema <-> Pydantic-model parity
check, low-confidence flagging, the runner's no-writeback posture, and a glob-safety regression
guaranteeing the new suite fixtures never leak into the ``ai_jobs`` fixture glob.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai import run_fixture_suite
from hb_assistant.construction.second_brain.local_ai.contracts import load_phase_10_contract
from hb_assistant.construction.second_brain.local_ai.fixture_runner_proof import (
    build_action_candidate_fixture_runner_proof,
)
from hb_assistant.construction.second_brain.local_ai.models import ActionCandidate
from hb_assistant.construction.store import ConstructionStore

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SUITE_DIR = _REPO_ROOT / "tests" / "fixtures" / "local_ai" / "fixture_suite"
_LOCAL_AI_DIR = _REPO_ROOT / "tests" / "fixtures" / "local_ai"


def _suite() -> dict:
    return run_fixture_suite(fixtures_dir=_SUITE_DIR)


def _row(suite: dict, scenario: str) -> dict:
    return next(r for r in suite["fixtures"] if r.get("scenario") == scenario)


# --------------------------------------------------------------------------------------------------
# Schema <-> model parity.
# --------------------------------------------------------------------------------------------------
def test_schema_matches_pydantic_model() -> None:
    """The published JSON schema and the ActionCandidate model must not drift apart."""
    file_schema = load_phase_10_contract("action_candidate_output_schema")
    model_schema = ActionCandidate.model_json_schema()
    assert not model_schema.get("$defs"), "enums expected inline; update parity check if $defs appear"

    # Property names agree exactly.
    assert set(file_schema["properties"]) == set(model_schema["properties"])

    # Required sets agree, modulo the const `external_action_requires_approval` (a defaulted field
    # in the model, so not "required" in the model schema, but published as required in the file).
    file_required = set(file_schema["required"]) - {"external_action_requires_approval"}
    assert file_required == set(model_schema["required"])

    # Every enum field's member set agrees between file and model.
    for name, prop in file_schema["properties"].items():
        if "enum" in prop:
            model_prop = model_schema["properties"][name]
            assert set(prop["enum"]) == set(model_prop["enum"]), f"enum drift in {name!r}"

    # The approval flag is a const-true in both.
    assert file_schema["properties"]["external_action_requires_approval"].get("const") is True
    assert model_schema["properties"]["external_action_requires_approval"].get("const") is True


# --------------------------------------------------------------------------------------------------
# Six-scenario matrix.
# --------------------------------------------------------------------------------------------------
def test_full_matrix_all_outcomes_match() -> None:
    suite = _suite()
    assert suite["count"] == 9
    assert suite["all_matched"] is True
    assert suite["high_risk_routing_ok"] is True
    assert suite["by_outcome"] == {"valid": 3, "schema_invalid": 5, "unavailable": 1}


def test_success_scenario_validates() -> None:
    row = _row(_suite(), "valid")
    assert row["status"] == "ok"
    assert row["schema_valid"] is True
    assert row["matched"] is True


def test_high_risk_routed_to_review_and_preaccept_rejected() -> None:
    suite = _suite()
    review = _row(suite, "high_risk_review")
    assert review["status"] == "ok"
    assert review["high_risk_review"] is True
    assert review["high_risk_routing_ok"] is True
    # A high-stakes candidate the model tried to pre-accept is rejected.
    preaccepted = _row(suite, "high_risk_preaccepted")
    assert preaccepted["status"] == "schema_invalid"


def test_unavailable_dependency() -> None:
    row = _row(_suite(), "unavailable_backend")
    assert row["status"] in {"unavailable", "timeout"}
    assert row["matched"] is True


def test_invalid_schema_missing_required_field() -> None:
    row = _row(_suite(), "missing_required_field")
    assert row["status"] == "schema_invalid"
    assert row["schema_valid"] is False


def test_stale_forbidden_field_rejected() -> None:
    row = _row(_suite(), "stale_forbidden_field")
    assert row["status"] == "schema_invalid"


def test_malformed_json_rejected() -> None:
    row = _row(_suite(), "malformed_json")
    assert row["status"] == "schema_invalid"


def test_no_accepted_action_without_source_refs() -> None:
    row = _row(_suite(), "empty_source_refs")
    assert row["status"] == "schema_invalid"


def test_low_confidence_is_flagged() -> None:
    row = _row(_suite(), "low_confidence")
    assert row["status"] == "ok"
    assert row["low_confidence"] is True


# --------------------------------------------------------------------------------------------------
# No-raw / no-writeback.
# --------------------------------------------------------------------------------------------------
def test_dry_run_with_store_writes_nothing() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "p10p06.db")
        store = ConstructionStore(db_path=db)
        suite = run_fixture_suite(fixtures_dir=_SUITE_DIR, store=store, dry_run=True)
        assert suite["all_matched"] is True
        receipts = store.list_local_model_run_receipts()
        assert receipts == [] or len(receipts) == 0
        # The forbidden-field placeholder must never reach a persisted row.
        assert "PLACEHOLDER_REJECTED_NEVER_PERSISTED" not in json.dumps(receipts)
        # And every row carries no receipt id (nothing was written).
        assert all(r.get("receipt_id") is None for r in suite["fixtures"])


def test_runner_surfaces_only_hashes_not_raw() -> None:
    blob = json.dumps(_suite())
    assert "PLACEHOLDER_REJECTED_NEVER_PERSISTED" not in blob
    assert "not valid json" not in blob  # the malformed payload itself is never echoed back


# --------------------------------------------------------------------------------------------------
# Glob-safety regression: suite fixtures must not leak into the ai_jobs fixture glob.
# --------------------------------------------------------------------------------------------------
def test_suite_fixtures_excluded_from_ai_jobs_glob() -> None:
    from hb_assistant.construction.second_brain.local_ai import ai_jobs

    loaded = ai_jobs._load_fixtures(str(_LOCAL_AI_DIR), 1000)
    ids = {f.get("fixture_id") for f in loaded}
    # The original four flat fixtures only; no suite_* fixtures from the subdirectory.
    assert len(loaded) == 4
    assert not any(str(i).startswith("suite_") for i in ids)


# --------------------------------------------------------------------------------------------------
# Proof builder.
# --------------------------------------------------------------------------------------------------
def test_proof_passes_all_gates() -> None:
    proof = build_action_candidate_fixture_runner_proof(write_evidence=False)
    assert proof["proof_passed"] is True
    assert proof["guard_sum"] == 0
    assert proof["dry_run_receipt_rows"] == 0
    assert all(proof["gates"].values())
