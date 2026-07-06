# N8C-7 — boundary proofs (no writeback, no raw, advisory-only)

## No mutation outside the four memory tables
Temp migrated DB seeded via repos (candidate claim + claim_extraction/source_summary/backlink
receipts + an enrichment_review context pack). Row counts of every `assistant_claim*`,
`assistant_enrichment*`, `assistant_context_pack*`, `source_intelligence*` table captured before/after:

- `preview` and `apply_memory_compilation(apply=False)` (dry-run): **non-memory row counts identical**
  (`test_memory_compiler.py::test_preview_and_dry_run_are_read_only`; smoke run confirmed).
- `apply_memory_compilation(apply=True)`: writes only `assistant_memory_*`; **all non-memory tables
  unchanged** (`test_memory_compiler.py::test_apply_writes_only_memory_tables`; smoke run: 4 nodes /
  4 mentions / 4 compilations written, claims/enrichment/context-pack/source untouched).
- The repository (`MemoryRepository`) only ever `INSERT`/`UPDATE`s the four memory tables — it holds no
  SQL against any other table.

## Claims stay candidate / unreviewed (no auto-acceptance)
The compiler READS claims (`ClaimRepository.get_claim`) and never mutates them. After apply, every claim
remains `status=candidate`, `review_state=unreviewed`
(`test_memory_compiler.py::test_claims_stay_candidate_unreviewed`; smoke run confirmed). A node's
`status`/`review_tier` and a compilation are advisory compiled records — they do **not** imply the
underlying claim was accepted.

## No raw bodies / prompts / responses persisted
- Mentions store bounded `evidence_excerpt` (hard cap) + `source_digest`/`card_digest` (sha256) +
  `receipt_id` — never the enrichment `result_json`, a raw source/email body, or a raw prompt/response.
- `mention_text` capped at 500; `evidence_excerpt` at 2 000; `summary` at 8 000; `key_points` ≤ 20.
- `export_memory_node` emits **JSON only**: ids + digests + bounded excerpts + relative paths. Smoke
  export contained no `result_json`, no `/Users/` absolute path
  (`test_memory_compiler.py::test_export_is_bounded_json`).

## Idempotency
- Same input → no duplicate nodes/mentions/compilations; re-apply reports `new_mentions=0`,
  `new_compilations=0`, node count stable
  (`test_memory_compiler.py::test_apply_is_idempotent_no_duplicates`; smoke run confirmed).
- Changed input digest → a new compilation that supersedes the prior `built` one
  (`test_changed_input_creates_new_compilation_and_supersedes`).
- `node_id` stable while normalized identity unchanged (`test_node_id_stable_when_identity_unchanged`).

## No vault / no rendering / no startup / no N8D
- No vault write, no source/card rendering change (compiler is DB-only).
- No startup compiler/scheduler/worker; compilation is opt-in via CLI/preview only, pack-scoped.
- No `src/hb_assistant/agent_bridge/` in the worktree; no `agent_bridge` import in any changed file
  (grep clean). No `merged`/`archived` node-merge or operator-disposition workflow (deferred; enum
  values reserved). No vector store / LlamaIndex / broad graph schema.
- No remote MCP write/compile/apply tool; `ai_outputs_card_upsert` stays the only sanctioned remote
  write.

## Advisory tiers observed
Smoke corpus (sources unindexed) produced node tiers `{low_confidence, stale_source}` — cautious
tiers, none `trusted_source_backed` — demonstrating the provenance-quality derivation is active and
never over-claims. `mention_tier()` rule table is unit-proven in
`test_memory_compiler.py::test_tier_rules` (trusted / stale / ambiguous / low-confidence /
Qwen-summary / raw-fallback / backlink).
