#!/bin/sh
# Static guard for deploy/nas/mcp/compose-mcp.yaml
set -eu

ROOT="$(cd "$(dirname "$0")" && pwd)"
COMPOSE="${ROOT}/compose-mcp.yaml"

fail() { echo "FAIL  $1" >&2; exit 1; }
pass() { echo "PASS  $1"; }

[ -f "$COMPOSE" ] || fail "missing compose-mcp.yaml"

ACTIVE="$(sed 's/#.*//' "$COMPOSE")"

echo "$ACTIVE" | grep -q 'network_mode:[[:space:]]*none' && fail "network_mode:none forbidden in MCP compose"
echo "$ACTIVE" | grep -q 'ports:' || fail "ports section required"

PUBLISH_LINE="$(echo "$ACTIVE" | grep -E '^[[:space:]]*-[[:space:]]*".*:8765:8765"' | head -1 || true)"
[ -n "$PUBLISH_LINE" ] || fail "missing ports publish line"

echo "$PUBLISH_LINE" | grep -q '127.0.0.1:8765:8765' || fail "publish must be exactly 127.0.0.1:8765:8765"
echo "$PUBLISH_LINE" | grep -q '0\.0\.0\.0' && fail "0.0.0.0 publish forbidden"
echo "$ACTIVE" | grep -q '8000' && fail "port 8000 must not appear in MCP compose"
echo "$ACTIVE" | grep -q 'hb-personal-assistant-backend' && fail "backend service must not appear in MCP compose"
echo "$ACTIVE" | grep -q 'hb-personal-assistant-mcp' || fail "missing hb-personal-assistant-mcp service"
echo "$ACTIVE" | grep -q 'HB_MCP_NAS_READONLY' || fail "missing HB_MCP_NAS_READONLY"
echo "$ACTIVE" | grep -q 'HB_MCP_PROFILE:[[:space:]]*"remote_cloudflare"' || fail "MCP profile must be remote_cloudflare"
# N8B OAuth: when enabled, both a public base URL and a writable (RW-mounted) OAuth store
# dir must be pinned, else discovery/token audience is unbuildable or the store is unwritable.
if echo "$ACTIVE" | grep -q 'HB_MCP_OAUTH_ENABLED:[[:space:]]*"1"'; then
  echo "$ACTIVE" | grep -q 'HB_MCP_PUBLIC_BASE_URL:[[:space:]]*"https://' || fail "OAuth enabled but HB_MCP_PUBLIC_BASE_URL (https) not set"
  echo "$ACTIVE" | grep -q 'HB_OAUTH_STORE_DIR:[[:space:]]*/app-support/audit/mcp/' || fail "OAuth store dir must be under the RW-mounted /app-support/audit/mcp"
fi
echo "$ACTIVE" | grep -q '/app-support/auth' && fail "auth mount forbidden" || true
echo "$ACTIVE" | grep -q 'text-vault' && fail "text-vault mount forbidden" || true
echo "$ACTIVE" | grep -q '/volume2/personal-assistant/vault/obsidian.*/mnt/vault:rw' || fail "vault mount must map NAS obsidian vault to /mnt/vault:rw"
echo "$ACTIVE" | grep -q '/volume1/homes/bfetting/Home.*/mnt/roots/home:ro' || fail "home mount must map to /mnt/roots/home:ro"
echo "$ACTIVE" | grep -q '/volume1/homes/bfetting/Work.*/mnt/roots/work:ro' || fail "work mount must map to /mnt/roots/work:ro"
echo "$ACTIVE" | grep -q '/volume1/homes/bfetting/mcp-outputs.*/mnt/outputs:rw' || fail "outputs mount must map to /mnt/outputs:rw"
echo "$ACTIVE" | grep -q ':/app-support/audit/mcp:rw' || fail "audit mount must be /app-support/audit/mcp:rw"
# DB is a READ-ONLY snapshot mount (never the live DB); canonical path satisfies the guard.
echo "$ACTIVE" | grep -q ':/volume2/personal-assistant/app-support/mcp-snapshot/db:ro' || fail "db must be the read-only snapshot mount /volume2/personal-assistant/app-support/mcp-snapshot/db:ro"
echo "$ACTIVE" | grep -qE ':/(volume2/personal-assistant/app-support|app-support)/db:(ro|rw)' && fail "live DB dir must NOT be mounted into the internet-facing MCP (use the snapshot)" || true
echo "$ACTIVE" | grep -q ':/volume2/personal-assistant/app-support/analytics:rw' || fail "analytics mount (writable plan store) required"

pass "compose-mcp.yaml static guards"
