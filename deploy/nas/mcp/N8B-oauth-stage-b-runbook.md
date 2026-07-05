# N8B OAuth — Stage B deploy + Cloudflare runbook

Stage A (OAuth 2.1 built onto `nas_mcp`, all local) is done and tested. Stage B activates it
in production and reconfigures the Cloudflare edge so the three OAuth-2.1-only web connectors
(Claude.ai, ChatGPT, Grok) can authenticate. **Operator (Bobby) runs every NAS-sudo and
Cloudflare-API step below** — the agent cannot (no passwordless sudo; no CF API token).

Fill these once (values live in your ops records / the N8B memory, NOT in git):

```sh
# --- your Cloudflare account-specific IDs (not secrets, but kept out of the repo) ---
export CF_ACCOUNT_ID=…            # Cloudflare account id
export CF_ZONE_ID=…               # zone for bobby-fetting.me
export CF_TUNNEL_ID=…             # PA-MCP tunnel id
export CF_ACCESS_APP_ID=…         # existing nas-mcp Access app id (service-token proof app)
# --- the SECRET: your scoped API token. Export it in your shell ONLY; never echo/commit it ---
export CF_API_TOKEN=…             # scopes: Access(Apps+Policies):Edit, Zone WAF:Edit
HOST=nas-mcp.bobby-fetting.me
```

---

## ⚠️ The one security decision to make consciously

To support OAuth-2.1-only web clients, **Cloudflare Access must be *bypassed* on `/mcp`**
(and on the OAuth/discovery paths). Those connectors cannot send Access service-token
headers, so the edge cannot authenticate them — authentication for `/mcp` moves to the
**origin OAuth/bearer** layer you just built.

- **What still protects `/mcp`:** origin OAuth token validation (audience-bound, 1 h expiry,
  revocable) **or** a static origin bearer; per-token scope→write denylist; rate limits;
  safe mode; the `remote_cloudflare` profile write-gates; the AI-Outputs folder-lock; plus
  edge WAF / Bot Fight Mode.
- **What you give up:** the edge Access identity/service-token requirement on `/mcp`. The
  origin is now genuinely internet-reachable and gated only by the origin credential.
- **Access still fully gates `/oauth/authorize`** — the one human step (grant consent) stays
  behind your SSO, so only you can approve a client.

This is inherent to onboarding web connectors; there is no configuration that both keeps
edge-Access on `/mcp` and lets Claude.ai/ChatGPT/Grok through. Proceed only if that posture
is acceptable. (Claude Desktop/Code, which *can* send headers, still work either way.)

---

## Part 1 — Rebuild + redeploy the image (activates `HB_MCP_OAUTH_ENABLED`)

The compose change (`HB_MCP_OAUTH_ENABLED=1`, `HB_MCP_PUBLIC_BASE_URL`, `HB_OAUTH_STORE_DIR`)
is already staged in `deploy/nas/mcp/compose-mcp.yaml`. The running image predates the
Stage-A code, so a rebuild is required.

**1a. On the Mac (cross-build amd64 → ship). Agent can run this half on request.**

```sh
cd <worktree>
docker buildx build --platform linux/amd64 --provenance=false --sbom=false \
  -f deploy/nas/Dockerfile -t hb-personal-assistant:nas --load .
docker save hb-personal-assistant:nas | gzip > /tmp/hb-nas-oauth.tar.gz
scp /tmp/hb-nas-oauth.tar.gz hb-nas:/tmp/          # your NAS ssh alias
```

**1b. On the NAS (sudo).**

```sh
# refresh the deploy tree (the NAS copy is a manual rsync, not a git checkout)
#   push compose-mcp.yaml + check-mcp-compose.sh from the worktree first, e.g.:
#   ssh hb-nas 'cat > /volume2/personal-assistant/deploy/nas/mcp/compose-mcp.yaml' < deploy/nas/mcp/compose-mcp.yaml
sudo docker load < /tmp/hb-nas-oauth.tar.gz
sh /volume2/personal-assistant/deploy/nas/mcp/check-mcp-compose.sh    # must PASS
cd /volume2/personal-assistant/deploy/nas/mcp
sudo docker compose -f compose-mcp.yaml up -d --force-recreate hb-personal-assistant-mcp
rm -f /tmp/hb-nas-oauth.tar.gz
```

