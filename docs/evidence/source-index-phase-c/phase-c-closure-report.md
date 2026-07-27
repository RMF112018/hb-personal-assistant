# Source Index Phase C Closure Report

## Bounded disposition

`COMPLETE — READY FOR INTEGRATION`

Phase C is reconciled to schema head V129. Supported fixtures cover V121, V124, V125, V126, V127,
V128, V129, and a fresh database. The production-shaped 800k+ rehearsal, Phase C gate, and existing
Phase A/B source-index gate all passed.

## Repository identity

- Repository: `RMF112018/hb-personal-assistant`
- Branch: `feat/source-index-permanent-identity`
- Main observed during validation: `9a3a53b980d7fa43b14baaf5b52bb21d32b4bc38`
- Common ancestor with main: `12d317d19328af6d501c436839bb45d095269a60`
- Validated implementation commit: `4a2cee2771578eb3f7011d360104358f8ea1133a`
- Validated tree: `eddf081483f0ffd1de83ab9e3bf6882d1ea49b8e`

## Implementation summary

- Reconstructed exact legacy V127 source-index shape from the real V93/V94/V122/V125/V126/V127
  contracts before seeding V121–V127 fixtures.
- Added deterministic V128/V129 entity, locator, and move-signal fixtures.
- Extended the independent schema oracle through V129.
- Made FTS, lineage, semantic parity, and representative query-plan checks identity-aware.
- Added explicit V128 entity/locator/move-signal row and semantic preservation checks.
- Added the Phase C gate to the GitHub source-index workflow with full history.
- Updated the specification, runbook, and compatibility note to distinguish the historical V124↔V127
  probe from the current V129 head.

## Acceptance and validation

| Area | Result |
|---|---|
| Supported-origin migration matrix V121/V124–V129/fresh → V129 | PASS |
| Complete ledger 1..129 | PASS |
| Schema, logical, semantic, FTS, lineage, permanent-identity parity | PASS |
| Backup, restore, interruption, locking, integrity, compatibility proofs | PASS |
| Phase C pytest + Ruff + strict mypy gate | PASS |
| Existing Phase A/B source-index pytest + Ruff gate | PASS |
| GitHub workflow YAML parse and diff whitespace check | PASS |
| PC-AC-048 production-shaped rehearsal | PASS — 800,002 source rows |

## Scale evidence

- Raw evidence:
  `docs/evidence/source-index-phase-c/phase-c-v129-800k-rehearsal.json`
- Evidence SHA-256:
  `895df98bfe5d45b58d6ca9b2fe361ee1dc40fbcc1cb85c7ced781f285e9aecd3`
- Source rows: `800002`
- Total measured rows: `2400132`
- Origin/head: `124 → 129`
- Migrated database size: `1738481664` bytes
- Backup SHA-256:
  `bb63f485d207e85bada3dd3db9d02cea03b82fec6b52b8ce1b3b552210b1bd2b`
- Integrity: quick check `ok`; integrity check `ok`; foreign-key violations `0`
- Backup verification: `valid`
- Independent restore validation: `valid`
- Disposable rehearsal footprint removed after verification: approximately `4.9 GB`

## Deviations and residual risk

- Three optional external-model review paths were unavailable: Claude session limit, Grok usage
  balance, and a signed-out ChatGPT browser session. The current repository posture does not require
  an external model approval. Full local gates passed; GitHub CI remains the independent execution
  check at integration.
- The V124 prior-executable probe intentionally proves only the historical read-only V124↔V127
  compatibility claim. It is not generalized to V128/V129.
- Unrelated pre-existing modified and untracked workspace files were preserved and excluded from the
  implementation commit.

## Recommended next gate

Open the integration pull request to `main`, require the source-index workflow to pass on the exact
head, merge without drift, then remove the integrated feature branch and any Phase C temporary
artifacts. This recommendation is not a substitute for the GitHub branch checks.
