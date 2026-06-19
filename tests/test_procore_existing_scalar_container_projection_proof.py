from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scripts.proofs import procore_existing_scalar_container_projection_proof as proof


def _inventory(path: Path, *, reuse_count: int = proof.EXPECTED_REUSE_TARGETS) -> Path:
    fields = [
        {
            "table": "procore_ep_example",
            "column": f"container_{idx}",
            "endpoint_key": "example-endpoint",
            "future_recommendation": "reuse_existing_scalar_decomposition_columns",
            "existing_scalar_decomposition_columns": [f"container_{idx}_id"],
        }
        for idx in range(reuse_count)
    ]
    fields.extend(
        [
            {
                "table": "procore_ep_example_children",
                "column": "payload",
                "endpoint_key": "example-endpoint",
                "future_recommendation": "represent_only_in_child_table",
                "existing_scalar_decomposition_columns": ["payload_id"],
            },
            {
                "table": "procore_ep_example",
                "column": "company_id",
                "endpoint_key": "example-endpoint",
                "future_recommendation": "company_id_policy_deferred",
                "existing_scalar_decomposition_columns": [],
            },
        ]
    )
    payload = {"fields": fields}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _make_db(path: Path) -> Path:
    conn = sqlite3.connect(path)
    columns = ["record_key TEXT PRIMARY KEY"]
    for idx in range(proof.EXPECTED_REUSE_TARGETS):
        columns.extend([f"container_{idx} TEXT", f"container_{idx}_id TEXT"])
    conn.execute(f"CREATE TABLE procore_ep_example ({', '.join(columns)})")
    values = {"record_key": "row-1"}
    for idx in range(proof.EXPECTED_REUSE_TARGETS):
        values[f"container_{idx}"] = None
        values[f"container_{idx}_id"] = None
    cols = list(values)
    conn.execute(
        f"INSERT INTO procore_ep_example ({', '.join(cols)}) "
        f"VALUES ({', '.join('?' for _ in cols)})",
        tuple(values[col] for col in cols),
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
    payload = {f"container_{idx}": {"id": idx} for idx in range(proof.EXPECTED_REUSE_TARGETS)}
    payload["container_1"] = {}
    conn.execute(
        """
        INSERT INTO procore_endpoint_raw_payloads (
          raw_payload_id, endpoint_key, payload_json, is_current,
          raw_procore_payload_persisted, source_quality
        ) VALUES ('raw-1', 'example-endpoint', ?, 1, 1, 'live_full_payload')
        """,
        (json.dumps(payload),),
    )
    conn.commit()
    conn.close()
    return path


def _install_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = SimpleNamespace(
        endpoint_id="example-endpoint",
        endpoint_family="example",
        primary_table="procore_ep_example",
        primary_columns=tuple(
            (f"container_{idx}.id", f"container_{idx}_id")
            for idx in range(proof.EXPECTED_REUSE_TARGETS)
        ),
        child_tables=(),
    )
    monkeypatch.setattr(proof.projection_registry, "load_registry", lambda: {"example-endpoint": plan})


def _counts(*, replayed: bool) -> dict[str, Any]:
    return {
        "fields": [
            {
                "table": "procore_ep_example",
                "bare_column": "container_0",
                "endpoint_key": "example-endpoint",
                "bare_column_non_null_count": 0,
                "scalar_columns": [
                    {
                        "column": "container_0_id",
                        "non_null_count": 1 if replayed else 0,
                    }
                ],
            },
            {
                "table": "procore_ep_example",
                "bare_column": "container_1",
                "endpoint_key": "example-endpoint",
                "bare_column_non_null_count": 0,
                "scalar_columns": [
                    {
                        "column": "container_1_id",
                        "non_null_count": 0,
                    }
                ],
            },
        ]
    }


def test_patch4_inventory_fails_closed_unless_exactly_35_reuse_targets(
    tmp_path: Path,
) -> None:
    with pytest.raises(proof.ProofError):
        proof.load_patch3_targets(_inventory(tmp_path / "too-small.json", reuse_count=34))

    targets = proof.load_patch3_targets(_inventory(tmp_path / "ok.json"))

    assert len(targets) == proof.EXPECTED_REUSE_TARGETS
    assert {target["future_recommendation"] for target in targets} == {
        "reuse_existing_scalar_decomposition_columns"
    }
    assert all(target["column"] != "company_id" for target in targets)


def test_collect_inventory_is_body_free_and_excludes_non_reuse_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_registry(monkeypatch)
    payload = proof.collect_inventory(
        db_path=_make_db(tmp_path / "proof.sqlite"),
        inventory_json=_inventory(tmp_path / "inventory.json"),
    )

    assert payload["target_field_count"] == proof.EXPECTED_REUSE_TARGETS
    first = payload["fields"][0]
    assert first["bare_column_registry_mapped"] is False
    assert first["scalar_columns"][0]["registry_mapped"] is True
    assert first["scalar_columns"][0]["source_path_check"]["path_non_empty_count"] == 1

    dumped = json.dumps(payload)
    assert "sample_value" not in dumped
    assert "raw_payload_values_emitted" in dumped
    assert "example.invalid" not in dumped


def test_source_absent_scalar_is_not_classified_as_covered() -> None:
    inventory = {
        "fields": [
            {
                "table": "procore_ep_example",
                "bare_column": "container_0",
                "endpoint_key": "example-endpoint",
                "scalar_columns": [
                    {
                        "column": "container_0_id",
                        "column_exists": True,
                        "registry_mapped": True,
                        "registry_json_path": "$.container_0.id",
                        "source_path_check": {"path_non_empty_count": 1},
                    }
                ],
            },
            {
                "table": "procore_ep_example",
                "bare_column": "container_1",
                "endpoint_key": "example-endpoint",
                "scalar_columns": [
                    {
                        "column": "container_1_id",
                        "column_exists": True,
                        "registry_mapped": True,
                        "registry_json_path": "$.container_1.id",
                        "source_path_check": {"path_non_empty_count": 0},
                    }
                ],
            },
        ]
    }

    result = proof.classify_results(
        inventory=inventory,
        reset_counts=_counts(replayed=False),
        post_counts=_counts(replayed=True),
    )

    by_column = {field["bare_column"]: field for field in result["fields"]}
    assert (
        by_column["container_0"]["post_proof_decision"]["decision_class"]
        == "covered_by_existing_scalar_decomposition_columns"
    )
    assert (
        by_column["container_1"]["post_proof_decision"]["decision_class"]
        == "needs_endpoint_specific_review"
    )
    assert by_column["container_1"]["scalar_columns"][0]["status"] == (
        "source_absent_for_specific_scalar_column"
    )
    assert result["parent_status_counts"] == {
        "covered_by_existing_scalar_decomposition_columns": 1,
        "needs_endpoint_specific_review": 1,
    }
