#!/usr/bin/env bash
# Source-index correctness & trust gate (Phase A).
#
# CI-safe: scratch SQLite + temp roots + mocked FS failures only. No live NAS, production DB, MCP
# snapshot, watcher activation against a real root, or network is required. Covers the four Phase A
# defects (A1 vault deletion safety, A3 canonical root mapping, A2 root trust, A4 poison-file quarantine),
# plus generation hardening, migrations, watcher lifecycle, connector serving, and the tool-surface /
# manifest parity guards that A2's docstring changes touch.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Mirror the repo's documented focused-run PYTHONPATH (src + the financial-review subrepo).
export PYTHONPATH="src:subrepos/construction-financial-review/src${PYTHONPATH:+:$PYTHONPATH}"

pytest -p no:cacheprovider -q \
  tests/test_source_index_vault_deletion_safety.py \
  tests/test_source_root_mapping.py \
  tests/test_source_root_trust.py \
  tests/test_source_index_quarantine.py \
  tests/test_source_index_quarantine_lifecycle.py \
  tests/test_source_index_generation_hardening.py \
  tests/test_source_index_metadata_first_bootstrap.py \
  tests/test_source_index_metadata_generation.py \
  tests/test_migrator_v117_source_index_bootstrap.py \
  tests/test_migrator_v123_relpath_index.py \
  tests/test_obsidian_source_watch.py \
  tests/test_obsidian_source_watch_lifecycle.py \
  tests/test_obsidian_source_watch_ownership.py \
  tests/test_obsidian_source_watch_reliability.py \
  tests/test_source_index_watcher_automated_refresh.py \
  tests/test_source_connector_service.py \
  tests/test_nas_mcp_source_connector.py \
  tests/test_source_connector_eval.py \
  tests/test_source_index_health_readonly_conn.py \
  tests/test_tool_manifest_freshness_guard.py \
  tests/test_n8c23_client_tool_manifest.py \
  tests/test_manifest_schema_parity.py \
  --deselect tests/test_source_connector_eval.py::test_all_source_tools_have_disambiguating_descriptions
  # ^ deselected: a PRE-EXISTING failure that reproduces on pristine origin/main (9c27839b) — the
  #   `assistant_source_index_health` tool description lacks a "vault"/"card" contrast word. It is unrelated
  #   to Phase A (that tool's description was never touched here); fixing it is an out-of-scope tool-surface
  #   change. Tracked as pre-existing debt in docs/evidence/source-index-phase-a/08-baseline-vs-feature-failures.md.

# Lint the source-index implementation + its tests. `ruff check` only (lint), NOT `ruff format --check`:
# some source-index modules pre-date the repo's formatter adoption and must not be reformatted here.
ruff check \
  src/hb_assistant/obsidian_mcp/source_indexer.py \
  src/hb_assistant/obsidian_mcp/source_connector_service.py \
  src/hb_assistant/obsidian_mcp/source_content_provider.py \
  src/hb_assistant/obsidian_mcp/source_health_service.py \
  src/hb_assistant/obsidian_mcp/source_index_repository.py \
  src/hb_assistant/obsidian_mcp/source_project_number.py \
  src/hb_assistant/obsidian_mcp/source_bootstrap.py \
  src/hb_assistant/obsidian_mcp/source_watch.py \
  src/hb_assistant/obsidian_mcp/source_root_trust.py \
  src/hb_assistant/obsidian_mcp/source_root_mapping.py \
  src/hb_assistant/obsidian_mcp/source_quarantine_ops.py \
  src/hb_assistant/store/migrator.py \
  src/hb_assistant/store/source_index_scan_generations_repository.py \
  src/hb_assistant/store/source_index_scan_quarantine_repository.py \
  src/hb_assistant/store/source_index_scan_quarantine_tables.py \
  src/hb_assistant/cli/source_watch.py \
  tests/test_source_index_vault_deletion_safety.py \
  tests/test_source_root_mapping.py \
  tests/test_source_root_trust.py \
  tests/test_source_index_quarantine.py \
  tests/test_source_index_quarantine_lifecycle.py
