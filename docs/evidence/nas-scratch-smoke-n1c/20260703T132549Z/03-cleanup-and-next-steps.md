# 03 — Cleanup, Standing Changes & Next Steps

## What was removed from the NAS (disposable)
- `/volume1/personal-assistant/app-support-smoke/` — scratch app-support root (fresh throwaway SQLite DB).
- `/volume1/personal-assistant/_n1c_build/` — build context (incl. `.env.n1c`).
- `/volume1/personal-assistant/_n1c_evidence/` — NAS-side logs (pulled into `nas-artifacts/` first).

Confirmed after cleanup: live `app-support` = **0 files**, port **8000 free**, only `ubuntu-1` + `homeAssistant` running.

## What remains on the NAS (inert, non-sensitive) — your call to keep or drop
| Item | Why kept | Remove with |
|---|---|---|
| Image `hb-personal-assistant:nas` (263MB) | Proven artifact; avoids a rebuild for N1D | `sudo docker image rm hb-personal-assistant:nas` |
| `config/hb-pa-config.smoke.yml` | Harmless scratch example (points at `app-support-smoke`) | `rm /volume1/personal-assistant/config/hb-pa-config.smoke.yml` |

## ⚠ Standing privilege you should revoke now
The NOPASSWD sudo grant added so I could run docker non-interactively is **still active**:
`/etc/sudoers.d/hb-n1c-docker` → `personal-assistant-svc ALL=(ALL) NOPASSWD: /usr/local/bin/docker`.

Because it's docker-only and docker == root-equivalent, **any** process running as `personal-assistant-svc`
can now become root without a password. It was only needed for this smoke. **Revoke it** (interactive sudo,
one prompt) in a NAS shell:

```sh
sudo rm -f /etc/sudoers.d/hb-n1c-docker && echo revoked && sudo -n /usr/local/bin/docker version >/dev/null 2>&1 && echo "STILL ACTIVE" || echo "confirmed: passwordless docker revoked"
```

I did not remove it myself — revoking a security grant is appropriately your action, and `rm` isn't covered by
the (docker-only) grant so I couldn't do it without a password anyway. (I also could not read `/etc/sudoers.d`
as the svc user to re-verify it — that dir is root-only, `drwxr-x---`.)

## Also outstanding from earlier phases (unchanged by N1C)
- SSH password **rotation** in progress (per your note) — good; the shared password was never written to disk by me.
- `auth`/`security` on live app-support still **0777 + broad ACL** — must be hardened **before** any secret lands (N1A `04`).
- Public WAN exposure still **operator-unconfirmed** (DSM firewall + router + Tailscale Funnel) — N1A `06`.
- `personal-assistant-svc` still in `administrators` — runtime-user split deferred (N1A `03`).

## To re-run N1C later (if image/context were removed)
1. Re-stage context: `COPYFILE_DISABLE=1 tar czf - src deploy pyproject.toml README.md LICENSE .dockerignore | ssh … 'mkdir -p …/_n1c_build && tar xzf - -C …/_n1c_build && chmod -R a+rX …/_n1c_build'`
2. `.env.n1c` (paths only): `HB_PUBLISH_ADDR=127.0.0.1`, `HB_CONFIG_FILE=…/hb-pa-config.smoke.yml`, `HB_APP_SUPPORT_DIR=…/app-support-smoke`
3. `sudo docker compose --env-file …/.env.n1c -f …/deploy/nas/compose.yaml build && … up -d` → curl `127.0.0.1:8000/health` → `… down`.

## Prohibited until separately authorized (per N1C scope)
Copied-DB smoke · live DB migration · credential/secret migration (MSAL/Procore/Text-Vault) · production
restart policy · `0.0.0.0` publish · firewall/exposure changes · cutover. **N1C ends here.**

## Suggested next phase
**N1D — permission/user hardening + exposure confirmation** (the N1A deferred blockers), *then* **N2 — safe DB
migration via SQLite backup API + secret provisioning**, then a controlled cutover. Also fold the `02` scaffold
fixes into the N1B commit.
