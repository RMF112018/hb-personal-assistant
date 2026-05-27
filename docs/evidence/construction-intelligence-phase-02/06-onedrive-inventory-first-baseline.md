# Phase 02 — Prompt 06 — OneDrive Baseline Inventory-First

## 1. Summary

Lands an explicit, queryable **inventory-first policy primitive** for the three Phase 02 canonical OneDrive sources, and extends the existing review-rule engine with four PII-focused rules tuned for personal-OneDrive risk. The codebase already enforced inventory-first invariants by **shape** (no bulk document-card creation path, no extraction surface, `DefaultPolicies` hard-blocks copy + full-text in vault). This prompt makes those invariants explicit and provides defense-in-depth assertions any caller can run.

New surfaces:

- `src/hb_assistant/construction/policy/inventory_first.py` — `InventoryFirstPolicy` Pydantic model (Literal[True]-locked guardrail flags), `InventoryFirstViolation` exception, `ONEDRIVE_INVENTORY_FIRST_SCOPES` frozenset, and four helper functions: `applies_to`, `build_policy`, `assert_no_bulk_document_cards`, `assert_no_full_text_extraction`.
- `resources/config/review_required_rules.seed.yaml` — appended four PII rules: `pii-tax-document` (high), `pii-government-id` (critical), `pii-health-record` (critical), `pii-personal-financial` (high). Total rule count goes 12 → 16. Every protected category invariant in `ReviewRules._check_consistency` still holds.

No new CLI command, no schema change, no crawler logic change. The new policy is *derived* deterministically from `SourceLocation.baseline_policy` — there is no separate storage. CLI surfaces automatically reflect the new rule count (`construction-agent validate` now reports `version=1; 16 rules; threshold=0.7`; `index status` reports `rule_count: 16`).

## 2. Repo HEAD — Before / After

| Marker | Value |
| --- | --- |
| Branch | `main` |
| HEAD before | `19891111928d06e5435be805a41eb127c7ee5b29` ("feat(construction-agent): resolve hilltop projecthome page and discover linked sources") |
| HEAD after  | (recorded after commit) |
| Working tree before | clean |

## 3. Files Changed

**Modified (3):**

- `resources/config/review_required_rules.seed.yaml` — +38/-0. Four new PII rules appended under a `# ---- Phase 02 PII rules ----` block. Existing 12 rules untouched.
- `src/hb_assistant/construction/policy/__init__.py` — +20/-0. Re-exports the new symbols from `inventory_first.py` alongside the existing policy surface.
- `tests/test_construction_review_policy.py` — +284/-0. 14 new tests covering applies_to / build_policy / Literal-locked guardrails / bulk-card guardrail / full-text guardrail / PII rule routing / rule count growth.
- `tests/test_construction_graph_delta.py` — +157/-0. 3 new tests that drive mocked OneDrive crawls for each of the three canonical source keys and assert (a) `assert_no_full_text_extraction(receipt.sample_items)` returns cleanly, (b) `construction_document_cards` table stays empty across the crawl, (c) the V2 inventory schema carries zero forbidden body/text columns.

**Created (2):**

- `src/hb_assistant/construction/policy/inventory_first.py` — the new policy primitive module.
- `docs/evidence/construction-intelligence-phase-02/06-onedrive-inventory-first-baseline.md` — this file.

**Deleted:** none. **Migrations applied:** none.

## 4. Governance Attestation

| Reference | Status |
| --- | --- |
| `CLAUDE.md` §5 — "Obsidian Vault Planning and Implementation Package Governance" | Honored. No payloads copied under `docs/plans/**`. |
| `.grok/skills/vault-package-governance/SKILL.md` | Honored. |
| Phase 01 evidence (`session-handoff.md`, `11-final-closeout-summary.md`) | Carried forward as authoritative context. |
| Phase 02 package files | Reviewed (Prompt_06 spec + Workstream E — OneDrive inventory-first). |

## 5. Validation Commands and Outputs

All from `/Users/bobbyfetting/hb-personal-assistant` on 2026-05-27.

### 5.1 `python -m pytest tests/test_construction_*.py tests/test_procore_*.py`

