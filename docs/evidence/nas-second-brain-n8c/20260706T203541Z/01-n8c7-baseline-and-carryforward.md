# N8C-8 — baseline & carry-forward

## Commits
- N8C-6 (context packs): `c9866927207190a8cae092125107148285d6f46d` — `feat(nas): add n8c context pack builder`.
- N8C-7 (memory compiler): **`b99151f175c2028fcda255b449be050172a50f0a`** — `feat(nas): add n8c memory compiler`
  (parent c9866927, no AI trailer; committed in Part 1 of this session, staged-only, not pushed).
- N8C-8 branch: **`ops/nas-second-brain-n8c-08-decision-open-loop-memory-20260706T203541Z`**, base
  **`b99151f1`** (the N8C-7 commit).

## Preflight (verified before any N8C-8 change)
- HEAD at `b99151f1`, `LATEST_SCHEMA_VERSION = 103`, no `src/hb_assistant/agent_bridge/` (no N8D in this
  worktree), branch = the N8C-7 branch at time of Part 1.
- No N8D merged → next schema version is **V104**.

## Carry-forward the N8C-8 extractor consumes (READ-ONLY)
- **N8C-4 claims (V100):** `claim_type` is a CHECK-constrained enum already including
  `decision_candidate` / `preference` / `commitment` / `task_candidate` / `risk` / `assumption` /
  `date` / `fact` / `unknown`. `ClaimRepository.list_claims(claim_type=…, status=…)` and `get_claim`
  are read-only. Extraction keys off this structured field — no LLM, no fuzzy inference.
- **N8C-5 enrichment receipts (V101):** `source_summary` results are thin (summary + key_points +
  confidence — no risks/preferences/open_questions arrays), so decision/preference/open-loop signal
  comes from claims, not summaries.
- **N8C-6 context packs (V102):** the pack's `claim_candidate` items carry `claim_id` + provenance;
  extraction is pack-scoped over `ContextPackRepository.list_items(pack_id)`.
- **N8C-7 memory (V103):** built compilations' `preferences_json` / `risks_json` /
  `open_questions_json` feed the WEAK secondary path (a new read-only
  `MemoryRepository.list_built_compilations_for_sources` helper — no schema change, no write).

## Boundaries carried forward (unchanged)
No N8D / `agent_bridge`; no vault mutation; no source/card rendering change; no claim/memory mutation
(only N8C-8-owned tables are written); candidate claims stay candidate/unreviewed;
`ai_outputs_card_upsert` remains the only sanctioned remote write.
