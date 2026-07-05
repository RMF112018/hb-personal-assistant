# 07 — Live Duplicate Prevention (4 assertions) — CLOSEOUT

**Verdict: PASS (all four)** — executed live on 2026-07-05 with per-step approval.

Supersedes the pre-live runbook at `../20260704T154735Z/07-duplicate-prevention-proof.md` (HOLD plan).

Run through a **separate** root-owned `hb-pa-proof07-runner` (`preflight` / `backup` / `assert-refusals` /
`assert-xroot` / `restore`); the proof-05 and proof-06 runners were left untouched (rollback paths intact).
Fresh backup `proof07-20260705T070028Z` (main-DB SHA `a6dbdd3f…`, size-verified) taken before any write.

## Assertion 1 — Second-watcher single-writer refusal — PASS
Using the real host-stamped watcher lease (two singleton rows in `source_intelligence_state`), owner **A**
acquired the lease; a **different** owner **B** was refused (`acquired=False`, A's rows untouched → fail
closed); B's release returned **False** (a non-owner cannot clear/steal the lease); A then released cleanly.
End state: no owner (`owner_after_A_release_none: true`). **Net-zero** — no lease residue. The lease API was
exercised directly, without ever starting the watchdog Observer/thread.

## Assertion 2 — Duplicate card refused — PASS
`generate_source_card(overwrite=False)` against the existing proof-06 card raised **`note_already_exists`**;
`source_intelligence_generated_notes` for the source stayed **1 → 1** (the `UNIQUE(source_id, note_rel_path)`
model + upsert prevents a second row). No second card written.

## Assertion 3 — SHA optimistic-concurrency — PASS
`patch_note` with a deliberately wrong `expected_sha256` raised **`sha256_mismatch`** (the check precedes the
atomic write), and the card file was **byte-for-byte unchanged** (sha `a6e2356f…` before **and** after).

## Assertion 4 — Cross-root non-collision (post-V99) — PASS
Two parts:
- **Formula (read-only):** `source_id_for("external_file", source_root_key=…, rel_path="note-a.txt")` →
  `nas_test` = `482f41ec…` (**matches the live id**), `nas_test2` = `c90eced77a54…` → **distinct**
  (`shared/x.txt` likewise distinct across roots).
- **Live coexistence:** a second bounded root `nas_test2` (one synthetic `note-a.txt`, the SAME rel_path as
  `nas_test`) was indexed (`scanned 1 / indexed 1 / errors 0`). Its `source_id` came back
  `c90eced77a543e86ed3ffd67f3c0b2a3` — distinct from `nas_test`'s `482f41ec…` for the **same rel_path**, and
  both rows **coexist** (pre-V99 the second would have silently overwritten the first). Its card landed at a
  **distinct** path: `…__c90eced77a54.md` vs the proof-06 `…__482f41ec8a37.md` (`card_paths_distinct: true`).

## Bounded writes + state
- Assertions 1–3 (`assert-refusals`): **DB rows net-zero**. The only writes were append-only mutation-audit
  entries (`app-support/analytics/obsidian_mcp/mutations.jsonl`) that legitimately record the refused
  attempts — an audit trail, not a data mutation.
- Assertion 4b (`assert-xroot`): the only row-adding step — `+1` source (`nas_test2` across
  `source_intelligence_*`) and `+1` `generated_notes` card, plus the one new vault card and the
  `test-source-root-2` dir. All reversible via the proof07 `restore` (DB restore + delete only
  `*__c90eced77a54.md` + remove `test-source-root-2`), which **leaves the proof-06 `nas_test` card intact**.

## Confirmations
- **Single-writer, dedup, SHA-guard, and cross-root identity all hold** on the live DB/vault.
- **DB remains `personal-assistant-svc:users` mode `0600`**; container ran as uid 1028 = svc.
- **Backend / scheduler / watcher absent** before, during (`--network none --rm` one-shots), and after.
- **No secrets/tokens/raw bodies** — synthetic files; identifiers are content-address hashes.
- **proof-05 / proof-06 rollback paths untouched.**

## Encountered + fixed during the run (honest record)
- `ObsidianMcpToolError` import path corrected to `obsidian_mcp.tools` (was `.errors`) — failed at import,
  no state change.
- `assert-refusals` initially mounted only `db` rw; `create_note`/`patch_note` audit **even refused
  attempts**, so the audit's `mkdir` under `app-support/analytics/obsidian_mcp` failed. Fixed by mounting the
  whole app-support `:rw`. The dup-card refusal itself had already fired correctly; no state was left behind.

## Rollback point
`proof07-20260705T070028Z` (main-DB SHA `a6dbdd3f…`, size-verified). `restore` not run at capture time —
the coexistence artifacts remain as the live demonstration; rollback is available on authorization.
