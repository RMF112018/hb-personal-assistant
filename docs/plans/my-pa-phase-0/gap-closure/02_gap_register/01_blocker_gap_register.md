# Blocker and Gap Register

## B-001: Stated commit SHA does not resolve

**Observed:** User-stated commit `63bb05c7163b85ff556f0a599a19cf9bba501280` did not resolve through GitHub. Accessible live `main` resolved to `d0cc5516f51f02c5a2d7f2e30379aab2b98abc52`.

**Risk:** Agent may remediate the wrong ref or overlook unpushed local work.

**Acceptance Criteria:**

- Current local `HEAD` is documented.
- Remote `origin/main` is documented.
- `63bb05c7163b85ff556f0a599a19cf9bba501280` is explicitly classified as found locally, found on another remote/branch, rewritten/not present, or user typo.
- Final package evidence names the canonical audited/remediated ref.

---

## B-002: Final closeout evidence contradicts validation outputs

**Observed:** Phase 13 claims “complete/clean,” while captured outputs show pytest failures, Ruff failures, and CLI errors.

**Risk:** False confidence in an unsafe or incomplete MVP.

**Acceptance Criteria:**

- Closure proof regenerated only after commands pass.
- Any remaining failure is fixed, deliberately excluded with rationale, or marked xfail with justification.
- Evidence matrix includes raw command status.

---

## B-003: CLI grammar mismatch

**Observed:** Implemented `auth` as a boolean-option command, but evidence/runbook expect `auth status`. Implemented `run` as `run --morning`, while launchd renders `run morning`.

**Risk:** User-facing commands and scheduled automation fail.

**Acceptance Criteria:**

- `auth` is a Typer sub-app with `login`, `status`, `logout`, `clear-cache`.
- `run` is a Typer sub-app with `morning`.
- Compatibility aliases may remain, but canonical tests must use subcommands.
- Tests cover all canonical commands.

---

## B-004: launchd executable and working directory likely invalid

**Observed:** LaunchdManager derives executable and working directory from Application Support parent, likely producing `~/Library/Application Support/.venv/bin/hb-assistant`.

**Risk:** LaunchAgent installs but cannot execute.

**Acceptance Criteria:**

- launchd config has explicit executable path and working directory resolution.
- Dry-run plist preview verifies executable existence or emits a blocking readiness failure.
- Working directory points to repo root or installed package working root.
- ProgramArguments match canonical CLI grammar.

---

## B-005: delegated Graph proof not current-state verifiable

**Observed:** Final diagnostics evidence indicates missing delegated token / no cache, while closeout claims delegated proof complete.

**Risk:** System cannot actually retrieve mail/calendar/file metadata for Bobby.

**Acceptance Criteria:**

- Current repo/runtime delegated proof is re-run.
- Proof validates delegated token classification via `scp`.
- `/me`, mail metadata, bounded body retrieval, calendarView, attachment metadata, file metadata, and controlled download proof are captured if permissions allow.
- Any permission gap is documented as a true blocker or explicit manual prerequisite.

---

## B-006: body mention detection is preview-only

**Observed:** Detector operates on `body_preview_redacted`. Body mentions outside preview are not guaranteed to be found.

**Risk:** Original requirement is not met.

**Acceptance Criteria:**

- Candidate messages can fetch bounded body content in memory.
- Raw body is never persisted.
- Detection result and optional redacted match window are persisted.
- Test proves a body-only Bobby mention outside preview is detected.

---

## B-007: Graph paging incomplete in clients

**Observed:** GraphHttpClient supports paging, but mail/calendar clients mostly use first-page reads.

**Risk:** Assistant misses emails, calendar events, files, or attachments.

**Acceptance Criteria:**

- Bounded paging implemented in mail inbox/sent, calendarView, attachment list, and drive children.
- Max page/item caps exist.
- Tests use mocked `@odata.nextLink`.

---

## B-008: file ingestion can proceed without valid source provenance

**Observed:** Some file ingestion paths can operate with `sid = 0` or demo sample records.

**Risk:** Parser outputs and files become untraceable.

**Acceptance Criteria:**

- Real ingest requires valid `source_record_id`.
- Demo/sample CLI is separated from real CLI.
- Real ingest fails closed if source provenance is missing.
- Tests cover both dry-run and real-path guard behavior.

---

## B-009: Daily Brief still contains stale placeholder sections

**Observed:** Brief generator has placeholder content for sections that should be wired after later phases.

**Risk:** Daily Brief does not provide operational value.

**Acceptance Criteria:**

- Brief generator consumes actual context builder output where available.
- Calendar, action, file review, retrieval, and workstream signals render from data.
- Placeholder text only appears when data is absent and must be framed as “No current items found,” not “later phase.”

---

## B-010: sensitive scanner scans names more than contents

**Observed:** Scanner checks file/path substrings; content scanning is insufficient.

**Risk:** Secrets embedded in `.md`, `.json`, `.py`, `.txt`, or evidence files can be missed.

**Acceptance Criteria:**

- Bounded text content scanning exists.
- Binary/large files are skipped safely with category output.
- Findings include category/path/line number only, never secret values.
- Scanner has tests with synthetic tokens and synthetic safe false positives.
