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
echo "$PUBLISH_LINE" | grep -q '0.0.0.0' && fail "0.0.0.0 publish forbidden"
echo "$ACTIVE" | grep -q '8000' && fail "port 8000 must not appear in MCP compose"
echo "$ACTIVE" | grep -q 'hb-personal-assistant-backend' && fail "backend service must not appear in MCP compose"
echo "$ACTIVE" | grep -q 'hb-personal-assistant-mcp' || fail "missing hb-personal-assistant-mcp service"
echo "$ACTIVE" | grep -q 'HB_MCP_NAS_READONLY' || fail "missing HB_MCP_NAS_READONLY"
echo "$ACTIVE" | grep -q '/app-support/auth' && fail "auth mount forbidden" || true
echo "$ACTIVE" | grep -q 'text-vault' && fail "text-vault mount forbidden" || true

pass "compose-mcp.yaml static guards"
