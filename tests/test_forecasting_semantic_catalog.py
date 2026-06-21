"""Semantic catalog YAML presence and parseability."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = REPO_ROOT / "docs" / "forecasting" / "semantic-catalog"

REQUIRED_YAML = [
    "semantic_catalog.yml",
    "procore_budget_semantics.yml",
    "procore_commitment_semantics.yml",
    "procore_purchase_order_semantics.yml",
    "procore_prime_contract_semantics.yml",
    "procore_change_event_semantics.yml",
    "procore_invoice_semantics.yml",
    "forecast_internal_semantics.yml",
    "normalization_rules.yml",
    "double_count_prevention_model.yml",
    "actuals_precedence_model.yml",
    "budget_column_roles.yml",
    "budget_dynamic_columns.yml",
]


def test_required_semantic_yaml_files_exist_and_parse() -> None:
    for name in REQUIRED_YAML:
        path = CATALOG_DIR / name
        assert path.exists(), name
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), name


def test_validation_sql_files_exist() -> None:
    sql_dir = CATALOG_DIR / "validation_queries"
    for name in (
        "double_count_prevention.sql",
        "purchase_order_relationships.sql",
        "actuals_reconciliation.sql",
        "projection_parity.sql",
        "cost_type_mapping_guard.sql",
        "budget_dynamic_columns.sql",
    ):
        assert (sql_dir / name).exists(), name