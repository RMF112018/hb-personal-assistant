# Phase 10 — Local-Agent Family Proof (experimental)

Branch: `experiment/local-agent-family-proof` · base HEAD `fff71545` · schema V43 · 2026-06-08

Proves a coherent, local-only, review-gated **family of agents** end-to-end on real local
data, under all no-raw / no-writeback guardrails. This bundle is command-output focused and
redacted: only counts, status booleans, and guard-column sums appear — never raw email/calendar
bodies, prompts, responses, URLs, tokens, or candidate titles.

## What the family is

A two-agent chain layered on the already-built Phase 10A extract/review code:

```
email thread raw context ──(existing)──▶ extract-packets ──▶ task/commitment candidates (+source refs)
        │                                                              │
        │                                              review-candidate --decision accepted --emit
        ▼                                                              ▼
  (already populated in Dev DB)                       --promote ──▶ accepted_tasks / accepted_commitments   ← NEW
                                                                       │
                                                       follow-up-watch scan (deterministic, no clock)        ← NEW
                                                                       ▼
                                              follow_up_watch_items / follow_up_status_events  (advisory)
```

Both new ends are registered as first-class entries in the agent registry
(`email_action_extraction_agent`, `follow_up_watch_agent`) so the family is discoverable.

## Repo / DB truth

- Target DB = the **Dev** app-support root (`HB Personal Assistant (Dev)`), schema **V43**.
- Dev DB readiness: `email_message_raw_content`=2252, `email_thread_raw_context`=1175 (model-ready),
  `calendar_event_raw_content`=500, `task_candidates`=21 (+21 `candidate_source_refs`),
  `accepted_*`/`follow_up_*`=0 (the gaps this work closes).
- Ollama: `mistral-nemo:12b`, `qwen2.5:14b`, `llama3.1:8b`, `gpt-oss:20b` available;
  `local-model status` → ready (probe-only).
- All apply-mode validation ran on a **copy** of the Dev DB (`/tmp/hb_local_agent_proof.sqlite`);
  the Dev and production DBs were never mutated.

## Verified end-to-end (on the Dev-DB copy, real data)

| Step | Command | Result |
|------|---------|--------|
| Promote 3 real accepted candidates | `phase-10 review-candidate --decision accepted --emit --promote` | `promoted=True` ×3 |
| Follow-up scan **dry-run** | `follow-up-watch scan --as-of … --summary` | `applied=False`, `scanned=3`, `would_persist=3`, `persisted=0` |
| Dry-run wrote zero rows | (sqlite count) | `follow_up_watch_items=0` |
| Follow-up scan **apply capped** | `follow-up-watch scan --apply --max-persist 2 --as-of …` | `persisted=2` (1 held back) |
| Re-run apply (idempotent) | `follow-up-watch scan --apply --max-persist 5 --as-of …` | `skipped_existing=2`, `persisted=1` |
| Classification (real items) | — | `by_status = {waiting_on_others: 2, waiting_on_me: 1}` |

Final copy-DB counts: `accepted_tasks=3`, `follow_up_watch_items=3`, `follow_up_status_events=3`.

## Guardrail proof (copy DB, after apply)

All 13 `_P10_GUARDS` columns summed to **0** on every new row:

```
accepted_tasks:          rows=3  guard_nonzero=NONE
follow_up_watch_items:   rows=2  guard_nonzero=NONE
follow_up_status_events: rows=2  guard_nonzero=NONE
GUARDRAIL_PROOF_PASS = True
```

(Columns: raw_email_body / raw_document_text / raw_calendar_payload / raw_procore_payload /
raw_prompt / raw_response / signed_url / download_url / external_writeback / graph_writeback /
procore_writeback / email_send / calendar_mutation — all `CHECK(=0)` and observed 0.)

Status events carry only a `source_ref_hash` (opaque source identifier copied verbatim from the
existing `candidate_source_refs`) + an already-redacted excerpt — no raw bodies move.

## Safety properties enforced (code + tests)

