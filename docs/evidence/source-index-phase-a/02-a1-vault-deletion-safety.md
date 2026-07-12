# A1 — Vault Deletion-Safety Gate

**Parent commit:** `963c1759` (A0). **Checkpoint commit:** see `git log` (recorded in the checkpoint report).

## Prior defect (repo-truth, origin/main)
`source_indexer.scan_vault_notes:917-961` reconciled deletions **unconditionally** after the walk loop:
after a cap-hit `break` (`truncated=True`) or swallowed per-file exceptions, it still ran
`for gone in active_rel_paths(_VAULT_ROOT_KEY) - seen: mark_deleted(...)`. It passed **no `error_sink`** to
the fail-open `walk_source_tree`, so an unreadable subtree looked empty and its notes were mass-deleted, and
it had **no empty-root blast-radius guard**. Deletion removed the note's FTS row and staled its generated
card — corrupting authoritative search state while the source note still existed on disk.

## Implementation (minimal certified-completeness gate; lightweight path retained)
No schema / generation / lease / cursor was added for the vault (ADR: the defect is *unsafe deletion
authority*, not lack of durable orchestration — escalation criteria to the V122 model are recorded below).

- **Completeness collector** — `scan_vault_notes` now passes `error_sink=walk_errors` into `walk_source_tree`
  (mirrors `source_bootstrap.py:482-485`), wraps the walk in try/except to detect interruption, and records:
  `truncated`, `walk_error_count`, `per_file_error_count`, `interrupted`, `root_available`,
  `eligible_files_seen`, `active_rows_before_scan` on `ScanReport`.
- **Reason-code contract** — `ScanReport.completeness` is one deterministic value with precedence
  `interrupted > truncated > walk_errors > file_errors`, plus `root_unavailable` (early return) and
  `empty_root_guard`; the certified value is `complete`. `deletion_reconciliation_allowed` is True **only**
  when `completeness == "complete"` (and the empty-guard did not fire).
- **Fail-closed** — any non-`complete` completeness returns immediately: pre-existing active rows are
  preserved, their FTS rows and generated cards are untouched, and successful inserts/updates observed during
  the (partial) scan are **retained**. No absence-based deletion occurs.
- **Empty-root blast-radius guard** — a certified-complete scan that observed `eligible_files_seen == 0`
  while `active_rows_before_scan > 0` is blocked (`completeness = "empty_root_guard"`); an established vault
  that scans empty stays protected **indefinitely** without an explicit operator override.
- **Transaction boundary** — confirmed-gone rows are reconciled via the new
  `SourceIndexRepository.mark_deleted_batch`, which runs the **entire batch** (source-row deactivation + FTS
  removal + generated-card staling) inside **one** `transaction(c)`, so a crash cannot leave a certified
  reconciliation half-applied. For the 5,000-note vault cap this is a single transaction (no durable
  reconciliation-progress state — chunking was intentionally not introduced). Index state only; **no source
  file is ever written or deleted** (no source-file mutation API was added).

## One-shot operator recovery
`hb-assistant source-watch vault-reconcile --allow-confirmed-empty --confirm` (local, operator-only, **not**
exposed to any remote MCP client). Safety controls: requires BOTH flags (else exit 2); acquires a process-local
advisory `flock` lease (no durable state); performs its **own** fresh certified-complete scan
(`allow_confirmed_empty_recovery=True` lifts only the empty-root guard — it never trusts a caller-supplied
scan result and still requires certification to reconcile); writes a redacted JSON audit receipt under
`<db-dir>/vault_reconcile_receipts/`. If its fresh scan is not certified-complete, it deletes nothing.

## Escalation criteria to the V122 vault-generation model (deferred, documented)
Escalate only if repo-truth testing shows: vault traversal cannot finish within the operational scan window;
resumable cursoring is required; repeated scans impose unacceptable FS/DB load; crash-safe continuation is
required; multiple scanner instances need durable lease ownership; confirmed absence must span multiple bounded
passes; or the in-memory `seen` set becomes impractical. None apply at the current vault scale.

## Prove-red / prove-green (node IDs)
`tests/test_source_index_vault_deletion_safety.py` — full list in the file. Prove-red run (`a1-prove-red.txt`,
against A0 parent `963c1759`): **12 of 16** safety tests failed (attribute contract absent, or the actual
unsafe deletion observed — e.g. `deleted: True`, generated card `'stale'`); the 4 legitimate-behavior guards
passed. Prove-green (`a1-validation.txt`): all **18** pass (16 function + 2 CLI). The pre-fix TypeError on the
`allow_confirmed_empty_recovery` kwarg and the observed FTS/card corruption are the concrete red evidence.

## Validation
`a1-validation.txt` — the 18 source-index suites + the new file. Static: `ruff check` clean and `mypy`
(`Success: no issues found`) on the 3 changed src modules; `source_watch.py` diff is +additions only (no
reformat churn of pre-existing code). The 3 known baseline failures (stale `== 123` V124 assertions) persist
unchanged and are unrelated to A1.

## Files changed
- `src/hb_assistant/obsidian_mcp/source_indexer.py` — `ScanReport` completeness fields + `as_dict`; gated
  `scan_vault_notes` with `allow_confirmed_empty_recovery`.
- `src/hb_assistant/obsidian_mcp/source_index_repository.py` — new `mark_deleted_batch` (single-transaction batch).
- `src/hb_assistant/cli/source_watch.py` — new `vault-reconcile` operator command (+`Path` import).
- `tests/test_source_index_vault_deletion_safety.py` — new prove-red/green suite (18 tests).
