# 05 — Next-Step Options to Unblock

The CLI (and MSAL login) needs a **Python 3.12+** runtime on the NAS. Three viable paths; each needs explicit
authorization because each expands scope beyond the current bounded proof.

## Option A — Docker/container CLI runtime (repo's intended path) — RECOMMENDED
Use the repo's `deploy/nas` container. Build/pull `hb-personal-assistant:nas` (`python:3.12-slim`), then run the CLI
inside it:
- `docker compose ... run --rm <svc> hb-assistant --help` (and `auth --help`, `auth login --help`) for the runtime proof.
- For the MSAL login, run `hb-assistant auth login` **inside the container** with the NAS `app-support/auth` dir
  **bind-mounted** so the cache lands at `/volume1/personal-assistant/app-support/auth/msal-token-cache.bin`, owned
  `personal-assistant-svc:users`, `600`. Device-code prompt prints to the container's stdout (TTY).
- **Requires:** lifting the "no Docker" boundary for a bounded container CLI/login proof; keeping backend/uvicorn OFF
  (run the CLI entrypoint only, not the server); `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1`; DB not mounted or mounted
  read-only.
- **Pros:** matches the intended production runtime; correct Python; reproducible. **Cons:** needs Docker
  authorization; must ensure the container runs only the CLI (no backend/MCP/watcher/DB migrate).

## Option B — Native Python 3.12+ interpreter (no Docker)
Obtain a 3.12+ interpreter without Docker: a Synology Python 3.12 package (if available in Package Center), `pyenv`,
or a portable python-build-standalone extract. Then venv + `pip install -e .` from the N4C repo.
- **Requires:** authorization for interpreter provisioning (download/extract/install).
- **Pros:** no Docker; lighter than a full backend image. **Cons:** unmanaged interpreter; must ensure `--help`
  imports trigger no DB/backend side effects (they should not — command bodies don't run on `--help`).

## Option C — Defer
Defer both the CLI runtime proof and N5C-A MSAL login to a dedicated runtime-provisioning phase (e.g., an "N4C-style"
container runtime phase), and keep N5C-A blocked meanwhile.

## Recommendation
**Option A** (container), because it is the repo's designed runtime and gives the correct Python with least ad-hoc
provisioning — provided you authorize a **bounded, CLI-only** container invocation (explicitly no backend/MCP/watcher,
no writable DB, cache-dir bind-mount only). If you prefer to avoid Docker entirely, **Option B**.

## Open question for the operator
How does your `n4c-backend-smoke` normally run the CLI/backend — via `deploy/nas/compose.yaml` (Docker), or another
mechanism? Confirming this pins the exact bounded command for the runtime proof.
