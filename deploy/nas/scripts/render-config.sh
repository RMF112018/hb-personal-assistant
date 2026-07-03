#!/bin/sh
# render-config.sh — copy an example HB_PA_CONFIG to the NAS config location, then validate it.
# Does NOT start anything. No secrets are added. Refuses to overwrite unless --force.
#
# Usage:
#   deploy/nas/scripts/render-config.sh nas   [dest]   # production-intent config
#   deploy/nas/scripts/render-config.sh smoke [dest]   # disposable scratch config
#   add --force to overwrite an existing dest
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NAS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

kind="${1:-}"; shift 2>/dev/null || true
force=0; dest=""
for a in "$@"; do
  case "$a" in
    --force) force=1 ;;
    *) dest="$a" ;;
  esac
done

case "$kind" in
  nas)   src="$NAS_DIR/hb-pa-config.nas.example.yml";   [ -n "$dest" ] || dest="/volume1/personal-assistant/config/hb-pa-config.yml" ;;
  smoke) src="$NAS_DIR/hb-pa-config.smoke.example.yml"; [ -n "$dest" ] || dest="/volume1/personal-assistant/config/hb-pa-config.smoke.yml" ;;
  *) echo "usage: render-config.sh nas|smoke [dest] [--force]"; exit 2 ;;
esac

[ -f "$src" ] || { echo "source example not found: $src"; exit 1; }
if [ -e "$dest" ] && [ "$force" -ne 1 ]; then
  echo "refusing to overwrite existing $dest (pass --force to override)"; exit 1
fi

mkdir -p "$(dirname "$dest")"
cp "$src" "$dest"
echo "wrote: $dest"
echo "-- validating rendered config --"
"$SCRIPT_DIR/check-runtime-safety.sh" "$dest"
echo "REMINDER: add NO secrets to $dest until auth/security folder permissions are hardened."
