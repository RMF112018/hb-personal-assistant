"""N8C-15 workflow registry: canonical catalog, per-type routing targets, and deferred-capability markers.
Also asserts N8C-15 remains schema-free (LATEST_SCHEMA_VERSION stays 108)."""

from __future__ import annotations

from hb_assistant.obsidian_mcp.workflow_models import ROUTING_TARGETS, WORKFLOW_TYPES
from hb_assistant.obsidian_mcp.workflow_registry import WORKFLOW_REGISTRY, catalog, get_spec
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION


def test_no_schema_bump() -> None:
    # N8C-15 is route-only and adds no schema; the head must remain at the N8C-14 (V108) version.
    assert LATEST_SCHEMA_VERSION == 108


def test_catalog_lists_all_types_and_targets() -> None:
    cat = catalog()
    assert set(cat["workflow_types"]) == set(WORKFLOW_TYPES)
    assert set(cat["routing_targets"]) == set(ROUTING_TARGETS)
    assert len(cat["workflows"]) == len(WORKFLOW_REGISTRY)
    assert cat["router_version"] == "workflow-router-v1"


def test_registry_covers_every_workflow_type() -> None:
    assert set(WORKFLOW_REGISTRY) == set(WORKFLOW_TYPES)


def test_action_draft_preparation_is_contract_only_deferred_to_n8c18() -> None:
    spec = get_spec("action_draft_preparation")
    assert spec.contract_only is True
    assert spec.primary_targets == ()  # routes to nothing live
    assert spec.deferred_capabilities  # returns deferred capabilities only
    assert spec.implementation_deferred_to == "N8C-18"


def test_context_workflows_implemented_in_n8c17_actions_deferred_to_n8c18() -> None:
    # N8C-17 implements these four as read-only context-assembly handlers. Only their action staging /
    # delivery remains deferred (N8C-18) — never a "build_*" implementation marker.
    for wf in ("meeting_prep", "daily_brief_context", "project_intelligence_context", "open_loop_triage"):
        spec = get_spec(wf)
        assert spec.implementation_deferred_to == "N8C-18"
        assert spec.deferred_capabilities  # only genuine action-staging / delivery gaps remain
        assert not any(cap.startswith("build_") for cap in spec.deferred_capabilities)
        assert spec.primary_targets


def test_catalog_notes_defer_ui_and_live_consumption() -> None:
    cat = catalog()
    assert cat["live_consumption_deferred_to"] == "N8C-16"
    assert cat["notes"]["operator_ui_deferred_to"] == "N8C-13"
    assert cat["notes"]["action_staging_deferred_to"] == "N8C-18"
    assert cat["notes"]["context_workflows_implemented_in"] == "N8C-17"


def test_get_spec_unknown_or_invalid_returns_none() -> None:
    assert get_spec("bogus") is None
    assert get_spec(None) is None


def test_source_file_lookup_routes_to_source_connector() -> None:
    spec = get_spec("source_file_lookup")
    assert spec.primary_targets == ("source_connector",)
