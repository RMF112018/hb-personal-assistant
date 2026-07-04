#!/bin/sh
# check-runtime-safety.sh — static safety validator for the NAS runtime scaffold (Phase N1B).
# Runs locally against the scaffold files (no Docker, no NAS, no DB). Exit 0 = all safe; nonzero = unsafe.
#
# Path/exposure checks operate on COMMENT-STRIPPED content (via `active`), so forbidden strings that
# appear only in explanatory comments do not trip a failure. The secret scan targets config-bearing
# files (compose/Dockerfile/yml/env) — not the scripts, which contain detection keywords by design.
#
# Usage:
#   deploy/nas/scripts/check-runtime-safety.sh [/path/to/rendered/hb-pa-config.yml]
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NAS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE="$NAS_DIR/compose.yaml"
DOCKERFILE="$NAS_DIR/Dockerfile"
NAS_CFG="$NAS_DIR/hb-pa-config.nas.example.yml"
SMOKE_CFG="$NAS_DIR/hb-pa-config.smoke.example.yml"

fails=0
pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; fails=$((fails+1)); }
have() { [ -f "$1" ]; }

# comment-stripped view of a file (removes # to end-of-line)
active() { sed 's/#.*//' "$1"; }
hasA()  { active "$1" | grep -qF -- "$2"; }         # active content contains fixed string
missA() { ! active "$1" | grep -qF -- "$2"; }       # active content lacks fixed string
hasAE() { active "$1" | grep -qE -- "$2"; }         # active content matches regex
missAE(){ ! active "$1" | grep -qE -- "$2"; }

echo "== files present =="
for f in "$COMPOSE" "$DOCKERFILE" "$NAS_CFG" "$SMOKE_CFG"; do
  if have "$f"; then pass "exists: ${f#"$NAS_DIR"/}"; else fail "missing: ${f#"$NAS_DIR"/}"; fi
done

echo "== compose safety =="
if have "$COMPOSE"; then
  hasA  "$COMPOSE" 'HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS: "1"' && pass "background workers disabled" || fail "worker kill switch missing/!=1"
  hasA  "$COMPOSE" 'HB_PA_CONFIG: /config/hb-pa-config.yml'      && pass "HB_PA_CONFIG set"            || fail "HB_PA_CONFIG missing"
  hasA  "$COMPOSE" ':8000:8000"'                                 && pass "publishes container port 8000" || fail "port 8000 mapping not found"
  hasA  "$COMPOSE" '${HB_PUBLISH_ADDR:-127.0.0.1}'               && pass "publish defaults to loopback" || fail "publish default is not loopback"
  missA "$COMPOSE" '0.0.0.0:8000'                                && pass "no 0.0.0.0 host publish"      || fail "compose publishes on 0.0.0.0"
  missA "$COMPOSE" '/Volumes'                                    && pass "no /Volumes (SMB) path"       || fail "compose references /Volumes"
  missA "$COMPOSE" 'Library/Application Support'                 && pass "no Mac app-support path"      || fail "compose references Mac app-support"
  missA "$COMPOSE" 'Documents/Obsidian Vault'                    && pass "no live Obsidian vault mount" || fail "compose mounts live Obsidian vault"
  missA "$COMPOSE" 'restart: "always"'                           && pass "restart != always"           || fail "restart policy is always"
  missA "$COMPOSE" 'restart: "unless-stopped"'                   && pass "restart != unless-stopped"    || fail "restart policy is unless-stopped"
  if active "$COMPOSE" | grep -Eiq '^[[:space:]]+(scheduler|source-?watcher|watcher)[a-z-]*:'; then fail "a scheduler/watcher service appears defined"; else pass "no scheduler/watcher service"; fi
  hasA  "$COMPOSE" ':/config/hb-pa-config.yml:ro'               && pass "config mounted read-only"     || fail "config not mounted read-only"
fi

