# Phase 10A — Candidate Review CLI Runbook (Operator)

**Audience:** Bobby (operator). **Posture:** local-first, advisory, read-only over
sources. **Hard rule:** review actions are **local SQLite updates only** — they
never send email, mutate a calendar, or write back to Graph or Procore, and never
read or emit raw bodies/prompts/responses/URLs/tokens. Source refs are immutable.

This runbook covers the operator workflow for triaging the local action candidates
(`task_candidates` / `commitment_candidates`) produced by extraction, using
`hb-assistant second-brain review …`. Every command supports `--json` (default) and
`--db <path>` (for an explicit SQLite file; defaults to the configured local DB).

---

## Command-path reconciliation (read this first)

Three distinct surfaces — do not confuse them:

| Surface | Command path | Purpose |
|---|---|---|
| Batch packet extraction | `hb-assistant second-brain extract-packets …` | Produce candidates from bounded email-thread packets (dry-run first / capped apply). |
| **Candidate review (this runbook)** | `hb-assistant second-brain review …` | Triage already-persisted candidates: list/show/summary + accept/ignore/reject/snooze/edit/export. |
| Earlier Phase 10 raw-content commands | `hb-assistant second-brain phase-10 …` | Raw email/calendar packets, raw-action-candidates, candidate-source, review-candidate (the earlier prototype). Unchanged. |

The review verbs operate **only on persisted candidate rows** — they never run
extraction or read raw content.

## Exit codes

`0` success · `2` validation error (invalid `--status`/enum, bad `--until`, no edit
fields, or mutually-exclusive/missing input) · `3` candidate not found · `1`
unexpected error.

---

## Operator steps

### 1. See the queue at a glance
```bash
hb-assistant second-brain review summary --json
```
Counts by `review_status` for task + commitment + combined.

### 2. List candidates (filterable)
```bash
hb-assistant second-brain review list --status pending --limit 25 --json
```
`--status` (pending|accepted|rejected|snoozed|suppressed), `--project`, `--limit`.
Newest-first (`created_utc` desc). Redacted fields only.

### 3. Inspect one candidate + its source refs
```bash
hb-assistant second-brain review show --candidate-id <id> --json
```
Shows the candidate and its immutable, redacted `source_refs` (hashes +
`evidence_redacted` excerpt). Add `--candidate-type task|commitment` to disambiguate
(otherwise auto-resolved).

### 4. Triage — accept / ignore / reject (single-id persists immediately)
```bash
hb-assistant second-brain review accept --candidate-id <id> --json
hb-assistant second-brain review ignore --candidate-id <id> --reason "not actionable" --json
hb-assistant second-brain review reject --candidate-id <id> --reason "incorrect extraction" --json
```
`accept`→`accepted`, `reject`→`rejected`, **`ignore`→`suppressed`**. Each records
`reviewed_utc`/`reviewed_by`/`review_note_redacted` and writes a
`candidate_review_events` audit row. A single explicit `--candidate-id` is an
intentional targeted action and **persists immediately** (no dry-run).

### 5. Snooze until a time
```bash
hb-assistant second-brain review snooze --candidate-id <id> \
  --until 2026-06-12T09:00:00-04:00 --json
```
Sets `review_status=snoozed` + `snoozed_until_utc`. A snoozed candidate still
surfaces under `review list --status snoozed` and in `review summary`. A
non-ISO-8601 `--until` exits 2.

### 6. Edit editable fields (review decision unchanged)
```bash
hb-assistant second-brain review edit --candidate-id <id> \
  --title "..." --assignee user --waiting-state waiting_on_me --json
```
Updates `title_redacted` / assignee (`assignee_class` for tasks,
`commitment_actor_class` for commitments) / `waiting_state`; **does not** change
`review_status`. Records a redacted before/after diff in the audit row
(`changes_json_redacted`). Invalid enum or no fields → exit 2.

### 7. Export the queue
```bash
hb-assistant second-brain review export --status pending \
  --out /tmp/phase10a_review_queue.json --json
```
Writes the redacted/safe queue (candidates + their source refs) to the local
`--out` file and prints a summary; omit `--out` to print the full payload. The
exported file is a **local** file containing only redacted fields.

### 8. Batch actions (dry-run first, then `--apply`)
```bash
# preview (default dry-run): reports would_apply / not_found / skipped_over_cap, writes nothing
hb-assistant second-brain review accept --candidate-id-file /tmp/ids.txt \
  --max-actions 25 --dry-run --json

# persist after reviewing the preview
hb-assistant second-brain review accept --candidate-id-file /tmp/ids.txt \
  --max-actions 25 --apply --json
```
Batch mode is available on `accept`/`ignore`/`reject`. The id-file is one
`candidate_id` per line (`#` comments skipped). Batch **defaults to dry-run** and
requires `--apply` to write; `--max-actions` caps how many are processed (the rest
are reported as `skipped_over_cap`); missing ids are reported as `not_found` and
never abort the run. `--candidate-id` and `--candidate-id-file` are mutually
exclusive (supplying both, or neither, exits 2).

---

## Guardrails (re-statement)

Local DB updates only · source refs immutable · review event written per action ·
no email send · no calendar mutation · no Graph writeback · no Procore writeback ·
no external/cloud LLM dependency · no raw body/prompt/response/URL/token persisted
or emitted. The 13 `_P10_GUARDS` columns stay 0 across all candidate-review tables.

## Evidence

Captured CLI/JSON/proof/test output:
`docs/evidence/construction-intelligence-phase-10a-candidate-review-cli/02-cli-review-evidence.md`.
No-raw/no-writeback attestation:
`…/01-no-raw-no-writeback-proof.md`. Design records: `docs/architecture/223`–`231`.
