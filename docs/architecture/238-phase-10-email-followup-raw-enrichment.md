# 238 — Phase 10: Email Follow-Up Raw Enrichment (V45)

Status: experiment (`experiment/phase-10-email-followup-raw-enrichment`) · Local-only · No cloud LLM ·
No external writeback · Schema head **V44 → V45** (additive)

## Purpose

Improve follow-up quality, open-loop detection, waiting-on-me / waiting-on-others classification, and
source-linked daily-brief intelligence by letting a **local-only** model read a *bounded, sanitized,
non-persisted* window of the actual email thread behind an already source-linked follow-up item —
without ever persisting raw content. Model-enriched fields land in a new review-safe V45 table and may
be consumed by the daily brief as clearly-labeled, raw-free, source-linked items.

This is additive. The deterministic follow-up watch scan, the daily brief, and every existing
consumer are unchanged unless the new opt-in flags are passed.

## Workflow

```
accepted_tasks / accepted_commitments (+ follow_up_watch_items)
  → eligible, email-source-linked, open candidates (candidate_source_refs)
  → ephemeral raw email window (no raw DB writes; quote/sig/disclaimer strip;
      URL/token/secret/email/phone redaction; HTML + attachments excluded; capped)
  → local-only structured model route (fail-closed; no cloud)
  → validation gates (schema, cited-refs ⊆ input, raw_excerpt_hash match, no raw leakage)
  → V45 email_followup_enrichments (review-safe; structured fields + hashes + source refs)
  → review surfaces + pending daily-brief items ("Model-enriched / pending review")
```

## Design

### V45 — `email_followup_enrichments` (`store/migrator.py`)
Additive `CREATE TABLE/INDEX IF NOT EXISTS`. Persists ONLY structured/redacted enriched fields
(`enriched_title`, `waiting_state`, `assignee_type`, `assignee_display`, `suggested_next_action`,
`due_at_utc`, `confidence`, `confidence_band`, `reason_codes_json`), source references
(`source_refs_json`, `email_thread_ref_hash`, `email_message_ref_hashes_json`), review/model metadata
(`review_status` default `pending`, `model_task`, `model_profile_id`, `prompt_template_version`), and
SHA-256[:12] hashes (`raw_excerpt_hash`, `input_context_hash`, `output_hash`). Unique
`idempotency_key`; five access indexes; the full 13 Phase-10 guard columns (`CHECK = 0`). No raw
body/prompt/response/HTML/URL/token/secret column exists. Classified in
`resources/json/table_lifecycle_status_contract.json` (count 221 → 222).

### Contracts (`local_ai/email_followup_models.py`, `local_ai/email_followup_route.py`)
`EmailFollowupEnrichmentRow` (persistence) and `EmailFollowupEnrichmentOutput` (strict model output;
`extra="forbid"`) with closed enums, confidence range, a field validator rejecting raw leakage in
free-text fields, and `validate_enrichment_output` cross-checks (cited refs must be provided, hash
match, deadline requires a `due_date` reason code). `find_raw_leak` is the shared scanner reused by
validators, the engine guard, and evidence scans.

### Raw window (`local_ai/raw_followup_window.py`)
Builds the bounded redacted window from `email_message_raw_content` directly — deliberately NOT
`raw_context.build_raw_email_context_packet` (which persists a packet row). Nothing is written.
`build_raw_local_preview(opt_in=True)` is the only path to surface the text; the object is marked
non-persistable.

### Route (`resources/config/local_model_task_routing.seed.yaml`)
`email_followup_raw_enrichment → default_extract` (mistral-nemo:12b), local-only fallback chain,
fail-closed via `route_task_family` (no cloud route exists). Reuses `StructuredOutputClient`
(hash-only receipts; never persists raw prompt/response).

### Engine (`local_ai/email_followup_enrichment.py`)
Selects eligible units, builds the window, routes+calls the model, validates, runs a defense-in-depth
per-field raw-leak guard, and persists V45 rows only under `apply` + a positive `max_persist`
(idempotent). Dry-run default. Missing raw / unavailable model / no eligible items degrade cleanly.

### CLI (`cli/second_brain.py`)
- `second-brain follow-up-watch enrich [--candidate-id] [--show-raw-local] [--dry-run|--apply --max-persist N] [--db] [--json|--no-json]`
- `second-brain follow-up-watch scan --with-raw-enrichment [--apply --max-persist N] [--dry-run] [--json]`
- `second-brain daily-run run --with-email-raw-enrichment` (read-only consumption of pending rows)

`--show-raw-local` requires `--dry-run` + `--no-json` and is refused with `--json`/`--apply`; the
preview is terminal-only with a warning banner and never written to JSON/evidence/logs.

### Daily brief (`daily_brief/email_followup_pending.py`)
Surfaces `review_status='pending'` rows labeled **"Model-enriched / pending review"**; low-confidence
items are labeled "low confidence / needs review" or omitted per policy. Source-linked, raw-free,
fail-closed (missing table / no rows → deterministic brief unchanged).

## Guarantees / invariants

- No raw body/prompt/response/HTML/URL/token/secret/email is ever persisted, logged, put in
  evidence, the browser brief, or the Obsidian brief. Raw content is loaded only in-memory for one
  enrichment call or one explicit operator preview.
- Local-only; no cloud route; fail-closed when no local model.
- Dry-run default; apply requires a positive cap; idempotent; source-linked only.
- No Microsoft 365 / Graph / calendar / Procore / MCP / external writeback.
- 13 guard columns stay 0; validation runs on DB copies; production DB is never mutated.

## Known limitations

- The production DB currently has no accepted follow-up candidates with email source refs, so the
  production-copy CLI run is a clean no-op; persistence/cap/idempotency are proven on a seeded copy
  and at the engine layer.
- `due_at_utc` invention is guarded heuristically (requires a `due_date` reason code) rather than by
  parsing context dates.
- Daily-brief consumption is exposed via `daily-run run --with-email-raw-enrichment` (payload
  section); wiring it into the rendered Obsidian/browser brief body is left for a follow-up.

See `docs/evidence/phase-10-email-followup-raw-enrichment/` and
`docs/runbooks/phase-10-email-followup-raw-enrichment-runbook.md`.
