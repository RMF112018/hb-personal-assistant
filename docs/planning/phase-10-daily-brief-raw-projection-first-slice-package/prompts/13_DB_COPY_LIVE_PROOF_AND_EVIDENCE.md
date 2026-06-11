# 13 — DB-Copy Live Proof and Evidence Generation

## Objective

Prove the implemented slice against a copied production DB without mutating production.

## Steps

1. Create a fresh `/tmp` DB copy.
2. Record production hash/size/mtime before.
3. Run projection dry-run on the copy.
4. Run projection apply on the copy.
5. Run coverage after projection.
6. Run calendar candidate dry-run/apply on the copy with caps.
7. Run Procore digest dry-run/apply on the copy with caps.
8. Run integrated daily-run copy proof if CLI supports DB override; otherwise run stage-level proof and explain limitation.
9. Run source-ref/usefulness/contradiction checks.
10. Run guard-column checks.
11. Run no-raw-leak scan.
12. Record production hash/size/mtime after and prove unchanged.

## Required evidence files

- `06-v49-projection-dry-run.json`
- `07-v49-projection-apply-copy.json`
- `08-v49-projection-coverage-after.json`
- `09-calendar-candidate-dry-run.json`
- `10-calendar-candidate-apply-copy.json`
- `11-procore-digest-dry-run.json`
- `12-procore-digest-apply-copy.json`
- `14-candidate-source-ref-coverage.json`
- `15-usefulness-gate-proof.json`
- `16-contradiction-known-bad-proof.json`
- `17-daily-run-integrated-copy-proof.json`
- `20-no-raw-leak-scan.txt`
- `21-guard-column-proof.json`
- `22-no-writeback-proof.md`
- `23-production-db-unchanged-proof.txt`
- `25-usefulness-scorecard.md`

## Acceptance

- Copy proof demonstrates structured projection and candidate/source-ref persistence on the copy.
- Production DB unchanged.
- Evidence raw-free.


## Safety constraints for this prompt

- Use DB copies for validation.
- Do not print raw private values.
- Do not mutate external systems.
- Do not mutate production DB during validation.
- Commit only code/docs/tests/evidence that are raw-free.
- Stop if any stop condition is triggered.
