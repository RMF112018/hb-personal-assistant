# 228. Phase 10A — Candidate review CLI (snooze / edit / export + batch)

Date: 2026-06-08

Package: HB Construction Intelligence — Phase 10A Candidate Review CLI Implementation Package (repo-truth update)

## Context

Records 226–227 added the read-only and single-candidate action verbs. This record
completes the `second-brain review` surface with the higher-value operations —
`snooze`, `edit`, `export` — and a **batch** mode for the action verbs, all over
service functions that already exist (`snooze_candidate`, `edit_candidate`,
`export_review_queue`).

```
review snooze --candidate-id <id> --until <iso> --json
review edit --candidate-id <id> --title "..." --assignee user --waiting-state waiting_on_me --json
review export --status pending --out /tmp/phase10a_review_queue.json --json
review accept --candidate-id-file /tmp/ids.txt --max-actions 25 --dry-run --json
```

## Decision

In `cli/second_brain.py`:

- **Generalized executor.** `_run_review_action` now takes `call_kwargs` (passed to
  the service fn) and maps `ValueError` → exit 2 (bad enum / bad `--until`) and a
  service `{"ok": False}` → exit 2 (`no_edits`) / exit 3 (`candidate_not_found`).
  `snooze` and `edit` reuse it (`call_kwargs={"until","note"}` /
  `{"title","assignee","waiting_state","note"}`); the existing action verbs pass
  `{"note": reason}`.
- **`snooze`** → `snooze_candidate` (review_status `snoozed` + `snoozed_until_utc`);
  bad `--until` → exit 2.
- **`edit`** → `edit_candidate` (title/assignee/waiting_state; `review_status`
  unchanged; audit records `changes_json_redacted`); invalid enum / no fields →
  exit 2.
- **`export`** → `export_review_queue`; with `--out`, writes the redacted queue JSON
  to a **local** file (`Path.write_text`) and emits a summary; without `--out`,
  emits the full payload. Read-only over candidates; the file carries only the
  service's safe/redacted fields.
- **Batch mode** on `accept`/`ignore`/`reject` (confirmed scope: all three):
  `--candidate-id-file` (one id per line; `#` comments skipped), `--max-actions`
  (default 50, caps processing → `skipped_over_cap`), `--apply/--dry-run`
  (**dry-run default**; `--apply` required to persist). `_dispatch_review_action`
  routes id-file → `_run_review_batch` (per-id resolve via `get_candidate`; missing
  ids recorded as `not_found`, never aborting the run; dry-run reports
  `would_set: <target>`), single `--candidate-id` → immediate `_run_review_action`
  (unchanged), both → exit 2, neither → exit 2.

**Single vs batch posture (confirmed):** a single explicit `--candidate-id` is an
intentional targeted action and persists immediately (matching the README / Prompt
05); batch file input carries higher risk, so it previews by default and requires
`--apply`.

**Exit-code map:** 0 success · 2 validation (bad enum/`--until`/`no_edits`/
mutually-exclusive or missing input/invalid `--status`) · 3 candidate not found ·
1 unexpected error.

## Verified

`pytest tests/test_phase_10a_candidate_review_cli.py` (17 tests): snooze (status + until; bad
until → 2); edit (fields updated, `review_status` preserved, source refs unchanged,
audit `changes_json_redacted` populated; invalid enum / no_edits → 2); export
(to `--out` file with `items` and no forbidden keys, plus stdout form; invalid
`--status` → 2); batch accept dry-run leaves rows `pending` (`would_apply==2`,
`not_found==1`) then `--apply` persists; `--max-actions` caps (`skipped_over_cap`);
mutually-exclusive / missing input → 2. Real CLI smoke ran edit → snooze → batch
reject (dry-run) → export end-to-end; the exported file scanned clean of
forbidden keys. Service / raw_content_review suites unchanged; `ruff` clean.
(`cli/second_brain.py` is outside the strict mypy scope.)

## Guardrails / non-goals

No service/store logic change; no new migration; no extraction
prompt/model/stable-key change; no packet-scope broadening. Review actions are
local DB updates only; source refs immutable; audit rows required. `--out`/exported
files are local and carry only redacted/safe fields. No email send, calendar
mutation, or Graph/Procore/external writeback; no raw body/prompt/response/URL/token
emitted.
