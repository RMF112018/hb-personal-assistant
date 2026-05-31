# Phase 07B — Calendar Project Matching (deterministic + heuristic, candidates only)

**Phase:** 07B — Prompt 05 (Calendar Project Matching)
**Status:** Implemented (candidate generation; review/promotion policy and thread-context signal land later).
Evidence: `docs/evidence/construction-intelligence-phase-07b-calendar-email/05-calendar-project-match-proof.json`.

Links indexed calendar events to known construction projects and writes **candidate** rows to
`calendar_project_match_candidates`. Pure local SQLite + source registry — no Graph calls, no token, no
writeback. Matching runs entirely over the **redacted** index; it never reads or stores a raw subject,
number, organizer, attendee, or location.

## Components

| Component | Path | Role |
|---|---|---|
| Matcher | `src/hb_assistant/construction/calendar/project_matcher.py` | `CalendarProjectMatcher.match()` (dry-run/apply), `ProjectDescriptor`, `MatchReport`/`CalendarMatchCandidate` |
| Repository | `src/hb_assistant/construction/store/repositories.py` | `list_calendar_event_index` (read), `upsert_calendar_project_match_candidate` (write) |
| Indexer correction | `src/hb_assistant/construction/calendar/event_indexer.py` | `_subject_token_hashes` also stores the hash of any full HB project number |
| CLI | `src/hb_assistant/cli/graph.py` (`graph calendar project-match`) | `--project`/`--source`/`--dry-run/--apply`/`--json`, mirrors `graph files project-match` |

## The redaction constraint and the additive P04 correction

P04 stored `subject_token_hashes_json` by splitting the subject on `\W+`, which fragments an HB project
number (`23-435-01` → `23`,`435`,`01`) — so exact number matching wasn't recoverable, and the calendar
source isn't project-bound. The smallest correct fix (additive, redaction-safe) is in P04's
`_subject_token_hashes`: before fragmentation, detect `\b\d{2}-\d{3}-\d{2}\b` and also store
`hash_value(full_number)`. A hash reveals nothing; re-index picks it up. The matcher then hashes each
known project number the same way and tests membership → genuine deterministic matching.

## Matching signals (over hashed tokens / domains)

| Signal (`candidate_type`) | Computation | `confidence_class` (score) | review_required |
|---|---|---|---|
| `project_number` | `hash_value(project_number) ∈ event.subject_token_hashes` (exact full-number hash) | `deterministic` (0.95) | No (unless conflicting/sensitive) |
| `project_name_tokens` | distinct project-name token-hash overlap ≥2 | `moderate` (0.6) | Yes |
| `project_name_tokens` | overlap == 1 | `weak` (0.0) | Yes |
| `participant_domain` | organizer/attendee domain vs project domains | — | (inert: no project-domain registry yet) |

`review_required` follows the contract `review_required_when` (`weak`, `moderate`, `model_proposed`,
`sensitive`, `private_event`, `conflicting_project_signals`); validated via
`load_calendar_project_match_contract()` (asserts `auto_promotion_allowed=false`).

**conflicting_project_signals**: when an event matches ≥2 distinct projects, every candidate for that
event is forced `review_required=True` with `signals.conflicting=true` (even a deterministic one).

**Private / unmatched events**: private events carry no subject tokens (P04 omits them) → no candidate;
events with no project overlap → no candidate (counted as `events_unmatched`).

## No auto-promotion

Every candidate is persisted with `promotion_status='candidate'`, and the matcher **never** writes
`calendar_event_index.project_key`/`project_match_*`. Promotion to an authoritative project relationship
is a later-phase review policy. `candidate_id = hash_value("{event_index_id}|{project_key}|{candidate_type}")`
makes apply idempotent.

## Persisted vs forbidden

`signals_json` carries **safe values only**: `candidate_type`, `project_number_hash_match` (bool),
`name_token_overlap` (count), `matched_token_hashes` (hashes), `event_token_count`, `conflicting`,
`is_cancelled`. `project_key` (the safe local kebab identifier) is required by the table. **Forbidden and
absent**: raw subject, raw project number, raw organizer/attendee email, location, event body, join URL,
token, signed URL. The `raw_body_persisted` / `external_writeback_performed` CHECK columns stay 0.

## Guardrails proven (temp-DB apply + tests)

- Deterministic (0.95) for a full-number-hash match; moderate/weak heuristic name-token candidates,
  always review-required; conflicting events route all candidates to review.
- No auto-promotion: event index `project_key` never set; all candidates `promotion_status=candidate`.
- Dry-run persists nothing; apply persists; idempotent (stable `candidate_id`).
- No raw number/subject/email in candidate rows or `signals_json`; CHECK columns 0; `graph/` static
  no-write-verb scan still clean (no Graph calls). No 07D readiness claimed.

## Deferred

`model_proposed` candidates (advisory; later), `email_thread_context` signal (needs P06–P08 email thread
data), `participant_domain` firing (needs a project-domain registry), and review/promotion policy.
