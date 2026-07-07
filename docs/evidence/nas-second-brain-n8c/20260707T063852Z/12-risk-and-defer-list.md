# 12 — Risk & Defer List

## Deferred (out of scope for N8C-10, by design)

- **N8D bridge / agent orchestration** — projections are a passive read product; consuming them into an
  agent/action loop is N8D and lives in a separate worktree. No `agent_bridge` import here.
- **Qwen/LLM enrichment of projections** — the builder is strictly deterministic (no LLM). Any future
  LLM-assisted summarization of a trusted-context packet is a later slice; it must preserve the
  read-only + bounded + no-writeback invariants.
- **Additional projection types** — `project_intelligence`, `decision_memory_context`,
  `open_loop_context`, `daily_brief_context` are enum-reserved and fall back to default policy today;
  bespoke policies for them are deferred until a consumer needs them.
- **Frontend surface** — API routes exist and are `_assert_safe`; a React panel that renders trusted vs
  candidate context is a UI slice, not this backend phase.
- **Cross-pack / global projections** — intentionally NOT built. Projections are pack-scoped; no global or
  whole-DB default exists (a guard against unbounded scans).
- **Remote build/apply** — never exposed. Building a projection is CLI/service-local only.

## Risks & mitigations

- *Stale projection served after a new disposition* — mitigated by digest-driven supersede: a new
  disposition changes `input_digest` → new `projection_id`; the prior same-type+scope projection is marked
  `superseded`. `mark_projection_stale_if_needed` also lets a consumer detect drift. Consumers should read
  `status` and prefer `built`.
- *Provenance loss* — mitigated by the DB provenance CHECK (≥1 anchor) + `test_items_preserve_provenance`.
- *Payload bloat / leak* — mitigated by hard caps + `_assert_safe` API test + excluded-item minimization.
- *Enum drift vs review overlay* — mitigated by re-using the N8C-9 enum tuples in the V106 schema module.

## Known non-blocking notes

- `construction/analytics/api.py` carries 13 pre-existing `I001` import-sort findings and other pre-existing
  ruff findings unrelated to this phase (the file predates this work and is large). The N8C-10 additions to
  it are ruff-clean; no pre-existing finding was "fixed" to avoid out-of-scope churn.
