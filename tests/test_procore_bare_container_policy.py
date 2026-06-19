from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.proofs import procore_bare_container_policy as policy
from scripts.proofs import procore_null_projection_audit as null_audit


def _patch4(path: Path, *, covered_count: int = 31) -> Path:
    fields = []
    for idx in range(covered_count):
        fields.append(
            {
                "table": "procore_ep_example",
                "bare_column": f"covered_{idx}",
                "endpoint_key": "example",
                "bare_column_non_null_after_replay": 2 if idx == 0 else 0,
                "post_proof_decision": {
                    "decision_class": "covered_by_existing_scalar_decomposition_columns",
                    "mapping_candidate": False,
                },
                "scalar_columns": [
                    {
                        "column": f"covered_{idx}_id",
                        "registry_json_path": f"$.covered_{idx}.id",
                        "source_non_empty_count": 1,
                        "after_replay_non_null_count": 1,
                        "status": "already_replays_existing_scalar_columns",
                    }
                ],
                "raw_payload_values_emitted": False,
            }
        )
    for idx in range(4):
        scalars = [
            {
                "column": f"partial_{idx}_id",
                "registry_json_path": f"$.partial_{idx}.id",
                "source_non_empty_count": 1,
                "after_replay_non_null_count": 1,
                "status": "already_replays_existing_scalar_columns",
            },
            {
                "column": f"partial_{idx}_missing",
                "registry_json_path": f"$.partial_{idx}.missing",
                "source_non_empty_count": 0,
                "after_replay_non_null_count": 0,
                "status": "source_absent_for_specific_scalar_column",
            },
        ]
        if idx == 0:
            scalars.append(
                {
                    "column": "partial_0_missing_extra",
                    "registry_json_path": "$.partial_0.missing_extra",
                    "source_non_empty_count": 0,
                    "after_replay_non_null_count": 0,
                    "status": "source_absent_for_specific_scalar_column",
                }
            )
        fields.append(
            {
                "table": "procore_ep_example",
                "bare_column": f"partial_{idx}",
                "endpoint_key": "example",
                "bare_column_non_null_after_replay": 0,
                "post_proof_decision": {
                    "decision_class": "partially_covered_existing_scalar_columns",
                    "mapping_candidate": False,
                },
                "scalar_columns": scalars,
                "raw_payload_values_emitted": False,
            }
        )
    path.write_text(json.dumps({"fields": fields}), encoding="utf-8")
    return path


def _patch5(path: Path) -> Path:
    fields = []
    for idx in range(3):
        fields.append(
            {
                "table": "procore_ep_purchase_order_contracts",
                "bare_column": f"custom_fields_custom_field_21407{idx}_value",
                "endpoint_key": "purchase-order-contracts",
                "bare_column_non_null_after_replay": 0,
                "post_proof_decision": {
                    "decision_class": "covered_by_existing_scalar_decomposition_columns",
                    "mapping_candidate": False,
                },
                "scalar_columns": [
                    {
                        "column": f"custom_fields_custom_field_21407{idx}_value_id",
                        "registry_json_path": f"$.custom_fields.custom_field_21407{idx}.value.id",
                        "source_non_empty_count": 1,
                        "after_replay_non_null_count": 1,
                        "status": "already_replays_existing_scalar_columns",
                    }
                ],
                "raw_payload_values_emitted": False,
            }
        )
    path.write_text(json.dumps({"fields": fields}), encoding="utf-8")
    return path


def _patch3(path: Path) -> Path:
    fields = [
        {
            "table": "procore_ep_child",
            "column": f"child_{idx}",
            "endpoint_key": "child-endpoint",
            "future_recommendation": "represent_only_in_child_table",
        }
        for idx in range(3)
    ]
    fields.extend(
        {
            "table": "procore_ep_entity",
            "column": f"entity_{idx}",
            "endpoint_key": "entity-endpoint",
            "future_recommendation": "represent_only_in_entity_dimension",
        }
        for idx in range(2)
    )
    path.write_text(json.dumps({"fields": fields}), encoding="utf-8")
    return path


