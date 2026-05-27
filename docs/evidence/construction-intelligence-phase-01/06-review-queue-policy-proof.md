# Phase 01 — Prompt 06 / Step 7: Review Queue & Sensitive Data Routing

Evidence for the deterministic, rules-driven review-required routing layer of
the construction-agent. Controller policy (a versioned YAML rule file) is the
authority; no model decisioning is permitted for contract, financial, legal,
incident, injury, or personnel material.

## Implementation summary

- New module `src/hb_assistant/construction/policy/` with:
  - `models.py` — Pydantic `ReviewRule`, `ReviewRules`, `RuleMatch` (`extra="forbid"`,
    `Literal`-typed `kind` / `sensitivity`, kebab-case `rule_id` validator,
    unique-id + protected-category-coverage invariants).
  - `loader.py` — `load_review_rules()` with seed → repo override → explicit path →
    `HB_CONSTRUCTION_REVIEW_RULES` env precedence (mirrors the existing
    construction source-registry loader).
  - `evaluator.py` — `ReviewPolicyEvaluator` (deterministic regex + substring,
    case-insensitive; emits every matching rule for one item so controllers see
    full provenance).
  - `router.py` — `ReviewQueueRouter` (iterates inventory, calls
    `ConstructionStore.enqueue_review_item`; idempotent on
    `(source_key, item_id, rule_id)`).
- Seeded controller policy `resources/config/review_required_rules.seed.yaml`
  with 12 rules covering every protected category plus one low-confidence rule
  (`term-budget-ambiguous`, confidence 0.5).
- Pydantic-generated schema artifact `resources/schemas/review_queue.schema.json`.
- V3 SQLite migration adds `construction_review_queue` + 2 indexes; additive,
  idempotent, bumped `schema_migrations` to 3.
- `ConstructionStore` extended with `list_inventory_for_source`,
  `enqueue_review_item`, `list_review_queue`, `count_review_queue`.
- `ManifestService.build_review_required_note` now defaults to pulling open
  rows from the store; explicit `items=` still bypasses the pull.
- New CLI sub-app `construction-agent review` with `evaluate` and `list`.

## Changed files

```
A  resources/config/review_required_rules.seed.yaml
A  resources/schemas/review_queue.schema.json
A  src/hb_assistant/construction/policy/__init__.py
A  src/hb_assistant/construction/policy/evaluator.py
A  src/hb_assistant/construction/policy/loader.py
A  src/hb_assistant/construction/policy/models.py
A  src/hb_assistant/construction/policy/router.py
A  tests/test_construction_review_policy.py
A  docs/evidence/construction-intelligence-phase-01/06-review-queue-policy-proof.md
M  src/hb_assistant/cli/construction.py
M  src/hb_assistant/construction/manifests/service.py
M  src/hb_assistant/construction/store/repositories.py
M  src/hb_assistant/store/migrator.py
M  tests/test_construction_store_repositories.py
```

## Validation

### Pytest — review policy suite

```
$ python -m pytest tests/test_construction_review_policy.py
............................................................     [100%]
34 passed in 0.55s
```

### Pytest — regression sweep across construction + store + config

```
$ python -m pytest tests/test_construction_*.py tests/test_store.py \
                   tests/test_store_links.py tests/test_config.py
141 passed in 1.15s
```

### Pytest — broader sweep (excluding documented hang-prone files and the
pre-existing `test_obsidian_writer` baseline failures unrelated to this work)

```
$ python -m pytest tests/ \
    --ignore=tests/test_cli_canonical.py \
    --ignore=tests/test_auth.py --ignore=tests/test_automation.py \
    --ignore=tests/test_actions_cli.py --ignore=tests/test_files_cli.py \
    --ignore=tests/test_mutation_lockout.py \
    --ignore=tests/test_sensitive_scan_cli.py \
    --ignore=tests/test_mvp_local_runtime_evidence.py \
    --ignore=tests/test_obsidian_writer.py \
    -k "not test_graph"
173 passed, 11 deselected in 1.46s
```

### Pytest — canonical CLI help subset (proves new `review` sub-app does not
break root help shape)

```
$ python -m pytest tests/test_cli_canonical.py -k "help_parses or _shape" -q
....                                                            [100%]
4 passed
```

### Ruff — scoped to new and modified files

