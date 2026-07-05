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
| **07** | Duplicate prevention (second-watcher refusal, dup-card, SHA overwrite, cross-root non-collision) | **PASS (all four)** — `07-live-duplicate-prevention-proof.md` |

**All four N8 live NAS proofs (04–07) are complete and PASS.**

## Open findings (flagged, not fixed)
- **Live NAS configs still point `application_support_root` at `/volume1`** (stale post-migration drift) —
  surfaced by Proof 06; worked around with a container-only `/volume2` config, no live config modified. See
  `06a-app-support-config-drift.md`.
- **Stale `/volume1/personal-assistant/bin/hb-mcp-runner` sudoers rule** (dead path). See `05a`.

## Rollback points (available; `restore` held for authorization)
- Proof 05: `.../db/backups/proof05-20260704T211230Z` (main-DB SHA `2359ec12…`, size-verified).
- Proof 06: `.../db/backups/proof06-20260705T063848Z` (main-DB SHA `4ef51db2…`, size-verified).
- Proof 07: `.../db/backups/proof07-20260705T070028Z` (main-DB SHA `a6dbdd3f…`, size-verified). Proof 07's
  coexistence additions (the `nas_test2` source + card + `test-source-root-2`) remain live as the
  demonstration; its `restore` reverses only those, leaving proofs 04–06 intact.
- Rollback is via each runner's `restore` subcommand. See `05a-temporary-privileged-runner-status.md`.

## Next steps (N8 live-proof closeout)
- Optionally `restore` the Proof 07 additions (needs authorization).
- **Revoke the three temporary runners** (proof05/06/07: remove each sudoers drop-in, runner, driver, and the
  proof06/07 configs) unless explicitly retained.
- Remediate the two `/volume1` drift items above (separate change).
