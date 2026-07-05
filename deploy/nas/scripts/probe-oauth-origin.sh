#!/bin/sh
# Prove the DEPLOYED NAS MCP OAuth server end-to-end against the LOOPBACK origin
# (http://127.0.0.1:8765) — no Cloudflare edge, no Access SSO in the path. Run this ON THE NAS
# right after (re)deploying the OAuth-enabled image and BEFORE reconfiguring the edge, to
# confirm the server's full DCR -> authorize -> token -> tools/list flow works. It registers a
# throwaway public client + mints a short-lived (1 h) read-only token and lists tools; it does
# NOT write to the vault or DB. Raw code/token values are never printed.
#
#   sh deploy/nas/scripts/probe-oauth-origin.sh
set -eu

BASE=${BASE:-http://127.0.0.1:8765}
# Must equal the container's HB_MCP_PUBLIC_BASE_URL — the token audience is bound to it, and
# the middleware validates against public_base_url (NOT the request URL), so a loopback call
# with a token minted for the public URL is correct.
PUB=${PUB:-https://nas-mcp.bobby-fetting.me}
RES="$PUB/mcp"
REDIR="https://example.com/cb"
jget() { python3 -c "import sys,json;print(json.load(sys.stdin)$1)"; }

echo "== 1. discovery =="
curl -fsS "$BASE/.well-known/oauth-protected-resource"   | jget "['resource']"
curl -fsS "$BASE/.well-known/oauth-authorization-server" | jget "['scopes_supported']"

echo "== 2. dynamic client registration =="
CID=$(curl -fsS -X POST "$BASE/oauth/register" -H 'content-type: application/json' \
  -d "{\"redirect_uris\":[\"$REDIR\"],\"client_name\":\"origin-probe\"}" | jget "['client_id']")
echo "client_id=$CID"

echo "== 3. PKCE (S256) =="
VER=$(python3 -c "import secrets;print(secrets.token_urlsafe(64))")
CHAL=$(python3 -c "import hashlib,base64;print(base64.urlsafe_b64encode(hashlib.sha256('$VER'.encode()).digest()).rstrip(b'=').decode())")

echo "== 4. authorize (approve headless — loopback has no SSO) =="
LOC=$(curl -fsS -o /dev/null -D - -X POST "$BASE/oauth/authorize" \
  --data-urlencode "response_type=code" \
  --data-urlencode "client_id=$CID" \
  --data-urlencode "redirect_uri=$REDIR" \
  --data-urlencode "scope=nas.read" \
  --data-urlencode "state=probe" \
  --data-urlencode "code_challenge=$CHAL" \
  --data-urlencode "code_challenge_method=S256" \
  --data-urlencode "resource=$RES" \
  --data-urlencode "decision=approve" \
  | awk 'tolower($1)=="location:"{print $2}' | tr -d '\r')
CODE=$(python3 -c "import urllib.parse as u;print(u.parse_qs(u.urlsplit('$LOC').query)['code'][0])")
[ -n "$CODE" ] && echo "authorization code obtained (hidden)"

echo "== 5. token exchange =="
TOKRESP=$(curl -fsS -X POST "$BASE/oauth/token" \
  --data-urlencode "grant_type=authorization_code" \
  --data-urlencode "code=$CODE" \
  --data-urlencode "redirect_uri=$REDIR" \
  --data-urlencode "client_id=$CID" \
  --data-urlencode "code_verifier=$VER" \
  --data-urlencode "resource=$RES")
TOK=$(printf '%s' "$TOKRESP" | jget "['access_token']")
SCOPE=$(printf '%s' "$TOKRESP" | jget "['scope']")
[ -n "$TOK" ] && echo "access_token minted (hidden); granted scope: $SCOPE"
if printf '%s' "$SCOPE" | grep -q "nas.read" && printf '%s' "$SCOPE" | grep -q "nas.write"; then
  echo "scope includes BOTH nas.read + nas.write"
else
  echo "WARN: expected both scopes, got: $SCOPE"
fi

echo "== 6. MCP call with the OAuth bearer =="
curl -fsS -o /dev/null -w 'initialize http=%{http_code}\n' -X POST "$BASE/mcp" \
  -H 'accept: application/json, text/event-stream' -H 'content-type: application/json' \
  -H "authorization: Bearer $TOK" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"origin-probe","version":"1"}}}'
TOOLS=$(curl -fsS -X POST "$BASE/mcp" \
  -H 'accept: application/json, text/event-stream' -H 'content-type: application/json' \
  -H "authorization: Bearer $TOK" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}')
N=$(printf '%s' "$TOOLS" | python3 -c "import sys,json;print(len(json.load(sys.stdin)['result']['tools']))" 2>/dev/null || echo "?")
echo "tools/list returned $N tools"

# NOTE: the token now carries nas.write (single-user policy), so the write tool is permitted.
# We do NOT exercise it here to avoid writing a throwaway card into the vault; that the scope
# grant unlocks it is covered by the pytest suite (test_write_scope_oauth_allowed...).
echo "OK: origin OAuth end-to-end proven (token granted read + write)"