```
$ ruff check src/hb_assistant/construction/policy/ \
             src/hb_assistant/cli/construction.py \
             src/hb_assistant/store/migrator.py \
             src/hb_assistant/construction/store/repositories.py \
             src/hb_assistant/construction/manifests/service.py \
             tests/test_construction_review_policy.py \
             tests/test_construction_store_repositories.py
All checks passed!
```

### Migration version + idempotency

```
$ python -c "from hb_assistant.store.migrator import SQLiteMigrator; \
             m=SQLiteMigrator(); print(m.apply(), m.apply())"
3 3
```

Construction tables after V3 (verified against an isolated tmp DB):

```
construction_crawl_receipts
construction_delta_tokens
construction_drive_item_inventory
construction_review_queue          <-- new in V3
construction_source_resolutions
```

`schema_migrations` rows: `(1, 'v1_initial_schema')`, `(2, 'v2_construction_delta')`,
`(3, 'v3_construction_review_queue')`.

### CLI smoke (against an isolated SQLite seeded with 10 inventory rows)

Setup: 10 inventory rows across `/Tropical/Contracts/`, `/Tropical/Financials/`,
`/Tropical/Legal`, `/Tropical/Safety/Incidents`, `/Tropical/HR/Employees`, and
`/Tropical/General` (with names like `Change Order 04 - Roofing.pdf`,
`Invoice 1042 - Subcontractor.pdf`, `Worker Injury Log.pdf`,
`Budget Estimate Draft.xlsx`, plus a clean-miss `Project Photos.zip`).

#### `review evaluate --dry-run`

```
{
  "mode": "dry_run",
  "rules": {"version": 1, "rule_count": 12, "low_confidence_threshold": 0.7},
  "summary": {
    "sources_evaluated": 1,
    "items_seen": 10,
    "matches_found": 11,
    "enqueued": 0,
    "skipped_already_open": 0
  }
}
```

`items_seen: 10` matches the 10 seeded inventory rows; `matches_found: 11`
reflects one item (`item-incident-folder` — "Site Incident Report.pdf" under
`/Tropical/Safety/Incidents`) firing both `folder-incidents` and
`term-incident` rules; `enqueued: 0` proves dry-run is non-persistent.

#### `review evaluate --apply` (1st run)

```
{
  "mode": "apply",
  "summary": {
    "sources_evaluated": 1, "items_seen": 10, "matches_found": 11,
    "enqueued": 11, "skipped_already_open": 0
  },
  "guardrails": {
    "external_systems": "read_only",
    "writeback": "none",
    "metadata_only": true,
    "model_decisioning": false,
    "controller_policy_authoritative": true,
    "deterministic_rules_only": true
  }
}
```

#### `review evaluate --apply` (2nd run — idempotency proof)

```
{
  "mode": "apply",
  "summary": {
    "sources_evaluated": 1, "items_seen": 10, "matches_found": 11,
    "enqueued": 0, "skipped_already_open": 11
  }
}
```

The `(source_key, item_id, rule_id)` UNIQUE constraint causes
`INSERT OR IGNORE` to skip every existing row.

#### `review list --status open`

```
{
  "total": 11,
  "counts_by_status": {"open": 11, "resolved": 0, "deferred": 0},
  "first_item": {
    "source_key": "tropical-sharepoint",
    "project_key": "tropical",
    "item_id": "item-personnel-folder",
    "rule_id": "folder-personnel",
    "classification_label": "personnel",
    "sensitivity": "high",
    "reason": "item lives under a personnel/HR folder",
    "suggested_action": "controller_review",
    "confidence": 1.0,
    "status": "open"
  }
}
```

### End-to-end vault preview — populated review note

After enqueueing the 11 matches above and running
`HB_CONSTRUCTION_VAULT_ROOT=$TMP construction-agent vault preview --apply --json`,
the writer produces `$TMP/02_Review_Queue/2026-05-27__review-required.md`
containing:

