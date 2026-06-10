Repository: `RMF112018/hb-personal-assistant`  
Local path: `/Users/bobbyfetting/hb-personal-assistant`  
Branch: `experiment/phase-10-top3-local-model-agent-convergence`  
Evidence root: `docs/evidence/phase-10-top3-local-model-agent-convergence`

Hard constraints apply from `../README.md`, `../STOP_CONDITIONS.md`, and `../reference/02_SAFETY_CONTRACT.md`.

# Prompt 02 — Daily Brief Intelligence / Synthesis Convergence

## Objective

Converge the existing daily-brief intelligence adapter and daily-brief synthesis path into one default-on, source-linked final-surface model-enrichment path.

## Required behavior

The daily-run path must produce a unified object, recommended name:

```python
model_enriched_intelligence
```

It must include safe metadata such as:

- `enabled`
- `available`
- `label`
- `generated_utc`
- `candidate_count`
- `candidate_freshness`
- `source_link_count`
- `source_link_coverage`
- `bullets_seen`
- `bullets_kept`
- `bullets_dropped`
- `unknown_source_ids_count`
- `pending_followup_count`
- `route_selected_profile`
- `route_model_name`
- `terminal_profile_id`
- `generation_profile_id`
- `fallback_chain`
- `withheld_reason`
- `degraded`
- `warnings`
- `guardrails`

## Source-link rule

Every model-generated bullet or action must cite at least one known source/candidate identifier. Unknown or malformed cited IDs must be counted and dropped. If no source-linked bullets survive, withhold the model-enriched section body and preserve deterministic fallback.

## Synthesis convergence rule

If both a narrative synthesis path and an intelligence object path exist:

- avoid duplicate model calls when one call can produce the unified object safely;
- otherwise clearly document why two calls remain temporarily necessary and ensure final surfaces still render one section;
- never allow conflicting facts between paths;
- deterministic brief remains source of truth.

## Required implementation

1. Add or update a contract/model for the unified object.
2. Route through local-only `model_router.route_task_family`.
3. Use existing structured-output repair only if raw prompt/response stays in memory.
4. Preserve existing deterministic fallback.
5. Update daily-run orchestration to build the unified object by default.
6. Preserve backward-compatible CLI behavior for old `--with-intelligence` flags if present.

## Evidence

Create:

- `03-current-surface-audit.md`
- update `04-unified-design-contract.md`
- `05-daily-brief-intelligence-convergence-proof.json`

## Tests

Add tests for:

- default-on behavior
- explicit disable behavior
- source ID alias mapping
- unknown source IDs dropped
- no surviving source links -> withheld
- model unavailable -> deterministic fallback
- schema-invalid after repair -> withheld with safe reason
