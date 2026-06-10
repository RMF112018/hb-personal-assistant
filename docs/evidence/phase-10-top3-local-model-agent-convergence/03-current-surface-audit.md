# 03 — Current Surface Audit (Prompt 01)

Repo-truth audit of the three candidates' current state on base `ebd8e74a`. All paths verified
by symbol search (no assumed line numbers).

## Candidate A — daily-brief intelligence vs synthesis

| Module | Symbol | Current behavior |
|---|---|---|
| `construction/second_brain/local_ai/daily_brief_intelligence.py` | `build_daily_brief_intelligence(...) -> DailyBriefIntelligenceResult` | Source-linked advisory bullets (6 sections + catchup). Routes via `model_router.route_task_family("daily_brief_synthesis_quality")`. Drops bullets not citing a known candidate id; withholds whole object on model/JSON/schema/source-link/redaction failure. `safe_payload()` already exposes: `status, enriched, withheld_reason, profile_id, model_name, candidate_count, candidate_freshness, candidate_availability, route_selected_profile, route_model_name, terminal_profile_id, generation_profile_id, fallback_chain, models_attempted, blockers, warnings, metrics{model_bullets_seen,bullets_kept,bullets_dropped,unknown_source_ids_count,source_link_coverage,...}, intelligence`. |
| `.../daily_brief_llm_synthesis.py` | `synthesize_daily_brief(...) -> BriefSynthesisResult`, `render_synthesis_markdown`, `render_degraded_markdown` | 9-section narrative brief; fail-closed → `degraded`. This is the **brief body**. |
| `.../daily_brief/email_followup_pending.py` | `build_pending_email_enrichment_section(store)`, `render_pending_enrichment_markdown` | V45 pending rows as raw-free source-linked items. Item label `PENDING_LABEL = "Model-enriched / pending review"`. Returns `{section, label, available, count, omitted_low_confidence, dropped_leak, items, guardrails}`. |

**Consumption today:**
- `daily_run.py::run_daily_local_agent` calls `synthesize_daily_brief` (apply only, when `synthesize_brief`)
  and `build_pending_email_enrichment_section` (always) — pending is rendered on browser+Obsidian.
- The **intelligence adapter** is only attached via the CLI opt-in `_attach_daily_run_intelligence`
  (`--with-intelligence`, default off) into the run JSON; it does **not** reach browser/Obsidian.
- No surface uses the exact label `Model Enriched Intelligence` (`grep` = 0 hits in `src/`).

## Candidate B — daily-run + scheduler

| Module | Symbol | Notes |
|---|---|---|
| `.../local_ai/daily_run.py` | `run_daily_local_agent(...)` | Builds status JSON + `run_summary`; preserves last-successful only on fresh safe success; repo-containment guard on output dirs; `_guardrails` includes `no_browser_auto_open`. Params incl. `synthesize_brief` (CLI passes `True`), `generate_browser=True`. |
| `.../local_ai/daily_run_html.py` | `render_daily_run_html`, `scan_daily_run_html`, `scrub_raw_text`, `_esc`, `_render_pending_followup_card` | Self-contained HTML; egress scrub+escape+fail-closed scan. Pending card already rendered before brief body. |
| `.../local_ai/daily_run_scheduler.py` | `DailyRunLaunchdManager` | `render_plist`, `_program_arguments` (emits `--synthesize/--no-synthesize`, `--generate-browser`, `--no-open-browser`), `preview_install`, `status`, `_readiness`. No MEI/email-raw knobs yet. |
| `.../local_ai/pipeline.py` | `run_local_agent_pipeline`, `STAGE_ORDER` | `follow_up_watch → procore_digest → calendar_prep → daily_brief_synthesis → daily_brief_render`. Apply requires `max_persist_per_stage`. No email-raw-enrichment stage. |
| `cli/second_brain.py` | `second_brain_daily_run_run` (`@daily_run_app.command("run")`), `_build_daily_run_scheduler`, `second_brain_daily_run_scheduler_install/status` | `--synthesize` default **True**; `--with-intelligence` default False; `--with-email-raw-enrichment` default False (JSON-only twin); `--open-browser` reserved/no-op. |

## Candidate C — V45 email raw enrichment

| Module | Symbol | Notes |
|---|---|---|
| `.../local_ai/email_followup_enrichment.py` | `run_email_followup_enrichment(...)`, `select_eligible_candidates(...)`, `compute_idempotency_key(...)` | Dry-run default; **apply raises `ValueError` without positive `max_persist`**; idempotent upsert; per-field `find_raw_leak` guard; persists only structured/hash/source-ref fields. Eligibility = accepted task/commitment, open, email-source-linked (`_EMAIL_FAMILIES`). |
| `.../local_ai/email_followup_route.py` | `run_email_followup_model`, `EmailFollowupEnrichmentOutput`, `find_raw_leak` | Local-only route (`route_task_family("email_followup_raw_enrichment")`); strict schema `extra="forbid"`; cross-context validation. |
| `.../local_ai/raw_followup_window.py` | `build_raw_followup_window`, `RawWindowCaps`, `RawFollowupWindow`, `build_raw_local_preview` | Bounded sanitized window; `window.available`, `raw_excerpt_hash`, `message_ref_hashes`, `thread_ref_hash`, `source_aliases`. Raw text only inside the guarded execution path. |
| `cli/second_brain.py` | `second_brain_follow_up_watch_enrich` (`@follow_up_watch_app.command("enrich")`) | Dry-run/apply, `--max-persist` required with `--apply`, `--show-raw-local` gated to `--dry-run` + `--no-json`. No `enrich-readiness` command yet; enrichment is **not** a daily-run stage. |
| `store/migrator.py` | `V45_STATEMENTS`, `_P10_GUARDS` | Table `email_followup_enrichments` + 11 guard CHECK columns. `LATEST_SCHEMA_VERSION = 45`. |

## Routing seed

`resources/config/local_model_task_routing.seed.yaml` defines both required families:
`daily_brief_synthesis_quality: brief_synthesis` and `email_followup_raw_enrichment: default_extract`,
with `guardrails: {local_only, no_cloud, no_raw_persistence}` (validated true by the loader).

## Gaps this package closes

1. No unified `Model Enriched Intelligence` section/label; adapter not on final surfaces; default off.
2. V45 enrichment not a daily-run stage; no readiness/eligibility surface.
3. Scheduler status/install does not report MEI / email-raw posture.

## Package doc defect noted (repair in Prompt 12)

`README.md`, `TRIGGER_PROMPT.md`, `prompts/14_*` reference `templates/FINAL_HANDOFF_TEMPLATE.md`,
but the file is at the package root and `PACKAGE_MANIFEST.json` lists it at root. Real path used for
`25-final-handoff.md`; package docs reconciled in the docs pass.
