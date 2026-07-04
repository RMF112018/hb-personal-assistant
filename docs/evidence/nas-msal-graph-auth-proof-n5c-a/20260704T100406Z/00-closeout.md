# N5C-A — MSAL / Graph Device-Code Auth Proof — Closeout

**Verdict: WARN** (core objective achieved; WARN is procedural — see below).
**The MSAL delegated token cache was successfully created and persisted to the NAS app-support auth directory with
least-privilege ownership/mode. No token values, device code, login URL, or MSAL cache contents are in committable
evidence.**

## Result
| Check | Result |
|---|---|
| Docker CLI runtime available (N5C-R2) | ✅ `hb-personal-assistant:nas` reused |
| Auth dir least-privilege (pre) | ✅ `700 personal-assistant-svc:users`, `cache_preexisting=no` |
| Device-code login completes | ✅ `login_exit=0`, `status=login_success` (delegated) |
| `msal-token-cache.bin` created on NAS | ✅ `cache_exists=yes` |
| Cache owner/mode | ✅ `mode=600 owner=personal-assistant-svc:users` (size 9623) |
| Auth dir remains `700` | ✅ `700 personal-assistant-svc:users` |
| Service user can read cache | ✅ `svc_can_read_cache=yes` |
| Production DB unchanged | ✅ `db_pre == db_post` (mtime + size `4151631872` identical) |
| No lingering containers | ✅ `lingering=0`, `running_hbpa=0` |
| No token values / device code / cache contents committed | ✅ (redacted; raw kept out of evidence) |
| Graph API smoke | ⏸ **deferred by design** (not separately authorized) |

## Why WARN (not PASS) — procedural, not a defect
Per the N5C-A acceptance criteria (§17), two conditions map to WARN even though the auth-cache creation fully
succeeded:
1. **Graph smoke deferred** — no `/me` (or other Graph) call was made; only the MSAL cache creation + metadata were
   proven. This is the intended default (§14).
2. **Reached success via the `--network host` variant** — the original default-bridge attempts failed on **intermittent
   Docker bridge DNS** (`Temporary failure in name resolution`), *before* any device code was issued. Host-network mode
   resolved reliably and the login then succeeded on the first host-network attempt. This is a Docker networking
   environment characteristic, **not** an MSAL/credential issue and not a defect in the auth path.

The **core objective — persist a delegated MSAL token cache to the NAS as `personal-assistant-svc`** — is **achieved**.

## Effective delegated scopes (names only; from the login result)
`User.Read`, `Mail.Read`, `Calendars.ReadWrite.Shared`, `Files.ReadWrite.All` (the reserved `offline_access` was
removed by `sanitize_delegated_scopes`, as designed). **Observation:** `Calendars.ReadWrite.Shared` and
`Files.ReadWrite.All` are write-capable delegated scopes — flagged for later scope-minimization review (not changed
here; N5C-A does not alter identity/scope config).

## Boundaries held (see 08)
No backend/uvicorn · no MCP · no scheduler/watcher · no source ingestion/card generation · no production DB writable
open (DB untouched) · no source-root/config activation beyond the read-only config mount · no Graph data fetched · no
secrets/tokens/device-code committed · no push/PR.

## Evidence index
- `01-preflight-from-n5c-r2.md` · `02-repo-truth-auth-reconfirmation.md` · `03-nas-auth-path-preflight.md`
- `04-login-execution-redacted.md` · `05-token-cache-metadata-proof.md` · `06-db-side-effect-and-container-cleanup-proof.md`
- `07-graph-smoke-deferred.md` · `08-boundaries-maintained.md` · `09-auth-carry-forward.md` · `10-git-status.md`
- `local-sensitive/README.md` (gitignored — holds the redacted account id + raw command detail).