echo "== Dockerfile safety =="
if have "$DOCKERFILE"; then
  hasA "$DOCKERFILE" 'analytics.api:create_app' && pass "CMD uses create_app factory" || fail "CMD missing create_app factory"
  hasA "$DOCKERFILE" '"--factory"'              && pass "uvicorn --factory"            || fail "missing --factory"
  hasA "$DOCKERFILE" '"0.0.0.0"'               && pass "container binds 0.0.0.0 (namespace-internal)" || fail "container host not 0.0.0.0"
  hasA "$DOCKERFILE" '.[analytics-ui]'          && pass "installs analytics-ui extra"  || fail "analytics-ui extra not installed"
  hasA "$DOCKERFILE" 'HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1' && pass "workers disabled by image default" || fail "image missing worker kill switch"
  hasAE "$DOCKERFILE" '^FROM python:3\.(1[2-9]|[2-9][0-9])'     && pass "python >=3.12 base"           || fail "base image not python >=3.12"
  hasA "$DOCKERFILE" 'USER hbsvc'               && pass "runs as non-root user"        || fail "no non-root USER"
fi

echo "== example configs safety =="
if have "$NAS_CFG"; then
  hasA  "$NAS_CFG" 'application_support_root: /volume1/personal-assistant/app-support' && pass "nas cfg app-support is NAS-local" || fail "nas cfg app-support wrong"
  missA "$NAS_CFG" '/Volumes' && pass "nas cfg no /Volumes" || fail "nas cfg references /Volumes"
  missA "$NAS_CFG" 'Library/Application Support' && pass "nas cfg no Mac path" || fail "nas cfg references Mac path"
fi
if have "$SMOKE_CFG"; then
  hasA "$SMOKE_CFG" 'app-support-smoke' && pass "smoke cfg uses scratch root" || fail "smoke cfg not a scratch root"
  if active "$SMOKE_CFG" | grep -Eq 'application_support_root:[[:space:]]*/volume1/personal-assistant/app-support[[:space:]]*$'; then fail "smoke cfg points at LIVE app-support"; else pass "smoke cfg distinct from live app-support"; fi
  missA "$SMOKE_CFG" '/Volumes' && pass "smoke cfg no /Volumes" || fail "smoke cfg references /Volumes"
fi

echo "== no secret material in config-bearing files =="
SECRET_RE='(-----BEGIN|(client_secret|password|access_token|refresh_token|api_key|fernet)[[:space:]]*[:=][[:space:]]*["'\'']?[A-Za-z0-9/_+.-]{12,})'
secret_found=0
for f in "$COMPOSE" "$DOCKERFILE" "$NAS_CFG" "$SMOKE_CFG" "$NAS_DIR/.env.example"; do
  [ -f "$f" ] || continue
  if active "$f" | grep -Eq "$SECRET_RE"; then echo "  offender: ${f#"$NAS_DIR"/}"; secret_found=1; fi
done
[ "$secret_found" -eq 0 ] && pass "no embedded secret values" || fail "possible secret value in a config-bearing file"

echo "== optional: rendered runtime config =="
RCFG="${1:-}"
if [ -n "$RCFG" ]; then
  if [ -f "$RCFG" ]; then
    hasAE "$RCFG" 'application_support_root:[[:space:]]*/volume1/' && pass "rendered cfg app-support is /volume1 NAS-local" || fail "rendered cfg app-support not /volume1"
    missA "$RCFG" '/Volumes' && pass "rendered cfg no /Volumes" || fail "rendered cfg references /Volumes"
    missA "$RCFG" 'Library/Application Support' && pass "rendered cfg no Mac path" || fail "rendered cfg references Mac path"
  else
    fail "rendered config not found: $RCFG"
  fi
else
  printf 'SKIP  no rendered config path passed (validate examples only)\n'
fi

echo "-----------------------------------------"
if [ "$fails" -eq 0 ]; then
  echo "RESULT: PASS (all safety invariants hold)"; exit 0
else
  echo "RESULT: FAIL ($fails invariant(s) violated)"; exit 1
fi
