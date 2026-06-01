# 07D Prompt 10 — Review-Controlled Correspondence Context (Evidence)

**Read-only projection — no schema change, no V25 table, no persistence.** Ties email thread
summaries to related records via a new `construction-agent correspondence context/status` sub-app.

## Preflight (repo truth)

- `git rev-parse HEAD` → `d39fb9692ffc7a38973dabda1b51748e96945df3` (Prompt 09 HEAD).
- `git status --short` → clean (only untracked `.claude/`, `.code-graph/`).
- `python --version` → Python 3.12.11 (`.venv/bin/python3.12`); `hb-assistant --version` → `1.3.0`.
- Schema version → **25**; package version → `1.3.0`.
- Ancestry — all ancestors of HEAD: 07A `3cf1652…`, 07B `748ed7e…`, 07C `733ffed…`.
- Evidence folder present with `00`–`09`; this adds `10`.

## What changed

- **Engine** `construction/correspondence/correspondence_context.py` (new) +
  `correspondence/__init__.py` (additive export; existing `CorrespondenceReviewBuilder` untouched):
  `CorrespondenceContextBuilder.context()` and `correspondence_context_status()` — read-only
  projection, persists nothing.
- **CLI** `cli/construction.py`: `construction-agent correspondence context/status` (read-only, no `--apply`).
- **Tests** `tests/test_correspondence_context.py` (6).
- **No store or schema changes.** Reuses `list_email_thread_summaries`, `list_email_messages`,
  `list_meeting_email_relationship_candidates`, `list_cross_source_relationship_candidates`, and
  `hash_value`. Table inventory unaffected (stays 120 — no new table).

## Design grounded in repo + live-data truth

- **Anchor = `email_thread_summaries`.** Per thread: meetings via
  `meeting_email_relationship_candidates` matched on `thread_key_hash == hash_value(thread_key)`;
  record ties via the email-source `cross_source_relationship_candidates` rolled up message→thread
  through `email_messages` (only message_id/thread_key are read — never web_link/body).
- **Eight categories** from `_categorize(target_family, target_record_type, relationship_type)`;
  `project_match` → a separate `project_confirmed` flag.
- **Where relationships exist:** only threads with ≥1 tie are linked; unlinked threads are counted only.
- **Review-controlled:** a thread/tie is review-required if any contributing edge is review-required /
  weak / model / sensitive; nothing is auto-promoted (read-only).

## Static + test validation (exit codes)

| Command | Result |
|---|---|
| `python -m compileall src tests` | exit 0 |
| `ruff check .` | exit 0 — All checks passed |
| `mypy src` | exit 0 — no issues in **187** source files |
| `pytest -m "not live and not integration and not manual"` | **2206 passed**, 1 deselected (exit 0) |

(Prompt 09 baseline 2200; +6 new correspondence-context tests.)

## CLI validation matrix (all exit 0)

`correspondence context` (+ `--project tropical`), `correspondence status`,
`construction-agent {validate, data-quality gates/no-writeback-proof/table-inventory}`,
`procore validate`, `graph files status/no-writeback-proof`, `graph calendar status`,
`graph mail status` — captured to `/tmp/p10/*.json` (ephemeral, not committed).

### Live `correspondence context` (project `tropical`)

- `threads_total=19`, `threads_linked=19`, `project_confirmations=19`, `review_required_threads=19`.
- `by_category` = {meetings 117, rfis 4, daily_log_issues 2, commitments 1}.
- `correspondence status` mirrors the summary.
- **Honest-coverage note (`documents=0` despite 22 sharepoint email edges):** the correspondence
  context anchors on email *thread summaries*, of which 07B materialized **19** (out of 66 distinct
  threads in `email_messages`). The 22 document/sharepoint email edges belong to threads that were
  **not** summarized (`has_summary=0`), so they are correctly **not** tied — there is no thread
  summary to anchor them. The RFI/daily-log/commitment edges belong to summarized threads and surface.
  This is honest "where relationships exist + a thread summary exists", not a categorization gap.
  submittals/changes/inspections have 0 live email edges (expected).

### Safety invariants

- No-raw-content regex over the serialized `context` and `status` payloads → **no match** (only
  bounded `summary_redacted`, counts, local refs/hashes, confidence classes, evidence-trail ids).
- `data-quality no-writeback-proof` `proof_passed=true`; `graph files no-writeback-proof` `ok=true`.
- `table-inventory` `schema_version=25`, `contract_table_count=120` (no new tables).
- `data-quality gates` `meeting_prep_readiness_claim="ready"` — unchanged.
- Read-only projection: nothing written to SQLite (the tests assert candidate counts are unchanged).

## Test-path coverage (new file)

success (thread tied to rfis + documents + meetings with right refs); blocked (threads but no
relationships → 0 linked, empty threads); review-required (weak edge → thread review-required);
no-raw-content; idempotency (two `context()` calls identical, candidate count unchanged — nothing
persisted); status coverage (summary-only, no per-thread detail).

## Guardrails honored / stop conditions

- No external writeback / write scopes; **no local SQLite writes at all** (read-only projection); no
  schema change.
- No raw email body/subject, web link, signed/download URL, token, or secret persisted (no-raw test +
  both no-writeback proofs).
- Weak / model / sensitive ties stay review-required and are never auto-promoted.
- Advisory only — no final legal/contractual/claim/safety/financial determination.
- Readiness not overstated: only threads with both a summary and a relationship are linked.
- No stop condition triggered; all validations classified and passing.

## Handoff

- **Changed:** new `correspondence_context` engine, additive `__init__` export, `correspondence` CLI
  sub-app, new test file, `docs/architecture/53-…md`, this evidence, README 07D ledger.
- **Gates pass/fail:** unchanged and honest (`meeting_prep_readiness_claim="ready"`); no new gate.
- **Next prompt allowed to proceed:** yes. Prompt 11 (Obsidian cross-source outputs, per the 07D
  package) may project the substrate / issue / risk / aging / correspondence context into the vault;
  the read-models and review routing are in place.
