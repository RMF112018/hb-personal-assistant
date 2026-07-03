#!/bin/sh
# smoke-local.sh — LOCAL, STATIC validation of the scaffold. Does NOT start the backend or a container,
# does NOT touch any DB/secrets/vault. Safe to run on the Mac or the NAS.
#   1) runs the safety invariant checks
#   2) parses the example YAML configs
#   3) if docker is present, validates compose syntax via `docker compose config` (no build, no up)
set -eu
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NAS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "== [1/3] safety invariants =="
"$SCRIPT_DIR/check-runtime-safety.sh"

echo "== [2/3] YAML parse of example configs =="
if command -v python3 >/dev/null 2>&1 && python3 -c "import yaml" >/dev/null 2>&1; then
  for y in "$NAS_DIR/hb-pa-config.nas.example.yml" "$NAS_DIR/hb-pa-config.smoke.example.yml"; do
    python3 -c "import sys,yaml; yaml.safe_load(open(sys.argv[1])); print('ok:', sys.argv[1])" "$y"
  done
else
  echo "SKIP (python3 + PyYAML not available here; parses under the app venv/container)"
fi

echo "== [3/3] compose syntax (no build, no up) =="
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  ( cd "$NAS_DIR" && docker compose -f compose.yaml config >/dev/null && echo "ok: compose.yaml is valid" )
else
  echo "SKIP (docker compose not available here — validate on the NAS)"
fi
echo "smoke-local: done (static only; backend NOT started)."
