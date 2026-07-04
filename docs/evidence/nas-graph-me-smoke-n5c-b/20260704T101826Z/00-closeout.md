# N5C-B — Bounded Microsoft Graph /me Smoke — Closeout

**Verdict: WARN** (core objective achieved).

## What N5C-B proved
The NAS-persisted delegated MSAL token cache is **usable from the NAS runtime container to make exactly one bounded
Microsoft Graph `/v1.0/me` request**, returning HTTP 200. This proves Graph connectivity + token-cache usability only.

- **Endpoint called (exactly one):** `https://graph.microsoft.com/v1.0/me`
- **HTTP status:** `200` · **Content-Type:** `application/json` · **`me_exit=0`**
- **Token cache:** the existing NAS cache was read and used silently (`acquire_token_silent` via the repo's
  `DelegatedAuthProvider.get_token`). No re-login, no device code.

## Why WARN (not PASS) — procedural only
The one-shot `docker run` required **`--network host`** due to the known Docker **default-bridge DNS instability** on
this Synology (same platform issue observed in N5C-A). No Graph/auth/credential defect was observed; the token cache
was valid and Graph accepted the token on the first attempt. This is the sole WARN driver.

## Sanitized result (key names + hashes only — no raw PII/tokens)
```
status=ok  graph_endpoint=/v1.0/me  http_status=200  content_type=application/json
response_keys = <field NAMES only>
account_proof: upn_sha256_12=<12-char hash>  id_present=true  mail_present=true  displayName_present=true
raw_body_printed=false  tokens_printed=false
```
No `displayName`, `mail`, `userPrincipalName`, `id`, tokens, authorization headers, device-code/login-URL, or MSAL
cache contents were printed or committed.

## Pre/post posture (unchanged)
| Item | Pre | Post |
|---|---|---|
| auth dir | `700 personal-assistant-svc:users` | `700 personal-assistant-svc:users` |
| token cache | `600 svc:users size=9623 mtime=1783159254` | **same** (`600`, `9623`, `1783159254`) — **no MSAL refresh** |
| svc cache readable | — | `yes` |
| DB | `size=4151631872 mtime=1783155303 svc:users 600` | **same** (untouched) |
| hb containers | `0` | `0` (`lingering=0`) |
| port 8000 | `not_listening` | `not_listening` |
| temp script | `written=yes` | `removed=yes` |

The token cache did **not** change (no silent refresh needed this run), so the "cache-refresh" WARN condition does
**not** apply — WARN is purely the `--network host` requirement.

## Scope / limits (explicit)
- N5C-B proved **NAS token-cache usability for Graph `/me`** (profile metadata) only.
- N5C-B did **not** prove mail/calendar/file scopes and did **not** call any mail/calendar/file/OneDrive/SharePoint
  endpoint.
- N5C-B did **not** perform source ingestion, card generation, or any DB access.
- **Scope minimization** (write-capable `Calendars.ReadWrite.Shared` / `Files.ReadWrite.All`) remains a later review
  item carried from N5C-A — unchanged here.
- **Docker bridge DNS instability** remains a separate platform issue; `--network host` was used only for this bounded
  one-shot smoke, not adopted as a runtime default.

## Boundaries held (see 08)
No backend/compose · no MCP · no scheduler/watcher · no source ingestion · no mail/calendar/file/OneDrive/SharePoint/
Procore/vault reads · no card generation · no DB writable open/mutation · no Cloudflare · no Tailscale Serve/Funnel ·
no router/firewall/Portainer change · no token/cache/device-code/login-URL/raw-Graph-body committed · no push/PR.

## Evidence index
`01-preflight.md` · `02-repo-truth-graph-command.md` · `03-token-cache-posture.md` · `04-graph-me-command.md` ·
`05-graph-me-result-sanitized.md` · `06-cache-post-run-posture.md` · `07-db-and-process-boundaries.md` ·
`08-boundaries-maintained.md` · `09-git-status.md` · `local-sensitive/README.md` (gitignored).
