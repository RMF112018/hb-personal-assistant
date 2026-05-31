# 27 — Phase 07B: Obsidian Calendar/Email Register Output

Phase 07B Prompt 10. Status: implemented at this record's commit.

## Problem

The redacted calendar/email read models and the aggregated `CorrespondenceReviewReport`
(Prompt 09) existed, but nothing rendered them into the Obsidian vault. There was no
`graph calendar obsidian` command and no calendar/email Obsidian projector.

## Change

New `CalendarEmailObsidianProjector` (`construction/calendar_email_obsidian.py`) renders ONE
marker-bounded **register note per project** (never one note per event/email) combining the
email correspondence warnings/previews, the calendar↔email relationship candidates, and
bounded calendar counts. Read-only on every layer — no Graph calls, no token, no SQLite
writes; the only output is the Obsidian note, written **only** when `dry_run=False`.

`project(*, project_key=None, dry_run=True, max_rows=25) -> CalendarEmailObsidianReport`:

- Data: `CorrespondenceReviewBuilder.review(project_key)` (warnings + previews + counts),
  `list_meeting_email_relationship_candidates(project_key)`, and `list_calendar_event_index()`
  (global calendar counts). All inputs are hashes/counts/datetimes; events expose no raw
  subject and their `project_key` is NULL live, so the calendar section is rendered as counts
  plus the candidate-derived event↔thread links (event ref = `hash_value(event_index_id)`).
- Render: a single marker-bounded block (markers `<!-- HB-CALENDAR-EMAIL-REGISTER:START -->` /
  `:END`) with **Overview**, **Review Warnings**, **Correspondence Previews**, **Meeting ↔
  Email Links**, and **Guardrails** sections. Relative path
  `Work/HB Personal Assistant/07_Calendar_Email_Intelligence/Projects/{project}/Calendar & Email Register.md`
  under `PathPolicy().get_vault_root()`.
- Write mechanism mirrors `EmailObsidianProjector._write_artifact`: ensure markers, regex-
  replace only inside the marker region (user text outside is preserved), idempotent.
- **Self leak-scan before any write** (`_scan_register_for_leaks`): forbidden calendar/email
  tokens (`<html`, `from:`, `-----original message-----`, `begin:vevent`, `join url`,
  `teams.microsoft.com`, `http(s)://`, …), a raw-email-address regex, and
  `_scan_text_for_secrets` (PEM/JWT/bearer/SAS/AWS, reused from the Procore prover). A note
  that would leak raises `ValueError` and is never written.

### CLI
`graph calendar obsidian` (`cli/graph.py`, under the calendar group): `--project`,
`--max-rows`, `--dry-run/--no-dry-run` (default dry), `--json`. Mirrors `graph mail obsidian`.

## Guardrail invariants
- No Microsoft 365 mutation/writeback; Graph-free; SQLite read-only (Obsidian is the only
  output, gated by `--no-dry-run`).
- No raw subject, body, address, organizer, attendee, location, event id, iCal UID, or
  join/web URL in the rendered note — hashes/counts/datetimes only; the pre-write leak scan
  enforces this.
- One register note per project (no one-note-per-event/email). Idempotent (marker-bounded).

## Evidence

`docs/evidence/construction-intelligence-phase-07b-calendar-email/10-obsidian-output-preview.md`
(local validation + redacted dry-run proof + a real-vault write proof). The rendered note
lives in the Obsidian vault, outside the repo. The no-writeback / no-raw-body prover does not
yet scan the V11/V14/V23 email/calendar tables — deferred to Phase 07B Prompt 12.
