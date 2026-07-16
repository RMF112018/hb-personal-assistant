# EXACT_FILE_REGISTER — Public v6 package (REM-PLAN-012-R1 / REM-PLAN-016)

Authentication chain (REM-PLAN-016): the internal `MANIFEST.sha256` covers every retained regular
file EXCEPT itself, and it hashes this register. This register lists every retained regular file
including itself and the manifest; the two self-referential control files carry an N/A SHA row and
are authenticated as described. The external `.tar.gz.sha256` sidecar hashes the completed archive,
and the reconstruction receipt recomputes the archive hash, every manifest entry, and the manifest's
own SHA-256 (reported outside the manifest).

| Relative path | Classification | Template/inheritance basis | Purpose | Surface | SHA-256 |
|---|---|---|---|---|---|
| `EXACT_FILE_REGISTER.md` | Audits | self-referential control file | exact-file register | Public | N/A — self-referential control file; verification basis: hashed by internal manifest |
| `MANIFEST.sha256` | Audits | self-referential manifest | internal manifest | Public | N/A — self-referential manifest; verification basis: authenticated by the archive external SHA-256 and reconstruction receipt |
| `00_SESSION_CONTROL.md` | Audits | Audits-template | 00 SESSION CONTROL | Public | `d5188b9a0312fa899ebddd17ee70e4c711a9561560ed13488292ad56d7a5e712` |
| `01_GOVERNANCE_AUTHENTICATION.txt` | Audits | supporting evidence — inherits Audits | 01 GOVERNANCE AUTHENTICATION | Public | `5b2e5b2d44f99e0bd6e6c42a0a4d0f790e72ef5d2d925ce84c742ee92fb5f473` |
| `02_REPOSITORY_TRUTH.txt` | Audits | supporting evidence — inherits Audits | 02 REPOSITORY TRUTH | Public | `14612cf4e69f166704463e2d0be22765b1cbad0099d2009dc0bee74fc78b2ba2` |
| `03_PR313_AND_GIT_HISTORY.txt` | Audits | supporting evidence — inherits Audits | 03 PR313 AND GIT HISTORY | Public | `14510b6aa83b08672ced249f7009e979f2211d3b6f04abef516e66e1a8ecd0f1` |
| `04_HISTORICAL_EVIDENCE_AUTHENTICATION.txt` | Audits | supporting evidence — inherits Audits | 04 HISTORICAL EVIDENCE AUTHENTICATION | Public | `752dbb3971c215d9bacbae6a5a67a410cde3c6c3952bc633349b1eccb9787acc` |
| `05_APPROVED_ARTIFACT_INVENTORY.md` | Audits | supporting evidence — inherits Audits | 05 APPROVED ARTIFACT INVENTORY | Public | `04fcf10f37fad621016046c3f68d3045f43bc103c7f0272c026caf670f9ead4b` |
| `06_SCHEMA_AND_MIGRATION_CHAIN.md` | Audits | supporting evidence — inherits Audits | 06 SCHEMA AND MIGRATION CHAIN | Public | `d7ee7642307be3168cfb72734757cf77ee3a14dc03441c0851b29c1d2c07f71d` |
| `07_RELEASE_ARTIFACT_BUILD_AND_IDENTITY.txt` | Audits | supporting evidence — inherits Audits | 07 RELEASE ARTIFACT BUILD AND IDENTITY | Public | `c6e4a2bffd296f3ae2f28b2998751690db860e1983a0fb5c03ff02e5a6d94173` |
| `08_PRODUCTION_DEPLOYMENT_READ_ONLY.txt` | Audits | bounded public summary (Audits) | 08 PRODUCTION DEPLOYMENT READ ONLY | Public | `e1a2f9b3867e3f621e5b4d3296e85981b8e9b2eae4088d1cbe2beb2c4cac301b` |
| `09_LIVE_DATABASE_READ_ONLY.txt` | Audits | bounded public summary (Audits) | 09 LIVE DATABASE READ ONLY | Public | `e0021fd7c3831892a8b51ef284191443f22c541dfc55e46c031507faa08c8e70` |
| `10_NF_ENV_001_OPENED_CONNECTION.txt` | Audits | supporting evidence — inherits Audits | 10 NF ENV 001 OPENED CONNECTION | Public | `ec0ef1c896a4100aa215a580d130f4a67f52b45ebd328387f4b64575f777d274` |
| `11_COMPATIBILITY_MATRIX.md` | Audits | supporting evidence — inherits Audits | 11 COMPATIBILITY MATRIX | Public | `d3753a5bcc7c6b00ba49d2370151422186cbf104942a36847b8d5aca430c4d72` |
| `12_REHEARSAL_SOURCE_AND_ISOLATION.txt` | Audits | bounded public summary (Audits) | 12 REHEARSAL SOURCE AND ISOLATION | Public | `92b43fb0b9c871d640909bff37e8d38b3d33b5c868719cc9f2b66a00b1b04ec9` |
| `13_BACKUP_RECEIPT_AND_RESTORE_PROOF.txt` | Audits | bounded public summary (Audits) | 13 BACKUP RECEIPT AND RESTORE PROOF | Public | `6542ecb213c3e60cccb8527107ac23d760b42d9f384796e8d986726849cc3afe` |
| `14_V124_V127_MIGRATION_REHEARSAL.txt` | Audits | supporting evidence — inherits Audits | 14 V124 V127 MIGRATION REHEARSAL | Public | `15e6bef8a4167f209fe47f3545a916c0e67d3d3c77f20100fbf8778ed2c62bcf` |
| `15_FAILURE_AND_RECOVERY_REHEARSAL.txt` | Audits | supporting evidence — inherits Audits | 15 FAILURE AND RECOVERY REHEARSAL | Public | `8ffa493a6711e031ccdfc5834ea1a3b9ee26af2c6f6f0ebfb401394a926cf0f7` |
| `16_POST_MIGRATION_VALIDATION.txt` | Audits | supporting evidence — inherits Audits | 16 POST MIGRATION VALIDATION | Public | `ab19a8bcff03060ae095d7242e5ccda04d17294140e163c5e122f5a860ce088b` |
| `17_ACCEPTANCE_CRITERIA_MATRIX.md` | Audits | Audits-template | 17 ACCEPTANCE CRITERIA MATRIX | Public | `ac0066e9aafcf91377732ad61dfbbb1a2d08f6dceabea04d92ac07c0e1f49978` |
| `18_FINDING_LEDGER.md` | Audits | Audits-template | 18 FINDING LEDGER | Public | `821873e7ff1c77a1bad274742d2416b141030cc0ccb965ddc5e58980da4afcd3` |
| `19_REDACTION_AND_SECRET_SCAN.txt` | Audits | supporting evidence — inherits Audits | 19 REDACTION AND SECRET SCAN | Public | `aad0ccf600670c82618cb8617229f3c22b5682c0c23da01fa0193a7abf92ed32` |
| `19b_PUBLICATION_SENSITIVITY_REVIEW.md` | Audits | supporting evidence — inherits Audits | 19b PUBLICATION SENSITIVITY REVIEW | Public | `2976a6bc82288277051978205bb8035deb0c2ee07571e4e40ffd8c3afc2a9ef2` |
| `20_EVIDENCE_INDEX.md` | Audits | Audits-template | 20 EVIDENCE INDEX | Public | `c02ba9883757b65948b99cdc3c6c349adb2f71fa9ce1346ad26f337ff8118394` |
| `21_FINAL_EVIDENCE_REPORT.md` | Audits | Audits-template | 21 FINAL EVIDENCE REPORT | Public | `1695390047056edfb2f57477a515eb36bccf4c665a2bfa85bcfdb36b7e60a20f` |
| `GATE-RECEIPTS.md` | Audits | supporting evidence — inherits Audits | GATE RECEIPTS | Public | `48157d85a977257c5620aaaa1c4f708f814b4711678a3669c858c53d8670144e` |
| `PRIVATE_EVIDENCE_REFERENCES.md` | Audits | supporting evidence — inherits Audits | PRIVATE EVIDENCE REFERENCES | Public | `b8b620a7c606d0a9e4c82e0b37d4c8fad690a97762d786f6e905d5e5065c30f4` |
| `PUBLIC_REDACTION_POLICY.md` | Audits | supporting evidence — inherits Audits | PUBLIC REDACTION POLICY | Public | `4054cb1d93deea9cafdf093d0b33b39147c8894594921ef69648b57931ff87d7` |
| `database/09a-before-state.txt` | Audits | bounded public summary (Audits) | 09a before state | Public | `b892d9cea89d06ea7388a4e9a26f4aa0bffc4a4ac4c466de2da4e8249f8a32fe` |
| `database/09b-schema-probe.txt` | Audits | bounded public summary (Audits) | 09b schema probe | Public | `64606e3e75f8b9a2356ad088fdd0cd4935fe1b5fda8af4e3f68491c844e8f9dc` |
| `database/09c-after-state-and-invariance.txt` | Audits | bounded public summary (Audits) | 09c after state and invariance | Public | `0ef9a3a9d60185263cf03cc269a5830149729005a4cbfd832872d609bf3abdaa` |
| `database/09d-snapshot-source-sizing.txt` | Audits | bounded public summary (Audits) | 09d snapshot source sizing | Public | `0d28a639439cf5f49fd914cd1dcc282c39c958b690e2a2054aef7d7d16ce06de` |
| `image/CANDIDATE_IMAGE_SUMMARY.md` | Audits | supporting evidence — inherits Audits | CANDIDATE IMAGE SUMMARY | Public | `c49ee8f7c61984047134c9001b3beee4db459de3f95d2fbeb729a2aaea3ccc16` |
| `repository/github-metadata.txt` | Audits | supporting evidence — inherits Audits | github metadata | Public | `9065bdb464f4ad9265e56b89f7f0f5f2698e469f9e263daa67382b523fb4528a` |
| `runtime/DEPLOYED_RUNTIME_SUMMARY.md` | Audits | supporting evidence — inherits Audits | DEPLOYED RUNTIME SUMMARY | Public | `aa09303abee967a042fdfe263a8147cfcc762c2906a1946004b67e7ff31fbe0b` |
| `runtime/mcp-config-redacted.txt` | Audits | supporting evidence — inherits Audits | mcp config redacted | Public | `64d5a56b96d6d76a46e142cd66618c2dbcf456aa74621d0bc8e6a64c0aac306e` |
| `runtime/migration-route-map.md` | Audits | supporting evidence — inherits Audits | migration route map | Public | `ab431251e058ff8a287336f1c0e46cf51d68fb5b5183d00779f1cff0355f7ed4` |

Content files (excluding the 2 control files): 35. Total retained regular files: 37.

