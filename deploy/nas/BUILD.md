# NAS Build Guide

How to produce the `hb-personal-assistant:nas` image for viewer mode.

## Runtime constraints (always)

- **Runtime must NOT use host networking.**
- **Runtime publish must be loopback only** (`127.0.0.1:8000`).
- **`start.sh` never builds implicitly** — image must exist before `compose up --no-build`.

## Option A — Prebuild / load (preferred short-term)

Build on a functioning machine (Mac/CI) with working Docker bridge DNS:

```sh
cd /path/to/hb-personal-assistant
docker build -f deploy/nas/Dockerfile -t hb-personal-assistant:nas .
docker save hb-personal-assistant:nas | gzip > hb-personal-assistant-nas.tar.gz
```

Transfer to NAS (tar over SSH if scp unavailable), then on NAS:

```sh
sudo docker load < hb-personal-assistant-nas.tar.gz
sudo docker images hb-personal-assistant:nas
```

## Option B — NAS build with host-network workaround

When NAS Docker **bridge DNS is broken** (N4C/N4C-PR-A observed PyPI resolution failures in bridge builds):

```sh
cd /path/to/staged/repo
sudo docker build --network host -f deploy/nas/Dockerfile -t hb-personal-assistant:nas .
```

**`--network host` is build-time only** — never use host networking for `compose up` runtime.

## Option C — Long-term fixes (deferred)

1. Fix Synology Docker bridge DNS (daemon investigation).
2. Vendor/cache Python wheels in build context for offline-ish NAS builds.
3. CI publish signed images to a registry the NAS can pull (future).

## Verify image before start

```sh
docker image inspect hb-personal-assistant:nas
deploy/nas/scripts/start.sh   # fails closed if image missing
```

## Do not

- Weaken `.dockerignore` secret/DB exclusions.
- Bake live config, secrets, or DB files into the image.
- Run `docker compose up --build` in viewer production start path.

See [VIEWER_MODE.md](VIEWER_MODE.md) for runtime posture.
