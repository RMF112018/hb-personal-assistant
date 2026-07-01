# Phase 10E — First-class `.eml` email archive notes (safe summary)

Deterministic, stdlib-only `.eml` handling: full-fidelity Markdown **archive notes**, concise
graph-safe **source cards**, and email-derived facts feeding the Phase 10C **note graph**.
No Qwen/Ollama, no DB migration, no graph link/tag apply (deferred to Phase 10F).

## What shipped

- `source_email_archive.py` — stdlib `.eml` parser (`parse_email_file`), full-fidelity renderer
  (`render_email_archive_note`), graph-safe card facts (`email_card_facts`), and the managed
  `hb-email` block (`email_marker` / `parse_email_marker` / `enrich_card_with_email`).
- First-class wiring: `.eml` body extraction (indexer), forced `document_type="email"` (analyzers),
  `email` in `HIGH_DOCUMENT_TYPES`, `eml → "Email message"` label, and note-graph email fields +
  strong/weak signals (`same_thread_topic`, `same_subject_normalized`, `same_participant`,
  `same_attachment_ref`, `same_project_alias` strong; `same_email_domain` weak-only).
- `scripts/obsidian_source_index_eml_archive.py` — bounded, idempotent `.eml` archive indexer
  (dry-run / `--apply` / `--update`), rollback bundle, distinct counters, `ollama_calls` attestation.

## Amendment #4 resolution (binding)

Archive notes live under a **separate top-level root `Email Archive/Work/<Domain>/`** (NOT under
`Source Notes/`). Self-index protection is provided by a dedicated guard `is_email_archive_path`
(keyed on the `Email Archive/` prefix), wired into `scan_vault_notes`, the `drain_queue` backstop
(new `EMAIL_ARCHIVE_SELF_INDEX_GUARD` skip code), and the watcher `_enqueue`. Proven live: **0**
`obsidian_note` FTS rows under `Email Archive/` after the apply — full email bodies/addresses never
reach the note index.

## Validation

| Check | Result |
|---|---|
| ruff check (12 touched files) | PASS |
| new tests (3 files) | PASS (24) |
| regression 10A–10D + self-index-guard/skip-codes/indexer/watch/backend (15 files) | PASS |

## Bounded production apply (`--apply --update --max-eml 10`)

Preconditions: backend down; 4 frozen flags False; queue (0,0); baseline generated 125 / not_generated 67; 15 indexed `.eml`.

| Counter | Value |
|---|---|
| `.eml` readable found / cloud-evicted | 54 / 90 |
| `.eml` selected / parsed | 10 / 10 |
| archive notes created (under `Email Archive/Work/`) | 10 |
| source cards updated in place (existing 10D `.eml`) | 9 |
| source cards generated (new) | 1 |
| `hb-email` graph-facts written | 10 |
| generated-note delta (125→126) | +1 |
| vault markdown delta (10 archives + 1 new card) | 11 |
| queue delta | 0 |
| `ollama_calls` | 0 |

Post-apply live proofs: generated 126/67; **0** `obsidian_note` rows under `Email Archive/`;
queue (0,0); all 10 archive notes start `note_type: email_archive` with full Body + Message
Metadata + Attachments + MIME/Source Fidelity sections and no absolute-path leak; all 10 cards
carry exactly one `hb-email` block + archive link and **0** carry a raw `## Body` (Amendment #3);
no duplicate card for any existing `.eml` (Amendment #2).

## Graph proof (dry-run, no apply)

`obsidian_source_note_apply_graph.py --dry-run --max-notes 100 …`: 100 candidate pairs,
`ollama_called: false`, `db_mutations: 0`. Email-derived basis counts: `same_participant` 36,
`same_project_alias` 36, `same_email_domain` 36 (weak-only), `same_thread_topic` 1,
`same_subject_normalized` 1 — alongside 10D `same_project_key/number/procore_id` 100.

## Bounded-scope note

The apply processed the deterministic first-10 readable `.eml` prefix (the approved `--max-eml 10`
bound). 6 of the original 15 10D `.eml` cards remain outside that prefix and were not upgraded this
run; a later run with a higher `--max-eml` can extend coverage. Not a defect — an honest bound.

## Guardrails honored

Deterministic only (no Ollama/network); no DB schema migration; module constant `EMAIL_ARCHIVE_FOLDER`
(no config-schema bump); rollback bundle (full DB backup + card backups + manifest) taken before apply;
all real email content (archive notes, addresses, message-ids, the `*-detail-local-sensitive.json`,
and the DB backup) isolated under `local-sensitive/` and never committed.
