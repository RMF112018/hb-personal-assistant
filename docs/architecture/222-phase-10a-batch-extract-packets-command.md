# 222. Phase 10A — Batch extract-packets command

Date: 2026-06-08

Package: HB Construction Intelligence — Phase 10 / 10A Local Action Intelligence (repo-truth update)

## Context

Manual loop validation proved the single-packet `extract-packet` path is viable (a 50-thread manual
dry-run produced 51 / accepted 50 / would_persist 45, 100% review-gated). The next step is to
operationalize it: a first-class batch command with a dry-run-first / capped-apply workflow, aggregate
summary reporting, duplicate skipping, and the same no-raw / no-writeback guardrails. This adds
`second-brain extract-packets` and a reusable orchestrator. No schema/migration/contract
change.

## Decision

### Reusable orchestrator — `local_ai/batch_extraction.py::run_batch_extraction`
Selects bounded email-thread units and runs the SAME extraction path per thread
(`build_email_thread_action_packet` → `extract_actions_for_packet`). Never broad raw packets, never
combining unrelated records.

- **Selection** (`email_thread_raw_context`): prefer rows with non-empty `messages_json`; order
  `length(messages_json) DESC` (matches the validated manual loop), tiebreak `thread_ref`; apply
  `offset`/`limit`; optional `thread_refs` allow-list; optional `only_unprocessed` (skip threads
  already present in `candidate_source_refs`). Done in Python over `list_email_thread_raw_context` so
  the shared store query is unchanged.
- **Dry-run default**: zero writes; reports `would_persist`. **Apply is explicit and REQUIRES
  `max_persist`**, which caps ACTUAL persisted candidates across the batch (not packets). Once the cap
  is reached, remaining threads are processed in dry-run (counted, never written).
- **Capping + dedup pushed into the extraction layer**: `extract_action_candidates_from_raw` /
  `extract_actions_for_packet` gained `max_persist` and `existing_stable_keys` params, and now report
  `skipped_existing` + `persisted_stable_keys`. The orchestrator seeds `existing_stable_keys` from
  persisted task+commitment `stable_key`s and adds newly-persisted keys as it goes, so duplicates are
  skipped (counted, never re-written) both against the DB and within the batch.
- **Counts** separated: produced, accepted, rejected, would_persist, persisted, skipped_existing,
  unsupported_candidate_type (accepted − would_persist), no_candidates, blocked, failed. Candidate
  types bucketed task / commitment / question / risk / other. Per-thread failures do not abort the run.
- **Unsupported source fails closed**: only `--source email` is implemented; `calendar`/`related`
  raise `UnsupportedBatchSourceError` (CLI exit 2).
- **Review artifact**: a redacted JSON artifact is written (default `/tmp/phase10a_extract_packets_
  <timestamp>.json`) unless `--no-artifact`; the path is returned in the response. Best-effort (an
  unwritable dir never fails the run).

### CLI — `extract-packets`
Defaults to dry-run; `--apply` requires `--max-persist` (fail-closed exit 2 otherwise). Mirrors
`extract-packet` options (`--db`, `--model`, `--profile`, `--provider`, `--timeout-seconds`) plus
`--source`, `--limit`, `--offset`, `--only-unprocessed`, `--thread-ref-file`, `--summary`,
`--artifact-dir`, `--no-artifact`. `--summary` includes the aggregate breakdowns even with `--json`.
Existing `extract-packet` behavior is unchanged.

## Safety / output (redaction)

Per-thread results carry the safe `thread_ref`, packet id/type, counters, diagnostics (counts only),
accepted candidates (structured, redacted), and rejections reduced to `{reason, unresolved_refs}`. Raw
email bodies, raw prompts, raw model responses, signed/download URLs, and tokens are never emitted.
Persisted rows reuse the V41 upsert adapters, which pin all raw-content + writeback guard columns to 0.

## Verified (mock, dry-run + apply)

Dry-run over 3 threads (task/commitment/question) → accepted 3, would_persist 2,
unsupported_candidate_type 1, zero rows. Apply `--max-persist 2` over 5 task threads → persisted
exactly 2 (would_persist 5), all rows `review` + `default_extract` + non-null template version.
Re-apply same thread → `skipped_existing` 1, no duplicate rows. Question accepted but not persisted.
Unresolved `src_9` reported in `source_alias_failures`, never persisted, batch continues. Guard columns
sum 0 on `task_candidates` + `candidate_source_refs`. Unsupported `calendar`/`related` fail closed.

## Guardrails / non-goals

Dry-run default; apply explicit + capped. No email send, calendar mutation, Procore/Graph writeback,
MCP raw exposure, or external writeback. Source aliases, object-root output, pre-validation review
normalization, and traceability defaults preserved. No schema/migration/contract change, no
README/ledger bump.
