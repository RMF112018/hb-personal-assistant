# 232 — Phase 10 Local-Agent Family

Status: experimental (branch `experiment/local-agent-family-proof`). Scope: a coherent,
local-only, review-gated **family of agents** layered on the existing Phase 10A substrate.
Authoritative truth is repo code + tests + the evidence bundle at
`docs/evidence/phase-10-local-agent-family/`.

## Purpose

Turn the existing Phase 10A read/extract substrate into working, source-linked, advisory
agent workflows that converge on a single reviewable surface — without violating any
no-raw / no-writeback / dry-run-first guardrail.

## Agents (this family)

| Agent | Surface | Determinism | Reads | Writes (apply-only, capped) |
|-------|---------|-------------|-------|------------------------------|
| Email extraction | `second-brain extract-packets` | model-assisted (mistral-nemo) | `email_thread_raw_context` | `task_candidates` / `commitment_candidates` + `candidate_source_refs` |
| Acceptance promotion | `phase-10 review-candidate --promote` | deterministic | candidate rows | `accepted_tasks` / `accepted_commitments` |
| Follow-up watch | `follow-up-watch scan` | deterministic, no-clock | `accepted_*` + `candidate_source_refs` | `follow_up_watch_items` / `follow_up_status_events` |
| Procore digest | `procore-digest build` | deterministic-first (optional synth) | `procore_action_signals` + text-intelligence read models | `daily_brief_action_candidates` (section `procore`) |
| Calendar meeting-prep | `calendar-prep build` | deterministic-first (optional synth) | `calendar_event_index` + `calendar_event_attendees` + bounded `calendar_event_action_packet` | `daily_brief_action_candidates` (section `calendar`) |
| Daily-brief synthesis | `daily-brief synthesize-candidates` | deterministic | `accepted_*` + `follow_up_watch_items` + `daily_brief_action_candidates` | `daily_brief_action_candidates` (sections `actions`/`waiting`/`follow_up`) |
| Daily-brief render *(consumption)* | `daily-brief render` | deterministic, **read-only** | `daily_brief_action_candidates` | none by default; optional path-safe file write (`--write` + `--confirm-vault-write`) |
| Pipeline *(orchestration)* | `pipeline run` | deterministic, dry-run-first | chains the five above | none of its own; stages persist via their capped paths |

The six producing agents are registered in `resources/config/phase_08a_agent_registry.seed.yaml`
(13 agents total: 9 required Phase-08A + 4 family entries; the extraction front-end reuses the
existing substrate). Daily-brief **render** is a consumption surface under the existing
`daily_brief_agent` — it adds no registry entry (count stays 13). `second-brain agents status`
validates the registry/tool policy (0 violations).

## Data flow (convergence)

```
email_thread_raw_context ─ extract ─▶ task/commitment candidates ─ review --promote ─▶ accepted_*
                                                                                   │
procore_action_signals ─ procore-digest ─▶ daily_brief_action_candidates(procore)  ├─ follow-up-watch ─▶ follow_up_watch_items
calendar_event_index ─── calendar-prep ──▶ daily_brief_action_candidates(calendar)  │
                                                                                   ▼
                          daily-brief synthesize-candidates ──▶ daily_brief_action_candidates(actions/waiting/follow_up)
                                                                                   ▼
                                                    unified, source-linked, reviewable brief candidates
                                                                                   ▼
                          daily-brief render ──▶ redacted Markdown/JSON brief (read-only) ─[opt --write]─▶ governed vault note / explicit non-repo file

  pipeline run ──▶ one repeatable daily run: follow-up-watch → procore-digest → calendar-prep → synthesize → render (dry-run-first, stage-bounded, fail-loud)
```

`daily_brief_action_candidates` is the **convergence table** — the email, Procore, and calendar
families feed it; the synthesis layer presents a unified brief by section; and **render** closes the
loop by turning those rows into a consumable, redacted daily brief.

## Key seams / reuse

- The Procore digest **composes** existing redacted read models (`build_operational_digest`,
  `build_overdue_queue`, `list_procore_action_signals`, `get_procore_text_intelligence`,
  `_dimensions_for`) — it does not reimplement Procore logic. Auxiliary-read-model failures are
  guarded so the deterministic core always returns.
- New store writers (`insert_accepted_*`, `upsert_follow_up_watch_item`,
  `insert_follow_up_status_event`, `insert_daily_brief_action_candidate`) all **omit** the 13
  `_P10_GUARDS` columns so `DEFAULT 0` / `CHECK(=0)` holds — the structural no-raw/no-writeback
  invariant. Inserts are idempotent on deterministic ids.
- No-clock convention: classifiers/builders take `now_utc`; the CLI stamps it once (`--as-of`).

