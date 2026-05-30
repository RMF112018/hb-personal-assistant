"""Phase 06B Prompt 05 — endpoint coverage matrix by family (names/types only).

Proves the coverage matrix surfaces normalizer name/version, captured-scalar / hash-only /
intentionally-omitted field NAMES, and projected entities/edges/signals — and never leaks raw
payload values. Offline; no network, no DB.
"""

from __future__ import annotations

import json
from pathlib import Path

from hb_assistant.procore import endpoints as ep_registry
from hb_assistant.procore.coverage import (
    _FAMILY_PROJECTION,
    build_coverage_matrix,
    compute_payload_coverage,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "procore_coverage"
_NOW = "2026-05-30T00:00:00+00:00"
# Synthetic markers that appear only as VALUES in the fixtures; they must never reach the matrix.
_LEAK_MARKERS = ("SYNTH", "example.test", "SYNTHSIG", "must be hashed only")


def _matrix(with_fixtures: bool = True):
    return build_coverage_matrix(
        payloads_dir=_FIXTURES if with_fixtures else None, now_utc=_NOW
    )


def _row(matrix, endpoint_id: str):
    for fam in matrix["families"].values():
        for e in fam["endpoints"]:
            if e["endpoint_id"] == endpoint_id:
                return e
    raise AssertionError(f"{endpoint_id} not in matrix")


def test_matrix_groups_all_families_and_endpoints() -> None:
    m = _matrix()
    assert m["endpoint_count"] == len(ep_registry.list_all())
    registry_families = {a.family for a in ep_registry.list_all()}
    assert set(m["families"].keys()) == registry_families
    assert m["family_count"] == len(registry_families)
    assert m["fixture_sampled_count"] == 5
    assert m["no_raw_values_persisted"] is True


def test_family_projection_map_covers_every_registry_family() -> None:
    # Drift guard: every family must have a documented projection entry.
    registry_families = {a.family for a in ep_registry.list_all()}
    assert registry_families <= set(_FAMILY_PROJECTION.keys())


def test_normalizer_meta_and_unregistered_held_endpoint() -> None:
    m = _matrix(with_fixtures=False)
    cli = _row(m, "commitment-line-items")
    assert cli["normalizer"]["registered"] is True
    assert cli["normalizer"]["normalizer_name"] == "normalize_commitment_line_item"
    assert cli["normalizer"]["normalizer_version"] == 1
    # budget-details is the held sentinel with no normalizer.
    bd = _row(m, "budget-details")
    assert bd["normalizer"]["registered"] is False
    assert bd["payload_source"] == "none" and bd["coverage"] == "contract_only"


def test_no_raw_values_anywhere_in_matrix() -> None:
    blob = json.dumps(_matrix())
    for marker in _LEAK_MARKERS:
        assert marker not in blob, f"raw value leaked: {marker}"


def test_financial_endpoint_coverage() -> None:
    r = _row(_matrix(), "commitment-line-items")
    assert r["sensitivity"] == "high" and r["payload_source"] == "fixture"
    cov = r["coverage"]
    assert {"amount", "total_amount", "wbs_flat_code"} <= set(cov["captured_scalar_fields"])
    assert "description_summary" in cov["hash_only_fields"]
    # raw free-text description is represented hash-only, never as a captured scalar.
    assert "description" not in cov["captured_scalar_fields"]
    assert "procore_financial_amount_facts" in r["projection"]["financial_tables"]


def test_high_sensitivity_endpoint_coverage() -> None:
    r = _row(_matrix(), "punch-items")
    assert r["sensitivity"] == "high" and r["review_required_default"] is True
    cov = r["coverage"]
    # all people refs + free-text are hash-only summaries, never raw.
    assert {"created_by_summary", "assignees_summary", "description_summary",
            "schedule_risk_reason_summary"} <= set(cov["hash_only_fields"])
    assert "description" not in cov["captured_scalar_fields"]
    assert "created_by" not in cov["captured_scalar_fields"]


def test_projected_containers_reported_for_enriched_family() -> None:
    cov = _row(_matrix(), "daily-log-weather")["coverage"]
    assert {"entities", "edges", "action_signals"} <= set(cov["projected_containers"])
    assert cov["entity_count"] >= 1 and cov["edge_count"] >= 1


def test_compute_payload_coverage_is_names_only() -> None:
    raw = json.loads((_FIXTURES / "rfis.json").read_text(encoding="utf-8"))
    report = compute_payload_coverage("rfis", raw, now_utc=_NOW)
    assert report["no_raw_values_persisted"] is True
    assert report["normalizer_name"] == "normalize_rfi"
    assert report["normalizer_version"] == 1
    # field-name buckets present; raw subject VALUE never present.
    assert "number" in report["captured_scalar_fields"]
    blob = json.dumps(report)
    assert "SYNTH rfi subject" not in blob
    # raw_field_paths are names + types only (no values).
    for entry in report["raw_field_paths"]:
        assert set(entry.keys()) == {"path", "type"}


def test_contract_only_without_payloads() -> None:
    m = _matrix(with_fixtures=False)
    assert m["fixture_sampled_count"] == 0
    for fam in m["families"].values():
        for e in fam["endpoints"]:
            assert e["payload_source"] == "none"
            assert e["coverage"] == "contract_only"
