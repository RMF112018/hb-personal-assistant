# 253 — Daily Brief Simplified Generation Contract

**Status:** Active (Phase 10, 253 v1)
**Supersedes the primary-surface ambiguity introduced across:** 249–252 (candidate/ranking/assembly,
synthesis, model-enriched intelligence, New Today).

> **New Today is the daily brief. Candidate-derived sections (Top Priorities, Calendar Prep, Procore /
> Project Signals, Email/Follow-up), LLM synthesis, and Model Enriched Intelligence are diagnostics.**

The 5:00 AM scheduled `second-brain daily-run run` had accreted overlapping subsystems whose mixed
degraded/withheld states ("synthesis degraded", "MEI withheld") made a perfectly useful brief read as
broken. 253 fixes the **status ownership** without rebuilding the (already-correct) New Today render
layer shipped in 252.

## Primary user-facing pipeline

```
resolve weekday date policy / refresh window
  → email/calendar + Procore projections available (existing ingestion/projection layers, untouched)
  → build New Today change events  (new_today_digest.build_new_today_digest — deterministic, raw-safe)
  → derive product status          (new_today_usefulness.evaluate_new_today_status)
  → build shared render model      (new_today_presentation.build_render_model — ONE model)
  → render Markdown + browser HTML from the SAME model
  → append collapsed "Run details / diagnostics"
  → write status JSON with the additive `daily_brief` block
```

The user-facing surfaces (Markdown brief, browser HTML) render **only** from the shared New Today
render model. The header/subhead/section contract is fixed:

```
Today's Daily Brief
Summary of the top items for {brief_date} and prep through {lookahead_end_date}
New Today
  Needs your attention
  Team follow-up / monitor
  Awareness only
[collapsed] Run details / diagnostics
```

## Diagnostic-only pipeline

Everything below remains wired (for development / audit) but is relocated, unchanged, into the
collapsed `<details>Run details / diagnostics` block beneath New Today, and **never** owns the
user-facing status:

- legacy candidate generation / ranking / assembly (`daily_brief_action_candidates`,
  `daily_brief_ranked_candidates`, `daily_brief_assembly_sections`) and their rendered sections;
- legacy LLM synthesis (`daily_brief_synthesis` / `synthesize_daily_brief`);
- Model Enriched Intelligence (`model_enriched_intelligence`);
- the legacy deterministic usefulness gate, ranking status, run/schedule/date-policy metadata.

## Daily-run status contract

Two statuses now coexist, with **distinct ownership**:

| Field | Owner | Purpose |
|---|---|---|
| top-level `status` | run orchestration (legacy) | backward-compat for scheduler / status readers / tests. Values unchanged (`success`, `deterministic_success_synthesis_degraded`, `partial`, `degraded`, `failure`, `skipped_weekend`). |
| `daily_brief.status` | New Today (product) | the user-facing daily-brief status. Drives the HTML banner + above-the-fold warning. |

Additive `daily_brief` block (status JSON + run return payload):

```json
{
  "daily_brief": {
    "primary_surface": "new_today",
    "status": "success | degraded | failed",
    "operator_usable": true,
    "degraded_reasons": [],
    "new_today": {
      "total_items": 0,
      "by_family": {},
      "email_degraded": false,
      "model_enrichment_status": "used | withheld | unavailable | not_requested",
      "deterministic_fallback_used": false
    },
    "diagnostics": {
      "legacy_status": "<top-level status>",
      "legacy_synthesis_status": "ok | degraded | diagnostic_only",
      "model_enriched_intelligence_status": "diagnostic_only",
      "legacy_candidate_sections_available": true
    }
  }
}
```

## New Today usefulness gate (`new_today_usefulness.evaluate_new_today_status`)

`daily_brief.status == "degraded"` is reserved for **product-relevant** New Today degradation, with a
stable reason code and an above-the-fold visible warning:

- `email_followup_degraded` — email substrate present but zero actionable follow-up derived;
- `projection_degraded` / `projection_coverage_degraded` — the email/calendar projection that feeds
  New Today failed or is coverage-degraded;
- `all_events_dropped_raw_safety` — events were built but the raw-safety fence dropped every one.

Explicitly **not** degradation (no status flip, no visible warning):

- a genuinely empty refresh window — *"No notable business changes…"* is a valid `success` brief;
- degraded LLM synthesis, MEI withheld, optional local-model (Ollama) unavailability — diagnostics.

`failed` is reserved for the case where New Today could not be built/rendered at all (digest
exception); the run still degrades to the legacy brief rather than hard-failing.

## Local model / enrichment contract

- **Deterministic source facts are authoritative.** Local Ollama may only polish wording / why-it-
  matters / recommended-action phrasing; it must never invent names, dates, amounts, projects, record
  numbers, or statuses. A leak withholds the overlay; a failure falls back to deterministic output.
- **Two distinct enrichment status fields, never conflated:**
  - `daily_brief.new_today.model_enrichment_status` (`used|withheld|unavailable|not_requested`)
    describes **New Today's own** optional overlay;
  - `daily_brief.diagnostics.model_enriched_intelligence_status` (`diagnostic_only`) describes the
    **legacy MEI** subsystem, which never touches New Today.
- **Flag ownership:** `--model-enriched-intelligence` is **legacy-MEI-only** and does NOT control New
  Today enrichment. v1: the scheduled run builds New Today **deterministically** (no Ollama in the
  critical path) → `model_enrichment_status = "not_requested"`. The bounded New Today overlay remains
  available via `second-brain daily-brief new-today`.

## Rendering contract

- One shared render model (`build_render_model`) feeds both Markdown (`render_markdown`) and browser
  HTML (`render_daily_run_html` → `_render_new_today_cards`). The surfaces cannot drift in content.
- Section ordering, attention grouping, project aliasing (`project_display_name` — never raw keys),
  the above-the-fold warning, and the output fence (`assert_clean_display` + `scan_text_for_forbidden`
  / `scan_daily_run_html`) all live in shared presentation code.
- The above-the-fold warning is driven by `daily_brief.status` (via the New Today model), never by the
  legacy top-level status.

## Allowed collapsed diagnostics

The `<details>Run details / diagnostics` block may contain legacy Top Priorities, Calendar Prep,
Procore / Project Signals, Email/Follow-up, synthesis/MEI sections, and run/schedule/status metadata —
but it must still pass the raw-safety and internal-artifact scans.

## Forbidden user-facing (above-the-fold) output

`friday_next_week` / date-policy internals, project keys, `id:` / `dbac-` / `rel-`, table names,
`None.`, JSON dumps, raw URLs / emails / tokens, tracebacks, status/success banners, and
candidate/synthesis/MEI metrics must never render above New Today.

## Validation acceptance gates

The acceptance artifact is the **generated browser HTML from the scheduled daily-run** (not unit tests
alone). Secondary artifacts: Markdown render, `latest-status.json`, New Today event JSON/proof, copy-
quality scan, raw-safety scan, and a production-DB SHA-unchanged proof (apply-mode validation runs on
a `/tmp` copy only). See `docs/evidence/phase-10-daily-brief-simplification/`.
