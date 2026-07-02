"""Supplemental purge dependency ordering for schedule clean-DB (SQLite FK gaps)."""

from __future__ import annotations

# child_table -> parent_table (delete child before parent)
SUPPLEMENTAL_DELETE_EDGES: list[tuple[str, str]] = [
    ("project_schedule_review_events", "project_schedule_review_items"),
    ("project_schedule_named_baseline_review_events", "project_schedule_named_baseline_review_items"),
    ("project_schedule_baseline_selections", "schedule_file_imports"),
    ("project_schedule_series_membership", "schedule_file_imports"),
    ("schedule_cpm_import_observability", "schedule_file_imports"),
    ("schedule_cpm_path_activities", "schedule_cpm_runs"),
    ("schedule_cpm_paths", "schedule_cpm_runs"),
    ("schedule_cpm_relationship_results", "schedule_cpm_runs"),
    ("schedule_cpm_activity_results", "schedule_cpm_runs"),
    ("schedule_cpm_diagnostics", "schedule_cpm_runs"),
    ("schedule_cpm_runs", "schedule_file_imports"),
    ("schedule_import_package_files", "schedule_import_packages"),
    ("schedule_package_equivalence_facts", "schedule_import_packages"),
    ("schedule_package_field_lineage", "schedule_import_packages"),
    ("schedule_version_diff_detail_facts", "schedule_version_diffs"),
    ("schedule_version_diff_impact_rollups", "schedule_version_diffs"),
    ("schedule_version_diff_facts", "schedule_version_diffs"),
    ("procore_ep_schedule_activities", "schedule_file_imports"),
    ("procore_ep_schedule_relationships", "schedule_file_imports"),
    ("procore_ep_schedule_wbs_nodes", "schedule_file_imports"),
    ("procore_ep_schedule_calendars", "schedule_file_imports"),
    ("procore_ep_schedule_activity_code_assignments", "schedule_file_imports"),
    ("procore_ep_schedule_udf_values", "schedule_file_imports"),
    ("schedule_source_capabilities", "schedule_file_imports"),
    ("schedule_baseline_activity_crosswalk", "schedule_baseline_projects"),
    ("schedule_baseline_health_facts", "schedule_baseline_projects"),
    ("schedule_baseline_projects", "schedule_file_imports"),
    ("schedule_quality_metric_results", "schedule_quality_evaluation_runs"),
    ("schedule_quality_scorecards", "schedule_quality_evaluation_runs"),
    ("schedule_quality_evaluation_runs", "schedule_file_imports"),
    ("schedule_version_identity_matches", "schedule_file_imports"),
    ("schedule_identities", "schedule_file_imports"),
]

PURGE_TABLE_STRATEGIES: dict[str, str] = {
    "schedule_file_imports": "by_project_key",
    "schedule_import_packages": "by_project_key",
    "project_schedule_review_items": "by_project_key",
    "project_schedule_named_baseline_review_items": "by_project_key",
    "project_schedule_named_baseline_slots": "by_project_key",
    "project_schedule_baseline_selections": "by_project_key",
    "project_schedule_series_membership": "by_project_key",
    "schedule_baseline_projects": "by_project_key",
    "schedule_identities": "by_project_key",
}


def supplemental_edges_for_tables(tables: set[str]) -> list[tuple[str, str]]:
    return [(child, parent) for child, parent in SUPPLEMENTAL_DELETE_EDGES if child in tables]


def topological_delete_order(
    tables: set[str],
    fk_edges: list[tuple[str, str]],
) -> list[str]:
    """Return tables in delete order (children before parents)."""
    edges = list(fk_edges) + supplemental_edges_for_tables(tables)
    # Edge child -> parent: child rows must be deleted before parent rows.
    indegree: dict[str, int] = {t: 0 for t in tables}
    dependents: dict[str, list[str]] = {t: [] for t in tables}
    for child, parent in edges:
        if child not in tables or parent not in tables:
            continue
        indegree[parent] += 1
        dependents[child].append(parent)
    order: list[str] = []
    ready = sorted(t for t in tables if indegree[t] == 0)
    while ready:
        node = ready.pop(0)
        order.append(node)
        for parent in dependents.get(node, []):
            indegree[parent] -= 1
            if indegree[parent] == 0:
                ready.append(parent)
        ready.sort()
    remaining = [t for t in tables if t not in order]
    order.extend(sorted(remaining))
    return order
