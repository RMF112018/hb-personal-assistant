# 04 — Login Execution (redacted)

## Command form (sanitized)
```
sudo /usr/local/bin/docker run --rm -it --network host --user 1028:100 \
  -e HB_PA_CONFIG=/config/hb-pa-config.yml \
  -e HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1 \
  -v <NAS-CONFIG-YML>:/config/hb-pa-config.yml:ro \
  -v /volume1/personal-assistant/app-support:/volume1/personal-assistant/app-support \
  hb-personal-assistant:nas \
  hb-assistant auth login --json
```
- `--network host` — chosen after diagnostics (below). Safe here because `auth login` **binds no ports** (outbound
  device-code client only) and the backend `CMD` is overridden. No inbound exposure.
- `--user 1028:100` — cache written as `personal-assistant-svc:users`.
- Config mounted read-only; app-support mounted so the cache persists to the NAS.

## Network attempts (device-code needs outbound DNS/HTTPS to Microsoft)
1. **Attempt 1 (default bridge):** failed — container could not resolve the Microsoft login endpoint hostname
   (the Microsoft login endpoint hostname), **before** any device code was issued. No token, no cache, no side effects.
2. **Diagnostics (no app-support mount, no login):** NAS host DNS ok; a bridge-HTTPS metadata probe **intermittently
   failed** name resolution while host-network DNS/TCP443/HTTPS all succeeded → Docker default-bridge embedded resolver
   is flaky on this Synology.
3. **Attempt 2 (`--network host`, gated on a host-network HTTPS probe = 200):** **succeeded**.

## Result (redacted)
- Device-code prompt displayed and completed in the browser by the operator. **The device code and login URL are not
  recorded** (operator redacted them; not in any evidence file).
- `login_exit=0`; `status=login_success`, `mode=delegated`.
- Delegated **account** identifier: **redacted** (kept in `local-sensitive/` only).
- **Effective delegated scopes (names):** `User.Read`, `Mail.Read`, `Calendars.ReadWrite.Shared`,
  `Files.ReadWrite.All`; reserved `offline_access` removed by the sanitizer.
- **No token values, refresh/access/ID tokens, or MSAL cache contents were printed to or stored in committable
  evidence.**
