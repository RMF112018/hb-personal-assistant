# Evidence Bundle Manifest

Create raw-free evidence under:

`docs/evidence/phase-10-daily-brief-effectiveness-ranking-policy-telemetry/`

Required files:

1. `00-repo-truth-audit.md`
2. `01-ranking-assembly-prerequisite.md`
3. `02-design-contract.md`
4. `03-schema-migration-proof.json`
5. `04-dry-run-single-day-no-write.json`
6. `05-dry-run-window-no-write.json`
7. `06-apply-tmp-db-proof.json`
8. `07-outcome-join-proof.json`
9. `08-rank-outcome-metrics-proof.json`
10. `09-procore-noise-metrics-proof.json`
11. `10-model-profile-eval-proof.json`
12. `11-feedback-calibration-lift-proof.json`
13. `12-rollup-proof.json`
14. `13-report-render-proof.md`
15. `14-source-ref-coverage-proof.json`
16. `15-no-raw-leak-scan.json`
17. `16-guard-columns-zero-proof.json`
18. `17-prod-db-sha-unchanged.txt`
19. `18-pytest-focused.txt`
20. `19-ruff.txt`
21. `20-mypy.txt`
22. `21-compile.txt`
23. `22-final-summary.md`

If the prerequisite is missing, create only:

- `00-repo-truth-audit.md`
- `01-ranking-assembly-prerequisite.md`
- `22-final-summary.md`

and stop with status `missing_ranking_assembly_prerequisite`.