```text
........................................................................ [ 21%]
........................................................................ [ 42%]
........................................................................ [ 63%]
........................................................................ [ 84%]
......................................................                   [100%]
342 passed in 3.35s
```

325 prior + 17 net new = 342 (14 review-policy tests + 3 OneDrive crawl integration tests).

### 5.2 `ruff check src/hb_assistant/construction/ src/hb_assistant/procore/ src/hb_assistant/cli/construction.py src/hb_assistant/cli/procore.py`

```text
All checks passed!
```

### 5.3 `hb-assistant construction-agent validate --json`

`ok=True, passed=4/4`. `review_rules` detail now reads `"version=1; 16 rules; threshold=0.7"` (was 12 rules in Prompts 00–05).

### 5.4 `hb-assistant construction-agent sources validate --json`

```json
{"project_count": 6, "source_count": 14, "resolved_count": 0, "pending_count": 9, "deprecated_count": 0, "ok": true, "blocking": false}
```

Unchanged.

### 5.5 `hb-assistant construction-agent index status --json`

`schema_version: 5`, `rule_count: 16`. Schema unchanged from Prompt 02; only the rule-set version-1 inventory grew.

### 5.6 `hb-assistant construction-agent graph auth status --json` / `graph sources resolve --json`

`token_type=none`; `status=auth_required, targets=14` — unchanged.

### 5.7 `hb-assistant procore mapping validate --json`

`ok=False, exit=1` by design.

## 6. Three OneDrive Sources × Inventory-First Policy

| Source key | Scope | `mode` | `classify_project_matches` | `graph_delta_required` | `local_folder_watcher` | `require_review_for_sensitive` | `applies_to` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `od_business_bobby_hedrickbrothers` | onedrive_business_root | inventory_first | True | True | secondary_signal_only | True | True |
| `od_personal_bobby`                 | onedrive_personal_root | inventory_first | False | False (default) | None | True | True |
| `od_shared_libraries_cloudtemp`     | onedrive_shared_library| inventory_first | True | False (default) | None | True | True |

All three sources `build_policy(source)` returns a populated `InventoryFirstPolicy`. SharePoint sources (legacy + canonical) all return `None` from `build_policy` — confirmed by `test_inventory_first_does_not_apply_to_sharepoint_sources`.

## 7. Closed-Loop Guardrails Matrix

| Guardrail | Enforcement | Verified by |
| --- | --- | --- |
| No bulk document cards (count > 1) | `assert_no_bulk_document_cards` (runtime) + existing `ManifestService.build_document_card` API shape (single-card only) | `test_assert_no_bulk_document_cards_raises_when_count_gt_one`; `test_assert_no_bulk_document_cards_ignores_non_onedrive_scope`; `test_onedrive_crawl_does_not_produce_document_cards` |
| No full-text extraction | `InventoryFirstPolicy.full_text_extraction_forbidden: Literal[True]` (type-level); `assert_no_full_text_extraction` (runtime); existing V2 schema has no body/text/excerpt columns | `test_assert_no_full_text_extraction_raises_on_forbidden_keys`; `test_inventory_first_policy_guardrails_are_literal_true_locked`; `test_onedrive_crawl_receipt_carries_no_forbidden_keys`; `test_onedrive_crawl_records_metadata_only_per_inventory_first_policy` |
| No source-document copies | `InventoryFirstPolicy.source_document_copy_forbidden: Literal[True]`; existing `DefaultPolicies.copy_originals_to_vault` rejected when True (Prompt 01) | `test_inventory_first_policy_guardrails_are_literal_true_locked` + the Prompt 01 `test_default_policies_rejects_copy_originals_true` |
| Sensitive records route to review | `baseline_policy.require_review_for_sensitive=True` on every OneDrive seed entry; existing rule engine routes via 12+4 rules | `test_build_inventory_first_policy_carries_baseline_policy_fields`; `test_new_pii_rules_route_personal_onedrive_files_to_review` |
| Inventory rows stay metadata-only | V2 `construction_drive_item_inventory` schema (Prompt 02 of Phase 01) carries no body/text columns | `test_onedrive_crawl_records_metadata_only_per_inventory_first_policy`; existing `test_no_body_or_text_columns_in_inventory` |
| Per-source policy is queryable | `build_policy(source)` returns deterministic `InventoryFirstPolicy` for OneDrive sources in inventory-first mode | `test_inventory_first_applies_to_onedrive_business_root` / `_personal_root` / `_shared_library`; `test_build_inventory_first_policy_carries_baseline_policy_fields`; `test_build_inventory_first_policy_returns_none_for_non_onedrive` |

