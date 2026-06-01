# 43 — Phase 07D source-scope all-folders + review-routing remediation

**Status:** Active (Phase 07D Prompt 01 — 07C remediation preflight)
**Supersedes nothing.** Extends the closed 07C records `32-phase-07c-source-scope-compliance.md` and
`40-phase-07c-data-quality-gates.md` (those remain authoritative for their phase; this record documents the
07D-era remediation that builds on them).

## Why

Phase 07D Prompt 00 classified two prerequisites that blocked meeting-prep readiness:

- **G1 — `document_source_scope_compliance`** was `deferred_not_blocking`. The source-scope evaluator treated
  any OneDrive source without a `selected_folder_item_ids` allowlist as non-compliant (root-wide → blocked).
  Every live OneDrive source lacked an allowlist, so `all_compliant=false`.
- **G2 — `review_required_routing_presence`** was `deferred_not_blocking`. The gate keyed only off
  `relationship_resolution_queue`, ignoring the 283 review-required document cards 07C already produced.

The operator clarified that the OneDrive allowlist must be able to express **all folders** — as an explicit
opt-in, never an implicit permission to crawl.

## What changed

### 1. Explicit OneDrive all-folders allowlist

- **`SourceLocation.allow_all_folders: bool = False`** (`construction/config/models.py`) — a fail-closed
  per-source opt-in. Default `False` keeps implicit root-wide blocked.
- **`OneDriveScopePolicy.allow_explicit_all_folders: bool = True`** (`policy/document_source_policy.py`,
  seed `document_source_policy.seed.yaml`) — policy switch enabling the capability. The Literal-locked
  `root_wide_indexing_allowed: Literal[False]` and `require_selected_folder_allowlist: Literal[True]` are
  unchanged: *implicit* root-wide is still forbidden.
- **Evaluator** (`construction/document/source_scope.py`) — OneDrive compliance now has two explicit paths:
  1. `selected_folder_item_ids` present → `scope_type=selected_folders`, compliant.
  2. `allow_all_folders` **and** `policy.onedrive.allow_explicit_all_folders` **and** a recognized OneDrive
     root kind → `scope_type=all_folders_explicit`, compliant (root and all nested folders).
  Anything else → `scope_type=root_wide`, non_compliant, `block_document_card_promotion`
  (reason `onedrive_implicit_root_blocked`).
- **Recognized root kinds** are a *local* allowlist `_ONEDRIVE_ALL_FOLDERS_ROOT_KINDS` =
  the canonical Phase 02 roots (`onedrive_business_root`, `onedrive_personal_root`,
  `onedrive_shared_library`) **plus** the legacy Phase 01 compat roots (`onedrive_personal`,
  `onedrive_shared`). It deliberately does **not** broaden the shared
  `ONEDRIVE_INVENTORY_FIRST_SCOPES`, which governs unrelated crawl behavior.
- **Report** gains `onedrive_scope_breakdown`
  `{all_folders_explicit_compliant, selected_folders_compliant, implicit_root_blocked}`, surfacing the
  `onedrive_all_folders_explicit_compliant` vs `onedrive_implicit_root_blocked` distinction.

The live seed (`sharepoint_onedrive_sources.seed.yaml`) sets `allow_all_folders: true` on all four OneDrive
roots: the three canonical Phase 02 sources and the legacy compat duplicate `bobby-onedrive` (a superseded
duplicate of the approved `od_personal_bobby`; all-folder OneDrive indexing is explicitly operator-approved).

### 2. Review-routing reconciliation across queues

`_gate_review_required_routing_presence` (`construction/data_quality/gates.py`) now defensively sums
`review_required=1` across the available review surfaces — `relationship_resolution_queue`,
`construction_document_cards`, `construction_review_queue`, `email_review_queue`,
`calendar_project_match_candidates` (a missing table contributes 0) — and passes when the total is positive.
A per-queue `review_routing_breakdown` is attached for evidence. Only `COUNT(*)` is issued; no raw content
is read.

## Guardrails preserved

No SQLite migration (schema stays **V24**). Read-only and local-first; no external writeback or write scopes.
The all-folders path is an explicit operator opt-in, never an implicit crawl; ambiguous/implicit OneDrive
root scope stays blocked. No raw content, URLs, tokens, or secrets are persisted. All document cards remain
`review_required`; nothing is auto-promoted. Outputs are advisory.

## Effect

On the live registry + current local SQLite state: `document_source_scope_compliance=pass` (4 OneDrive roots
`all_folders_explicit`, 0 blocked) and `review_required_routing_presence=pass` (283 document cards + 8
calendar candidates). Both are removed from `meeting_prep_readiness.blocked_by`; `auto_readiness_allowed`
stays `False` (07D is never auto-claimed). On an empty store the data-presence gates defer as before.

Evidence: `docs/evidence/construction-intelligence-phase-07d-cross-source-meeting-prep/01-07c-remediation-preflight.md`.
