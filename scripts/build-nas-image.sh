#!/usr/bin/env bash
# Build hb-personal-assistant:nas from a clean git-archive context (RT-01 Tier B).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

IMAGE="${IMAGE:-hb-personal-assistant:nas}"
PLATFORM="${PLATFORM:-linux/amd64}"
OUTPUT_DIR="${OUTPUT_DIR:-/tmp}"

die() { printf 'build-nas-image: %s\n' "$1" >&2; exit 1; }

require_clean_tree() {
  if ! git diff --quiet || ! git diff --cached --quiet; then
    die "refusing build: working tree or index is dirty (use git archive from clean HEAD)"
  fi
}

if [[ "${1:-}" == "--check-only" ]]; then
  require_clean_tree
  command -v docker >/dev/null 2>&1 || die "docker not found"
  command -v git >/dev/null 2>&1 || die "git not found"
  echo "build-nas-image: prerequisites ok"
  exit 0
fi

require_clean_tree

DEPLOY_SHA="$(git rev-parse HEAD)"
SHORT_SHA="$(git rev-parse --short HEAD)"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
STAGING="$(mktemp -d)"
trap 'rm -rf "$STAGING"' EXIT

printf 'build-nas-image: staging git archive at %s\n' "$DEPLOY_SHA"
git archive HEAD | tar -x -C "$STAGING"

MANIFEST_PATH="$STAGING/.hb-build-manifest.json"
python3 - <<PY
import json
from pathlib import Path
payload = {
    "deploy_sha": "$DEPLOY_SHA",
    "context_clean": True,
    "context_method": "git_archive",
    "build_timestamp": "$TS",
    "image_attestation_tier_target": "CODE_VERIFIED_CLEAN_CONTEXT",
}
Path("$MANIFEST_PATH").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

printf 'build-nas-image: docker build platform=%s\n' "$PLATFORM"
docker build --platform "$PLATFORM" \
  --build-arg "HB_BUILD_SHA=$DEPLOY_SHA" \
  --build-arg "HB_BUILD_COMMIT_VERIFIED=0" \
  --build-arg "HB_BUILD_TIMESTAMP=$TS" \
  -f deploy/nas/Dockerfile \
  -t "$IMAGE" \
  "$STAGING"

IMAGE_DIGEST="$(docker image inspect "$IMAGE" --format '{{.Id}}')"
printf 'build-nas-image: image digest %s\n' "$IMAGE_DIGEST"

printf 'build-nas-image: forbidden-path scan\n'
docker run --rm --entrypoint test "$IMAGE" ! -e /app/.claude
docker run --rm --entrypoint test "$IMAGE" ! -e /app/local_audit_outputs

TARBALL="$OUTPUT_DIR/hb-nas-${SHORT_SHA}.tar.gz"
BUILD_MANIFEST_OUT="$OUTPUT_DIR/hb-nas-${SHORT_SHA}.build-manifest.json"

docker save "$IMAGE" | gzip > "$TARBALL"
TARBALL_SHA="$(shasum -a 256 "$TARBALL" | awk '{print $1}')"

python3 - <<PY
import json
from pathlib import Path
base = json.loads(Path("$MANIFEST_PATH").read_text(encoding="utf-8"))
base.update({
    "image_digest": "$IMAGE_DIGEST",
    "image_tag": "$IMAGE",
    "tarball_path": "$TARBALL",
    "tarball_sha256": "$TARBALL_SHA",
    "tarball_bytes": Path("$TARBALL").stat().st_size,
    "forbidden_path_scan": "pass",
})
Path("$BUILD_MANIFEST_OUT").write_text(json.dumps(base, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

cat "$BUILD_MANIFEST_OUT"
printf '\nbuild-nas-image: OK\n  tarball=%s\n  sha256=%s\n' "$TARBALL" "$TARBALL_SHA"