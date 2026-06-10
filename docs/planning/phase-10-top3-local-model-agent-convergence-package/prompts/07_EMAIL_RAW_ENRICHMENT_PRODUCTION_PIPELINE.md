Repository: `RMF112018/hb-personal-assistant`  
Local path: `/Users/bobbyfetting/hb-personal-assistant`  
Branch: `experiment/phase-10-top3-local-model-agent-convergence`  
Evidence root: `docs/evidence/phase-10-top3-local-model-agent-convergence`

Hard constraints apply from `../README.md`, `../STOP_CONDITIONS.md`, and `../reference/02_SAFETY_CONTRACT.md`.

# Prompt 07 — Email Raw Enrichment Production Pipeline

## Objective

Integrate V45 email raw enrichment into the daily-run apply pipeline as a bounded, local-only, review-safe stage.

## Required behavior

The daily-run pipeline must include an email raw enrichment stage when:

- daily-run is in apply mode;
- raw email enrichment is enabled;
- readiness reports eligible rows;
- local model route is available;
- cap is positive;
- source links are valid.

Dry-run must report `would_enrich` / `would_persist` but persist nothing.

Apply must:

- enforce `max_persist` / daily-run stage cap;
- persist only V45 review-safe rows;
- remain idempotent;
- source-link every persisted row;
- update pending-row consumption so final brief can show pending review-safe items;
- never persist raw body/prompt/response.

## Required CLI behavior

Add/normalize daily-run flags:

- `--email-raw-enrichment`
- `--no-email-raw-enrichment`
- `--email-raw-enrichment-max-persist N` if separate from stage caps is needed

If existing `--with-email-raw-enrichment` exists, preserve it as alias and update help text.

## Required stage receipt

Daily-run receipt must include:

```json
{
  "stage": "email_followup_raw_enrichment",
  "status": "ok|skipped|degraded|failed",
  "eligible": 0,
  "would_persist": 0,
  "persisted": 0,
  "skipped_by_reason": {},
  "degraded_reason": null
}
```

No raw fields.

## Evidence

Create:

- `12-email-raw-enrichment-dry-run-proof.json`
- `13-email-raw-enrichment-capped-apply-proof.json`
- `14-email-raw-enrichment-idempotency-proof.json`
- update `15-daily-run-integrated-proof.json`

## Tests

Add tests for:

- dry-run no persistence
- apply requires cap
- cap respected
- idempotency
- model unavailable skip/degrade
- source-link required
- raw policy disabled skip/degrade
- final pending rows appear in Model Enriched Intelligence section
- guard columns remain zero