```markdown
---
type: construction-review-required
domain: construction
status: active
tags: [construction, review, queue]
owner: Bobby Fetting
generated: 2026-05-27T13:05:17.345061+00:00
---

# Review Required

> **Projection only.** SQLite is authoritative.
> Items appear here when classification or policy routes them to manual review.

- generated_at: `2026-05-27T13:05:17.345061+00:00`
- item_count: 11

## Items

| item_id | source_key | project_key | reason | suggested_action | classification |
| --- | --- | --- | --- | --- | --- |
| `item-personnel-folder` | `tropical-sharepoint` | `tropical` | item lives under a personnel/HR folder | controller_review | personnel |
| `item-low-conf-budget` | `tropical-sharepoint` | `tropical` | document name contains an ambiguous budget/estimate term | controller_review | financial |
| `item-legal-folder` | `tropical-sharepoint` | `tropical` | item lives under a legal folder | controller_review | legal |
| `item-invoice` | `tropical-sharepoint` | `tropical` | document name indicates an invoice or pay application | controller_review | financial |
| `item-injury-term` | `tropical-sharepoint` | `tropical` | document name contains an injury-related term | controller_review | injury |
| `item-incident-folder` | `tropical-sharepoint` | `tropical` | document name contains an incident-related term | controller_review | incident |
| `item-incident-folder` | `tropical-sharepoint` | `tropical` | item lives under an incidents or safety folder | controller_review | incident |
| `item-financials-folder` | `tropical-sharepoint` | `tropical` | document name contains an ambiguous budget/estimate term | controller_review | financial |
| `item-financials-folder` | `tropical-sharepoint` | `tropical` | item lives under a financials folder | controller_review | financial |
| `item-contract-folder` | `tropical-sharepoint` | `tropical` | item lives under a contracts folder | controller_review | contract |
| `item-change-order` | `tropical-sharepoint` | `tropical` | document name indicates a change order | controller_review | contract |

## Guardrails

- delta_token_storage: `sqlite`
- external_systems: `read_only`
- markdown_role: `projection_only`
- metadata_only: `true`
- sqlite_authoritative: `true`
- writeback: `none`
```

Every cell traces to a `rule_id` in the seeded YAML. The clean-miss row
(`item-clean-miss` — "Project Photos.zip") correctly produces zero queue rows.

## Guardrails attested

- **No model decisioning** for contract / financial / legal / incident /
  injury / personnel material. Every match traces deterministically to a
  `rule_id` in `resources/config/review_required_rules.seed.yaml`. Verified by
  reading the evaluator (`evaluator.py` — pure regex/substring) and the seed
  file (no inferred categories).
- **Sensitive material routes to review.** Every seed rule with
  `sensitivity: high|critical` always produces a match when its pattern fires;
  there is no suppression path. Verified by `test_evaluator_matches_*` suite.
- **Controller policy authoritative.** Code only loads + applies the YAML;
  evaluator never invents classification labels. Pydantic
  `ReviewRules._check_consistency` rejects any seed missing a protected
  category — model loading fails fast if a controller deletes coverage.
- **No source-document body / content / text read.** Evaluator inputs are
  `name` + `parent_path` only (already in
  `construction_drive_item_inventory`). The renderer's
  `ReviewRequiredItem` model carries no body field. Verified by
  `test_rendered_note_never_leaks_body_text`.
- **SQLite is authoritative.** All queue state lives in
  `construction_review_queue`; the Markdown note is a recomputable projection.
- **External systems read-only.** This prompt makes zero Graph, Procore,
  OneDrive, or Outlook calls. SQLite is the only mutation surface.
- **Apply gating preserved.** Vault writes still require
  `HB_CONSTRUCTION_VAULT_ROOT` (or `AppConfig.paths.construction_vault_root`).
  `review evaluate --apply` writes only to SQLite — no vault writes.

## Known limitations

- Full `python -m pytest` is not in scope. The handoff documents pre-existing
  hangs in `test_cli_canonical.py` (non-help subset), `test_auth.py`,
  `test_automation.py`, `test_actions_cli.py`, `test_files_cli.py`,
  `test_graph_*`, `test_mutation_lockout.py`, `test_sensitive_scan_cli.py`,
  `test_mvp_local_runtime_evidence.py` — all interactive MSAL / subprocess
  driven. Not introduced by this work.
- `tests/test_obsidian_writer.py` has 4 pre-existing baseline failures
  (`action_item_ids` keyword drift between test and
  `MarkerBoundedWriter.write_bounded_section` signature). Predates this
  session; out of scope.
- Live Graph round-trip not exercised — the prompt is purely SQLite-driven and
  this remains blocked on interactive MSAL auth.
- The seed rule patterns are tuned for common folder/document naming
  conventions (`/Contracts/`, `Change Order`, `Invoice`, `Injury`, `OSHA`,
  etc.). Bobby may tune via `config/review_required_rules.yml` or
  `HB_CONSTRUCTION_REVIEW_RULES` without code changes.

## Commit

```
feat(construction-agent): add review queue policy
```
