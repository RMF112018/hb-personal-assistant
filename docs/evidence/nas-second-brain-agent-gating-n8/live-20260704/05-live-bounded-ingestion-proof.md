# 05 — Live Bounded Ingestion (first live DB write) — CLOSEOUT

**Verdict: PASS** — executed live on 2026-07-04 with per-step approval. First live write to the NAS DB.

Supersedes the pre-live runbook at `../20260704T154735Z/05-bounded-ingestion-proof.md` (HOLD plan).

## Preflight blocker and resolution
The live DB is `personal-assistant-svc:users` mode `0600` and `bfetting` cannot read or write it;
`docker` needs root; there is no host Python with `hb_assistant`. A direct bounded ingestion as
`bfetting` was therefore impossible. **Resolution:** a narrow, revocable, root-owned proof runner was
installed as a temporary privileged path (see `05a-temporary-privileged-runner-status.md`), exposing
only fixed `status|backup|ingest|restore` subcommands — no docker/su/shell/sqlite3/python grant, no
arbitrary paths or args. All Proof 05 steps ran through it; the DB stayed `0600` svc-owned throughout.

## Runner / sudoers (temporary privileged path)
- Runner installed root-owned; scoped sudoers drop-in grants `bfetting` only the four fixed subcommands.
- Container ran the pinned source image `--network none --rm --user 1028:100` (service identity), so no
  server, watcher, or scheduler persisted after each one-shot returned.

## Mandatory backup (taken before any write)
- **Backup dir:** `/volume2/personal-assistant/app-support/db/backups/proof05-20260704T211230Z`
- **Main-DB SHA-256 prefix:** `2359ec12…`
- **Size verification:** backup main file `4151631872` bytes == live DB `4151631872` bytes (exact match); WAL captured as 0 bytes (DB checkpointed).
- This backup is the sole authorized rollback point (`restore` not run — held pending explicit authorization).

## Migration + bounded ingest (one-shot)
- **Schema:** `v98 → v99` (root-scoped source identity applied at rest; `latest_expected` = 99).
- **V99 remap:** all **9,128** existing file `source_id`s re-keyed to fold `source_root_key` into identity,
  rewritten across **8 FK'd tables** via deferred foreign keys — **zero row loss**.
- **Bounded scan** over `source_root_key=nas_test`: **scanned 3 / indexed 3 / skipped 0 / deleted 0 / errors 0 / truncated false**.

## Row-count deltas (before → after)
| table | before | after | Δ |
|---|---|---|---|
| source_intelligence_sources | 9128 | 9131 | **+3** |
| source_intelligence_metadata | 9128 | 9131 | **+3** |
| source_intelligence_text | 5738 | 5741 | **+3** |
| source_intelligence_chunks | 2926 | 2929 | **+3** |
| source_intelligence_relationships | 285 | 285 | unchanged |
| source_intelligence_generated_notes | 195 | 195 | unchanged |
| source_intelligence_summaries | 7 | 7 | unchanged |
| source_intelligence_events | 3496 | 3496 | unchanged |

Growth is exactly the 3 bounded test files (sources / metadata / text / chunks each +3); relationships,
generated_notes, summaries, and events are **unchanged** — no cards, no relationships, no summaries.

## Exact files indexed
The three `nas_test` files were indexed: `note-a.txt`, `note-b.txt`, `shared/x.txt`. Each received a
**distinct root-scoped `source_id`** (identity now folds `source_root_key`); the resolved ids are recorded
in uncommitted `local-sensitive/` and are not reproduced in committed evidence.

## Confirmations
- **No source cards were generated and no vault write occurred** (card/summary/watcher generation all disabled in the ingest config; generated_notes/summaries counts unchanged).
- **No Proof 06 or Proof 07 ran.**
- **DB remains `personal-assistant-svc:users` mode `0600`** (container wrote as uid 1028 = svc; ownership preserved post-ingest).
- **Backend / scheduler / watcher / listeners were absent** before, during (`--network none --rm` one-shot), and after — verified by the runner's read-only status (no `:8000` listener, no HB process) pre- and post-ingest.
- **No secrets, tokens, or raw document bodies were printed** — synthetic test files only; identifiers reproduced here are structural paths and content hashes of synthetic data.
