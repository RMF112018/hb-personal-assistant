# 26 — Phase 07B: Review-Controlled Correspondence Intelligence

Phase 07B Prompt 09. Status: implemented at this record's commit.

## Problem

The redacted email/calendar read models (thread summaries, the review queue, model
classifications, meeting↔email candidates) all existed, but nothing aggregated them into a
project-level, review-gated, advisory correspondence preview. Obsidian rendering is a later
prompt (P10), so this layer is purely the **intelligence/preview** feeding it.

## Change

New `CorrespondenceReviewBuilder` in a new `construction/correspondence/` package. It is
**read-only on every layer** — no Microsoft Graph calls, no token, and **no local SQLite
writes at all**. There is no correspondence table; the report is a transient Pydantic object
(no migration; schema head stays V23).

`review(*, project_key=None, lookback_days=30, max_previews=10, max_warnings=50) ->
CorrespondenceReviewReport`:

- **Previews** — project thread summaries within the lookback (by `last_message_datetime`),
  newest-first and capped; each preview carries `thread_ref = hash_value(thread_key)`, the
  message count, the time window, `review_required`, and the already metadata-only
  `summary_redacted`. No subject, address, or body.
- **Review warnings** — the open `email_review_queue` aggregated by `category`; each warning
  is enriched from the `review_categories` registry (`get_review_category`) with `label`,
  `sensitivity_level`, `recommended_review_action`, and the evidence-safe explanation (e.g.
  "possible claim language; not a determination, review required"). Categories absent from
  the registry (e.g. classifier/router reasons like `model_review`) fall back to a generic
  "review required; not a determination" medium warning. Warnings sort high-sensitivity
  first.
- **Supplementary counts** — totals + review-required tallies from thread summaries, the
  review queue, model classifications (incl. risk-flag count), and meeting↔email candidates.
- The report records `read_only=True`, `persisted=False`, a `guardrails` block
  (`sqlite_writes: none`, `determinations: none_advisory_only`), and a disclaimer that the
  output is "advisory signals, not determinations".

### CLI
`graph mail correspondence` (`cli/graph.py`, under the `graph mail` group): `--project`,
`--lookback-days`, `--max-previews`, `--max-warnings`, `--json`. No dry-run/apply flag —
nothing is written.

## Guardrail invariants
- No Microsoft 365 mutation/writeback; Graph-free; **read-only on SQLite** (verified against
  the real store: row counts identical before/after the run).
- `project_key` (a safe slug) is the only un-hashed identifier; `thread_key` is hashed;
  no raw subject/body/address/URL appears in the report.
- **No final determinations** — warnings/previews are advisory; the disclaimer and the
  registry's "not a determination / review required" language make this explicit; sensitive
  items route to human review.

## Evidence

`docs/evidence/construction-intelligence-phase-07b-calendar-email/09-review-controlled-correspondence-proof.md`
(local validation + redacted live read-only proof). The no-writeback / no-raw-body prover
does not yet scan the V11/V14/V23 email/calendar tables — deferred to Phase 07B Prompt 12.
