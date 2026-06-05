"""Phase 07C Prompt 03 — source-scope compliance evaluator + policy loader."""

from __future__ import annotations

from hb_assistant.construction.config.models import SourceLocation, SourceRegistry
from hb_assistant.construction.document import (
    evaluate_source_scope_compliance,
    non_compliant_source_keys,
)
from hb_assistant.construction.policy.document_source_policy import (
    DocumentSourcePolicy,
    OneDriveScopePolicy,
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
    # Phase 07D — the explicit all-folders capability is enabled by the seed.
    assert policy.onedrive.allow_explicit_all_folders is True
    assert policy.onedrive.non_compliant_action == "block_document_card_promotion"
    assert policy.sharepoint.non_compliant_action == "block_document_card_promotion"
    assert policy.defaults.read_only is True
    assert policy.defaults.external_writeback_allowed is False


# ---------------------------------------------------------------------------
# Phase 07D — explicit OneDrive all-folders allowlist path
# ---------------------------------------------------------------------------


def _four_path_registry() -> SourceRegistry:
    """One source per required path: SharePoint nested, OneDrive subset, OneDrive
    explicit all-folders, OneDrive implicit/unconfigured root (blocked)."""
    return SourceRegistry(
        sources=[
            _src("sp_nested", "sharepoint_project_drive_folder", folder_item_id="F"),
            _src("od_subset", "onedrive_business_root", selected_folder_item_ids=["f1"]),
            _src("od_all_folders", "onedrive_business_root", allow_all_folders=True),
            _src("od_implicit_blocked", "onedrive_business_root"),
        ]
    )


def test_four_scope_paths_sharepoint_subset_allfolders_and_implicit_blocked() -> None:
    report = evaluate_source_scope_compliance(_four_path_registry(), DocumentSourcePolicy())
    by_key = {r["source_key"]: r for r in report["sources"]}

    # 1. SharePoint approved scope indexes all nested folders -> compliant.
    assert by_key["sp_nested"]["compliance_status"] == "compliant"
    assert by_key["sp_nested"]["system"] == "sharepoint"

    # 2. OneDrive explicit selected-folder subset -> compliant.
    assert by_key["od_subset"]["compliance_status"] == "compliant"
    assert by_key["od_subset"]["scope_type"] == "selected_folders"

    # 3. OneDrive explicit all-folders opt-in -> compliant.
    allf = by_key["od_all_folders"]
    assert allf["compliance_status"] == "compliant"
    assert allf["scope_type"] == "all_folders_explicit"
    assert "onedrive_all_folders_explicit_compliant" in allf["reasons"]
    assert "root_and_all_nested_folders" in allf["reasons"]

    # 4. OneDrive implicit/unconfigured root -> blocked (fail-closed).
    blocked = by_key["od_implicit_blocked"]
    assert blocked["compliance_status"] == "non_compliant"
    assert blocked["action"] == "block_document_card_promotion"
    assert "onedrive_implicit_root_blocked" in blocked["reasons"]

    assert report["all_compliant"] is False  # the implicit root is still blocked
    assert report["blocked_sources"] == ["od_implicit_blocked"]
    assert report["onedrive_scope_breakdown"] == {
        "all_folders_explicit_compliant": 1,
        "selected_folders_compliant": 1,
        "implicit_root_blocked": 1,
    }


def test_legacy_compat_onedrive_root_kind_allows_explicit_all_folders() -> None:
    """A legacy Phase 01 compat root kind (onedrive_personal) is honored for the
    explicit all-folders path, but only with the explicit opt-in."""
    reg = SourceRegistry(
        sources=[
            _src("legacy_optin", "onedrive_personal", allow_all_folders=True),
            _src("legacy_no_optin", "onedrive_personal"),
        ]
    )
    by_key = {
        r["source_key"]: r
        for r in evaluate_source_scope_compliance(reg, DocumentSourcePolicy())["sources"]
    }
    assert by_key["legacy_optin"]["compliance_status"] == "compliant"
    assert by_key["legacy_optin"]["scope_type"] == "all_folders_explicit"
    # Same legacy kind WITHOUT the opt-in stays blocked (implicit root-wide).
    assert by_key["legacy_no_optin"]["compliance_status"] == "non_compliant"


def test_all_folders_blocked_when_policy_disables_capability() -> None:
    reg = SourceRegistry(sources=[_src("od_all", "onedrive_business_root", allow_all_folders=True)])
    policy = DocumentSourcePolicy(onedrive=OneDriveScopePolicy(allow_explicit_all_folders=False))
    rec = evaluate_source_scope_compliance(reg, policy)["sources"][0]
    assert rec["compliance_status"] == "non_compliant"
    assert "onedrive_implicit_root_blocked" in rec["reasons"]


def test_all_folders_compliant_registry_is_fully_compliant_and_idempotent() -> None:
    reg = SourceRegistry(
        sources=[
            _src("od_a", "onedrive_business_root", allow_all_folders=True),
            _src("od_b", "onedrive_personal_root", allow_all_folders=True),
        ]
    )
    r1 = evaluate_source_scope_compliance(reg, DocumentSourcePolicy())
    r2 = evaluate_source_scope_compliance(reg, DocumentSourcePolicy())
    assert r1["all_compliant"] is True
    assert r1["blocked_sources"] == []
    assert r1["onedrive_scope_breakdown"]["all_folders_explicit_compliant"] == 2
    assert non_compliant_source_keys(reg, DocumentSourcePolicy()) == set()
    # Idempotent: identical structured output across runs (no persisted state).
    assert r1 == r2
