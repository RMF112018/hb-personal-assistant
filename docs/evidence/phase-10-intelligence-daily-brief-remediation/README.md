# Phase 10 — Intelligence Daily Brief Remediation (evidence)

Date: 2026-06-09 · Local-only · No cloud LLM · No external writeback · No raw-content egress

Branch `experiment/phase-10-intelligence-daily-brief-remediation` (base `main` HEAD `8981ceb8`,
schema head **V44 — no migration added**). All numbers here are **metrics-only and redacted**: no raw
prompt, raw model response, candidate title, URL, email, join link, or token is reproduced.

## Why this package

The prior local-model-routing evidence noted the 12B model was *"not consistently schema-valid for
the richer intelligence schema across calls (one call enriched, another withheld)"*. Reproducing on a
`/tmp` Dev DB copy confirmed two concrete root causes — not mere model variance — and an ambiguous
profile report:

1. **`no_source_linked_bullets` (source-link loss).** The adapter showed the model the 37-char
   canonical id (`dbac-<32 hex>`) and asked it to echo it verbatim into `source_ids`. A 12B model
   garbles long hex ids, so every bullet failed the source-link filter and the whole enrichment was
   withheld.
2. **`schema_invalid` (executive_catchup type).** The model reliably returns the correct 7-key object
   but emits `executive_catchup` as a prose **string**, not a list. The field validator ran in
   `mode="after"`, so Pydantic's list-type check failed *before* coercion → `schema_invalid` on every
   attempt (primary + fallback = 6 attempts, ~148s, then withheld).
3. **Profile reporting ambiguity.** The CLI labelled `selected_profile = result.profile_id`, which is
   the *terminal* profile. On fallback it read `default_extract` even though the **route** selected
   `brief_synthesis` — making operators think the wrong profile was routed.

## What was fixed (commits on this branch)

| Commit | Subject |
| --- | --- |
| `f837d9a0` | clarify daily brief intelligence routing diagnostics (route vs terminal profile) |
| `58ed3161` | surface daily brief candidate availability semantics |
| `33c5e1b6` | harden daily brief intelligence schema and source links (alias scheme + mode=before coercion) |
| `7af97ad2` | stabilize daily brief intelligence CLI diagnostics (`--db` echo, `eval_mode`) |

## Result (live `/tmp` Dev DB copy, 2026-06-09, 20 candidates)

| Surface | Before | After |
| --- | --- | --- |
| Standalone `daily-brief intelligence` | withheld (`no_source_linked_bullets` **or** `schema_invalid`), 142–218s | **enriched**, `source_link_coverage=1.0`, 12 bullets, **first attempt, no fallback**, ~53s |
| Profile report | `selected_profile=default_extract` (ambiguous) | `route_selected_profile=brief_synthesis`, `terminal_profile_id=brief_synthesis`, divergence warnings when they differ |
| Source linking | model garbled 37-char ids | short alias `c1…cN` mapped back to canonical (`alias_mapping_used=true`) |

Both outcomes remain **fail-closed**: on any model/JSON/schema/source-link/redaction failure the
enrichment is withheld and the deterministic brief is preserved — now with **precise diagnostics**
(`schema_error_category`, `attempts`, `repair_attempted`, `unknown_source_ids_count`, route vs
terminal profile) instead of a silent or ambiguous result.

## Evidence index

- `route-proof-summary.json` — route selects `brief_synthesis` (`selected_routed`, `no_cloud=true`).
- `standalone-intelligence-pre-summary.json` — enriched, coverage 1.0, 12 bullets (~53s).
- `daily-run-dry-run-summary.json` — `--with-intelligence` dry-run: 0 persisted, `pipeline_dry_run`
  warnings, no browser output.
- `daily-run-apply-copy-summary.json` — apply on copy: 5 stages ok, bounded persist, egress clean,
  intelligence enriched (`pipeline_apply`).
- `standalone-intelligence-post-summary.json` — post-apply: enriched, coverage 1.0.
- `idempotency-summary.json` — second apply persists 0 (no duplication).
- `candidate-row-count-proof.md`, `guard-column-proof.md`, `egress-scan-proof.md`,
  `profile-reporting-consistency-proof.md`, `synthetic-eval-labeling-proof.md`,
  `live-model-performance-proof.md`, `failure-fallback-proof.md`, `forbidden-string-scan-proof.md`,
  `final-audit.md`.

## Guardrails (all held)

- No schema migration (head stays V44); no cloud LLM; no email/calendar/Procore/Graph/external
  writeback. Receipts hash-only. The guard columns sum to **0**. Production DB byte-identical
  before/after (mtime/size/row counts unchanged). Raw model output never committed.

## Reproduce (local only)

```bash
cp "<(Dev) app-support db>" /tmp/hb_daily_brief_intelligence_test.sqlite
.venv/bin/hb-assistant second-brain local-model route --task-family daily_brief_synthesis_quality --json
.venv/bin/hb-assistant second-brain daily-brief intelligence --date 2026-06-09 --db /tmp/hb_daily_brief_intelligence_test.sqlite --dry-run --json
.venv/bin/hb-assistant second-brain daily-run run --db /tmp/hb_daily_brief_intelligence_test.sqlite --date 2026-06-09 --dry-run --with-intelligence --no-open-browser --no-generate-browser --json
.venv/bin/hb-assistant second-brain daily-run run --db /tmp/hb_daily_brief_intelligence_test.sqlite --date 2026-06-09 --apply --max-persist-per-stage 10 --max-total-persist 30 --with-intelligence --no-open-browser --no-generate-browser --json
```

Raw `/tmp` captures (model bullet text) are intentionally **not** committed — only the metrics above.