def test_policy_rollups_are_nonduplicative_and_body_free(tmp_path: Path) -> None:
    result = policy.build_policy(
        patch4_summary=_patch4(tmp_path / "patch4.json"),
        patch5_summary=_patch5(tmp_path / "patch5.json"),
        patch3_inventory=_patch3(tmp_path / "patch3.json"),
    )

    summary = result["summary"]
    assert summary["covered_total"] == 34
    assert summary["covered_non_custom"] == 31
    assert summary["covered_custom"] == 3
    assert summary["partial"] == 4
    assert summary["source_absent_scalar_leaves"] == 5
    assert summary["child_entity_deferred"] == 5
    assert summary["high_confidence_mapping_candidates"] == 0
    assert summary["projection_code_repair_candidates"] == 0
    assert summary["date_datetime_mapping_candidates"] == 0
    assert summary["covered_subtype_counts"][
        "bare_container_custom_field_covered_by_scalar_decomposition"
    ] == 3

    dumped = json.dumps(result)
    assert "sample_value" not in dumped
    assert "raw_payload_values_emitted" in dumped


def test_covered_fields_are_dispositioned_but_not_actionable(tmp_path: Path) -> None:
    result = policy.build_policy(
        patch4_summary=_patch4(tmp_path / "patch4.json"),
        patch5_summary=_patch5(tmp_path / "patch5.json"),
        patch3_inventory=_patch3(tmp_path / "patch3.json"),
    )
    first = result["deprecated_covered"]["fields"][0]
    decision = first["post_proof_decision"]

    assert decision["mapping_candidate"] is False
    assert decision["projection_code_repair_candidate"] is False
    assert decision["deprecation_candidate"] is True
    assert decision["suppress_from_actionable_mapping_rollup"] is True
    assert first["legacy_non_null_bare_container_values_present"] is True
    assert decision["legacy_non_null_bare_container_values_present"] is True
    assert result["actionable_rollup"]["covered_bare_containers_visible_in_disposition_evidence"] == 34
    assert result["actionable_rollup"]["covered_bare_containers_suppressed_from_actionable_mapping_rollup"] == 34


def test_partial_fields_keep_source_absent_scalars_separate(tmp_path: Path) -> None:
    result = policy.build_policy(
        patch4_summary=_patch4(tmp_path / "patch4.json"),
        patch5_summary=_patch5(tmp_path / "patch5.json"),
        patch3_inventory=_patch3(tmp_path / "patch3.json"),
    )
    partial = result["partially_covered"]["fields"][0]

    assert (
        partial["post_proof_decision"]["decision_class"]
        == "bare_container_partially_covered_scalar_source_absent"
    )
    assert partial["post_proof_decision"]["mapping_candidate"] is False
    assert len(partial["source_absent_scalar_columns"]) == 2
    assert all(
        scalar["status"] == "source_absent_for_specific_scalar_column"
        for scalar in partial["source_absent_scalar_columns"]
    )


def test_policy_fails_closed_on_count_drift(tmp_path: Path) -> None:
    with pytest.raises(policy.PolicyError):
        policy.build_policy(
            patch4_summary=_patch4(tmp_path / "patch4.json", covered_count=30),
            patch5_summary=_patch5(tmp_path / "patch5.json"),
            patch3_inventory=_patch3(tmp_path / "patch3.json"),
        )


def test_null_audit_accepts_bare_column_source_proof_and_preserves_flags(
    tmp_path: Path,
) -> None:
    source_proof = {
        "fields": [
            {
                "table": "procore_ep_example",
                "bare_column": "container",
                "post_proof_decision": {
                    "decision_class": "bare_container_deprecated_covered_by_scalar_decomposition",
                    "decision_status": "reporting_policy_deprecation_candidate",
                    "mapping_candidate": False,
                    "projection_code_repair_candidate": False,
                    "deprecation_candidate": True,
                    "suppress_from_actionable_mapping_rollup": True,
                    "next_action": "no_action_existing_scalar_decomposition_verified",
                    "evidence_basis": "test evidence",
                },
            }
        ]
    }
    path = tmp_path / "source-proof.json"
    path.write_text(json.dumps(source_proof), encoding="utf-8")

    decisions = null_audit._source_proof_decisions(path)  # noqa: SLF001
    normalized = null_audit._normalized_post_proof_decision(  # noqa: SLF001
        decisions[("procore_ep_example", "container")]
    )

    assert normalized["mapping_candidate"] is False
    assert normalized["projection_code_repair_candidate"] is False
    assert normalized["deprecation_candidate"] is True
    assert normalized["suppress_from_actionable_mapping_rollup"] is True
