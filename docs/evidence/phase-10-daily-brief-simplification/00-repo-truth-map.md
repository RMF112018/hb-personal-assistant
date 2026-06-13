# 00 — Repo-truth map (daily brief simplification audit)

- **Branch:** `feature/phase-10-ollama-candidate-ranking-brief-assembly`
- **HEAD at audit:** `9678e2e4` — `feat(second-brain): add New Today overnight change digest to daily brief (252 v1)`

## Relevant daily-brief modules (all under `src/hb_assistant/construction/second_brain/local_ai/`)

| Module | Role |
|---|---|
| `daily_run.py` | `run_daily_local_agent()` — the scheduled `second-brain daily-run run` orchestrator. Owns status finalization, browser/Obsidian/status outputs. |
| `pipeline.py` | deterministic stage sequence (projection → candidates → render). |
| `new_today_digest.py` | `build_new_today_digest()` — builds `DailyBriefChangeEvent` business events; `persist_new_today_digest()`; `compute_refresh_window()`. |
| `new_today_presentation.py` | `build_render_model()` (shared model) + `render_markdown()`. |
| `new_today_usefulness.py` | **(253, new)** `evaluate_new_today_status()` — the product status gate. |
| `daily_run_html.py` | `render_daily_run_html()` + `_render_new_today_cards()` — browser HTML. |
| `daily_brief_synthesis.py` | legacy candidate generation (`build_daily_brief_candidates`). |
| `daily_brief_assembly.py` / `candidate_ranking.py` | legacy V51 ranking + assembly overlay. |
| `daily_brief_render.py` | legacy deterministic section render. |
| `daily_brief_llm_synthesis.py` | legacy LLM synthesis (`synthesize_daily_brief`). |
| `model_enriched_intelligence.py` | legacy MEI (`build_model_enriched_intelligence`). |
| `usefulness_gate.py` | legacy candidate-count usefulness gate. |
| `daily_brief_presentation.py` | `assert_clean_display()` output fence; display group ordering. |
| `project_aliases.py` | `project_display_name()` / `resolve_project()`. |
| `model_eval_metrics.py` | `scan_text_for_forbidden()`. |

## CLI commands that can generate/render a daily brief (`cli/second_brain.py`)

- `second-brain daily-run run` — the scheduled product run (this work's target).
- `second-brain daily-brief new-today` — build/persist New Today digest (deterministic + optional Ollama overlay).
- `second-brain daily-brief render | synthesize-candidates | rank-candidates | intelligence | evaluate-effectiveness | build | packet` — legacy/diagnostic surfaces.

## Call graph — `daily-run run` → HTML

`second_brain_daily_run_run()` → `run_daily_local_agent()` → `compute_daily_brief_window()` →
`run_local_agent_pipeline()` (projection, email-followup, watch, procore digest, calendar prep,
candidate synthesis, render) → email-raw enrichment (apply) → MEI → LLM synthesis (apply) → legacy
usefulness gate → **New Today digest + status gate** → `render_daily_run_html()` → atomic write
`daily-brief-<date>.html` / `-latest-attempted` / `-latest-deterministic` / `-latest` → `_write_status()`.

## Call graph — `daily-brief new-today` → persistence

`daily_brief_new_today()` → `compute_refresh_window()` → `build_new_today_digest()` → optional Ollama
overlay → `build_render_model()` → `render_markdown()` → raw-safety fence → `persist_new_today_digest()`
(events + hash-only refs into `daily_brief_change_events` / `daily_brief_change_event_refs`, V54, all
13 guard columns pinned 0 by CHECK).

## Render paths

- Markdown: `new_today_presentation.render_markdown(model)` then legacy body wrapped in a `<details>`.
- Browser HTML: `daily_run_html.render_daily_run_html(..., new_today=model)`; New Today is the primary
  visible body, all legacy content relocated into the collapsed `<details class='diag'>`.
- Obsidian: `daily_brief/output.write_brief_output()` (only with `--confirm-vault-write`).

## Status fields and owners (pre-253)

| Field | Owner |
|---|---|
| top-level `status` | run orchestration (synthesis + legacy usefulness gate) |
| `synthesis` / `synthesis_status` / `deterministic_fallback` | legacy LLM synthesis |
| `model_enriched_intelligence` | legacy MEI |
| `usefulness_gate` | legacy candidate-count gate |
| `candidate_ranking` | legacy V51 ranking |
| `new_today` (summary) | New Today (counts only — **did not own status**) |
| `operator_usable` | legacy usefulness gate |

## Where legacy influenced daily-run (pre-253, the defect)

`daily_run.py` built New Today **after** finalizing the legacy status and passed that legacy `status`
into `build_render_model(nt_digest, status=status)`. So degraded LLM synthesis
(`deterministic_success_synthesis_degraded`) forced the New Today degraded warning **above the fold**
even when New Today was fully useful.

## Where New Today influenced daily-run (pre-253)

Only the rendered body order (prepended) + a counts-only `new_today` summary. It did **not** own the
user-facing status.

## Where HTML and Markdown diverged

Only in presentation (cards vs. bullets, CSS classes, count badges); **content is shared** via
`build_render_model`. No content divergence.

## Where project aliasing / redaction / safety scans apply

- Aliasing: `project_display_name()` inside `new_today_digest` extractors (never raw keys).
- Redaction: `_safe()` per field in `new_today_digest`; `scrub_raw_text()` in `daily_run_html`.
- Fences: `assert_clean_display()` (Markdown), `scan_text_for_forbidden()` (fields),
  `scan_daily_run_html()` (HTML egress).

## What can be removed from the PRIMARY path without deleting diagnostics

- Legacy candidate/ranking/assembly section render, LLM synthesis body, and MEI section — already
  relocated into the collapsed diagnostics block by 252; 253 additionally ensures none of them owns
  the user-facing status. No code deleted; all remain available as diagnostics.
