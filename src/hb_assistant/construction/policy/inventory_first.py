"""Inventory-first policy primitive for OneDrive construction sources.

Phase 02 canonical seed declares ``baseline_policy.mode="inventory_first"`` on
every OneDrive entry (business root, personal root, shared library). This
module turns that seed metadata into an **explicit, queryable** policy object
and provides type-level + runtime guardrails callers can use to prove they are
honoring the constraints.

Hard guardrails (locked at the ``Literal[True]`` type level on the policy):

- ``bulk_document_cards_forbidden`` — single-card creation via
  :class:`ManifestService.build_document_card` (with explicit ``policy_reason``)
  is still allowed; batch creation is rejected via
  :func:`assert_no_bulk_document_cards`.
- ``full_text_extraction_forbidden`` — the construction agent has no full-text
  extraction code path. :func:`assert_no_full_text_extraction` provides a
  defense-in-depth check callers can run against any item iterable to confirm
  no forbidden keys ever leak through.
- ``source_document_copy_forbidden`` — Phase 02 ``DefaultPolicies`` already
  hard-blocks source-document copies into Obsidian; this flag mirrors that
  invariant on the per-source policy.

The policy is **derived** from :class:`SourceLocation` — there is no separate
storage. :func:`build_policy` returns ``None`` for any source that is not a
OneDrive scope in inventory-first mode, so non-OneDrive sources are correctly
unaffected.
"""

from __future__ import annotations

from typing import Any, Iterable, Literal, Optional

from pydantic import BaseModel

from hb_assistant.construction.config import BaselineMode, SourceLocation


class InventoryFirstViolation(RuntimeError):
    """Raised when code attempts an operation forbidden by InventoryFirstPolicy."""


ONEDRIVE_INVENTORY_FIRST_SCOPES: frozenset[str] = frozenset(
    {
        "onedrive_business_root",
        "onedrive_personal_root",
        "onedrive_shared_library",
    }
)

_FORBIDDEN_ITEM_KEYS: frozenset[str] = frozenset(
    {
        "body",
        "content",
        "text",
        "excerpt",
        "preview",
        "full_text",
        "text_excerpt",
    }
)

_GUARDRAILS_DEFAULT: dict[str, bool | str] = {
    "external_systems": "read_only",
    "bulk_document_cards": "forbidden",
    "full_text_extraction": "forbidden",
    "source_document_copies": "forbidden",
    "metadata_only": True,
}


class InventoryFirstPolicy(BaseModel):
    """Operational policy for a OneDrive source running in inventory-first mode."""

    source_key: str
    scope: str
    mode: BaselineMode
    classify_project_matches: bool
    graph_delta_required: bool
    local_folder_watcher: Optional[str] = None
    require_review_for_sensitive: bool
    bulk_document_cards_forbidden: Literal[True] = True
    full_text_extraction_forbidden: Literal[True] = True
    source_document_copy_forbidden: Literal[True] = True
    guardrails: dict[str, bool | str] = {}

    model_config = {"extra": "forbid"}


def applies_to(source: SourceLocation) -> bool:
    """Return True iff ``source`` is a OneDrive scope in inventory-first mode."""
    if source.kind not in ONEDRIVE_INVENTORY_FIRST_SCOPES:
        return False
    if source.baseline_policy is None:
        return False
    return source.baseline_policy.mode == "inventory_first"


def build_policy(source: SourceLocation) -> Optional[InventoryFirstPolicy]:
    """Return the active :class:`InventoryFirstPolicy` for ``source`` or None."""
    if not applies_to(source):
        return None
    bp = source.baseline_policy
    assert bp is not None  # narrowed by applies_to
    return InventoryFirstPolicy(
        source_key=source.source_key,
        scope=source.kind,
        mode=bp.mode,
        classify_project_matches=bp.classify_project_matches,
        graph_delta_required=bp.graph_delta_required,
        local_folder_watcher=bp.local_folder_watcher,
        require_review_for_sensitive=bp.require_review_for_sensitive,
        guardrails=dict(_GUARDRAILS_DEFAULT),
    )


def assert_no_bulk_document_cards(*, source_key: str, scope: str, intended_card_count: int) -> None:
    """Pre-flight guard: reject bulk DocumentCard creation for inventory-first sources.

    Single-card creation (count <= 1) is preserved because the existing opt-in
    :class:`ManifestService.build_document_card` API requires an explicit
    ``policy_reason`` and is metadata-only by construction.
    """
    if scope not in ONEDRIVE_INVENTORY_FIRST_SCOPES:
        return
    if intended_card_count > 1:
        raise InventoryFirstViolation(
            f"bulk DocumentCard creation forbidden under inventory-first policy: "
            f"source_key={source_key!r}, scope={scope!r}, "
            f"intended_card_count={intended_card_count}"
        )


def assert_no_full_text_extraction(items: Iterable[dict[str, Any]]) -> None:
    """Defense-in-depth: raise if any item dict carries a forbidden body/text key."""
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        leaks = _FORBIDDEN_ITEM_KEYS & set(item.keys())
        if leaks:
            raise InventoryFirstViolation(
                f"full-text extraction forbidden under inventory-first policy: "
                f"item index {index} carries forbidden keys {sorted(leaks)}"
            )
