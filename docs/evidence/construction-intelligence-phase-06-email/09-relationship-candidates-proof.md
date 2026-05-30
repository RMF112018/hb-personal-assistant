# 09 — Email Relationship Candidates (project, Procore, files, meetings)

Phase 06 Prompt 09 · **local-only** (no Graph, no mailbox) · candidates are **not determinations**

Synthesizes cross-system relationship candidates linking project-matched emails to project identity,
Procore controls/financials, SharePoint/OneDrive files, and calendar meetings. Reads stored email
intelligence + the repo's Procore/calendar/drive tables; the only writes are local
`email_relationship_candidates` rows.

Evidence artifact: [`email-relationship-candidates.json`](./email-relationship-candidates.json).

## What landed

- **`construction/store/repositories.py`** — `list_email_project_matches` + `list_email_relationship_candidates`.
- **`construction/email/relationship_builder.py`** (new) — `RelationshipCandidateBuilder(store)`:
  for each project-matched message in the lookback window, emits a `project` candidate (from the stored
  match), a `procore_*` candidate when the sender is a Procore notification (control type detected from
  the bounded preview), a `procore_payment_application|invoice|contract` candidate when a financial
  keyword appears and financials are available (routes to review), and a `calendar_event` candidate on
  Outlook meeting-email patterns. Counts existing Prompt 08 `*_drive_item` file candidates and surfaces
  Procore/drive/calendar availability. `RelationshipReport` carries counts + redacted samples only.
- **`cli/graph.py`** — `graph mail relationships --project … --lookback-days … [--dry-run/--no-dry-run]
  --json` (local-only; default persist).

## Reconciliation (package ↔ repo truth)

- **Local-only synthesis** consuming `index` + `discover` (persisted) output. Prompt 07's live discover
  was dry-run, so the evidence below first ran `discover --no-dry-run` to populate `email_project_matches`
  (the documented operational sequence index → discover → relationships).
- **Graceful by availability:** `procore_live_records` (1,780 for tropical) + `procore_financial_contracts`
  (74) are live; `construction_drive_items` and `construction_project_identity` are empty live, so the
  project link targets `construction_project_identity` by key and file resolution stays name-hash-based.
- **Not determinations** (08_RELATIONSHIP doc): every candidate's `evidence_redacted` says "possible …";
  the report carries `disclaimer: "candidates are not determinations; each requires human review"`. The
  system never asserts validity / entitlement / liability.

## Live validation — `graph mail relationships --project tropical --lookback-days 30 --json`

Exit 0. `messages_considered: 40`, `candidates_generated: 47`,
`candidates_by_type: {project: 40, procore_rfi: 4, procore_daily_log: 2, procore_contract: 1}`,
`review_required_count: 5`. Procore availability context:

```
rfis 72 · rfi-responses 123 · submittals 100 · meetings 96 · meeting-topics 108 ·
change-events 100 · observations 100 · inspections 74 · rfqs 7 · financial_contracts 74
drive_items_available 0 · calendar_events_available 0
```

Project-scoped persisted candidate breakdown (after run; redacted evidence — no subjects/addresses):

```
project                n=40  conf>=0.7  review_any=1
sharepoint_drive_item  n=22  conf>=0.5  review_any=1   (Prompt 08 source-links)
procore_rfi            n= 4  conf>=0.85
procore_daily_log      n= 2  conf>=0.85
procore_contract       n= 1  conf>=0.6  review_any=1   (financial -> review)

sample evidence:
  procore_rfi        :: possible rfi relationship (procore notification)
  procore_daily_log  :: possible daily log relationship (procore notification)
```

**Idempotent:** re-running kept the project-scoped candidate count stable at 69 (deterministic
`candidate_id` upserts; processing receipts accumulate as audit logs). No token/address/subject leak.

## Guardrails

- **No Graph / no mailbox** — the command reads local SQLite only; the only writes are
  `email_relationship_candidates` + an audit receipt.
- **Redaction** — candidates carry type/target/signal/confidence/review + a "possible …" evidence
  string; no subjects or addresses. Financial/legal-sensitive topics route to review.

## Verification

- `tests/test_relationship_builder.py` (project/procore/calendar candidates, financial only-when-available
  + routes review, dry-run no-persist, idempotent, lookback exclusion) + `tests/test_graph_mail_cli.py`
  relationships case → pass. `test_mutation_lockout.py` / `test_email_body_security.py` → green (the new
  module has no Graph/mutation/plaintext patterns).
- `ruff check .` clean; `mypy src` no issues (125 files); `compileall` OK.
- Full safe subset green **except 4 pre-existing weekend-driven `test_automation.py` failures** (today,
  2026-05-30, is a Saturday; orchestrator skips weekends) — unrelated.

## Stop conditions — none triggered

No mailbox mutation, no `Mail.ReadWrite`/`Mail.Send`, no destructive migration, no full-body persistence,
no attachment-content download. `relationships` makes no Graph call.
