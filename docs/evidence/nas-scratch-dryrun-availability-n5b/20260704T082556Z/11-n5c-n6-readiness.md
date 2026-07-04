# 11 — N5C / N6 Readiness (roadmap unchanged)

N5B does not redefine the roadmap. It confirms reachability + surfaces one new activation gate.

## New gate surfaced by N5B — read-only enforcement for `syn-work`
Before any `syn-work` activation, a **real** read-only enforcement mechanism must exist. Today there is **none**:
- Filesystem: `/volume1/homes/bfetting/Work` is mode `777` → no FS enforcement.
- Config: `ExternalSourceRoot` has **no `read_only` field** (`extra=forbid`); `read_only=true` is dropped by the
  loader → no config enforcement.

Options (any one, before activation):
1. Add a schema-honored `read_only` field to `ExternalSourceRoot` + enforce it on the read/index path (hardening).
2. Use the existing `sensitive` field if/where it gates write-capable workflows (verify semantics first).
3. Tighten the path: a read-only bind-mount or corrected perms/ACL on the NAS side.

Until then, keep `syn-work` `enabled=false` and run no write-capable workflow against it.

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
  preflight; (4) **read-only enforcement for `syn-work`** (this phase's new gate) while its path is mode `777`.

## Net
N5B confirms NAS vault + `syn-work` are reachable/readable by svc from a scratch context, and scratch config validates
non-active. Deeper dry-run/reconcile deferred; `syn-work` activation blocked on real read-only enforcement. N5C/N6 not
authorized.
