# Phase 07B Prompt 10 — Obsidian Calendar/Email Register: Proof (redacted)

Date: 2026-05-31 · Branch: `main` · Repo SHA at start: `3699e1d` · Package `1.3.0` ·
Schema head V23 (no migration — Obsidian output is file writes).

Adds `CalendarEmailObsidianProjector` (new `construction/calendar_email_obsidian.py`) that
renders ONE marker-bounded, redacted register note per project — no one-note-per-event/email
— combining the email correspondence warnings/previews, calendar↔email candidates, and
bounded calendar counts. Read-only on every layer; the Obsidian note is the only output,
written only on `--no-dry-run`. All values below are structural facts only — no UPN, tenant
GUID, raw subjects/addresses, or body content.

## Files changed

- `src/hb_assistant/construction/calendar_email_obsidian.py` (new — projector +
  `CalendarEmailObsidianReport` + marker write + `_scan_register_for_leaks`)
- `src/hb_assistant/cli/graph.py` (`graph calendar obsidian` command + import)
- `tests/test_phase07b_obsidian_calendar_email.py` (new — 3 tests)
- `docs/architecture/27-phase-07b-obsidian-calendar-email.md` (new)
- this evidence file

The rendered register note lives in the Obsidian vault (outside the repo) at the
vault-relative path:
`Work/HB Personal Assistant/07_Calendar_Email_Intelligence/Projects/tropical/Calendar & Email Register.md`.

## Preflight (HEAD 3699e1d, all exit 0)

`git status --short` (clean except untracked `.claude/`), `python -m compileall -q src tests`,
`ruff check .` (All checks passed!), `mypy src` (Success), `pytest -m "not live and not
integration and not manual"` (0 failed).

## Post-implementation local validation (all exit 0)

| Command | Result |
| --- | --- |
| `python -m compileall -q src tests` | exit 0 |
| `ruff check .` | All checks passed! |
| `mypy src` | Success: no issues found in 164 source files |
| `pytest tests/test_phase07b_obsidian_calendar_email.py -v` | 3 passed |
| `pytest -m "not live and not integration and not manual"` | 0 failed |
| `pytest tests/test_mutation_lockout.py` | passed (graph/ static no-write scan clean) |
| `hb-assistant construction-agent validate --json` | exit 0 |
| `hb-assistant procore validate --json` | exit 0 |
| `hb-assistant graph files status --json` | exit 0 |
| `hb-assistant graph mail status --json` | exit 0 |
| `hb-assistant graph calendar status --json` | exit 0 |
| `hb-assistant graph calendar obsidian --json` (dry-run; no vault write) | exit 0 |
| `hb-assistant construction-agent data-quality gates --json` | exit 0 |
| `hb-assistant construction-agent data-quality no-writeback-proof --json` | proof_passed=true |

`ruff format` is NOT enforced repo-wide; `ruff check .` is the authoritative lint gate and
passes. `ruff format` was not run.

The 3 unit tests (auto-isolated to a tmp vault by the `isolated_hb_pa_config` conftest
fixture) cover: dry-run plans exactly **1** grouped note and writes nothing; apply writes a
marker-bounded note that passes `_scan_text_for_secrets` and contains no `@`/`http`/
`begin:vevent`/`join url`/original-message tokens, with previews rendered as hashes; and
re-apply replaces only the marker region while preserving surrounding user text (markers not
duplicated).

## Live proof

### 1. Dry-run against the real store (writes nothing)

`graph calendar obsidian --project tropical --json`:

| Field | Value |
| --- | --- |
| dry_run / notes_planned / notes_written | true / 1 / 0 |
| events_referenced | 108 |
| threads_referenced | 19 |
| warnings_referenced | 6 |
| candidates_referenced | 117 |
| plaintext_written / guardrails.leak_scanned | false / true |

The render passed the internal leak scan (it raises otherwise); the vault file was **not**
created by the dry-run.

### 2. Real-vault write (`--no-dry-run`, user-authorized)

`graph calendar obsidian --project tropical --no-dry-run --json` → `notes_written=1`,
`plaintext_written=false`. Read-back of the written note:

- `HB-CALENDAR-EMAIL-REGISTER` start/end markers present.
- `_scan_text_for_secrets(note)` → `[]` (clean).
- Forbidden-token scan (`@`, `http`, `begin:vevent`, `join url`, `-----original message-----`,
  `teams.microsoft.com`) → 0 hits; raw-email regex → no match.
- 8,298 chars; sections: Overview, Review Warnings, Correspondence Previews, Meeting ↔ Email
  Links, Guardrails.
- **Idempotent:** re-running `--no-dry-run` left exactly **1** marker block in the note.

### 3. Post-write checks

- `no-writeback-proof --json` → `proof_passed=true`, `no_raw_values_persisted=true` (an
  Obsidian write is not a Microsoft 365 writeback).
- `pytest tests/test_mutation_lockout.py` → clean.

## Scope notes

- No Microsoft 365 mutation/writeback; no SQLite writes; no Phase 07D meeting-prep readiness
  is claimed.
- The register is advisory — warnings/previews are signals, not determinations; sensitive
  items route to human review.
- The no-writeback prover does not yet scan the V11/V14/V23 email/calendar tables — deferred
  to Phase 07B Prompt 12.