## Guardrails (enforced in code + tests + DB)

Dry-run default; `--apply` fail-closed without `--max-persist`; max-persist caps actual writes;
source-ref gate (no source refs → no persist); redaction (Procore digest never emits
`metadata_json` / `encrypted_full_text_ref` / `text_hash` / free-text titles); optional Procore
synthesis is fed only already-redacted aggregates, is in-memory (never persisted), and fails
closed. No Microsoft 365 / Procore / external writeback; no cloud LLM; state stays local.

## Checkpoint 3 — Calendar meeting-prep (this run)

Adds calendar as the third source family. The Dev DB realities that shaped it (read-only probe):
`calendar_event_index`=500 / `calendar_event_raw_content`=500 (1:1), bodies HTML-only
(`body_text` empty, `body_html`≈460/500), `join_url` present 404/500, **`project_key` and
`source_ref_hash` empty 0/500**.

- **Normalization is composed, not reinvented.** `build_calendar_prep_candidates`
  (`local_ai/calendar_prep.py`) discovers upcoming non-cancelled/non-private events from a new
  read-only reader `list_calendar_prep_source_events` (safe redacted fields + attendee
  count/DISTINCT domains only), windows them deterministically (`[as_of, as_of+lookahead_days)`),
  and enriches each via the existing bounded `build_calendar_event_action_packet`
  (HTML→text, Teams-boilerplate / join-URL / dial-in / passcode / meeting-id stripping,
  attendees→domains). A calendar-scoped `_safe_excerpt` pass additionally drops scheme-less
  domain/link tokens and email addresses the shared normalizer leaves behind (proven against the
  live Dev DB copy).
- **Deterministic fallbacks** for the missing columns: `source_ref = cal:<sha256(event_index_id)>`;
  `project_key` falls back to `__unassigned__`. No raw subject is ever used — the candidate title is
  the index `subject_redacted`.
- **Persistence** is one rollup row per event into `daily_brief_action_candidates`
  (section `calendar`, idempotent on `(brief_date, calendar, source_ref)`); the redacted body
  excerpt lives only in the in-memory `--summary` JSON, never in a persisted row. The daily-brief
  synthesis convergence surfaces the `calendar` section automatically (same generic mechanism as
  `procore`).
- **Guardrails proven** (Dev DB copy, then removed): dry-run zero writes; `--apply` fail-closed
  without `--max-persist`; capped + idempotent; all 13 `_P10_GUARDS` columns = 0; `calendar_event_*`
  source tables unchanged; no join URL / raw HTML / email / raw subject / token in any persisted row
  or emitted excerpt.

## Checkpoint 4 — Daily-brief rendering / consumption (this run)

Closes the loop from "candidates exist in the convergence table" to "a consumable brief." Adds
`second-brain daily-brief render` (`local_ai/daily_brief_render.py`), a **read-only** consumer of
`daily_brief_action_candidates`.

- **Render is pure/read-only.** `render_daily_brief` reads only the 11 safe columns from
  `list_daily_brief_action_candidates` (already redacted at write time), groups internal sections
  into ordered display headings (Today's Actions, Waiting / Follow-Up, Risks / Watch Items, Procore
  Project Signals, Calendar Prep, Unassigned / Needs Review), and emits structured JSON + redacted
  Markdown. Deterministic order (no wall-clock): display-section → project_key → priority →
  `daily_brief_action_candidate_id` (the stable per-candidate traceback indicator). Section/project
  filters + `--limit` report skipped counts; the empty set yields a valid empty brief.
