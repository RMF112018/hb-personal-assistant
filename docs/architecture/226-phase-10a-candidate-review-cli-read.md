# 226. Phase 10A — Candidate review CLI (read-only verbs)

Date: 2026-06-08

Package: HB Construction Intelligence — Phase 10A Candidate Review CLI Implementation Package (repo-truth update)

## Context

Records 223–225 landed the V43 schema, the review service, and the store API.
This record covers the first operator-facing surface: three **read-only** Typer
verbs under the existing `second-brain review` group, wired over the
`candidate_review` service. No new business logic — thin CLI over existing
functions.

```
hb-assistant second-brain review list --status pending --limit 25 --json
hb-assistant second-brain review show --candidate-id <id> --json
hb-assistant second-brain review summary --json
```

The `review` group already hosts the Phase 09 burden-mart verbs
(`policy-status`/`burden`/`queue`/`clusters`); `list`/`show`/`summary` are additive
and non-colliding. The group help string was broadened to reflect both purposes.

## Decision

In `cli/second_brain.py`, added the three commands to `review_app` following the
group's conventions: `json_out = typer.Option(True, "--json/--no-json")`,
in-function imports of `ConstructionStore` + the service module, output via the
existing `_emit_08c(payload, *, json_out, human, exit_code)` helper, and the
established `try … _emit_08c(…) / except typer.Exit: raise / except ValueError →
exit 2 / except Exception → exit 1` wrapper.

- **`review list`** — `--status` / `--project` / `--limit` / `--db` /
  `--json`. Calls `list_review_candidates`; invalid `--status` (service
  `ValueError`) → exit 2.
- **`review show`** — `--candidate-id` (required) / `--candidate-type` (optional;
  auto-resolves) / `--db` / `--json`. Calls `show_review_candidate`; emits the
  candidate + its immutable, redacted `source_refs`. `candidate_not_found` → exit 3.
- **`review summary`** — `--project` / `--db` / `--json`. Calls `review_summary`;
  per-type + combined `review_status` counts.

Each accepts `--db` (per the prompt) → `ConstructionStore(db_path=db)` (defaults to
the configured DB). A new `_candidate_review_guardrails()` helper supplies a
candidate-review-appropriate guardrail block (`read_only`, `advisory_only`,
`local_only`, `no_determination`, `no_raw_no_writeback`, `source_refs_immutable`) —
the Phase-09 `_review_common_guardrails` is burden-mart specific and is not reused.

**Exit-code map:** 0 success · 2 invalid `--status` · 3 candidate not found ·
1 unexpected error.

**Redaction:** the service returns only redacted/safe fields
(`title_redacted`/`reason_redacted`/`evidence_redacted`, source-ref hashes); the
CLI emits them verbatim and adds nothing raw.

## Verified

`pytest tests/test_phase_10a_review_cli.py` (5 tests, `CliRunner` + temp `--db`):
summary counts; list + `--status` filter; invalid status → exit 2; show
found (with `source_refs`) + not-found → exit 3; and a recursive no-raw-key guard
over the JSON output of all three verbs. Real CLI smoke
(`review summary --db <tmp> --json`) returns exit 0 with the expected envelope.
`ruff` clean; regression (`candidate_review`, `schema`) unchanged.
(`cli/second_brain.py` is outside the strict mypy scope.)

## Guardrails / non-goals

Read-only only — mutation verbs (accept/ignore/reject/snooze/edit/export) are later
prompts. No new migration; no service/store logic change; no extraction
prompt/model/stable-key change; no packet-scope broadening. No email send, calendar
mutation, or Graph/Procore/external writeback; no raw body/prompt/response/URL/token
emitted.
