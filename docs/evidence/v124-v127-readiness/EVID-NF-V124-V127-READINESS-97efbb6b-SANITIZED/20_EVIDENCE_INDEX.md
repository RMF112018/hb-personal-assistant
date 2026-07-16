# 20 — Evidence Index — v6 (public tier, remediation-corrected)

generated_utc: 2026-07-16 (v6)
trust states: trusted | partially_trusted | untrusted | conflicting | not_evaluated
per-claim trust: NAS-probe-derived + summarized-from-NAS + NAS-load-referencing items = partially_trusted;
self-computed local artifacts (repo/git reads, local rehearsal, analysis docs, hashes) = trusted.
(20 lists every packaged file except itself + MANIFEST.sha256, which cover it in turn.)

| # | File | Size | SHA-256(16) | Trust |
|---|---|---|---|---|
| 1 | 00_SESSION_CONTROL.md | 5532 | d5188b9a0312fa89… | trusted |
| 2 | 01_GOVERNANCE_AUTHENTICATION.txt | 3831 | 5b2e5b2d44f99e0b… | trusted |
| 3 | 02_REPOSITORY_TRUTH.txt | 1753 | 14612cf4e69f1667… | trusted |
| 4 | 03_PR313_AND_GIT_HISTORY.txt | 1593 | 14510b6aa83b0867… | trusted |
| 5 | 04_HISTORICAL_EVIDENCE_AUTHENTICATION.txt | 2986 | 752dbb3971c215d9… | trusted |
| 6 | 05_APPROVED_ARTIFACT_INVENTORY.md | 5196 | 04fcf10f37fad621… | trusted |
| 7 | 06_SCHEMA_AND_MIGRATION_CHAIN.md | 5616 | d7ee7642307be316… | trusted |
| 8 | 07_RELEASE_ARTIFACT_BUILD_AND_IDENTITY.txt | 1723 | c6e4a2bffd296f3a… | partially_trusted |
| 9 | 08_PRODUCTION_DEPLOYMENT_READ_ONLY.txt | 1368 | e1a2f9b3867e3f62… | partially_trusted |
| 10 | 09_LIVE_DATABASE_READ_ONLY.txt | 1144 | e0021fd7c3831892… | partially_trusted |
| 11 | 10_NF_ENV_001_OPENED_CONNECTION.txt | 6180 | ec0ef1c896a4100a… | partially_trusted |
| 12 | 11_COMPATIBILITY_MATRIX.md | 3864 | d3753a5bcc7c6b00… | trusted |
| 13 | 12_REHEARSAL_SOURCE_AND_ISOLATION.txt | 1310 | 92b43fb0b9c871d6… | partially_trusted |
| 14 | 13_BACKUP_RECEIPT_AND_RESTORE_PROOF.txt | 1350 | 6542ecb213c3e60c… | partially_trusted |
| 15 | 14_V124_V127_MIGRATION_REHEARSAL.txt | 1359 | 15e6bef8a4167f20… | partially_trusted |
| 16 | 15_FAILURE_AND_RECOVERY_REHEARSAL.txt | 2037 | 8ffa493a6711e031… | partially_trusted |
| 17 | 16_POST_MIGRATION_VALIDATION.txt | 1193 | ab19a8bcff03060a… | partially_trusted |
| 18 | 17_ACCEPTANCE_CRITERIA_MATRIX.md | 6504 | ac0066e9aafcf913… | trusted |
| 19 | 18_FINDING_LEDGER.md | 7663 | 821873e7ff1c77a1… | trusted |
| 20 | 19_REDACTION_AND_SECRET_SCAN.txt | 1452 | aad0ccf600670c82… | trusted |
| 21 | 19b_PUBLICATION_SENSITIVITY_REVIEW.md | 4083 | 2976a6bc82288277… | trusted |
| 22 | 21_FINAL_EVIDENCE_REPORT.md | 14620 | 1695390047056edf… | trusted |
| 23 | EXACT_FILE_REGISTER.md | 7913 | self-ref (SHA in MANIFEST) | trusted |
| 24 | GATE-RECEIPTS.md | 7583 | 48157d85a977257c… | trusted |
| 25 | PRIVATE_EVIDENCE_REFERENCES.md | 4908 | b8b620a7c606d0a9… | trusted |
| 26 | PUBLIC_REDACTION_POLICY.md | 3090 | 4054cb1d93deea9c… | trusted |
| 27 | database/09a-before-state.txt | 1201 | b892d9cea89d06ea… | partially_trusted |
| 28 | database/09b-schema-probe.txt | 1177 | 64606e3e75f8b9a2… | partially_trusted |
| 29 | database/09c-after-state-and-invariance.txt | 1162 | 0ef9a3a9d6018526… | partially_trusted |
| 30 | database/09d-snapshot-source-sizing.txt | 1231 | 0d28a639439cf5f4… | partially_trusted |
| 31 | image/CANDIDATE_IMAGE_SUMMARY.md | 1361 | c49ee8f7c6198404… | trusted |
| 32 | repository/github-metadata.txt | 892 | 9065bdb464f4ad92… | trusted |
| 33 | runtime/DEPLOYED_RUNTIME_SUMMARY.md | 1620 | aa09303abee967a0… | partially_trusted |
| 34 | runtime/mcp-config-redacted.txt | 724 | 64d5a56b96d6d76a… | partially_trusted |
| 35 | runtime/migration-route-map.md | 4730 | ab431251e058ff8a… | trusted |

total files indexed: 35 (+ 20_EVIDENCE_INDEX.md + MANIFEST.sha256, self-covering)
partially_trusted: 15  |  trusted: 20
bulk rehearsal DB copies (5.7GB) held OUTSIDE the package, referenced by SHA-256.
Deep-disclosure raw captures (runtime inspects/logs, verbose build/load logs, full candidate inspect)
are retained PRIVATE and referenced via PRIVATE_EVIDENCE_REFERENCES.md; the Docker image archive is private.
