#!/bin/sh
# viewer-common.sh — shared guards for NAS read-only viewer lifecycle scripts.
# Source from other deploy/nas/scripts/*.sh (do not execute directly).
set -eu

VIEWER_IMAGE="${VIEWER_IMAGE:-hb-personal-assistant:nas}"
VIEWER_CONTAINER="${VIEWER_CONTAINER:-hb-personal-assistant-backend}"
DOCKER="${DOCKER:-/usr/local/bin/docker}"

if [ -z "${NAS_DIR:-}" ]; then
  _VC_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  NAS_DIR="$(cd "$_VC_SCRIPT_DIR/.." && pwd)"
fi

# Loopback-only host publish (never 0.0.0.0).
export HB_PUBLISH_ADDR="${HB_PUBLISH_ADDR:-127.0.0.1}"
case "$HB_PUBLISH_ADDR" in
  127.0.0.1|localhost) ;;
  *)
    echo "refusing: HB_PUBLISH_ADDR must be loopback (127.0.0.1); got '$HB_PUBLISH_ADDR'" >&2
    exit 2
    ;;
esac

export HB_CONFIG_FILE="${HB_CONFIG_FILE:-/volume1/personal-assistant/config/hb-pa-config.yml}"
export HB_APP_SUPPORT_DIR="${HB_APP_SUPPORT_DIR:-/volume1/personal-assistant/app-support}"

viewer_require_config() {
  if [ ! -f "$HB_CONFIG_FILE" ]; then
    echo "refusing: HB_CONFIG_FILE not found: $HB_CONFIG_FILE" >&2
    exit 2
  fi
}

viewer_require_compose_invariants() {
  _compose="$NAS_DIR/compose.yaml"
  if [ ! -f "$_compose" ]; then
    echo "refusing: missing compose.yaml at $_compose" >&2
    exit 2
  fi
  _active="$(sed 's/#.*//' "$_compose")"
  echo "$_active" | grep -qF 'HB_NAS_RUNTIME: "1"' || {
    echo "refusing: compose.yaml must set HB_NAS_RUNTIME=1" >&2
    exit 2
  }
  echo "$_active" | grep -qF 'HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS: "1"' || {
    echo "refusing: compose.yaml must disable background workers" >&2
    exit 2
  }
  echo "$_active" | grep -qF 'HB_PA_CONFIG: /config/hb-pa-config.yml' || {
    echo "refusing: compose.yaml must set HB_PA_CONFIG" >&2
    exit 2
  }
  echo "$_active" | grep -qF '${HB_PUBLISH_ADDR:-127.0.0.1}' || {
    echo "refusing: compose.yaml must default publish to loopback" >&2
    exit 2
  }
}

viewer_require_image() {
  if ! "$DOCKER" image inspect "$VIEWER_IMAGE" >/dev/null 2>&1; then
    echo "refusing: Docker image missing: $VIEWER_IMAGE" >&2
    echo "hint: build or load the image first (see deploy/nas/BUILD.md); start.sh never builds implicitly." >&2
    exit 2
  fi
}

viewer_compose() {
  (cd "$NAS_DIR" && "$DOCKER" compose -f compose.yaml "$@")
}
