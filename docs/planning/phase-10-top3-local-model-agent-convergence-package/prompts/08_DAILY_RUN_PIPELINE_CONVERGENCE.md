Repository: `RMF112018/hb-personal-assistant`  
Local path: `/Users/bobbyfetting/hb-personal-assistant`  
Branch: `experiment/phase-10-top3-local-model-agent-convergence`  
Evidence root: `docs/evidence/phase-10-top3-local-model-agent-convergence`

Hard constraints apply from `../README.md`, `../STOP_CONDITIONS.md`, and `../reference/02_SAFETY_CONTRACT.md`.

# Prompt 08 — Pipeline-Level Convergence Across All Three Candidates

## Objective

Ensure daily-run orchestration treats all three candidates as one coherent run, not separate bolted-on surfaces.

## Required final order

Recommended stage order:

1. follow_up_watch
2. email_followup_raw_enrichment
3. procore_digest
4. calendar_prep
5. daily_brief_synthesis / candidate generation
6. relationship_candidates if enabled
7. model_enriched_intelligence
8. daily_brief_render
9. browser/Obsidian/status writes

Adapt only if repo-truth requires a safer ordering.

## Required behavior

- If email raw enrichment writes pending V45 rows, Model Enriched Intelligence consumes them in the same run.
- If local model is unavailable, deterministic daily brief still renders and status records degraded/withheld model enrichment.
- If render egress scan fails, withhold unsafe browser output and preserve last successful path.
- If any generation stage fails, status is partial/degraded and honest.
- Last-successful pointer updates only on fresh, safe success.
- Apply remains bounded by stage and global caps.

## Evidence

Create/update:

- `15-daily-run-integrated-proof.json`
- `16-model-unavailable-fallback-proof.json`
- `23-output-path-safety-proof.md`

## Tests

Add an integration-style test with a fake/static local model client and seeded DB copy or in-memory store that proves:

- V45 pending row created/available
- Model Enriched Intelligence built
- Browser/Obsidian/status surfaces match
- no raw content in outputs
