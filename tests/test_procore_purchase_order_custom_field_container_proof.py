from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scripts.proofs import procore_purchase_order_custom_field_container_proof as proof


def _inventory(path: Path, *, include_all: bool = True, extra: bool = False) -> Path:
    fields = []
    targets = list(proof.TARGET_SCALARS)
    if not include_all:
        targets = targets[:-1]
    for column in targets:
        fields.append(
            {
                "table": proof.TABLE,
                "column": column,
                "endpoint_key": proof.ENDPOINT,
                "future_recommendation": "needs_additional_source_sample",
                "existing_scalar_decomposition_columns": proof.TARGET_SCALARS[column],
            }
        )
    if extra:
        fields.append(
            {
                "table": proof.TABLE,
                "column": "custom_fields_custom_field_999999_value",
                "endpoint_key": proof.ENDPOINT,
                "future_recommendation": "needs_additional_source_sample",
                "existing_scalar_decomposition_columns": [
                    "custom_fields_custom_field_999999_value_id"
                ],
            }
        )
    fields.extend(
        [
            {
                "table": "procore_ep_rfis",
                "column": "ball_in_court",
                "endpoint_key": "rfis",
                "future_recommendation": "reuse_existing_scalar_decomposition_columns",
                "existing_scalar_decomposition_columns": ["ball_in_court_id"],
            },
            {
                "table": "procore_ep_projects",
                "column": "company_id",
                "endpoint_key": "projects",
                "future_recommendation": "company_id_policy_deferred",
                "existing_scalar_decomposition_columns": [],
            },
            {
                "table": "procore_ep_budget_detail_rows",
                "column": "actual_cost",
                "endpoint_key": "budget-detail-rows",
                "future_recommendation": "budget_detail_dead_convenience_column",
                "existing_scalar_decomposition_columns": [],
            },
        ]
    )
    path.write_text(json.dumps({"fields": fields}), encoding="utf-8")
    return path