## 8. New PII Review Rules

Four rules added to `resources/config/review_required_rules.seed.yaml`. All use the existing `ReviewRule` Pydantic schema — no model changes. All sensitivity is `high` or `critical` and suggested_action is `controller_review`. Match patterns chosen to fire on real PII document names without false-positive storms on construction filenames:

| rule_id | kind | sensitivity | classification_label | pattern (excerpt) |
| --- | --- | --- | --- | --- |
| `pii-tax-document`     | document_name | high     | `pii_tax`                | `1099|w-?2|w-?9|tax\s*return|form\s*1040` |
| `pii-government-id`    | document_name | critical | `pii_government_id`      | `(passport|driver'?s?\s*license|social\s*security|ssn|state\s*id)` |
| `pii-health-record`    | document_name | critical | `pii_health`             | `(medical|health|phi|hipaa|prescription|insurance\s*claim)` |
| `pii-personal-financial` | risk_term   | high     | `pii_personal_financial` | `bank statement,brokerage,401k,ira statement,credit report` |

Verified to route the canonical names `1099-2025.pdf`, `passport_scan_jane.pdf`, `medical_records_2024.pdf`, `Bank Statement Jan 2026.pdf` to the expected labels and sensitivities by `test_new_pii_rules_route_personal_onedrive_files_to_review`.

## 9. Guardrail Attestation

- External systems remain read-only. `InventoryFirstPolicy.guardrails["external_systems"]="read_only"`.
- No source-document copies into Obsidian — `source_document_copy_forbidden: Literal[True]` locked at type level + existing `DefaultPolicies` block.
- No full-document text in vault notes — `full_text_extraction_forbidden: Literal[True]` locked at type level + zero extraction code paths in the construction module.
- No bulk document cards — `assert_no_bulk_document_cards` runtime guard + existing one-card-at-a-time API.
- No deletion / movement / overwrite / rename of source files.
- No production webhooks introduced.
- No company-wide rollout.
- Sensitive records route to review — verified across all 16 rules.
- Models execute no file operations. Mailbox stays read-only.
- No live Graph round-trip — non-interactive shell. All tests use `MagicMock` HTTP.

## 10. Blocked Live / External Validation

- **Live OneDrive crawl** — requires interactive MSAL login. Code paths are exercised via mocked HTTP. Once a token is cached, running `hb-assistant construction-agent graph delta --source od_business_bobby_hedrickbrothers --apply` will populate the V2 inventory; the inventory-first policy returned by `build_policy` for the same source will then govern downstream consumers.
- **Procore** — OAuth still stubbed; mapping validate continues to exit 1 by design (hilltop pending in separate seed).

## 11. Phase 02 Acceptance Progress

- **OneDrive inventory-first policy primitive** — closed (this prompt).
- **Per-OneDrive-source policy queryable** — closed (`build_policy(source)`).
- **Bulk-document-card guardrail** — closed (`assert_no_bulk_document_cards`).
- **Full-text-extraction guardrail** — closed (`assert_no_full_text_extraction` + Literal-locked flag).
- **PII review-rule coverage for personal OneDrive** — closed (4 new rules).
- **Crawler integration that auto-attaches the policy to receipts** — deferred (consumers can call `build_policy` directly today).
- **CLI surface for the policy** — deferred (no `policy show` command; data flows through registry + Python API).

## 12. Next Prompt Readiness

- Repo at expected baseline (HEAD `1989111`).
- Working tree changes captured in §3.
- 342/342 scoped tests pass; ruff clean.
- All Phase 02 hard guardrails intact.
- Inventory-first policy primitive exposes the three OneDrive constraints as queryable Pydantic objects.
- CLI surface unchanged except for the rule-count delta (12 → 16) which propagates automatically.

**Status: ready for Phase 02 — Prompt 07.**
