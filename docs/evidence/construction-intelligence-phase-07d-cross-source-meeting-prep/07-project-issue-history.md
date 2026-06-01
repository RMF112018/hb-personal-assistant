# 07D Prompt 07 — Project Issue History (Evidence)

Additive over schema **V25** (no migration). Materializes `project_issue_history_items` by grouping
the cross-source substrate into per-issue families (deterministic + strong-heuristic only) via a new
`construction-agent issue-history` sub-app.

## Preflight (repo truth)

- `git rev-parse HEAD` → `a400af3c44e404e8e0746a2d711b892e6ca71a18` (Prompt 06 HEAD).
- `git status --short` → clean (only untracked `.claude/`, `.code-graph/`).
- `python --version` → Python 3.12.11 (`.venv/bin/python3.12`); `hb-assistant --version` → `1.3.0`.
- Schema version → **25**; package version → `1.3.0`.
- Ancestry — all ancestors of HEAD: 07A `3cf1652…`, 07B `748ed7e…`, 07C `733ffed…`.
- Evidence folder present with `00`–`06`; this adds `07`.

## What changed

- **Engine** `construction/issue_history/issue_history_builder.py` (+ `__init__.py`):
  `IssueHistoryBuilder.build()` (dry-run default / `--apply`), per-anchor grouping, best-effort
  activity/status resolution, bounded status normalization, and a read-only
  `project_issue_history_status()`.
- **Store** `construction/store/repositories.py`: `upsert/list/count_project_issue_history_item(s)`.
- **CLI** `cli/construction.py`: `construction-agent issue-history build/status`.
- **Tests** `tests/test_issue_history.py` (9).
- Reused unchanged: `relationships/contracts.py`, the V25 table already present in `store/migrator.py`,
  and the `list_cross_source_relationship_candidates` / `list_procore_live_records` / `hash_value`
  helpers. `project_issue_history_items` was already registered in the table-lifecycle contract
  (inventory count stays 120 — untouched).

## Design grounded in repo + live-data truth

- **Grouping = one family per anchor source record** (not a transitive component, which would
  collapse the project into mega-families through shared entities). Live result: 598 bounded families.
- **Eligible edges = deterministic + strong_heuristic, excluding sensitive_high_impact / model_proposed.**
  Weak/model/sensitive are never grouped and never promoted.
- **Activity/status best-effort honest:** procore anchors resolve against `procore_live_records`
  (557/562 refs match) for real `updated_at_utc` + normalized status + computed `age_days`; unresolved
  anchors get NULL activity + a `stale_unknown` flag.
- **Status normalization:** Procore dict-string statuses (`{'id':…,'name':'Open','mapped_to_status':'open'}`)
  are mapped to a bounded token and never persisted raw.

## Static + test validation (exit codes)

| Command | Result |
|---|---|
| `python -m compileall src tests` | exit 0 |
| `ruff check .` | exit 0 — All checks passed |
| `mypy src` | exit 0 — no issues in **182** source files |
| `pytest -m "not live and not integration and not manual"` | **2182 passed**, 1 deselected (exit 0) |

(Prompt 06 baseline 2173; +9 new issue-history tests.)

## CLI validation matrix (all exit 0)

`issue-history build` (dry-run), `issue-history build --apply`, `issue-history status`,
`construction-agent {validate, data-quality gates/no-writeback-proof/table-inventory}`,
`procore validate`, `graph files status/no-writeback-proof`, `graph calendar status`,
`graph mail status` — captured to `/tmp/p07/*.json` (ephemeral, not committed).

### Live `issue-history build` (project `tropical`)

| Run | mode | families_written | review_required | resolved / unresolved activity |
|---|---|---|---|---|
| dry-run | dry_run | 0 (planned 598) | — | — |
| apply | apply | 598 | 36 | 522 / 76 |

- `by_confidence_class` = {deterministic: 562, strong_heuristic: 36} (all 36 strong families are
  review-required; the 562 deterministic are not).
- `by_status` = bounded normalized tokens only: approved 253, unknown 158, open 132, closed 14, draft
  11, void 9, pending 6, none 5, out_for_pricing 5, overdue 4, initiated 1 — no raw dict-strings.
- `by_issue_kind` = procore endpoints (budget-modifications, change-events, commitment-contracts,
  commitment-change-orders, inspections, …) plus `email_message` / `calendar_event` for cross-source
  anchors.
- `issue-history status` → `items=598`, `review_required=36`, `resolved_activity=522`.

### Safety invariants (after live apply)

- No-raw-content regex over the serialized `build --apply` and `status` payloads → **no match**;
  the raw Procore status dict-string (`mapped_to_status`/`'name'`) is **not** present.
- All eight guard `CHECK(… = 0)` columns stay 0 on `project_issue_history_items` (asserted in tests).
- `data-quality no-writeback-proof` `proof_passed=true`; `graph files no-writeback-proof` `ok=true`.
- `table-inventory` `schema_version=25`, `contract_table_count=120` (no new tables).
- `data-quality gates` `meeting_prep_readiness_claim="ready"` — unchanged.

## Test-path coverage (new file)

success (per-anchor grouping, two edges → one family, deterministic, not review-required, guard
columns 0); strong→review_required; weak/model/sensitive excluded (0 families); activity resolution +
status normalization (`age_days` deterministic via injected now); unresolved anchor → NULL +
`no_source_activity_timestamp`; no-raw-content (incl. no raw status payload); idempotent apply; dry-run
writes nothing; status coverage.

## Guardrails honored / stop conditions

- No external writeback / write scopes; no mutation beyond the local SQLite issue-history table; no
  schema change.
- No raw content, raw status payload, signed/download URL, token, secret, prompt, or response
  persisted (no-raw test + both no-writeback proofs).
- Weak/model/sensitive relationships excluded from grouping and never auto-promoted; strong-heuristic
  families stay review-required.
- Advisory only — no final legal/contractual/claim/safety/financial determination.
- Readiness not overstated: activity/status only asserted when resolvable; otherwise flagged stale.
- No stop condition triggered; all validations classified and passing.

## Handoff

- **Changed:** new `issue_history` engine + `__init__`, 3 store methods, `issue-history` CLI sub-app,
  new issue-history test file, `docs/architecture/50-…md`, this evidence, README 07D ledger.
- **Gates pass/fail:** unchanged and honest (`meeting_prep_readiness_claim="ready"`); no new gate.
- **Next prompt allowed to proceed:** yes. Prompt 08 (risk digest) may build on the issue-history
  families and the substrate; grouping, activity resolution, and review routing are in place.