- **File write is off by default, two modes, both marker-bounded + atomic + path-redacted**, reusing
  the approved `daily_brief.output` primitives (`write_brief_output`, `_ensure_markers`,
  `_replace_bounded`, `_atomic_write_text`, `SECTION_*` markers). `--write` with `--output-path`
  writes an **explicit ABSOLUTE non-repo** file (refuses repo-contained paths so private content
  can't be committed, and refuses to clobber a foreign file lacking the brief marker); `--write`
  without a path writes the **governed vault** note (`--vault-brief-dir` overrides the base dir for
  test/isolation). Both default to dry-run unless `--write`.
- **No new agent / no schema change.** Render is a consumption surface under the existing
  `daily_brief_agent`; registry stays 13. No DB write, no re-persist (proven: candidate row counts
  unchanged before/after render; guard columns stay 0). No Graph/Procore/calendar/email/external
  writeback, no cloud LLM, no MCP. Redaction proven on JSON, Markdown, and written files (no
  http/join-URL/email/HTML/token).

### `--raw` — local-consumption real content (egress boundary preserved)

A single-user, local-first tool gains little from redacting the operator's own data out of his own
brief, so `daily-brief render --raw` surfaces the **real** (un-redacted) content for **local
consumption only**: calendar items show the real subject + location/organizer; Procore items show
the real signal titles. This is sourced live from the local raw tables
(`calendar_event_raw_content`; `procore_action_signals.title_redacted`, which holds the real label)
by a deterministic **forward-map** — recomputing each candidate's id from its source row — so no
schema change, source-pointer column, or migration is needed. The egress boundary is unchanged:
`--raw` affects only the in-memory JSON/Markdown and the explicitly-written **non-repo** file (the
existing path-safety still refuses repo paths); persisted `daily_brief_action_candidates` rows stay
redacted and guard-protected, and nothing raw is logged or written to `docs/evidence`. Default
(no `--raw`) is byte-for-byte the redacted brief. The model-context packets already carried real
content (`build_calendar_event_action_packet` feeds the real subject/body), so model context needed
no change.

## Checkpoint 5 — Pipeline orchestration + governed-vault hardening (this run)

Chains the five proven workflows into one repeatable daily run via `second-brain pipeline run`
(`local_ai/pipeline.py::run_local_agent_pipeline`) and hardens the governed-vault write.

- **In-process, minimal orchestrator.** The pipeline calls the five builder functions in order
  (follow-up-watch → procore-digest → calendar-prep → daily-brief synthesis → daily-brief render),
  sharing one `now_utc`. It deliberately does **not** reuse the heavier Phase-08B
  `automation_executor`/run-registry (locks/retry/replay) — the run receipt is in-memory structured
  JSON; no run-receipt table is written, no new schema, no new agent (registry stays 13; orchestration
  is a surface, not an agent).
- **Operator-safety posture (per the amendments):**
  - *Dry-run default; apply fail-closed.* `--apply` requires `--max-persist-per-stage` (else exit 2
    `apply_requires_per_stage_cap`).
  - *Stage-bounded caps with explicit scope.* `--max-persist-per-stage` caps each write stage
    independently; the optional `--max-total-persist` is a global ceiling (stages beyond it run
    dry-run; `total_persist_capped` is reported).
  - *Fail-loud.* A stage that raises is recorded `status=failed` with a redacted `reason_code`; the
    run continues to a complete receipt, but `ok=false`/`partial=true` and the CLI exits **1** unless
    `--allow-partial` (then exit 0, payload still `ok=false`).
  - *Stale-brief protection.* `brief_freshness ∈ {fresh, partial, preexisting}` + a `warnings` list +
    a banner prepended to the brief markdown: a dry-run persists nothing → `preexisting`; a failed
    generation stage → `partial`; render-only subset → `preexisting`.
  - *Read-only render / no vault write.* The render stage is read-only; the pipeline never writes a
    file or the vault. `--raw` surfaces `raw_local_consumption_only=true`.
- **Governed-vault hardening.** `daily-brief render` governed write (`--write`, no `--output-path`)
  now requires a second opt-in `--confirm-vault-write` (matches the repo `--confirm` convention); a
  bare `--write` refuses with `vault_write_requires_confirmation` (exit 2, nothing written). The
  explicit `--output-path` mode is unchanged (already absolute-non-repo + repo-refused).
- **Proven (live, Dev-DB copy):** dry-run runs all 5 stages with 0 writes (would-persist 39); apply
  fail-closed (exit 2); capped apply → `fresh`; idempotent re-run (39 → 0 with a cap above backlog);
  all 13 `_P10_GUARDS` columns = 0; render-only subset → `preexisting`; vault write refused without
  confirmation and written with it (temp vault); stdout redaction-clean.

## Checkpoint 6 — Production-like daily run + weekday window policy + browser brief + launchd (this run)

- **Central weekday-aware date/window policy.** `local_ai/daily_brief_window.py` —
  `compute_daily_brief_window(run_at_local, timezone="America/New_York", *, last_successful_date)`
  returns a frozen `DailyBriefWindow` (run_date, run_weekday, previous/next_business_day,
  lookback/lookahead/calendar_prep start+end, `label`, included_dates, explanation, catch_up). One
  source of truth for every date the run uses — **no stage invents its own dates**. Behaviour by
  weekday: **Monday** `monday_carryover` (lookback prior-Friday→Mon incl. weekend; lookahead through
  Friday of the run week); **Tue–Thu** `standard_weekday` (prev business day → next business day);
  **Friday** `friday_next_week` (lookback Thu→Fri; lookahead through **next Friday** = weekend + next
  workweek). Weekend resolution: a fresh Sat/Sun with the most-recent Friday already successful →
  `skipped_weekend`; otherwise a wake catch-up of a missed Friday resolves to the Friday policy
  (`catch_up=True`). Pure/deterministic + DST-correct (zoneinfo on local NY dates).
- **Policy threading.** `calendar_prep` gains optional `window_start_iso`/`window_end_iso`
  (offset-aware local bounds → UTC) overriding `lookahead_days`; `run_local_agent_pipeline` gains
  optional `window` (forwards the calendar window + emits `date_policy` in the receipt). Both are
  backward-compatible — with no window the behaviour is exactly Checkpoint 5 (no regression).
- **Daily-run wrapper.** `local_ai/daily_run.py` `run_daily_local_agent(...)` resolves the policy,
  runs the pipeline (apply, conservative caps `--max-persist-per-stage 10` / `--max-total-persist
  30`), then renders the raw brief to two private local-consumption surfaces and writes status —
  dry-run-default, fail-loud, never auto-opens a browser.
- **Polished browser brief.** `local_ai/daily_run_html.py` renders a self-contained HTML
  (inline CSS, zero network) with status banner, `date_policy` panel, the six section cards +
  carryover/next-week label, and candidate IDs. Two-layer egress containment: per-value
  `scrub_raw_text` (URLs/join links/SAS/JWT/bearer/emails → safe markers) + `html.escape`, then a
  fail-closed whole-document scan (reuses `daily_brief_html._scan_html_for_external_assets`); a
  non-empty scan withholds the HTML and preserves last-good.
- **Stable non-repo output paths.** Browser `daily-brief-latest.html` (stable) + dated archive +
  `daily-brief-latest-attempted.html` under `<app_support>/html/`; status `latest-status.json` +
  dated + `last-successful.json` pointer under `<app_support>/daily-run-status/`; governed Obsidian
  note via the Checkpoint-5 `write_brief_output` (marker-bounded, raw allowed). Output dirs inside
  the repo are refused (`output_path_inside_repo_refused`). `latest.html` updates **only** on a fresh
  success → last-good is preserved on failure; a partial run writes a clearly-marked degraded
  `attempted.html` only.
- **Redacted status file.** Machine-readable, safe for evidence: run timestamp, git head, status,
  brief_date, freshness, full `date_policy`, stage receipts (counts only — no `detail`), summary,
  redacted output paths, warnings, redacted failure reason. Never carries raw bodies.
- **Weekday launchd scheduler.** `local_ai/daily_run_scheduler.py` `DailyRunLaunchdManager` (modeled
  on `automation/launchd_manager.py`, separate from the Phase 12 `morning` job). Label
  `com.hb.personal-assistant.daily-local-agent`; **weekday-only** `StartCalendarInterval` as an array
  of five entries (Weekday 1–5, Hour 5, Minute 0; no weekend entries). Catch-up is launchd-native on
  wake; the wrapper's policy + idempotency make a weekend catch-up safe. `install`/`uninstall`
  default to dry-run/plan (write nothing); `--apply` performs the real `launchctl load`.
- **CLI.** `second-brain daily-run run` + `second-brain daily-run scheduler {install,status,
  uninstall}`. Governed Obsidian write requires `--confirm-vault-write` (exit 2 otherwise);
  `--no-open-browser` is the only behaviour (auto-open reserved/off). Registry stays **13 agents**
  (daily-run + scheduler are surfaces, not agents).
- **Proven (live, Dev-DB copy + temp dirs):** Monday apply → `success`/`fresh`, persisted 10,
  egress-clean, browser+vault+status written, all 13 `_P10_GUARDS` = 0; **weekday windowing** Friday
  calendar would-persist 18 (window→2026-06-26) vs Wednesday 8 (→2026-06-18); Saturday catch-up →
  Friday brief (`catch_up=true`), fresh Saturday (Friday done) → `skipped_weekend`; egress scan clean
  across HTML/status/vault; status file counts/dates only (no raw); repo-contained output refused.
  Failure-preserves-last-good + partial-degraded are unit-test proven (live single-stage injection
  not feasible — shared store, same limitation as Checkpoint 5).

## Dispositions (families not implemented this run, evidence-based)

- **MCP packet builder / Obsidian workflows**: infra exists, tables empty
  (`claude_context_packets`=0, `obsidian_note_index`=0) → build-on-demand, no blocker but lower ROI now.
- **File/document enrichment**: data-blocked (`files`=0, no `extracted_text` table populated).
- **Inbox classification / entity normalization / relationship engine**: detectors/extractors
  exist; deterministic relationship scoring already shipped (`relationship_scoring.py`); no
  high-ROI agent gap this run.
- **Review/API/dashboard**: CLI-only by design; the review surface is the CLI + the unified
  `daily_brief_action_candidates`. No web surface added.

See `docs/evidence/phase-10-local-agent-family/README.md` for command outputs + guardrail proof.