def _make_db(path: Path) -> Path:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE procore_ep_purchase_order_contracts (
          record_key TEXT PRIMARY KEY,
          custom_fields_custom_field_214072_value TEXT,
          custom_fields_custom_field_214072_value_id TEXT,
          custom_fields_custom_field_214072_value_label TEXT,
          custom_fields_custom_field_214078_value TEXT,
          custom_fields_custom_field_214078_value_company_name TEXT,
          custom_fields_custom_field_214078_value_id TEXT,
          custom_fields_custom_field_214078_value_label TEXT,
          custom_fields_custom_field_214087_value TEXT,
          custom_fields_custom_field_214087_value_id TEXT,
          custom_fields_custom_field_214087_value_label TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO procore_ep_purchase_order_contracts (
          record_key,
          custom_fields_custom_field_214072_value_id,
          custom_fields_custom_field_214078_value_company_name,
          custom_fields_custom_field_214078_value_id,
          custom_fields_custom_field_214087_value_id
        ) VALUES ('row-1', NULL, NULL, NULL, NULL)
        """
    )
    conn.execute(
        """
        CREATE TABLE procore_endpoint_raw_payloads (
          raw_payload_id TEXT PRIMARY KEY,
          endpoint_key TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          is_current INTEGER NOT NULL,
          raw_procore_payload_persisted INTEGER NOT NULL,
          source_quality TEXT NOT NULL
        )
        """
    )
    payload = {
        "custom_fields": {
            "custom_field_214072": {"value": {"id": 72, "label": "redacted"}},
            "custom_field_214078": {
                "value": {"id": 78, "company_name": "redacted", "label": "redacted"}
            },
            "custom_field_214087": {"value": {}},
        }
    }
    conn.execute(
        """
        INSERT INTO procore_endpoint_raw_payloads (
          raw_payload_id, endpoint_key, payload_json, is_current,
          raw_procore_payload_persisted, source_quality
        ) VALUES ('raw-1', 'purchase-order-contracts', ?, 1, 1, 'live_full_payload')
        """,
        (json.dumps(payload),),
    )
    conn.commit()
    conn.close()
    return path


def _install_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    columns = [
        ("custom_fields.custom_field_214072.value.id", "custom_fields_custom_field_214072_value_id"),
        (
            "custom_fields.custom_field_214072.value.label",
            "custom_fields_custom_field_214072_value_label",
        ),
        (
            "custom_fields.custom_field_214078.value.company_name",
            "custom_fields_custom_field_214078_value_company_name",
        ),
        ("custom_fields.custom_field_214078.value.id", "custom_fields_custom_field_214078_value_id"),
        (
            "custom_fields.custom_field_214078.value.label",
            "custom_fields_custom_field_214078_value_label",
        ),
        ("custom_fields.custom_field_214087.value.id", "custom_fields_custom_field_214087_value_id"),
        (
            "custom_fields.custom_field_214087.value.label",
            "custom_fields_custom_field_214087_value_label",
        ),
    ]
    plan = SimpleNamespace(primary_columns=tuple(columns))
    monkeypatch.setattr(proof.projection_registry, "plan_for", lambda endpoint: plan)


def _counts(*, replayed: bool) -> dict[str, Any]:
    def scalar(column: str, value: int) -> dict[str, Any]:
        return {"column": column, "non_null_count": value}

    return {
        "fields": [
            {
                "bare_column": "custom_fields_custom_field_214072_value",
                "bare_column_non_null_count": 0,
                "scalar_columns": [
                    scalar("custom_fields_custom_field_214072_value_id", 1 if replayed else 0)
                ],
            },
            {
                "bare_column": "custom_fields_custom_field_214078_value",
                "bare_column_non_null_count": 0,
                "scalar_columns": [
                    scalar(
                        "custom_fields_custom_field_214078_value_company_name",
                        1 if replayed else 0,
                    ),
                    scalar("custom_fields_custom_field_214078_value_id", 1 if replayed else 0),
                ],
            },
            {
                "bare_column": "custom_fields_custom_field_214087_value",
                "bare_column_non_null_count": 0,
                "scalar_columns": [
                    scalar("custom_fields_custom_field_214087_value_id", 0),
                ],
            },
        ]
    }


def test_patch5_target_selection_fails_closed_for_missing_or_extra_targets(
    tmp_path: Path,
) -> None:
    with pytest.raises(proof.ProofError):
        proof.load_patch3_targets(_inventory(tmp_path / "missing.json", include_all=False))

    with pytest.raises(proof.ProofError):
        proof.load_patch3_targets(_inventory(tmp_path / "extra.json", extra=True))

    targets = proof.load_patch3_targets(_inventory(tmp_path / "ok.json"))

    assert len(targets) == 3
    assert {target["column"] for target in targets} == set(proof.TARGET_SCALARS)


def test_collect_inventory_is_body_free_and_keeps_siblings_comparative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_registry(monkeypatch)

    payload = proof.collect_inventory(
        db_path=_make_db(tmp_path / "proof.sqlite"),
        inventory_json=_inventory(tmp_path / "inventory.json"),
    )

    assert payload["target_container_count"] == 3
    assert payload["target_scalar_count"] == 4
    by_column = {field["bare_column"]: field for field in payload["fields"]}
    target = by_column["custom_fields_custom_field_214072_value"]
    assert target["scalar_columns"][0]["registry_mapped"] is True
    assert target["scalar_columns"][0]["source_path_check"]["path_non_empty_count"] == 1
    assert target["comparative_sibling_columns"] == [
        {
            "column": "custom_fields_custom_field_214072_value_label",
            "registry_json_path": "$.custom_fields.custom_field_214072.value.label",
            "scope": "out_of_scope_comparative_metadata",
        }
    ]

    dumped = json.dumps(payload)
    assert "sample_value" not in dumped
    assert "redacted" not in dumped
    assert "raw_payload_values_emitted" in dumped


def test_source_absent_scalar_leaf_is_not_covered() -> None:
    inventory = {
        "fields": [
            {
                "bare_column": "custom_fields_custom_field_214072_value",
                "container_path_check": {"path_non_empty_count": 1, "shape_counts": {"object": 1}},
                "scalar_columns": [
                    {
                        "column": "custom_fields_custom_field_214072_value_id",
                        "column_exists": True,
                        "registry_mapped": True,
                        "registry_json_path": "$.custom_fields.custom_field_214072.value.id",
                        "source_path_check": {"path_non_empty_count": 1},
                    }
                ],
                "comparative_sibling_columns": [],
            },
            {
                "bare_column": "custom_fields_custom_field_214078_value",
                "container_path_check": {"path_non_empty_count": 1, "shape_counts": {"object": 1}},
                "scalar_columns": [
                    {
                        "column": "custom_fields_custom_field_214078_value_company_name",
                        "column_exists": True,
                        "registry_mapped": True,
                        "registry_json_path": "$.custom_fields.custom_field_214078.value.company_name",
                        "source_path_check": {"path_non_empty_count": 1},
                    },
                    {
                        "column": "custom_fields_custom_field_214078_value_id",
                        "column_exists": True,
                        "registry_mapped": True,
                        "registry_json_path": "$.custom_fields.custom_field_214078.value.id",
                        "source_path_check": {"path_non_empty_count": 1},
                    },
                ],
                "comparative_sibling_columns": [],
            },
            {
                "bare_column": "custom_fields_custom_field_214087_value",
                "container_path_check": {"path_non_empty_count": 1, "shape_counts": {"object": 1}},
                "scalar_columns": [
                    {
                        "column": "custom_fields_custom_field_214087_value_id",
                        "column_exists": True,
                        "registry_mapped": True,
                        "registry_json_path": "$.custom_fields.custom_field_214087.value.id",
                        "source_path_check": {"path_non_empty_count": 0},
                    }
                ],
                "comparative_sibling_columns": [],
            },
        ]
    }

    result = proof.classify_results(
        inventory=inventory,
        reset_counts=_counts(replayed=False),
        post_counts=_counts(replayed=True),
    )

    by_field = {field["bare_column"]: field for field in result["fields"]}
    assert (
        by_field["custom_fields_custom_field_214072_value"]["post_proof_decision"][
            "decision_class"
        ]
        == "covered_by_existing_scalar_decomposition_columns"
    )
    assert (
        by_field["custom_fields_custom_field_214087_value"]["post_proof_decision"][
            "decision_class"
        ]
        == "custom_field_metadata_missing"
    )
    assert by_field["custom_fields_custom_field_214087_value"]["scalar_columns"][0][
        "status"
    ] == "source_absent_for_specific_scalar_column"
