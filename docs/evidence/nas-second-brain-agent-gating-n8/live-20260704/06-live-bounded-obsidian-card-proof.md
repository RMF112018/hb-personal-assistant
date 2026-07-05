# 06 — Live Bounded Obsidian Source Card — CLOSEOUT

**Verdict: PASS** — executed live on 2026-07-05 with per-step approval. One deterministic source card
written into the real NAS vault; DB and vault consistent.

Supersedes the pre-live runbook at `../20260704T154735Z/06-bounded-obsidian-write-proof.md` (HOLD plan).

## Scope executed
Generated **exactly one** Obsidian source card for the fixed `nas_test` source `note-a.txt` through the
real `hb_assistant` path (`source_notes.generate_source_card`, `overwrite=False`), via a **separate**
root-owned `hb-pa-proof06-runner` (`card-preflight` / `backup` / `card` / `restore`). The proof-05 runner
was left byte-for-byte untouched as the DB rollback path.

## Wrong-vault stop-condition (caught before any write)
The initial runner constant targeted `/volume2/personal-assistant/vault` (the parent). `card-preflight`
plus operator review established the **real seeded Obsidian vault root is
`/volume2/personal-assistant/vault/obsidian`** (it holds `.obsidian/`, the operator's Home/Work notes, and
a pre-seeded `Source Notes/{Home,Shared,Work}`). The constant was corrected before any write — the
wrong-vault stop-condition never resulted in a mis-placed file.

## Partial-write stop-condition + recovery (honest record)
The first `card` attempt **partial-failed**: the atomic vault write (`create_note` line 321) completed, but
the subsequent mutation-audit (`record_mutation` line 323) raised `DbStorageGuardError` because
`PathPolicy().get_app_support()` had no approved `/volume2` root — **both live NAS configs
(`config/hb-pa-config.yml`, `config/hb-pa-config.mcp.yml`) still set `application_support_root: /volume1/…`**
(stale post-migration drift; see `06a`). This left the card file present but no `generated_notes` row.

Recovery, each step operator-authorized:
1. `restore` — DB rolled back from backup `proof06-20260704T214326Z` (size-verified vs manifest) and the
   single partial card file deleted. Clean pre-card state confirmed (`card_already_exists: false`).
2. Fix — a minimal **container-only** `HB_PA_CONFIG` (`application_support_root:
   /volume2/personal-assistant/app-support`) plus mounting the real app-support `:rw` so the mutation audit
   lands under `/volume2`. No live NAS config was modified.
3. Re-install, fresh backup `proof06-20260705T063848Z`, clean `card` retry.

## Result (retry — clean)
- Card: `Source Notes/Shared/note-a.txt__482f41ec8a37.md`, sha256 `a6e2356f…`, `status: generated`, `overwritten: false`.
- Card path is under the **correct** vault `/volume2/personal-assistant/vault/obsidian`.

## Row-count deltas (before → after)
| table | before | after | Δ |
|---|---|---|---|
| source_intelligence_generated_notes | 195 | 196 | **+1** |
| source_intelligence_relationships | 285 | 285 | unchanged |
| source_intelligence_summaries | 7 | 7 | unchanged |
| source_intelligence_sources | 9131 | 9131 | unchanged |
| source_intelligence_text | 5741 | 5741 | unchanged |
| source_intelligence_chunks | 2929 | 2929 | unchanged |

Exactly **one** `generated_notes` row for the source (`generation_status: generated`) — the
`UNIQUE(source_id, note_rel_path)` dedup model holds. No stray relationships, summaries, or source rows.

## Confirmations
- **Correct vault** — write landed in `/volume2/personal-assistant/vault/obsidian` (NAS-local; asserted 3 ways: runner constant under `/volume2`, driver `NAS_VAULT_PREFIX` guard rejecting Mac paths, host `stat`). The Mac vault was never a target.
- **Atomic + SHA-guarded** — real `create_note`: atomic temp+replace, SHA optimistic-concurrency, vault-root containment.
- **Card identity carries the fixed `source_id`** — filename suffix `__482f41ec8a37` (`source_id12_in_path: true`).
- **Exactly one card** — no second card; `overwritten: false`; a re-run under `overwrite=False` would refuse (`note_already_exists`).
- **Bounded DB write** — only `generated_notes` +1 (the card's own record); everything else unchanged.
- **Single-writer** — no `:8000` listener / no backend/scheduler/watcher before, during (`--network none --rm` one-shot), or after.
- **DB remains `personal-assistant-svc:users` mode `0600`**; container wrote as uid 1028 = svc.
- **No secrets/tokens/raw bodies** — synthetic file; identifiers shown are a truncated content-hash suffix and a content sha of synthetic data.
- **Proof-05 rollback path untouched.**

## Rollback point
`proof06-20260705T063848Z` (main-DB SHA `4ef51db2…`, size-verified). Full rollback via the proof06
runner's `restore` (DB restore + delete the single `*__482f41ec8a37.md` card) — not run; held for authorization.
