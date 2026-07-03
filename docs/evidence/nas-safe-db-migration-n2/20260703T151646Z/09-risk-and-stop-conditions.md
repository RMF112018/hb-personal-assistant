# N2 · 09 — Risks and Stop Conditions

## Risks (must all be cleared before copied-DB smoke)

| # | Risk | Status after N2 |
|---|---|---|
| 1 | Schema-version drift (constant vs recorded head) | **RESOLVED** (constant → 98; guard test added) |
| 2 | auth/security NAS ACLs not hardened (0777) | **OPEN** — blocks secrets |
| 3 | Public exposure not confirmed (firewall/router/Tailscale) | **OPEN** |
| 4 | Runtime-user / admin split (`svc` in `administrators`) | **OPEN** |
| 5 | Mac live DB hot / WAL during copy | Addressed by quiesce plan (`06`) — not yet executed |
| 6 | Raw-copy corruption of a WAL DB | Addressed by backup-API plan (`05`) — mandatory, not `cp` |
| 7 | Auto-migrate-on-open writes the copied DB | Expected/allowed; post-N2 a no-op on an already-98 copy (`02` Q10, `07`) |
| 8 | `/health` can touch the DB | Runs with workers disabled; read-only surface |
| 9 | Workers/watchers must stay disabled | `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1` everywhere |
| 10 | Text-Vault key/blob/DB consistency | Planned (`08`); secrets blocked until #2 cleared |
| 11 | Portainer reclaiming port 8000 | Keep Portainer off 8000 |
| 12 | DB path on `/Volumes` (SMB) | Refused by `05` stop condition; NAS-local only |

## Stop conditions (abort the copied-DB path)

Live backend still running · DB still hot · schema drift unresolved · destination on SMB/`/Volumes` ·
`integrity_check` != ok · unexplained row-count deltas · auth/security not hardened when secrets are in
scope · public exposure unresolved when the DB is network-reachable · any scheduler/watcher active.

## N2-specific hygiene observations (pre-existing, not caused by the schema fix)

- **`test_nas_runtime_scaffold.py::test_dockerignore_excludes_config_db_and_secrets` fails** on the
  scaffold branch: it asserts `.dockerignore` contains `**/security/` and `**/auth/`, but commit
  581ad598's own N1C fix deliberately **removed** those globs (they were excluding the real
  `src/hb_assistant/{auth,security}/` source packages, which broke the container import). The test is
  self-contradictory with its own commit and is **unrelated to schema drift**. N2 does not fix it
  (bounded scope). Recommend fixing it in N2B by updating the test to assert the narrowed secret-file
  patterns (`**/*.key`, `**/*.pem`, `**/msal-token-cache*.bin`, `**/text-vault.key`, `**/text-vault/`)
  instead of the broad package-directory globs.
- **A test regenerates a tracked evidence file.** `test_automation_executor_service.py` rewrites
  `docs/evidence/construction-intelligence-phase-08b-automation-hardening/phase-08b-final-no-writeback-proof.md`
  as a side-effect, stamping the live DB head (`schema_version=98`; committed value was a stale `63`).
  This is a pre-existing test-writes-tracked-file quirk. In N2 it was **reverted** and is **not
  staged**. Flag for follow-up: tests should write such artifacts under `tmp_path`, not the repo tree.
