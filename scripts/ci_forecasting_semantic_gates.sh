#!/usr/bin/env bash
# CI-safe forecasting semantic gate checks. No live DB, Procore, or SchemaCrawler required.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export HB_FORECASTING_EVIDENCE_SKIP_NO_RAW=1

pytest tests/test_forecasting_field_classifiers.py \
       tests/test_forecasting_db_evidence_package.py \
       tests/test_forecasting_gates.py \
       tests/test_forecasting_runtime_normalization.py \
       tests/test_forecasting_semantic_catalog.py \
       tests/test_forecasting_external_fixture.py \
       tests/test_forecasting_evidence_script_integration.py \
       tests/test_forecasting_readiness.py \
       tests/test_forecasting_projection_parity_keys.py \
       tests/test_forecasting_project_eligibility.py \
       tests/test_procore_normalizers_financial_amounts.py \
       -q

ruff check src/hb_assistant/forecasting/ tests/test_forecasting_*.py