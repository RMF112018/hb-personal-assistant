# 05 — Approved Artifact Inventory (NF-F-001 / V127 deploy)
generated_utc: 2026-07-16  command_class: LOCAL_REPOSITORY_READ_ONLY  source: origin/main 97efbb6b

## A. Deployment / image / health / backup-recovery artifacts (deploy/nas/, blob SHA @ origin/main)
deploy/nas/Dockerfile                                b6da10c2eef9f2f63b5262736ac5c1e1173e39db
deploy/nas/BUILD.md                                  30040a207c1177d891bbc24c6043feb653a67aae
deploy/nas/compose.yaml                              60ea7b6de92324204979dab0eceab59a26862af3
deploy/nas/VIEWER_MODE.md                            09752b5262b35513864dafe68c02f49fdc5b5010
deploy/nas/README.md                                 6bc5cc6f20cfda0e927a2f4bb4bea6fe67c66383
deploy/nas/CLEANUP.md                                002889268d1a874ca80b7c543126a1cca0507061
deploy/nas/mcp/compose-mcp.yaml                      c5ec6d40ad38a873661b48ca3eeaa8666e3b2243
deploy/nas/mcp/compose-<edge-provider>d.yaml              00638fe67ce0ce7a303a3813b6a3806249bf8f19
deploy/nas/scripts/snapshot-mcp-db.sh                6d5775664ccb7cb0071ae129811a7206d2615b44
deploy/nas/scripts/install-snapshot-cron.sh          36067f1af09431488fbb649ad4e1b9b31c1eace5
deploy/nas/scripts/merge-workspace-to-live.sh        625390853aca9e76f7b09b034a02000754a35e49
deploy/nas/scripts/validate-db.sh                    a1725171eb520320ea7c4d9ab94d575c306d0009
deploy/nas/scripts/check-runtime-safety.sh           c4473bc6de00e299ccb4c1b4ae5275f00d9fd41e
deploy/nas/scripts/emergency-shutdown.sh             adb773570801fe4555f4c28480f1fff4d25f6b65
deploy/nas/scripts/start.sh                          64ecf7a48dcbefc910396e63b9a3c2c7885f0819
deploy/nas/scripts/stop.sh                           f015e70d878f19866caf975779b19a2c80515b10
deploy/nas/scripts/restart.sh                        87c0e32f294c28eaa99c7cbf463dd2736803dc4c
deploy/nas/scripts/status.sh                         73e349c57cfa47b060ec93ac2d8acf776232827a
deploy/nas/scripts/health.sh                         32dc34f4b0c7e36a5e1e9a83910720bddb512d0c
deploy/nas/scripts/render-config.sh                  4c139f61b7fefbfa2bb55863e47598f979d0b851

## B. NF-F-001 authorization code modules (origin/main blob SHA)
src/hb_assistant/store/migration_authorization.py          a6de75e2597833739e8a52e72394af3d1af09f72
src/hb_assistant/store/database_identity.py                cb99661aff6981d17520624d6ff713214b6ba425
src/hb_assistant/store/migration_audit.py                  9365114594f18ac5b37a3457387889b537b2c44c
src/hb_assistant/store/schema_readiness.py                 ebf089b2be9e6f78260dfc92d34c866e84e338c2
src/hb_assistant/store/startup_schema_policy.py            5faecc1b2318a0316c5c08827e9933276c40c017
src/hb_assistant/config/db_storage_guard.py                432e7e006762222ff9d35e10d8387c06f1bf9b6d
src/hb_assistant/store/migrator.py                         f210fd135b7755d9584072f01ab932a96cc1d4bc

## C. Governance-doc EVIDENCE GAP
Searched repo (docs/, .ai/) + external governance sources: NO committed NF-F-001 architecture / implementation plan /
plan-review / implementation-audit / corrective-review / evidence-index / migration-runbook exists.
Code references plan sections (plan §6/§12, N-A1..N-A4, RC-1..RC-3, NF-AUD-003/004/005) with NO
in-repo plan file. Durable design record = (1) git commit history on fix/nf-f-001-ambient-migration-ownership
and (2) external governance review REVIEW-NF-F-001-PR313-ALL-REVIEW-CLOSURE-v1.2.md (SHA 1bbceefb…, authenticated 01).
-> Logged as Finding (evidence gap): NF-DOC-001 (Medium) missing committed design/plan/audit artifacts.

## D. NF-F-001 commit trail (candidate line e247ad08..51ce5f28, the durable design record)
51ce5f28 Corrective-2 (RC-A..RC-D): closure-encapsulated trust core + always-bound managed identity
10d7b6ae NF-AUD-004 corrective: add replay-rejection test (origin binding blocks reused authorization)
db1050b0 NF-AUD-004 corrective fix: startup policy selects capability by decision reason
93f22cbd NF-AUD-003/004/005 corrective: successor prove-green tests
d6efea24 NF-AUD-003 corrective: convert 100 ordinary apply() call sites to ensure_schema_ready
b02bf51e NF-AUD-004/005 corrective: enforced-issuer capability + FD-stable opened-target identity
2ee1ddd5 NF-F-001 Stage 9: lint cleanup — contextlib.suppress in _is_temp_fixture (SIM105)
a1554aaf NF-F-001 Stage 8: runtime reachability — ordinary paths perform 0 managed migrations
ca3734e8 NF-F-001 Stage 6: sanitized migration-guard audit events
0192e160 NF-F-001 Stage 7: prove-green migration-ownership authorization guard tests
045eea9e NF-F-001 Stage 5: authorized/readiness caller adaptation + automatic managed-local CLI bootstrap
11c3fb97 NF-F-001 Stage 2: de-ambient managed migration at N-A4 (constructor) and N-A3 (schedule)
f9b78d11 NF-F-001 Stage 4: connection-aware migrator apply() + opened-target identity guard (+RC-3)
042f220c NF-F-001 Stage 3 (RC-1 MANAGED_LOCAL): distinct managed-local storage class + auto app-bootstrap authorization
822560d5 NF-F-001: read-only schema readiness verifier
94b21c88 NF-F-001: migration-authorization model + typed error hierarchy
d4d5b2c6 NF-F-001 RC-2: exact-path storage-class classifier
