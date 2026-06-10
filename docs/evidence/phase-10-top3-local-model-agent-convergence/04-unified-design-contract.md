# 04 — Unified Design Contract (Prompt 01)

## 1. Converged data flow (text diagram)

```
daily-run run (default: apply-safe gates; MEI on; browser on; auto-open off)
  └─ run_daily_local_agent
       1. run_local_agent_pipeline
            follow_up_watch
            email_followup_raw_enrichment   ← NEW stage (apply+enabled+eligible+route+cap>0)
            procore_digest
            calendar_prep
            daily_brief_synthesis (candidate generation)
            [relationship_candidates if enabled]
            daily_brief_render (deterministic brief = source of truth)
       2. synthesize_daily_brief (apply only)  → narrative BODY (unchanged; --synthesize)
       3. build_model_enriched_intelligence     ← NEW unified object (default on)
            = daily-brief intelligence adapter result  (source-linked advisory bullets)
            + V45 pending follow-up rows (incl. any persisted this run by stage above)
       4. render → ONE "Model Enriched Intelligence" section on:
            browser HTML  · Obsidian markdown · status JSON · CLI JSON
            (deterministic candidates + synthesis narrative remain; MEI is advisory)
```

The intelligence adapter and synthesis remain **two local model calls**. This is intentional and
permitted by Prompt 02 ("document why two calls remain"): synthesis is the narrative body; the
adapter produces the source-linked advisory bullets. **Convergence is at the render/status contract
layer** — the operator sees exactly one section. No conflicting facts: the deterministic brief is
authoritative; MEI bullets are advisory and source-linked; pending rows are clearly labeled.

## 2. Unified object — `model_enriched_intelligence` (raw-safe)

Built by new `local_ai/model_enriched_intelligence.py::build_model_enriched_intelligence(...)`.
Returned dict (status/render contract):

```
enabled, available, label="Model Enriched Intelligence", generated_utc, degraded, withheld_reason,
candidate_count, candidate_freshness, source_link_count, source_link_coverage,
bullets_seen, bullets_kept, bullets_dropped, unknown_source_ids_count,
pending_followup_count, route_selected_profile, route_model_name,
terminal_profile_id, generation_profile_id, fallback_chain, warnings, guardrails,
intelligence (filtered source-linked bullets, advisory),   # omitted/empty when withheld
pending_followup { count, items[], omitted_low_confidence, dropped_leak }
```

- `enabled=False` → `{enabled:false, available:false, label, degraded:false, withheld_reason:"disabled"}`
  plus pending counts (pending is deterministic, independent of the disable flag).
- Adapter withheld / model unavailable → `available:false`, explicit `withheld_reason`, `degraded:true`,
  `bullets_*` from the adapter, `intelligence` empty; **pending still surfaced** (survives degrade).
- `source_link_count` = sum of cited candidate ids across kept bullets; `source_link_coverage` from
  adapter metrics (1.0 by construction for kept bullets).
- No raw text, prompts, responses, URLs, tokens, emails, HTML — adapter already redaction-scans; pending
  builder already leak-guards; the renderer reuses `scrub_raw_text`/`_esc`.

## 3. Default-on behavior

- `daily-run run`: new `--model-enriched-intelligence/--no-model-enriched-intelligence` (**default True**).
  Independent of `--synthesize` (narrative body, unchanged). `--with-intelligence/--no-intelligence`
  kept as a backward-compatible alias for the new flag; help text updated.
- Scheduler install: ProgramArguments emit the effective MEI + email-raw posture; status surfaces the
  effective value even when default (no explicit arg). Browser never auto-opened.

## 4. Status JSON shape (compact block, in status file + run JSON)

```json
{ "model_enriched_intelligence": {
    "enabled": true, "available": true, "label": "Model Enriched Intelligence",
    "degraded": false, "withheld_reason": null,
    "candidate_count": 0, "source_link_count": 0, "bullets_kept": 0, "bullets_dropped": 0,
    "pending_followup_count": 0, "route_selected_profile": "...", "terminal_profile_id": "..." } }
```
No row-level raw content, no raw prompt/response.

## 5. Browser / Obsidian rendering contract

- Exact heading `Model Enriched Intelligence` (`<h2>` browser / `##` Obsidian), near top of body.
- Advisory bullets with safe candidate-id citations; pending V45 items as a clearly-labeled subsection.
- Withheld/degraded → honest banner, no body. Browser passes existing `scan_daily_run_html` egress scan.
- Obsidian keeps marker-bounded governed write.

## 6. Email pending-enrichment integration contract

- Apply pipeline runs `email_followup_raw_enrichment` (bounded by `max_persist`, idempotent, source-linked,
  no raw persistence) before MEI is built, so newly-persisted pending rows appear the same run.
- Readiness (`enrich-readiness`) is read-only and **never materializes raw body** — eligibility from source
  refs / hashes / window-builder availability metadata only.

## 7. Local model route / fallback contract

- Adapter: `route_task_family("daily_brief_synthesis_quality")`; enrichment:
  `route_task_family("email_followup_raw_enrichment")`. Both local-only, fail-closed; no cloud route exists.
- Unavailable model → route `blocked`; adapter withholds, enrichment skips/degrades; deterministic brief renders.

## 8. Model-unavailable behavior

Deterministic brief + synthesis-or-degraded body still render; MEI `available:false`, `degraded:true`,
`withheld_reason` set; status honest; last-successful pointer preserved (run not a fresh success).

## 9. Raw/private content boundary

Raw text only ever exists ephemerally inside the guarded enrichment execution path and the local browser/
Obsidian consumption surfaces (already scrubbed). Never in status, evidence, tests, logs, persisted rows,
or repo. Guard columns stay zero.

## 10. Validation + evidence plan

New tests: `tests/test_phase_10_daily_brief_intelligence_convergence.py`,
`_model_enriched_intelligence_render.py`, `_daily_run_scheduler_hardening.py`,
`_email_raw_enrichment_readiness.py`, `_email_raw_enrichment_pipeline.py`, `_top3_daily_run_integration.py`
(injected `StaticOutputClient` backend; seeded `:memory:`/temp store — never prod DB). DB-copy live proof
on a `/tmp` copy resolved from `PathPolicy().get_db_path()`; prod sha256 unchanged; guard columns zero;
forbidden-string scan clean. Evidence files `05`–`26` per the package matrix.

## 11. Non-goals

Schema migration; single unified model call; cloud routing; any external/Graph/Procore/calendar/email
writeback; raw persistence; browser auto-open; new frontend.

## 12. Stop conditions

Any raw/private leak, uncapped apply, prod-DB mutation, cloud fallback, guard-column nonzero, failed safety
scan, or inability to prove no residual work → stop and emit a partial handoff.
