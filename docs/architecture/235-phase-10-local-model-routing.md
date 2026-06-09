# 235 — Phase 10: Local Model Evaluation + Routing for Daily-Brief Intelligence

Status: experiment (`experiment/local-model-routing-daily-brief-intelligence`) · Local-only ·
No cloud LLM · No external writeback · No schema migration (schema head V44 unchanged)

## Purpose

Stop the daily brief from degrading into a sparse dump by adding a **quality layer** across the
already-operational Phase 10 daily-run loop:

1. A repeatable **evaluation harness** that measures which local model/profile is reliable per repo
   task (JSON validity, schema validity, redaction safety, latency, operator usefulness).
2. A deterministic **task → profile router** with a local-only fallback chain (never cloud).
3. An optional, advisory **daily-brief intelligence** adapter that produces a compact, source-linked
   executive object, fail-closed to the deterministic brief.

This is additive: existing consumers (e.g. daily-run `--synthesize`) keep their hardcoded defaults.

## Data flow

```
phase_10_local_model_profiles.seed.yaml ──┐
local_model_task_routing.seed.yaml ────────┤→ model_router.route_task_family() → profile decision
                                           │       │ (validates Ollama availability via provider.probe_models)
                                           │       ▼
daily_brief_action_candidates (redacted) ──┴→ daily_brief_intelligence.build_daily_brief_intelligence()
                                                   │ StructuredOutputClient (schema, retry/repair, hash-only receipt)
                                                   │ → source-link filter (cite real candidate IDs) → redaction scan
                                                   ▼
                                        advisory intelligence (JSON sidecar) OR withheld → deterministic brief

model_eval.run_model_eval()  ──→ per-family decisive recommendation (recommended profile, blocked
  families, fallback route, reason codes, use_next_run) — synthetic (offline) or live modes.
```

## Files

| File | Role |
| --- | --- |
| `resources/config/local_model_task_routing.seed.yaml` | task family → profile + fallback chains (separate from the proven profiles seed) |
| `…/local_ai/model_router.py` | `LocalModelTaskRouting`, fail-closed loader, `route_task_family()`, `build_profiles_report()` |
| `…/local_ai/model_eval.py` | `run_model_eval()`, `ModelEvalResult`, per-family decisive recommendation, compact calendar/procore eval schemas |
| `…/local_ai/model_eval_fixtures.py` | `ModelEvalFixture`, synthetic committed fixtures, opt-in `load_raw_fixtures()` (refuses repo paths) |
| `…/local_ai/model_eval_metrics.py` | redaction scanner (category codes only), usefulness rubric, aggregation |
| `…/local_ai/daily_brief_intelligence.py` | `DailyBriefIntelligence` schema + `build_daily_brief_intelligence()` |
| `cli/second_brain.py` | `local-model profiles\|route\|eval`, `daily-brief intelligence`, `daily-run run --with-intelligence` |

## Model profile / router design

Profiles (model name, timeout, enabled, heavy gate, single-hop `fallbacks`) live in the existing
`phase_10_local_model_profiles.seed.yaml` and its proven `LocalModelProfiles` model (untouched). A
**separate** routing seed maps each task family to a profile and an ordered local-only fallback
chain. `route_task_family()`:

- resolves the chain (routed profile → fallback chain → seed single-hop), de-duplicated, local only;
- marks a profile available iff it is enabled, not heavy-gated, and its model is installed
  (availability from `provider.probe_models`; `present_models=None` ⇒ daemon unreachable);
- selects the first available profile, else **fails closed** (`blocked=true`) with a reason code
  (`unknown_task_family` / `daemon_unreachable` / `no_available_local_model` / `config_error`),
  still reporting the would-be primary so the operator sees the decision;
- **never** routes to a cloud model (there is no cloud provider in the seed; `no_cloud=true`).

## Eval task families

`email_action_extraction_json` (→ `ActionCandidate`), `daily_brief_synthesis_quality` /
`short_operator_catchup` (→ `DailyBriefSynthesis`), `calendar_prep_summary` /
`procore_digest_summary` (→ compact eval schemas). Synthetic mode replays committed redacted
fixtures through the offline `StaticOutputClient`; live mode resolves a real client per profile.
Each profile is measured independently (cross-model fallback disabled during measurement) so the
comparison is clean; redaction + JSON checks run on raw output **in memory** (capturing backend) and
only booleans, category codes, hashes, and aggregate metrics survive. Output is **decisive**:
recommended profile per family, blocked/unsafe families, fallback route, reason codes, `use_next_run`.

## Daily-brief intelligence integration

`build_daily_brief_intelligence()` consumes the already-redacted `daily_brief_action_candidates`
read model (safe fields only — raw-safe by construction), routes the `daily_brief_synthesis_quality`
family, and asks the local model (via `StructuredOutputClient`) for a compact object with: executive
catch-up, top priorities, open loops, waiting-on-me, waiting-on-others, meeting prep, project/Procore
risk. **Every bullet must cite ≥1 existing candidate ID** — bullets are filtered to the intersection
of cited `source_ids` with the known IDs; unsourced bullets are dropped. The schema coerces loose
model output (bare strings / `summary`/`title` keys) so a single stray item degrades to *partial*
enrichment rather than failing the whole brief. Surfaced via `daily-brief intelligence` and the
opt-in `daily-run run --with-intelligence` (default off; attaches an advisory `intelligence` block).

## Fallback behavior (fail-closed)

Enrichment is **withheld** and the deterministic brief is preserved on any of: model unavailable /
daemon unreachable, JSON invalid, schema invalid, zero source-linked bullets surviving, or a
redaction-scan hit on the filtered output. Withholding is reported (`enriched=false`, `withheld_reason`)
but is never an error — the command still returns `ok` because the deterministic brief is the safe
fallback. Proven live: one real call enriched (3 source-linked bullets, coverage 1.0, ~34s); another
withheld (`schema_invalid`); `--mock` withheld (`daemon_unreachable`). See
`docs/evidence/phase-10-local-model-routing/`.

## Guardrails

Local Ollama only; no cloud route. No email send, calendar mutation, Procore/Graph/external
writeback. No raw prompt/response persisted or returned (receipts are hash-only; default no DB
write). The 13 Phase 10 guard columns stay 0. Redaction scanner returns category codes only. Opt-in
raw fixtures must live outside the repo (repo-contained paths refused). Eval/intelligence emit JSON +
redacted evidence only; raw model bullet text is for local operator consumption and is never committed.

## Non-goals

No cloud LLM; no new scheduler/browser/Obsidian workflow (integration only); no new DB tables or
migration; no replacement of deterministic candidate generation; no dashboard/UI; no file/document
parsing.

## What is not implemented (yet)

- Persisted per-run eval/intelligence rows (kept to JSON/evidence/sidecar to avoid a migration).
- Wiring `--models auto` in eval to the router's recommendation (eval currently compares all enabled
  non-heavy profiles for a clean per-family decision).
- Converging the new intelligence adapter with the existing `--synthesize` `DailyBriefSynthesis`
  path (left as separate opt-ins; convergence is the natural follow-up).

## Operator runbook

See `docs/runbooks/phase-10-local-model-routing-runbook.md`.
