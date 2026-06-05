"""Phase 07C Prompt 03 — source-scope compliance evaluator.

Read-only verification that every ENABLED file source obeys the explicit
document-source scope policy before document cards are materialized:

- SharePoint sources index the approved drive / approved project-drive scope and
  all nested folders -> compliant.
- OneDrive sources are compliant via one of two explicit declarations: an explicit
  selected-folder allowlist (``selected_folder_item_ids``), OR an explicit
  all-folders opt-in (``allow_all_folders: true`` on a recognized OneDrive root
  kind, with the policy's ``allow_explicit_all_folders`` enabled) covering the root
  and all nested folders. *Implicit* root-wide OneDrive indexing is never allowed,
  so a OneDrive source with neither declaration is NON-COMPLIANT and blocked from
  document-card promotion (fail-closed).

Offline and read-only: it loads the in-memory source registry + policy and returns
a structured report. It performs no Graph call, acquires no token, and writes
nothing. The ``read_only: Literal[True]`` model boundary is asserted, never weakened.
``non_compliant_source_keys`` is the blocking signal the Prompt 04 materializer
consumes.
"""

from __future__ import annotations

from typing import Any

from hb_assistant.construction.config.models import SourceLocation, SourceRegistry
from hb_assistant.construction.policy.document_source_policy import DocumentSourcePolicy
from hb_assistant.construction.policy.inventory_first import ONEDRIVE_INVENTORY_FIRST_SCOPES

_BLOCK_ACTION = "block_document_card_promotion"

# Recognized OneDrive *root* kinds eligible for the explicit all-folders path.
# Local to the document-source-scope evaluator on purpose: it must NOT broaden the
# shared inventory-first scope set (``ONEDRIVE_INVENTORY_FIRST_SCOPES``), which
# governs unrelated crawl behavior. It extends the canonical Phase 02 root kinds
# with the legacy Phase 01 compat root kinds (``onedrive_personal`` /
# ``onedrive_shared``) so a superseded compat duplicate of an approved personal
# OneDrive root can be explicitly opted in — but only via ``allow_all_folders``.
_ONEDRIVE_ALL_FOLDERS_ROOT_KINDS = frozenset(ONEDRIVE_INVENTORY_FIRST_SCOPES) | {
    "onedrive_personal",
    "onedrive_shared",
}


def _system_of(source: SourceLocation) -> str:
    kind = str(source.kind)
    if kind.startswith("sharepoint"):
        return "sharepoint"
    if kind in ONEDRIVE_INVENTORY_FIRST_SCOPES or kind.startswith("onedrive"):
        return "onedrive"
    return "not_applicable"


def _is_onedrive_root_kind(source: SourceLocation) -> bool:
    """True when the source kind names a recognized OneDrive root scope.

    The explicit all-folders path is honored only on these kinds so a OneDrive
    source with an unresolved / unrecognized root identity can never be treated as
    an all-folders allowlist (it stays blocked as ambiguous).
    """
    return str(source.kind) in _ONEDRIVE_ALL_FOLDERS_ROOT_KINDS


