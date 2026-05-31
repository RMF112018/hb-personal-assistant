# Phase 07C — Prompt 03: Source Indexing Readiness and Scope Compliance Proof

**Phase:** Construction Intelligence 07C — Document Intelligence Promotion
**Prompt:** 03 — Source Indexing Readiness and Scope Compliance
**Generated (UTC):** 2026-05-31
**Baseline:** validations ran against working tree at parent commit
`b5c27d595a1c1994df38cc4d1dee5ff505206f4b`; schema version **24** (unchanged — no migration); package
**1.3.0**. Landing commit is the child of that parent.

> Leak-safe: source **kind/scope enums** and **counts** only — no raw source keys, site names, drive IDs,
> URLs, paths, tokens, secrets, GUIDs, or UPNs.

## 1. What changed (read-only verification; no migration, no writeback)

- **Explicit policy:** `resources/config/document_source_policy.seed.yaml`
  (`phase07c-document-source-policy-v1`) + loader `construction/policy/document_source_policy.py`
  (Literal-locked read-only / no-writeback defaults).
- **Allowlist primitive:** additive optional `selected_folder_item_ids` on `SourceLocation`.
- **Evaluator:** `construction/document/source_scope.py`
  (`evaluate_source_scope_compliance` / `non_compliant_source_keys`).
- **Command:** `hb-assistant graph files scope-compliance --json` (read-only report; exit 0).

## 2. Scope policy (explicit)

| Source class | Required scope | Non-compliant action |
|---|---|---|
| SharePoint | approved drive / approved project-drive scope, nested folders included | `block_document_card_promotion` |
| OneDrive | selected-folders-only (allowlist required); root-wide NOT allowed | `block_document_card_promotion` |

## 3. Compliance result (by kind/scope + counts only)

Live registry: **14 enabled sources evaluated** — `all_compliant=false`.

| System | Count | Compliance | Notes |
|---|---:|---|---|
| SharePoint (`sharepoint_project_drive_folder`, `sharepoint_site`, `sharepoint_site_page`) | 10 | compliant | approved drive / project-drive / site scope |
| OneDrive (`onedrive_business_root`, `onedrive_personal_root`, `onedrive_shared_library`, `onedrive_personal`) | 4 | **non-compliant → blocked** | root-wide, no selected-folder allowlist |

Summary: `enabled_evaluated=14`, `compliant=10`, `non_compliant=4`, `not_applicable=0`;
`blocked_sources` = the 4 OneDrive sources (`action=block_document_card_promotion`). This is the intended
fail-closed state — OneDrive document cards will not materialize until a selected-folder allowlist is set.

## 4. Validation matrix

| Command | Exit | Result |
|---|---:|---|
| `python -m compileall src tests` | 0 | clean |
| `ruff check .` | 0 | `All checks passed!` |
| `mypy src` | 0 | `Success: no issues found in 168 source files` |
| focused: `pytest test_document_source_scope.py test_graph_files_scope_compliance.py` | 0 | 5 passed |
| `pytest -m "not live and not integration and not manual"` | 0 | `2016 passed, 1 deselected` (+5 vs Prompt 02) |
| `graph files scope-compliance --json` | 0 | `all_compliant=false`; 4 OneDrive roots blocked; SharePoint compliant; guardrails read-only/no-writeback/no-graph-calls |
| `construction-agent validate --json` | 0 | ok (unaffected by the new optional field) |
| `graph files status` / `graph files no-writeback-proof` / `graph calendar status` / `graph mail status` / `procore validate` (all `--json`) | 0 | green |
| `data-quality gates` / `no-writeback-proof` / `table-inventory` (`--json`) | 0 | unchanged (`document_card_population_status` deferred; meeting_prep/risk_digest blocked) |

## 5. Read-only / boundary confirmation

The evaluator asserts `all(read_only is True)` and reports `read_only_enforced: true`. The command
acquires no token, constructs no Graph client, performs no write. The `read_only: Literal[True]` model
boundary is preserved; no scope/permission is changed or inspected for write capability. No raw paths,
signed/download URLs, tokens, or secrets are emitted.

## 6. Leak scan

Policy seed, new modules, command output sample, architecture doc, and this evidence scanned: kind/scope
enums + counts only; no raw source keys/site names/URLs/paths/tokens/secrets/GUIDs/UPNs.

## 7. Outcome

SharePoint/OneDrive scope policy is now explicit and enforced; non-compliant OneDrive root sources are
blocked fail-closed; no stop condition triggered; no readiness overstated. **07C is cleared to proceed to
Prompt 04 (Document Card Materialization)**, which must call `non_compliant_source_keys()` and skip the
blocked sources, populating only compliant-source cards with hashed/redacted derivatives.
