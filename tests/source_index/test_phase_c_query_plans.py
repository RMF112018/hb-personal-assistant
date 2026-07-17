"""PC-WI-01 Stage-2 — representative query plans.

Representative read queries against a head database use acceptable indexes rather than full-table
scans (PC-AC-026). Plans are captured read-only via ``EXPLAIN QUERY PLAN``.
"""

from __future__ import annotations

from hb_assistant.store.source_index_migration_assurance import (
    plan_has_unindexed_scan,
    plan_uses_index,
    query_plan,
)
from tests.support.source_index_migration_fixture import HEAD_VERSION, build_fixture


def test_root_scoped_lookup_uses_root_relpath_index(tmp_path):
    res = build_fixture(tmp_path, HEAD_VERSION, row_count=6)
    plan = query_plan(
        res.db_path,
        "SELECT source_id FROM source_intelligence_sources "
        "WHERE source_kind = ? AND source_root_key = ? AND rel_path = ?",
        ("external_file", "root-a", "docs/a.md"),
    )
    assert plan_uses_index(plan, "idx_si_sources_root_relpath"), plan
    assert not plan_has_unindexed_scan(plan), plan


def test_active_generation_lookup_avoids_full_scan(tmp_path):
    res = build_fixture(tmp_path, HEAD_VERSION, row_count=6)
    plan = query_plan(
        res.db_path,
        "SELECT generation_id FROM source_index_scan_generations "
        "WHERE root_key = ? AND status = 'running'",
        ("root-a",),
    )
    assert not plan_has_unindexed_scan(plan), plan
