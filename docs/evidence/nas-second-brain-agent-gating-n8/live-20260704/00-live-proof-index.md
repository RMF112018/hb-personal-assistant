# 00 — N8 Live Proofs — Index (2026-07-04)

Docs-only checkpoint recording the completed live NAS proofs for N8. No code, no config, no NAS action
was performed to produce this evidence. Proof runbooks live at `../20260704T154735Z/`.

## Status

| Proof | Scope | Status |
|---|---|---|
| **04** | Bounded NAS test source root (3 synthetic files, isolated `nas_test` key) | **PASS** — `04-live-nas-source-root-proof.md` |
| **05** | First live DB write: mandatory backup → V99 migrate (9,128 remapped) → bounded 3-file ingest | **PASS** — `05-live-bounded-ingestion-proof.md` |
| **06** | One bounded Obsidian source card into the NAS vault | **HOLD** — not started; requires per-step approval |
| **07** | Duplicate prevention (second-watcher refusal, dup-card, SHA overwrite, cross-root non-collision) | **HOLD** — not started; requires per-step approval |

## Rollback point
- **Available.** Proof 05 took a mandatory byte backup at
  `/volume2/personal-assistant/app-support/db/backups/proof05-20260704T211230Z` (main-DB SHA `2359ec12…`,
  size-verified). Rollback is via the runner's `restore` subcommand — **not run**, held pending explicit
  authorization after a stop condition. See `05a-temporary-privileged-runner-status.md`.

## Next required step
- **Prepare the Proof 06 package for review — do NOT execute it.** Proof 06 (one bounded card into the NAS
  vault) and Proof 07 remain on HOLD until Bobby approves the specific step. The temporary Proof 05 runner
  stays installed (rollback/status only) and must be revoked at N8 live-proof closeout unless explicitly retained.
