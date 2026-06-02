# Phase 08A · Synthesized Prompt 04 — Retrieval Policy, Context Budget, Retrieval Broker — Proof

Implements the deterministic Retrieval and Source Broker Agent (A03): the only path
to model-bound context. Local-first, no embeddings, no raw SQL, no raw source
access, no external writeback, no new SQLite tables (schema stays V26 / 141).
Package baseline `c2656e1` is stale; actual HEAD at start was `05e8486`.

## Repo-truth preflight (before edits)

| Check | Result |
| --- | --- |
| `git rev-parse HEAD` | `05e848614908050ce527c9e13c3e5dc09429f700` |
| `git status --short` | clean except untracked `.claude/`, `.code-graph/` |
| `construction-agent validate --json` | `schema_version=26` |
| `data-quality table-inventory --json` | `contract_table_count=141` |
| `data-quality no-writeback-proof --json` | `proof_passed=true` |

## Files changed

Created:
- `src/hb_assistant/resources/json/retrieval_policy_contract.json`, `context_budget_contract.json` (from package).
- `resources/config/phase_08a_retrieval_policy.seed.yaml` (from package), `phase_08a_context_budget.seed.yaml` (authored; contract-field-name reconciliation).
- `src/hb_assistant/construction/second_brain/retrieval/__init__.py`, `models.py`, `policy.py`, `readers.py`, `broker.py`.
- `tests/test_retrieval_policy.py`, `tests/test_retrieval_broker.py`.
- `docs/architecture/61-phase-08a-retrieval-policy-and-broker.md`.
- `docs/evidence/.../retrieval-policy-proof.md`, `retrieval-broker-agent-proof.json`.

Modified:
- `src/hb_assistant/construction/second_brain/contracts.py` (registered 2 contracts).
- `src/hb_assistant/construction/second_brain/__init__.py` (re-export retrieval API).
- `tests/test_phase_08a_contracts.py` (required-key maps for the 2 new contracts).

## Validation commands and exit codes

| Command | Result |
| --- | --- |
| `python -m compileall src tests` | exit 0 |
| `ruff check .` | All checks passed! (exit 0) |
| `mypy src` | Success: no issues found in 205 source files (exit 0)* |
| `pytest tests/test_retrieval_policy.py tests/test_retrieval_broker.py` | 16 passed |
| `pytest -m "not live and not integration and not manual"` | 2362 passed, 4 skipped, 1 deselected (exit 0) — +19 new tests |
| `construction-agent validate --json` | `schema_version=26` (unchanged) |
| `data-quality table-inventory --json` | `contract_table_count=141` (unchanged) |
| `data-quality no-writeback-proof --json` | `proof_passed=true` (unchanged) |

\* pre-existing benign note about an unused `hb_assistant.retrieval.context` override; no errors.

## Evidence proof

`retrieval-broker-agent-proof.json` — `proof_passed: true`; deterministic synthetic
run across tiers 1/2/3: every item carries source_ref + confidence + review_tier;
Tier 3 visible but `review_required` (not concluded); `no_raw_content: true`;
`no_raw_source_access: true`; `no_arbitrary_sql: true`; budget enforced
(context_char_count ≤ 24000); allowlisted + denied families enumerated;
`guardrails.mcp_implemented: false`.

## Guardrail proof points (tests)

- **No raw source access** — readers select only hardcoded safe columns; envelope
  forbidden-field validator rejects raw reference fields (`test_no_raw_source_access`).
- **Items carry source refs + confidence + review tier + warnings**
  (`test_retrieve_returns_source_linked_items`).
- **Tier 3 visible, not concluded** — review-required relationship stays
  `review_tier=3`, `review_status=review_required` (`test_tier3_visible_but_review_required`).
- **Excluded families denied** — requesting `raw_email_body` yields a
  `denied_excluded_family` coverage warning and no item (`test_excluded_family_denied`).
- **V25 not rewritten** — relationship rows identical before/after retrieve
  (`test_v25_rows_unchanged_after_retrieve`).
- **Receipts metadata-only** — `retrieval_query_receipts` +
  `retrieval_context_refs` persisted with all 10 `CHECK(col=0)` guard columns at 0,
  mode `dry_run` (`test_receipt_persisted_with_guards_zero`).
- **Deterministic budget** — staged tier→recency→confidence truncation is stable
  across runs (`test_budget_truncates_deterministically`).

## Reconciliations / known limitations

- Context-budget seed authored to carry the contract's exact required-field names
  (`deterministic_truncation`, `degradation_behavior`) — the package seed used
  `truncation`/`degradation_modes`.
- Three allowlisted families have no read model yet
  (meeting_prep_brief_sections, review_controlled_correspondence_context,
  approved_obsidian_generated_outputs) → graceful coverage warning, never fabricated.
- Relationship sensitivity/model-proposed flags live on V25 *candidates*, not the
  promoted `cross_source_relationships` table; the broker forces Tier 3 from a row's
  `review_required` flag. `derive_relationship_state` covers all 8 labels and is unit-tested directly.

## Env var names (no values)
`HB_SECOND_BRAIN_RETRIEVAL_POLICY`, `HB_SECOND_BRAIN_CONTEXT_BUDGET`.

## Next prompt readiness
The broker produces a `ContextEnvelope` (via `to_context_envelope`) for the Claude
adapter. Next: research-packet agent (consumes broker output), orchestrator/query +
daily-brief wiring (Prompts 05/06/13), LlamaIndex/embeddings (Phase 09), and the
V27 agent receipt tables + 08A no-writeback proof arm (owning prompts).