**1c. Verify the OAuth surface is live at the origin (loopback, on the NAS).** No auth needed
for discovery; `/mcp` must still 401 without a credential.

```sh
curl -s http://127.0.0.1:8765/.well-known/oauth-protected-resource | python3 -m json.tool
#   expect: "resource":"https://nas-mcp.bobby-fetting.me/mcp", scopes ["nas.read","nas.write"]
curl -s http://127.0.0.1:8765/.well-known/oauth-authorization-server | python3 -m json.tool
#   expect: authorization_endpoint/token_endpoint/registration_endpoint, S256
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8765/mcp \
  -H 'accept: application/json, text/event-stream' -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
#   expect: 401  (origin still requires a credential)
```

---

## Part 2 — Cloudflare edge: gate `/oauth/authorize`, bypass the rest

Access matches the **most specific path**, so a path-scoped app on `/oauth/authorize` wins
over a catch-all bypass on `/`. All calls hit the CF API (`https://api.cloudflare.com`) with
`-H "Authorization: Bearer $CF_API_TOKEN"`.

**2a. Identity-gate the consent endpoint (only you can approve grants).**

```sh
curl -s -X POST \
 "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID/access/apps" \
 -H "Authorization: Bearer $CF_API_TOKEN" -H 'content-type: application/json' \
 --data @- <<JSON | python3 -m json.tool
{
  "name": "nas-mcp-oauth-authorize",
  "type": "self_hosted",
  "domain": "nas-mcp.bobby-fetting.me/oauth/authorize",
  "session_duration": "24h",
  "app_launcher_visible": false
}
JSON
# capture the returned app id → $AUTHZ_APP_ID, then attach an allow-Bobby-only policy:
curl -s -X POST \
 "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID/access/apps/$AUTHZ_APP_ID/policies" \
 -H "Authorization: Bearer $CF_API_TOKEN" -H 'content-type: application/json' \
 --data @- <<JSON | python3 -m json.tool
{ "name": "bobby-only", "decision": "allow", "precedence": 1,
  "include": [ { "email": { "email": "bfetting@outlook.com" } } ] }
JSON
```

**2b. Bypass Access for the machine-to-machine + resource paths.** Reconfigure the existing
`nas-mcp` app (`$CF_ACCESS_APP_ID`) — which today carries the service-token policy on the
whole host — to a **Bypass everyone** policy. It stays the catch-all (`/`), so it covers
`/mcp`, `/oauth/register`, `/oauth/token`, `/.well-known/*`, `/health`; the more-specific
`/oauth/authorize` app from 2a keeps SSO.

```sh
# list current policies to find the service-token policy id, then replace with a bypass:
curl -s "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID/access/apps/$CF_ACCESS_APP_ID/policies" \
 -H "Authorization: Bearer $CF_API_TOKEN" | python3 -m json.tool
curl -s -X POST \
 "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID/access/apps/$CF_ACCESS_APP_ID/policies" \
 -H "Authorization: Bearer $CF_API_TOKEN" -H 'content-type: application/json' \
 --data @- <<JSON | python3 -m json.tool
{ "name": "public-bypass-origin-oauth-guards", "decision": "bypass", "precedence": 10,
  "include": [ { "everyone": {} } ] }
JSON
# then DELETE the old service-token (non_identity) policy id from the list above.
```

> Keep the service-token itself around if you still want header-based access from Claude
> Desktop/Code; with `/mcp` bypassed it is no longer required, but it does no harm.