- Dry-run is the default for every new command; apply is explicit.
- `--apply` fails closed without `--max-persist` (exit code 2, `error="apply_requires_max_persist"`).
- `--max-persist` caps actual writes; remaining changed items are counted, not written.
- Promotion is never automatic — requires `--emit` + `accepted` decision + explicit `--promote`; idempotent.
- Items with no source refs are never persisted (`skipped_no_source_refs`).
- Unchanged items are skipped (`skipped_existing`); a status change emits exactly one status event.
- The classifier is deterministic and reads no clock (`--as-of` stamped once at the CLI boundary).
- Oversized thread-context blobs (`messages_json` > 1.5MB; real data has up to ~4.5MB) are skipped
  and counted (`skipped_oversized`); the packet builder independently hard-caps model input to ≤12KB.

## Tests

- `tests/test_phase_10_acceptance_promotion.py` (6) — promotion writers, idempotency, guard cols,
  CLI `--promote` gating (no-promote default, accepted-only, requires emit).
- `tests/test_phase_10_follow_up_monitor.py` (16) — classifier branches + determinism + no-clock,
  dry-run zero writes, apply-requires-cap, max-persist cap, source-ref gate, dedup, status-change
  event, guard cols zero, empty-input clean, no-raw output, CLI wiring, oversized guard.
- `tests/test_agent_registry.py` / `tests/test_second_brain_agents_cli.py` — updated agent-count
  assertions (9 required + 2 family = 11); `agents status` → `registry_valid`, `tool_policy_valid`,
  `violations_count=0`.

Targeted suites green; `ruff check` + `mypy` clean on changed modules.

## Pre-existing failures (NOT caused by this work)

Confirmed via `git stash` on clean HEAD `fff71545`:
`test_email_body_indexing.py::test_capture_encrypts_and_stores_ref_only` (double body fetch) and
`test_phase_10_email_task_extraction.py::test_commitment_persists_to_commitment_table` — plus the
schema-lifecycle / 08b-gate set noted in prior evidence. Independent of this branch.

## Branch status

Experimental, **ready for audit** — not auto-mergeable (per the working-mode brief). No live Graph
crawl, no migration, no production/Dev DB mutation were required or performed.

---

# Checkpoint 2 — Procore digest + daily-brief synthesis

Adds two further verticals on top of Checkpoint 1, proven on the **production-DB copy** (real
Procore data) and via unit tests. The convergence table is `daily_brief_action_candidates`.

## Procore action-signal digest (`second-brain procore-digest build`)

Composes existing redacted Procore read models (`build_operational_digest`, `list_procore_action_signals`,
`get_procore_text_intelligence`, `_dimensions_for`) into a per-project / per-signal-type digest.
Deterministic-first; optional `--synthesize` advisory narrative (off by default, in-memory only,
fed only redacted aggregates). Verified on a copy of the production DB (V42, 5836 open signals, 3
real projects: alton-hilltop-pbg / pga-modern-garage / tropical):

| Step | Result |
|------|--------|
| dry-run | `projects=3, groups=83, total_open_signals=5836, by_importance={high:1434, medium:4235, low:167}, would_persist=83, persisted=0`; headlines `ok=True` for all 3 |
| dry-run wrote 0 rows | `daily_brief_action_candidates=0` |
| apply `--max-persist 5` | `persisted=5` (78 held back) |
| re-apply `--max-persist 5` | `skipped_existing=5, persisted=5` (idempotent) |
| redaction | output carries no `metadata_json` / `encrypted_full_text_ref` / `text_hash` / titles / `owner_entity_key` |
| source untouched | `procore_action_signals` still 5836 (no Procore writeback) |

## Daily-brief synthesis (`second-brain daily-brief synthesize-candidates`)

