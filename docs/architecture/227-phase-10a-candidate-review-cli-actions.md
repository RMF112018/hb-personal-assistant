# 227. Phase 10A — Candidate review CLI (accept / ignore / reject)

Date: 2026-06-08

Package: HB Construction Intelligence — Phase 10A Candidate Review CLI Implementation Package (repo-truth update)

## Context

Record 226 added the read-only review verbs. This record covers the three
local-only **state-transition** verbs under `second-brain review`, wired over the
existing service mutators (`accept_candidate`/`ignore_candidate`/`reject_candidate`,
`local_ai/candidate_review.py`). No new business logic — thin CLI plus a small
shared executor.

```
hb-assistant second-brain review accept --candidate-id <id> --json
hb-assistant second-brain review ignore --candidate-id <id> --reason "not actionable" --json
hb-assistant second-brain review reject --candidate-id <id> --reason "incorrect extraction" --json
```

## Decision

In `cli/second_brain.py`, three `review_app` commands share one executor
`_run_review_action(*, command, service_fn, candidate_id, candidate_type, reason,
db, json_out)`:

1. `ConstructionStore(db_path=db)`.
2. **CLI-side type resolution:** `store.get_candidate(candidate_id,
   candidate_type=…)` — so the operator only needs `--candidate-id` (the README
   shows no `--candidate-type`; the service mutators require a concrete type). When
   the candidate is absent → `candidate_not_found`, **exit 3**. An optional
   `--candidate-type` disambiguates when supplied.
3. Call the per-verb `service_fn(store, candidate_id=…, candidate_type=<resolved>,
   note=reason)` (reviewer fixed to `"operator"`, matching the existing
   `phase-10 review-candidate` path).
4. Emit `{command, phase:"10A", **result, guardrails}`, **exit 0**;
   `except typer.Exit: raise / except Exception → exit 1`.

**Status mapping:** `accept`→`accepted`, `reject`→`rejected`,
**`ignore`→`suppressed`** (the operator-verb normalization, owned by the service).
Each call records the V43 lifecycle columns (`reviewed_utc`/`reviewed_by`/
`review_note_redacted`) and writes a `candidate_review_events` audit row (the store
insert propagates on failure — no silent swallow). A dedicated
`_candidate_review_action_guardrails()` block documents the mutation posture
(`local_db_update_only`, `advisory_only`, `review_event_written`,
`source_refs_immutable`, `no_external_writeback`, `no_email_send`,
`no_calendar_mutation`, `no_graph_or_procore_writeback`).

Persistence is immediate (per the README — no `--emit`/dry-run flag); these are
reversible local advisory flips, distinct from the M365/Procore/Obsidian writes the
"dry-run before any write" guardrail governs. `--reason` notes are truncated by the
service (`review_note_redacted` / audit `user_note_redacted`); nothing raw is
emitted.

**Exit-code map:** 0 success · 3 candidate not found · 1 unexpected error.

## Verified

`pytest tests/test_phase_10a_candidate_review_cli.py` (10 tests total): accept transitions
pending→accepted, writes one audit row, and leaves `candidate_source_refs` count
unchanged; ignore stores `suppressed`; reject `--reason` stores `rejected` +
`review_note_redacted`; unknown id → exit 3; and a no-raw-key guard over the
mutation outputs. Real CLI smoke (`review accept` then `review show`) confirms the
transition, `reviewed_by="operator"`, and a generated `review_event_id`
end-to-end. Service mutator + schema suites unchanged; `ruff` clean.
(`cli/second_brain.py` is outside the strict mypy scope.)

## Guardrails / non-goals

Only accept/ignore/reject (snooze/edit/export are later prompts). No service/store
logic change; no new migration; no extraction prompt/model/stable-key change; no
packet-scope broadening. Review actions are local DB updates only; source refs
immutable; audit row required. No email send, calendar mutation, or
Graph/Procore/external writeback; no raw body/prompt/response/URL/token emitted.