**2c. Exempt the host from Bot Fight Mode / managed challenge.** The connector backends
(server-to-server `register`/`token`/`mcp`) must not be challenged. Add a WAF skip rule:

```sh
curl -s -X POST \
 "https://api.cloudflare.com/client/v4/zones/$CF_ZONE_ID/rulesets/phases/http_request_firewall_custom/entrypoint" \
 -H "Authorization: Bearer $CF_API_TOKEN" -H 'content-type: application/json' \
 --data @- <<JSON | python3 -m json.tool
{ "rules": [ { "action": "skip",
   "action_parameters": { "products": ["bic","securityLevel"], "phases": ["http_ratelimit"] },
   "expression": "(http.host eq \"nas-mcp.bobby-fetting.me\")",
   "description": "N8B: skip bot/challenge for MCP OAuth connectors" } ] }
JSON
```

*(If Super Bot Fight Mode is on for the zone, add a Bot Management skip rule instead / as
well — verify in the dashboard that server-to-server calls to the host are not challenged.)*

**2d. Edge verification (from the Mac).**

```sh
# /mcp with no credential → 401 from the origin (edge no longer blocks it):
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://nas-mcp.bobby-fetting.me/mcp \
  -H 'accept: application/json, text/event-stream' -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'          # expect 401
# discovery reachable unauthenticated through the edge:
curl -s https://nas-mcp.bobby-fetting.me/.well-known/oauth-protected-resource | python3 -m json.tool
# /oauth/authorize in a BROWSER → Cloudflare SSO challenge (only you pass):
open "https://nas-mcp.bobby-fetting.me/oauth/authorize?response_type=code&client_id=probe&redirect_uri=https://example.com&scope=nas.read&code_challenge=x&code_challenge_method=S256"
#   expect: CF Access login page (not the origin). After SSO it will 400 (probe params) — that
#   is the ORIGIN responding, proving SSO passed and the path reaches the OAuth handler.
```

---

## Part 3 — Connect + prove each client

For each, add a **custom MCP connector** pointing at `https://nas-mcp.bobby-fetting.me/mcp`.
The client fetches discovery → does DCR → opens `/oauth/authorize` in your browser → you pass
CF SSO → the NAS consent page renders → **Approve** → client exchanges the code (PKCE) → calls
`tools/list` + a read tool.

- **Claude.ai (web):** Settings → Connectors → Add custom connector → URL above → follow the
  OAuth prompt → approve on the consent page → confirm the tool list loads.
- **ChatGPT:** Connectors / developer-mode custom MCP → same URL → same dance.
- **Grok:** custom MCP connector → same URL → same dance.

**Verify server-side (NAS):** each successful client shows up in the audit as an OAuth actor.

```sh
sudo tail -n 50 /volume2/personal-assistant/app-support/audit/mcp/mcp-audit-$(date +%Y%m%d).jsonl \
 | python3 -c 'import sys,json;[print(json.loads(l).get("auth_method"),json.loads(l).get("client_label"),json.loads(l).get("tool_name")) for l in sys.stdin]'
#   expect rows: oauth  chatgpt_<id>/<client>  tools/list|<read tool>
# and confirm the OAuth store persisted clients/tokens (hashed only):
sudo ls -la /volume2/personal-assistant/app-support/audit/mcp/oauth/
```

A read-only client (scope `nas.read`) calling `ai_outputs_card_upsert` must be denied with
`tool_denied_by_token_scope` — a good negative check to run from one connector if it exposes
the write tool.

---

## Rollback

1. `sudo docker compose -f compose-mcp.yaml up -d --force-recreate` after reverting the compose
   env (or set `HB_MCP_OAUTH_ENABLED=0`) → OAuth routes unmount, surface returns to bearer-only.
2. Re-add the service-token policy on `$CF_ACCESS_APP_ID` and delete the bypass policy →
   `/mcp` is edge-gated again (web connectors will stop working, by design).
3. Remove the `/oauth/authorize` app and the WAF skip rule.