Unifies accepted tasks + stale follow-up watch items + the Procore digest rows into
`daily_brief_action_candidates` by section (`actions` / `waiting` / `follow_up` / `procore`) and
returns one advisory brief view. On the production-DB copy (no accepted/watch rows there) the brief
correctly surfaced the **procore** section with real redacted rollups (e.g. "216 open
invoice_payment_due signals"); the email sections are covered by unit tests on seeded data.

## Guardrail proof (production-DB copy)

```
daily_brief_action_candidates: rows=10  guard_nonzero=NONE     # all 13 _P10_GUARDS = 0
procore_action_signals: 5836 (unchanged — no writeback)
```

## Tests (Checkpoint 2)

- `tests/test_phase_10_procore_digest.py` (16) — shape/source-linking, redaction (forbidden keys),
  dry-run zero writes, apply needs flag+cap, max-persist cap, idempotency, guard cols 0, empty clean,
  synthesis off-by-default + no-client fail-closed + redacted-input-only, CLI wiring.
- `tests/test_phase_10_daily_brief_synthesis.py` (9) — section routing, dry-run zero, apply needs
  flag+cap, cap, idempotency, guard cols 0, unified brief includes Procore rows, empty clean, CLI.
- Registry count assertions updated to 12; `agents status` valid, 0 violations.

Targeted suites green; `ruff` + `mypy` clean on changed modules. Pre-existing clean-HEAD failures
(`test_email_body_indexing`, `test_phase_10_email_task_extraction::test_commitment_persists...`)
remain, independent of this branch.

## Family dispositions (evidence-based, not implemented this run)

| Family | Evidence | Verdict |
|--------|----------|---------|
| Calendar meeting-prep | Dev `calendar_event_index`=500 / `calendar_event_raw_content`=500, HTML-only bodies, join-urls, no project_key/source_ref | **Implemented (Checkpoint 3, below)** — normalization slice + deterministic fallbacks shipped |
| MCP packet builder | infra present, `claude_context_packets`=0 | Deferred — build-on-demand, lower ROI now |
| Obsidian workflows | safe writer + path policy exist, `obsidian_note_index`=0 | Deferred |
| File/document enrichment | `files`=0, no populated extracted-text | **Data-blocked** |
| Inbox classification / entity / relationship | detectors/extractors exist; deterministic relationship scoring already shipped | No high-ROI agent gap this run |
| Review/API/dashboard | CLI-only by design | Out of scope; review surface = CLI + `daily_brief_action_candidates` |

## Checkpoint 2 status

Experimental, **ready for audit**. No migration, no production/Dev DB mutation (copy only), no
Procore/Graph/external writeback, no cloud LLM.

## Micro-closeout (post-audit fixes)

Addresses two audit findings; no Checkpoint 3 scope:
- **R1 — `procore-digest --limit` now bounds the digest, not just display.** The top-`limit`
  highest-count groups per project feed BOTH the output and `would_persist`/apply; `--max-persist`
  remains the separate hard cap on actual writes. `group_count` still reports the true total
  (truncation is visible — no silent cap), and a new `groups_considered` field reports the bounded
  count. Covered by a new `test_limit_bounds_groups_and_would_persist`.
- **Test-count accuracy.** Corrected the per-file counts (acceptance 7→6, follow-up 15→16; the
  Checkpoint 1 total of 22 is unchanged). At audit, Checkpoint 2 had 24 tests (`procore_digest` was
  15, not the stated 16); this closeout adds the one R1 regression test, bringing `procore_digest`
  to 16 and Checkpoint 2 to **25** — now matching reality. Historical Phase-08A/09 frozen evidence
  (`agent_count: 9`) is intentionally left unchanged (point-in-time snapshots, not test-enforced).

## Checkpoint 3 — Calendar meeting-prep (this run)

Adds calendar as the third source family: `second-brain calendar-prep build` — deterministic,
bounded, source-linked, dry-run-default meeting-prep candidates that feed the same
`daily_brief_action_candidates` convergence table (section `calendar`). No calendar mutation, no
Graph/external writeback, no cloud LLM.

### Calendar DB readiness (read-only probe, Dev DB V43)

```
calendar_event_index: 500   calendar_event_raw_content: 500 (1:1 via event_index_id)
body_text nonempty: 0/500   body_html nonempty: ~460/500   → HTML→text normalization required
join_url present: 404/500   → stripped/flagged, never persisted
project_key present: 0/500  source_ref_hash present: 0/500 → deterministic fallback required
window @ as-of 2026-06-08, lookahead 14d: 39 events in-window (138 future, 5 cancelled, 0 private)
```

### What was implemented

- New read-only reader `list_calendar_prep_source_events` — safe redacted fields
  (`subject_redacted`, `location_redacted`, organizer/attendee **domains**, start/end, online flag)
  + attendee count and DISTINCT domains; excludes cancelled/private; never subjects/bodies/join
  URLs/attendee names/emails.
- New builder `local_ai/calendar_prep.py::build_calendar_prep_candidates` — deterministic window +
  ordering (`now_utc` passed in, no clock read); per-event enrichment **composes** the existing
  bounded `build_calendar_event_action_packet` (HTML→text, join-URL / dial-in / passcode / Teams
  boilerplate stripped, attendees→domains) plus a calendar-scoped `_safe_excerpt` pass that also
  drops scheme-less domain/link tokens and email addresses; deterministic fallbacks
  `source_ref = cal:<sha256(event_index_id)>` and `project_key → __unassigned__`.
- CLI `calendar-prep build` mirrors `procore-digest build` (`--db --limit --lookahead-days --as-of
  --dry-run/--apply --max-persist --summary --json`, optional `--synthesize`).
- Registry: `calendar_prep_agent` added → **13 agents** (`agents status`: registry_valid,
  tool_policy_valid, violations 0).

### Live proof (copy of Dev DB; scratch copy removed after)

```
calendar-prep build --lookahead-days 14 --limit 25 --as-of 2026-06-08T00:00:00+00:00 --dry-run
  → events_in_window=39, events_considered=25, would_persist=25, persisted=0, applied=false
  → daily_brief_action_candidates(calendar) rows after dry-run: 0

--apply --max-persist 8 → applied=true, persisted=8 (capped); re-apply → skipped_existing=8 (idempotent)
guardrail query: 13 _P10_GUARDS columns over section='calendar' rows = 0 (all)
calendar_event_index / calendar_event_raw_content counts: 500 / 500 (unchanged — no mutation)
redaction scan (persisted rows + --summary excerpts): 0 http/URL, 0 teams/zoom domains,
  0 email-shaped tokens, 0 html tags, 0 meeting-id/passcode literals, no raw subject
```

### Tests (Checkpoint 3)

- `tests/test_phase_10_calendar_meeting_prep.py` (24) — window excludes cancelled/private/far-future,
  deterministic source-ref + project fallback, missing-source-ref skipped-closed, join-URL / dial-in /
  passcode / meeting-id / scheme-less-link / email redaction, HTML→bounded text, oversized body
  bounded, no full attendee list / emails, raw subject never emitted, dry-run zero writes, apply
  needs flag + cap, max-persist cap, idempotency, guard cols 0, persisted rows carry no raw content,
  no calendar-table mutation, synthesis off-by-default + no-client + malformed-output fail-closed +
  redacted-input-only, daily-brief surfaces `calendar` section, CLI wiring (dry-run default,
  non-summary drops excerpts, apply needs cap, capped apply).
- Registry count assertions updated to **13**; `tests/test_agent_registry.py` +
  `tests/test_second_brain_agents_cli.py` green.

Targeted suite green (87 tests across Checkpoint 1/2/3 + registry); `ruff` + `ruff format` + `mypy`
clean on changed modules. The two pre-existing clean-HEAD failures
(`test_email_body_indexing::test_capture_encrypts_and_stores_ref_only`,
`test_phase_10_email_task_extraction::test_commitment_persists...`) remain, independent of this
branch (confirmed by re-running with this work stashed). A third environment-dependent failure
(`test_calendar_event_indexing::test_raw_content_flag_produces_rows_and_counts`) also fails with this
work stashed — it reads a shared `raw_content` policy state, unrelated to Checkpoint 3.

## Checkpoint 3 status

Experimental, **ready for audit / merge consideration**. No migration, no production/Dev DB mutation
(copy only), no calendar/Graph/Procore/external writeback, no cloud LLM. Checkpoints 1 and 2
preserved (regression green).
