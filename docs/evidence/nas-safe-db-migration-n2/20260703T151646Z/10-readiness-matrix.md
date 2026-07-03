# N2 · 10 — Readiness Matrix

Legend: PASS = done/verified · WARN = partial/external gate · FAIL = broken · NO = deliberately not authorized.

| # | Item | Status | Note |
|---|---|---|---|
| 1 | N2 worktree based on correct scaffold branch | **PASS** | `fix/nas-schema-drift-n2-20260703T151646Z` off `feature/nas-runtime-scaffold-n1b-20260703T123726Z` (581ad598) |
| 2 | Schema-drift root cause identified | **PASS** | migrator applies+records v98; `LATEST_SCHEMA_VERSION` stayed 97 (`02`) |
| 3 | `LATEST_SCHEMA_VERSION` corrected | **PASS** | `migrator.py:17` 97 → 98 (`03`) |
| 4 | Schema tests added/updated | **PASS** | new `test_schema_version_head_consistency.py` (5 tests) + schedule-bundle wiring |
| 5 | Targeted tests pass | **PASS** | 41 targeted + schedule 328 + forecasting 1166, all green; red→green proven (`04`) |
| 6 | SQLite backup-API plan complete | **PASS** | `05` (plan only, not executed) |
| 7 | Live DB quiesce plan complete | **PASS** | `06` (plan only) |
| 8 | Copied-DB smoke plan complete | **PASS** | `07` (plan only) |
| 9 | Secrets / Text-Vault plan complete | **PASS** | `08` (plan only, no secrets touched) |
| 10 | auth/security hardening | **WARN** | still 0777 on NAS; required before secrets (external) |
| 11 | Public exposure confirmation | **WARN** | firewall/router/Tailscale still unconfirmed (external) |
| 12 | Runtime-user / admin split | **WARN** | `svc` still in `administrators` (external) |
| 13 | Ready for N2B/N3 copied-DB implementation | **WARN** | schema code ready; non-code security gates (10–12) still open → N2B first |
| 14 | Copied-DB smoke authorized | **NO** | prohibited until explicitly authorized |
| 15 | Production cutover authorized | **NO** | prohibited |

## Additional (pre-existing, surfaced in N2)

| Item | Status | Note |
|---|---|---|
| `test_nas_runtime_scaffold.py::test_dockerignore_excludes_config_db_and_secrets` | **FAIL (pre-existing)** | scaffold test contradicts its own N1C `.dockerignore` fix; unrelated to schema drift; fix in N2B (`09`,`11`) |
| Tests writing tracked evidence files (08b/08c) | **WARN (pre-existing)** | reverted, not staged; follow-up to route to `tmp_path` (`09`) |

## Verdict

**N2 = PASS.** Schema drift fixed and proven; migration plans complete. Copied-DB smoke and production
cutover remain **NO**. Proceed to **N2B** (security gates + closeout) before **N3** (copied-DB).
