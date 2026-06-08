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

All six are registered in `resources/config/phase_08a_agent_registry.seed.yaml` (13 agents
total: 9 required Phase-08A + 4 family entries; the extraction front-end reuses the existing
substrate). `second-brain agents status` validates the registry/tool policy (0 violations).

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
```

`daily_brief_action_candidates` is the **convergence table** — the email family and the
Procore family both feed it, and the synthesis layer presents a unified brief by section.

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
