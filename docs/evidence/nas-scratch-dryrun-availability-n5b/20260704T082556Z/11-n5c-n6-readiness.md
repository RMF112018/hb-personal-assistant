# 11 — N5C / N6 Readiness (roadmap unchanged)

N5B does not redefine the roadmap. It confirms reachability + surfaces one new activation gate.

## Gate surfaced by N5B — read-only enforcement for `syn-work` — RESOLVED (filesystem/ACL)
This gate is now **resolved at the filesystem layer**: a `personal-assistant-svc` ACL
(`allow:r-x---a-R-c--:fd--`, no write/append/delete) governs `/volume1/homes/bfetting/Work`, and a bounded empirical
test proved svc read succeeds while svc write is denied in `Work`, `NAS - HB`, `Altman` with no leaked artifact
(`13`). Option 3 below was taken (read-only ACL). The other options remain **optional future hardening**, not gates:
1. Add a schema-honored `read_only` field to `ExternalSourceRoot` + enforce it on the read/index path — a code-quality
   improvement so activation does not depend solely on per-path ACLs (`05`).
2. Wire the existing `sensitive` field if/where it gates write-capable workflows (verify semantics first).
3. **Done** — read-only ACL for svc on the NAS path (option chosen).

The ACL is the authoritative control (the compat `777` mode bits are overridden by the present ACL). Continue to keep
`syn-work` `enabled=false` until activation is separately authorized; the FS layer now backstops read-only regardless.

## N5C — MSAL/Graph + Procore re-provision (determined; needs interactive login)
- Device-code `hb-assistant auth login` on the NAS → `<app-support>/auth/msal-token-cache.bin` (0600 svc); scopes
  include `Files.ReadWrite.All` (covers `hb-onedrive`/Graph). Do not copy the Mac cache.
- Procore: client secret via env/protected file; mint fresh `<app-support>/auth/procore_token.json` (0600 svc);
  `HB_PROCORE_LIVE` off.
- N5C may also host the **on-NAS** first-indexing dry-run (deferred from `07`) against an intentionally-enabled
  scratch config, isolated from the production DB/vault.

## Downstream (meanings unchanged)
- **N6** — NAS operator control tooling (benefits from the confirmed scratch context + stable NAS path map).
- **N7** — MCP-on-NAS via SSH launcher (needs vault mirror + config; bearer/public-URL off by default).
- **N8** — second-brain / watchers / scheduler gating. Gated by: (1) the `source_root_key` identity fix before any
  multi-root activation; (2) a Linux scheduler to replace macOS `launchd`; (3) Text Vault fail-closed startup
  preflight. (Read-only enforcement for `syn-work` is **no longer** an open gate — resolved via ACL, `13`.)

## Net
N5B confirms NAS vault + `syn-work` are reachable/readable by svc from a scratch context, scratch config validates
non-active, and `syn-work` read-only is now enforced by ACL (svc write-denied, `13`) → **PASS**. Deeper
dry-run/reconcile remain conservatively deferred (non-blocking). N5C/N6 not authorized.
