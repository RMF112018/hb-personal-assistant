# 00 — N8A Closeout

**Phase:** N8A — Second-Brain Agent / Watchers / Scheduler Gating (live-proof closeout)
**Stamp:** `20260705T075807Z` · **Branch:** `ops/nas-second-brain-agent-gating-n8a-20260705T075807Z` · **Base:** `origin/main` @ `704f59c8`
**Verdict: PASS (audit + reconciliation; both approved remediations already resolved) / 2 pending operator read-only confirmations.**

N8A is the live-proof closeout N8 left open. Scope (operator-set): *live cleanup, no re-proof* · Mac scheduler *report-only* · `/volume1` drift *remediate live*. Outcome: the two live remediations turned out to be **already-resolved no-ops**, so N8A made **zero live NAS mutation** and needed **no privileged runner** — it verified state read-only and reconciled the committed evidence to live truth.

## Done (PASS)

1. **Clean base + gating intact.** Fresh worktree off `origin/main` @ `704f59c8`; `LATEST_SCHEMA_VERSION=99`; the three temp-DB gating suites re-run **23 passed** (default-off 6 · watcher-ownership 11 · V99 identity 6) — default-off, single-writer lease/lock, and root-scoped source identity are intact on the clean base. (`03`, `08`)
2. **Inventory re-confirmed** — every background-execution path is gated and default-off under `HB_NAS_RUNTIME=1`; no code drift vs N8. (`02`)
3. **Live-state reconciliation (read-only, non-sudo).** Committed N8 `05a`/`06a` are **stale** — reconciled to live truth: (`live/01`)
   - **Temp proof runners `hb-pa-proof05/06/07` → absent** (already revoked).
   - **`/volume1` config drift → resolved**: both live configs read `/volume2/personal-assistant/app-support`; `_vault_disabled` sentinel intact; no `/volume1` token. (`live/02`)
   - **At rest, confirmed present:** the one Proof-06 card `Source Notes/Shared/note-a.txt__482f41ec8a37.md`; the proof05/06/07 rollback backups.
4. **No new privilege, no mutation.** No sudoers drop-in, no NOPASSWD grant, no config/DB/vault write, no card. "Sudo remains password-required" held end-to-end. (`live/03`, `09`)
5. **Mac scheduler reported (not touched).** `com.hb.personal-assistant.scheduler.production` loaded-but-idle, targets the Mac DB → **N8B/N9 cutover action item**. (`live/04`)
6. **Bounded proofs 04–07 referenced, not re-run** — N8 PASS on the base; at-rest lineage confirmed. (`04`–`07`)
7. **Redaction/secrets** — 16 sensitive-scan findings all pre-existing, **zero N8A-added**; no hostname/tailnet-IP/secret literal committed; 0 attribution trailers. (`08`)

## Operator root confirmations (sudo password-required)

- **Dead `/volume1` sudoers rule** (`05a`): **DONE** — operator-run `sudo grep` → `rc=1` (absent; already removed at N8 closeout). Password entered interactively; no NOPASSWD grant. (`live/03` §B)
- **DB at-rest counts** (optional, **not run**): a read-only `sudo` pass over the `0600` svc-owned DB would reconfirm V99 + no duplicate rows. Not a blocker — N8 proved these live and N8A wrote nothing that could change them. (`live/00` item 2)

## Acceptance-criteria status

| Criterion | Status |
|---|---|
| Mac & NAS can't both run competing jobs unnoticed | **Met** (NAS default-off + host-stamped lease/lock; Mac scheduler idle, reported as cutover item) |
| Workers/schedulers default-off unless deliberately enabled | **Met** (`03`, 23 passed) |
| Enabled job has ownership/lease/receipt/stop command | **Met** (verified via ownership suite; primitives intact) |
| NAS vault/source roots used intentionally | **Met** (nas_test lineage + card at rest under `/volume2`) |
| Bounded ingestion/card proof succeeds | **Met by reference** (N8 live 05/06 PASS; card confirmed at rest) |
| Duplicate prevention proven | **Met by reference** (N8 live 07 PASS; single card at rest; N8A wrote nothing) |
| Destructive writes remain gated | **Met** (write policy default-off; no N8A write) |
| Evidence contains no secrets | **Met** (`08`) |
| N8B readiness explicitly assessed | **Met** (`10` — NOT READY, foundations strengthened) |

## Residual risk / carried

- **Vault dir mode `777`** (pre-existing) — fold into the secret-folder-hardening track (N8B item #4), not N8A.
- **Mac↔NAS single-writer cutover** — unload the Mac production scheduler before any NAS scheduler (N8B/N9).
- **Committed N8 `05a`/`06a` are stale** — this N8A evidence supersedes them by reference (runners revoked; drift resolved).

## Next step

Bobby reviews the N8A evidence diff and authorizes (a) a local docs-only commit and (b) optionally the two pending root read-only confirmations. **No push until then.**
