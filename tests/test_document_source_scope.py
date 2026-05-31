"""Phase 07C Prompt 03 — source-scope compliance evaluator + policy loader."""

from __future__ import annotations

from hb_assistant.construction.config.models import SourceLocation, SourceRegistry
from hb_assistant.construction.document import (
    evaluate_source_scope_compliance,
    non_compliant_source_keys,
)
from hb_assistant.construction.policy.document_source_policy import (
    DocumentSourcePolicy,
    load_document_source_policy,
)


def _src(source_key: str, kind: str, **kw: object) -> SourceLocation:
    return SourceLocation(source_key=source_key, kind=kind, display_name=source_key, **kw)


def _registry() -> SourceRegistry:
    return SourceRegistry(
        sources=[
            _src("sp_project", "sharepoint_project_drive_folder", folder_item_id="F"),
            _src("od_root_blocked", "onedrive_business_root"),
            _src(
                "od_selected_ok",
                "onedrive_business_root",
                selected_folder_item_ids=["f1", "f2"],
            ),
            _src("procore_proj", "procore_project"),
            _src("od_disabled", "onedrive_personal_root", enabled=False),
        ]
    )


def test_evaluator_classifies_and_blocks_root_wide_onedrive() -> None:
    report = evaluate_source_scope_compliance(_registry(), DocumentSourcePolicy())
    assert report["command"] == "graph files scope-compliance"
    assert report["ok"] is True
    assert report["read_only_enforced"] is True
    # disabled source is not evaluated
    assert report["summary"]["enabled_evaluated"] == 4
    assert report["all_compliant"] is False

    by_key = {r["source_key"]: r for r in report["sources"]}
    assert "od_disabled" not in by_key  # disabled skipped

    assert by_key["sp_project"]["compliance_status"] == "compliant"
    assert by_key["sp_project"]["system"] == "sharepoint"

    blocked = by_key["od_root_blocked"]
    assert blocked["compliance_status"] == "non_compliant"
    assert blocked["action"] == "block_document_card_promotion"
    assert "root_wide_onedrive_indexing_not_allowed" in blocked["reasons"]

    assert by_key["od_selected_ok"]["compliance_status"] == "compliant"
    assert by_key["od_selected_ok"]["scope_type"] == "selected_folders"

    assert by_key["procore_proj"]["compliance_status"] == "not_applicable"

    assert report["blocked_sources"] == ["od_root_blocked"]
    assert report["summary"] == {
        "enabled_evaluated": 4,
        "compliant": 2,
        "non_compliant": 1,
        "not_applicable": 1,
    }


def test_non_compliant_source_keys_helper() -> None:
    keys = non_compliant_source_keys(_registry(), DocumentSourcePolicy())
    assert keys == {"od_root_blocked"}


def test_guardrails_are_read_only_and_no_writeback() -> None:
    report = evaluate_source_scope_compliance(_registry(), DocumentSourcePolicy())
    g = report["guardrails"]
    assert g["external_systems"] == "read_only"
    assert g["writeback"] == "none"
    assert g["graph_calls"] == "none"
    assert g["token_acquisition"] == "none"
    assert g["microsoft_365_writeback_enabled"] is False
    assert g["onedrive_root_wide_allowed"] is False


def test_policy_loads_from_seed_with_locked_guardrails() -> None:
    policy = load_document_source_policy()
    assert policy.version == "phase07c-document-source-policy-v1"
    assert policy.onedrive.root_wide_indexing_allowed is False
    assert policy.onedrive.require_selected_folder_allowlist is True
    assert policy.onedrive.non_compliant_action == "block_document_card_promotion"
    assert policy.sharepoint.non_compliant_action == "block_document_card_promotion"
    assert policy.defaults.read_only is True
    assert policy.defaults.external_writeback_allowed is False
