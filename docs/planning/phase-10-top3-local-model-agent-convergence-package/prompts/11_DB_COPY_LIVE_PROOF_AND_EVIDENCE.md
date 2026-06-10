Repository: `RMF112018/hb-personal-assistant`  
Local path: `/Users/bobbyfetting/hb-personal-assistant`  
Branch: `experiment/phase-10-top3-local-model-agent-convergence`  
Evidence root: `docs/evidence/phase-10-top3-local-model-agent-convergence`

Hard constraints apply from `../README.md`, `../STOP_CONDITIONS.md`, and `../reference/02_SAFETY_CONTRACT.md`.

# Prompt 11 — DB-Copy Live Proof and Evidence Generation

## Objective

Prove live behavior on a DB copy without mutating production DB.

## Required process

1. Locate the production/dev DB path using existing repo config/path-policy commands.
2. Compute sha256 before.
3. Copy DB to `/tmp` or another safe disposable path.
4. Run migrations on the copy only if required by normal app startup.
5. Execute:
   - email raw enrichment readiness on copy
   - email raw enrichment dry-run on copy
   - email raw enrichment capped apply on copy, seeded if natural eligible rows do not exist
   - idempotency rerun on copy
   - daily-run integrated apply on copy
   - model-unavailable fallback proof
6. Compute production DB sha256 after.
7. Confirm unchanged.
8. Confirm guard columns zero in touched tables.
9. Run forbidden-string scan over evidence and generated proof outputs.

## Natural data vs seeded data

If natural DB data has no eligible email-source-linked accepted follow-up records:

- Do not treat this as failure.
- Record natural readiness truth.
- Seed the DB copy with minimal synthetic, redacted, source-linked fixture rows to prove persistence/cap/idempotency.
- Clearly label seeded proof as seeded-copy proof.
- Do not seed production DB.

## Evidence

Create:

- `11-email-raw-enrichment-eligibility-proof.json`
- `12-email-raw-enrichment-dry-run-proof.json`
- `13-email-raw-enrichment-capped-apply-proof.json`
- `14-email-raw-enrichment-idempotency-proof.json`
- `15-daily-run-integrated-proof.json`
- `16-model-unavailable-fallback-proof.json`
- `17-forbidden-string-scan.txt`
- `18-no-writeback-proof.md`
- `19-guard-column-proof.json`
- `20-production-db-unchanged-proof.txt`

## Stop conditions

- Production DB hash changes.
- Raw content appears in evidence.
- Guard columns nonzero.
- Any writeback path is detected.
