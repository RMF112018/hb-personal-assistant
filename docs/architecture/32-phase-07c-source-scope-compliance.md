# 32 — Phase 07C: Source Indexing Readiness and Scope Compliance

**Phase:** 07C (Document Intelligence Promotion) — Prompt 03.
**Status:** Implemented at this record's commit.
**Evidence:** `docs/evidence/construction-intelligence-phase-07c-document-intelligence/03-source-indexing-readiness-proof.md`.

Closes audit gap **G3** (Prompt 00/01): make the SharePoint vs OneDrive source-scope policy explicit and
enforceable, and verify every enabled source before Prompt 04 materializes document cards — blocking
non-compliant sources fail-closed. Read-only and offline; no migration, no Graph call, no writeback.

## Explicit scope policy

`resources/config/document_source_policy.seed.yaml` (`version: phase07c-document-source-policy-v1`),
loaded by `construction/policy/document_source_policy.py` (mirrors `file_ingestion.py`: seed → repo
override → explicit; `read_only`/no-writeback/no-vault-copy/no-raw-path/no-signed-url defaults are
`Literal`-locked so YAML cannot loosen them):

- **SharePoint** — `intended_scope: approved_drive_or_approved_project_drive_scope`, nested folders
  included, delta/baseline receipt required; non-compliant → `block_document_card_promotion`.
- **OneDrive** — `intended_scope: selected_folders_only`, nested under selected folders;
  `root_wide_indexing_allowed: false`, `require_selected_folder_allowlist: true`; non-compliant →
  `block_document_card_promotion`.

## Allowlist primitive (additive)

`SourceLocation` (`construction/config/models.py`) gains one optional field
`selected_folder_item_ids: list[str] | None = None` — the OneDrive selected-folder allowlist that makes
the policy satisfiable. Optional/defaulted, so existing config validates unchanged; `model_config`
remains `extra: forbid`.

## Read-only evaluator + command

`construction/document/source_scope.py` `evaluate_source_scope_compliance(registry, policy)` iterates
**enabled** sources, asserts the `read_only: Literal[True]` boundary (never weakened), classifies each as
SharePoint / OneDrive / not_applicable, and assigns compliance:

- SharePoint approved drive / project-drive / site scope → `compliant`.
- OneDrive → `compliant` iff `selected_folder_item_ids` is non-empty; otherwise `non_compliant`
  (root-wide / no allowlist) with `action="block_document_card_promotion"`.

It returns a report (`summary`, `by_system`, per-source records, `blocked_sources`, read-only guardrails).
`non_compliant_source_keys(registry, policy)` is the blocking signal the **Prompt 04** materializer
consumes (the verdict is recomputed, not persisted — no schema change). Surfaced via the new
`hb-assistant graph files scope-compliance --json` command (thin CLI wrapper, `--json`, exit 0; matches
`graph files status`). Reuses `ONEDRIVE_INVENTORY_FIRST_SCOPES` to identify OneDrive scopes.

## Current verdict (repo truth)

Against the live registry: 14 enabled sources — 10 SharePoint compliant, **4 OneDrive root-wide blocked**
(`onedrive_business_root` / `onedrive_personal_root` / `onedrive_shared_library` / `onedrive_personal`,
none carrying a selected-folder allowlist). `all_compliant=false`. This is the intended fail-closed state:
OneDrive document cards will not materialize until a selected-folder allowlist is configured.

## Guardrails
Offline/read-only (no token, no Graph call, no writeback); SharePoint+OneDrive policies explicit; non-
compliant sources blocked fail-closed. No raw text/paths/URLs/tokens/secrets in SQLite, evidence, or vault;
evidence uses kind/scope enums + counts only. No high-impact determination or candidate promotion. Gates
and readiness unchanged (this prompt adds a readiness report, not a gate).
