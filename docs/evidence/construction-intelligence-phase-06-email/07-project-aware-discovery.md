# 07 — Project-Aware Email Discovery (matching)

Phase 06 Prompt 07 · read-only / metadata-only · no mailbox mutation · no new scope

Matches a bounded window of messages to **pilot projects** using HB project number, project names,
Procore identifiers, SharePoint/OneDrive links, participant domains, and thread continuation — with the
confidence bands from the schema doc. Subject/bodyPreview are matched **in-memory** (never persisted
raw); only the match result persists. Dry-run previews; `--no-dry-run` persists `email_project_matches`
+ the message project verdict. Mailbox is read-only; the only writes are local SQLite.

Evidence artifacts: [`email-discovery-dry-run.json`](./email-discovery-dry-run.json) (live preview),
[`email-project-match-test-results.json`](./email-project-match-test-results.json) (matcher unit results).

## What landed

- **`construction/email/project_matcher.py`** — pure `ProjectMatcher`, `ProjectDescriptor`,
  `MatchSignal`, `PROJECT_MATCH_SIGNALS` (the confidence bands), HB number regex `\b\d{2}-\d{3}-\d{2}\b`,
  and `load_pilot_project_descriptors()` building descriptors from the seed registries.
- **`construction/email/project_discovery.py`** — `ProjectEmailDiscovery(mail_client, store)`: reads the
  bounded window live, matches each message × descriptor, runs a thread-continuation pass, aggregates a
  metadata-only `DiscoveryReport`, and (non-dry-run) persists matches + the message verdict.
- **`construction/email/message_indexer.py`** — promoted `_normalize` to a shared module-level
  `normalize_message` (+ `compute_thread_key`) reused by the discovery persist path (no behavior change).
- **`cli/graph.py`** — `graph mail discover --project … --lookback-days … --max-messages …
  [--dry-run/--no-dry-run] --json` (default dry-run preview).

## Reconciliation (package ↔ repo truth)

- **Project descriptors come from the seed YAMLs.** The live `construction_project_identity` table is
  unseeded, so the authoritative pilot set is `load_procore_projects()` (status `pilot`: tropical,
  pga-modern-garage, alton-hilltop-pbg, the-wellington) merged with `load_source_registry()` for the HB
  project number (`23-435-01`), normalized name, and display name.
- **`discover` reads live** (runbook: discover-dry-run precedes index; matching needs the subject, which
  the indexer stores only hashed). Only the match result (signal, confidence, redacted evidence, project
  number/name) persists.
- **Signal bands** taken from the package `project_match_signals.json` + schema doc, encoded as the
  `PROJECT_MATCH_SIGNALS` module constant. `<0.60 → review_required`.
- **Participant-domain signal is wired but inert** (no per-project domain registry yet — `known_domains`
  is empty, so the 0.60 signal only fires once domains are configured). SharePoint/OneDrive-link
  detection is best-effort on `bodyPreview` + `webLink` (no full body).
- **Idempotency:** matches upsert on `UNIQUE(message_id, project_key, match_signal)`.

## Live validation — `graph mail discover --project tropical --lookback-days 30 --max-messages 100 --dry-run --json`

Exit 0. Against Bobby's mailbox (archive 2 / inbox 100 / sent 100 = **202 scanned**), **40 messages
matched project tropical (23-435-01)**, best confidence 1.0, 7 flagged for review:

| signal | count |
|---|---|
| `hb_project_number_in_subject` (1.00) | 2 |
| `procore_notification_identifier` (0.85) | 6 |
| `project_name_in_subject` (0.80) | 30 |
| `project_name_in_body_preview` (0.70, review) | 7 |
| `thread_continuation` (0.75) | 3 |

The report carries **counts + signal histograms only** — no subjects, addresses, tokens, or raw folder
ids (leak scan: clean). Guardrails attested: `mailbox_read_only`, `full_body_persisted: false`,
`attachment_content_retrieved: false`, `subject_matched_in_memory_only: true`.
(Note: `project_name_in_subject` on the common word "Tropical" is intentionally a lower-confidence,
preview-only signal; high-confidence number/Procore signals anchor the match, and review routing is a
later prompt.)

## Matcher unit results — `email-project-match-test-results.json`

8/8 fixture cases pass: number-in-subject→1.0, number-in-preview→0.95(review), name-in-subject→0.8,
name-in-preview→0.7(review), procore-notification→0.85, known-domain→0.6(review), no-match→∅,
other-project-number→∅ (matched against tropical only).

## Verification

- `tests/test_project_matcher.py` (10) + `tests/test_project_discovery.py` (dry-run no-persist, commit
  persists matches + message verdict, thread continuation, idempotent re-commit, no-match) +
  `tests/test_graph_mail_cli.py` discover case → pass. Indexer/lockout/guard tests → green.
- `ruff check .` clean; `mypy src` no issues (123 files); `compileall` OK.
- Full safe subset green **except 4 pre-existing weekend-driven `test_automation.py` failures** (today,
  2026-05-30, is a Saturday; orchestrator skips weekends) — unrelated.

## Stop conditions — none triggered

No mailbox mutation path, no `Mail.ReadWrite`/`Mail.Send` request, no destructive migration, no
full-body default persistence, no attachment-content download. Subject matched in-memory only; the only
writes are local SQLite match/message rows.
