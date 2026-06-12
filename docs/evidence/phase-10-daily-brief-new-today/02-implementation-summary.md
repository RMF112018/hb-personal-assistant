# 02 — Implementation summary (Phase 10 · 252 · New Today)

## New modules

- **`construction/second_brain/local_ai/new_today_digest.py`** — deterministic, source-linked digest.
  - `compute_refresh_window(store, brief_date)` — the refresh-window contract: use the most recent
    successful nightly-refresh boundary from run markers (`procore_live_sync_runs` /
    `email_calendar_raw_ingestion_runs` / `construction_source_sync_state`); else a deterministic
    fallback window ending at the 5:00 AM ET brief anchor, starting before the prior ~8 PM refresh.
    Returns the resolved window + `source` + `rationale` for evidence.
  - Per-family extractors → `DailyBriefChangeEvent`: email (message + actionable follow-up; **email
    usefulness gate**), calendar (changed + upcoming in the look-ahead), Procore (**detail-or-drop**:
    a record renders only when real number/vendor/amount/status/impact joins, else it is demoted to a
    diagnostic), SharePoint/OneDrive file changes.
  - Deterministic sentence builders (executive phrasing) + attention classifier
    (`Needs your attention` / `Team follow-up / monitor` / `Awareness only`).
  - `persist_new_today_digest(...)` — fail-closed on `--max-persist` (total projected = events + refs).
- **`construction/second_brain/local_ai/new_today_presentation.py`** — the single render model both
  surfaces consume: groups by attention class (required order, empty groups omitted), composes the
  user-facing degraded warning, emits sanitized Markdown through `assert_clean_display`.
- **`construction/second_brain/local_ai/ollama_new_today.py`** — bounded advisory overlay. The packet
  carries bounded **local** context (deterministic facts + a short raw title excerpt for grounding;
  never persisted/committed/cloud). The model may only polish `why_it_matters` / `recommended_action`
  and suggest an attention class (±1 step, only when deterministic confidence < 0.85). The
  deterministic `summary_text` is never overwritten; any leaky field withholds the whole layer;
  hash-only receipt via `insert_local_model_run_receipt`.

## Edited modules

- **`store/migrator.py`** — V54 tables + `LATEST_SCHEMA_VERSION = 54`.
- **`construction/store/repositories.py`** — `insert_daily_brief_change_event` /
  `insert_daily_brief_change_event_ref` / `list_daily_brief_change_events` (no-raw-param contract).
- **`construction/second_brain/local_ai/project_aliases.py`** — `project_display_name(key, store=)`
  (seed `display_name` → identity store → cleaned title-case; never a raw slug).
- **`daily_brief_presentation.py`** — `project_label` now routes through the display resolver, so
  neither the brief nor the collapsed diagnostics ever render a raw project key.
- **`daily_run_html.py`** — `new_today` param: page becomes "Today's Daily Brief", New Today section
  cards render first, and the legacy section cards + status/run metadata are wrapped in a collapsed
  `<details>` "Run details / diagnostics" block. Egress fences unchanged.
- **`daily_run.py`** — builds the digest + render model, prepends New Today and wraps the legacy brief
  markdown in the collapsed diagnostics block, passes `new_today` to the HTML renderer, propagates the
  email-degraded signal to warnings, and adds a `new_today` block to the run payload. Fully guarded.
- **`cli/second_brain.py`** — `second-brain daily-brief new-today` (dry-run default; `--apply` needs
  `--max-persist` + a `/tmp` `--db`; `--no-client` deterministic success path; `--mock-output`).

## Layout result

`Today's Daily Brief` → subhead → **New Today** (Needs your attention / Team follow-up / monitor /
Awareness only) is the only visible primary body; everything legacy + run/status metadata lives in
the collapsed **Run details / diagnostics** block after it. No status banner on success; one concise
warning line when degraded.