def _evaluate_source(source: SourceLocation, policy: DocumentSourcePolicy) -> dict[str, Any]:
    """Classify a single enabled source. Returns its compliance record."""
    system = _system_of(source)
    record: dict[str, Any] = {
        "source_key": source.source_key,
        "kind": str(source.kind),
        "system": system,
        "scope_type": None,
        "compliance_status": "not_applicable",
        "action": None,
        "reasons": [],
    }

    if system == "sharepoint":
        # Approved drive / project-drive / site scope, nested folders included.
        record["scope_type"] = (
            "approved_project_drive_folder"
            if str(source.kind) == "sharepoint_project_drive_folder"
            else "approved_sharepoint_scope"
        )
        record["compliance_status"] = "compliant"
        record["reasons"] = ["approved_sharepoint_drive_or_project_drive_scope"]
        return record

    if system == "onedrive":
        allowlist = source.selected_folder_item_ids or []
        if allowlist:
            # Explicit subset: listed folders and all nested folders therein.
            record["scope_type"] = "selected_folders"
            record["compliance_status"] = "compliant"
            record["reasons"] = [
                "selected_folder_allowlist_present",
                "onedrive_selected_folders_compliant",
            ]
        elif (
            source.allow_all_folders
            and policy.onedrive.allow_explicit_all_folders
            and _is_onedrive_root_kind(source)
        ):
            # Explicit operator opt-in: root and all nested folders.
            record["scope_type"] = "all_folders_explicit"
            record["compliance_status"] = "compliant"
            record["reasons"] = [
                "explicit_all_folders_allowlist_declared",
                "root_and_all_nested_folders",
                "onedrive_all_folders_explicit_compliant",
            ]
        else:
            # Ambiguous / implicit root-wide, or all-folders requested without an
            # explicit opt-in or on an unrecognized root kind: blocked, fail-closed.
            record["scope_type"] = "root_wide"
            record["compliance_status"] = "non_compliant"
            record["action"] = _BLOCK_ACTION
            record["reasons"] = [
                "root_wide_onedrive_indexing_not_allowed",
                "explicit_all_folders_or_selected_allowlist_required",
                "onedrive_implicit_root_blocked",
            ]
        return record

    # procore / mailbox / anything non-file: not a document-card source.
    record["scope_type"] = "n/a"
    record["reasons"] = ["not_a_sharepoint_or_onedrive_file_source"]
    return record


def evaluate_source_scope_compliance(
    registry: SourceRegistry, policy: DocumentSourcePolicy
) -> dict[str, Any]:
    """Evaluate every ENABLED source against the document-source scope policy."""
    # Preserve the read-only boundary; never weaken it.
    if not all(s.read_only is True for s in registry.sources):
        raise ValueError("source registry contains a non-read-only source; refusing to evaluate")

    enabled = [s for s in registry.sources if s.enabled]
    records = [_evaluate_source(s, policy) for s in enabled]

    by_system: dict[str, int] = {}
    for r in records:
        by_system[r["system"]] = by_system.get(r["system"], 0) + 1

    compliant = [r for r in records if r["compliance_status"] == "compliant"]
    non_compliant = [r for r in records if r["compliance_status"] == "non_compliant"]
    not_applicable = [r for r in records if r["compliance_status"] == "not_applicable"]
    blocked = [r["source_key"] for r in non_compliant]

    # Phase 07D — surface the explicit-compliant vs implicit-blocked OneDrive
    # distinction so the data-quality gate and evidence can report it.
    onedrive = [r for r in records if r["system"] == "onedrive"]
    onedrive_scope_breakdown = {
        "all_folders_explicit_compliant": sum(
            1 for r in onedrive if r["scope_type"] == "all_folders_explicit"
        ),
        "selected_folders_compliant": sum(
            1 for r in onedrive if r["scope_type"] == "selected_folders"
        ),
        "implicit_root_blocked": sum(
            1 for r in onedrive if r["compliance_status"] == "non_compliant"
        ),
    }

    return {
        "command": "graph files scope-compliance",
        "ok": True,
        "policy_version": policy.version,
        "read_only_enforced": True,
        "all_compliant": not non_compliant,
        "summary": {
            "enabled_evaluated": len(records),
            "compliant": len(compliant),
            "non_compliant": len(non_compliant),
            "not_applicable": len(not_applicable),
        },
        "by_system": by_system,
        "onedrive_scope_breakdown": onedrive_scope_breakdown,
        "sources": records,
        "blocked_sources": blocked,
        "guardrails": {
            "external_systems": "read_only",
            "writeback": "none",
            "graph_calls": "none",
            "token_acquisition": "none",
            "microsoft_365_writeback_enabled": False,
            "sharepoint_policy": policy.sharepoint.intended_scope,
            "onedrive_policy": policy.onedrive.intended_scope,
            "onedrive_root_wide_allowed": policy.onedrive.root_wide_indexing_allowed,
            "onedrive_explicit_all_folders_allowed": policy.onedrive.allow_explicit_all_folders,
        },
    }


def non_compliant_source_keys(registry: SourceRegistry, policy: DocumentSourcePolicy) -> set[str]:
    """Return the set of enabled source keys blocked from document-card promotion.

    The blocking signal consumed by the Phase 07C Prompt 04 document-card
    materializer (which must skip these sources).
    """
    report = evaluate_source_scope_compliance(registry, policy)
    return set(report["blocked_sources"])
