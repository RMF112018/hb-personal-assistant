# 09 — Risk & Defer List

## Deferred (with rationale)
1. **Model-based extraction (Qwen/Ollama)** — deferred by design. N8C-4 is deterministic/rule-based
   only. The `ingest_claim_candidates` seam reserves `extracted_by="future_qwen"` so a later worker-queue
   slice writes through the same validated path with no schema change.
2. **Remote MCP claim tools** — not added. Keeping the internet-facing surface at the N8C-3 12-tool
   `assistant_*` set; remote claim exposure is a separate, future operator decision. Claims are
   local-API + internal only this slice.
3. **Scheduled stale scan / maintenance loop** — deferred. N8C-4 provides the status/`source_state`/
   `valid_until`/`stale_after`/`superseded_by` fields + `mark_stale()` hooks a future loop can drive.
4. **Decision / preference / open-loop subsystems, context packs, graph/entity compilers, frontend
   command center, research/feedback** — out of scope; represented here only as claim *types*.

## Out of scope (not implemented)
Qwen queue, Ollama, autonomous extraction, decision/preference/open-loop workflows, context packs,
graph compiler, entity/concept/domain compiler, frontend command center, research/skeptic, feedback
learning, maintenance loops, broad MCP write tools, `db_allowlist` expansion, raw/import DB mutation,
mass vault/card rewrite, remote claim-write tools.

## Stop-condition check — none tripped
N8C-3 committed cleanly (`86701ad8`) and its evidence records the intentional deep-content default;
N8C-4 branched from it; no Qwen/Ollama required; no broad graph schema; no raw/import DB mutation
(claim repo writes only `assistant_claim*` — grep-verified); no startup job (no-auto-run proven);
no remote claim-write surface; source/card ambiguity + deletion handled safely (block); stale labeled;
evidence carries no secrets/raw private content/unredacted absolute paths.

## Residual notes
- Schema advanced 99 → 100 (one additive migration, idempotent, empty tables). Existing migration
  guard tests updated to track the constant.
- The pre-existing failing `test_migrator_v65_schedule_float.py` (stale `== 67` assertion) is unrelated
  to N8C-4 and was left untouched.
