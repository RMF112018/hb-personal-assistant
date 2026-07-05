# 00 — N8 Live Proofs — Index (2026-07-04 / updated 2026-07-05)

Docs-only checkpoint recording the completed live NAS proofs for N8. No code and no live NAS config was
changed to produce this evidence (all values sourced from the live proof runs). Proof runbooks live at
`../20260704T154735Z/`.

## Status

| Proof | Scope | Status |
|---|---|---|
| **04** | Bounded NAS test source root (3 synthetic files, isolated `nas_test` key) | **PASS** — `04-live-nas-source-root-proof.md` |
| **05** | First live DB write: mandatory backup → V99 migrate (9,128 remapped) → bounded 3-file ingest | **PASS** — `05-live-bounded-ingestion-proof.md` |
| **06** | One bounded Obsidian source card into the NAS vault (recovered from a partial-write stop condition) | **PASS** — `06-live-bounded-obsidian-card-proof.md` |
| **07** | Duplicate prevention (second-watcher refusal, dup-card, SHA overwrite, cross-root non-collision) | **HOLD** — not started; requires per-step approval |

## Open finding
- **Live NAS configs still point `application_support_root` at `/volume1`** (stale post-migration drift) —
  surfaced by Proof 06; worked around with a container-only `/volume2` config, no live config modified. See
  `06a-app-support-config-drift.md`.

## Rollback points (available; `restore` not run — held for authorization)
- Proof 05: `.../db/backups/proof05-20260704T211230Z` (main-DB SHA `2359ec12…`, size-verified).
- Proof 06: `.../db/backups/proof06-20260705T063848Z` (main-DB SHA `4ef51db2…`, size-verified).
- Rollback is via each runner's `restore` subcommand. See `05a-temporary-privileged-runner-status.md`.

## Next required step
- **Prepare the Proof 07 package for review — do NOT execute it.** Proof 07 (duplicate prevention) remains
  on HOLD until Bobby approves the specific step. The temporary proof-05 and proof-06 runners stay installed
  (rollback/status only) and must be revoked at N8 live-proof closeout unless explicitly retained.
