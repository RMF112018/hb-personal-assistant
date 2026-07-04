# 05 — Exact Docker Command Form for the Later MSAL Login (N5C-A)

**Reference only — NOT run in N5C-R2.** Provided so the separately-authorized N5C-A can use the proven runtime.

## Difference vs the N5C-R2 help proof
The help proof used `--rm --network none` and **no mounts**. The MSAL login differs in three necessary ways:
1. **Network required** — the device-code flow calls `login.microsoftonline.com` / Graph → **do not** use
   `--network none` (use the default bridge).
2. **Interactive TTY** — device-code prints a URL + short code and waits → needs `-it` so the operator can complete
   sign-in and the process blocks until done.
3. **Persist the cache to the NAS** — bind-mount app-support at an **identical container path** so
   `PathPolicy.get_auth_dir()` (= `application_support_root/auth`) resolves to the mounted NAS dir, and run as
   **1028:100** so the cache is owned `personal-assistant-svc:users`.

## Proposed command (to be confirmed/authorized in N5C-A)
```bash
sudo /usr/local/bin/docker run --rm -it \
  --user 1028:100 \
  -e HB_PA_CONFIG=/config/hb-pa-config.yml \
  -e HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1 \
  -v <NAS-CONFIG-YML>:/config/hb-pa-config.yml:ro \
  -v /volume1/personal-assistant/app-support:/volume1/personal-assistant/app-support \
  hb-personal-assistant:nas \
  hb-assistant auth login --json
```
- `<NAS-CONFIG-YML>` = the NAS config whose `paths.application_support_root` **equals**
  `/volume1/personal-assistant/app-support` (verify before running).
- Result: cache written to `/volume1/personal-assistant/app-support/auth/msal-token-cache.bin`, owner
  `personal-assistant-svc:users`, mode `600` (PathPolicy sets auth dir `700`).

## Preconditions to verify in N5C-A (do not assume)
1. `<NAS-CONFIG-YML>`'s `application_support_root` == `/volume1/personal-assistant/app-support` (else the cache lands
   in the wrong place). The NAS config at `<nas>/config/hb-pa-config.yml` exists — **verify its contents first**.
2. No pre-existing `msal-token-cache.bin` (confirmed absent now) — or explicit replacement authorization.
3. `auth login --json` is DB-safe (already proven in N5C-R: no store/DB/migrator import; writes only the cache).

## Safety notes / hardening options for N5C-A
- **DB exposure:** the full `app-support` mount includes `db/`, but `auth login` opens **no** DB (proven). To
  eliminate even the possibility, N5C-A may instead bind-mount **only** the auth subtree
  (`-v /volume1/personal-assistant/app-support/auth:/volume1/personal-assistant/app-support/auth`) **if** PathPolicy
  tolerates the narrower mount; otherwise use the full-tree mount above and rely on the proven no-DB-open behavior.
- **No backend:** command is overridden to `hb-assistant auth login` — uvicorn never starts.
- **No ports:** do not pass `-p` (login needs egress, not ingress).
- **Post-login proof:** stat the cache for `mode=600 owner=personal-assistant-svc:users`, confirm svc can read it,
  attest no token values printed — exactly the N5C-A §12 metadata proof.

## Status
CLI runtime **proven** (N5C-R2 PASS). MSAL login is **unblocked** but **NOT** attempted here; it remains for a
separate N5C-A authorization.
