# 08 — NAS Runtime Config Plan

## Single seam: `paths.application_support_root`
`HB_PA_CONFIG` → YAML (`config/loader.py:49`); everything derives from `paths.application_support_root`
(`config/path_policy.py`). The rendered NAS config already sets it to `/volume1/personal-assistant/app-support`
(`deploy/nas/hb-pa-config.nas.example.yml`), so auth/security/text-vault/db/logs/cache all resolve correctly.
**No new YAML keys are required** for the Text Vault (key/blobs are files under `security/`).

## Config posture (keep as scaffolded)
- Config mounted **read-only**; app-support mounted r/w at the identical container path.
- `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1` (exact value) — keep; disables poll loop + source-root registration + watcher.
- Publish loopback (`HB_PUBLISH_ADDR=127.0.0.1`); `restart: "no"`; no scheduler/watcher service; no vault/source-root mounts.
- Add non-secret `identity.tenant_id`/`identity.client_id` to the rendered YAML only if they differ from defaults (for MSAL re-provision).

## Secrets stay OUT of YAML (env / protected files at runtime, N5+)
- Text Vault key: prefer the **key FILE** at `<app-support>/security/text-vault.key` (0600 svc) over env
  `HB_TEXT_VAULT_KEY`, to keep the key out of the process environment. (Copy deferred — see below.)
- `PROCORE_CLIENT_SECRET` / `PROCORE_ACCESS_TOKEN` / `HB_ANTHROPIC_API_KEY` via env or protected files only.

## Deferred (separate explicit authorization) — Text Vault key+blob copy spec
1. Non-privileged stage (bfetting, no sudo): `tar -C <source-vault> -cf - text-vault.key ./text-vault` piped over
   the ssh **exec** channel (`ssh … "cat > <nas-tmp>/vault.tar"`; NAS sshd has no SFTP, so no scp/rsync) into a
   bfetting-writable NAS tmp dir. Reversible; nothing privileged.
2. Operator interactive sudo (password-gated): create `<app-support>/security/text-vault` (0700), extract, set each
   `.enc` = 0600 + dir 0700, place `text-vault.key` 0600, `chown -R personal-assistant-svc:users`. Remove the tmp tar.
3. NAS coherence re-proof as svc read-only: count `.enc` blobs vs the 7,198 distinct refs (existence only; no
   decrypt, no print). Expect 0 missing.

Until step 2 runs, do not start any writable process against the copied app-support root (auto-migration write risk, 09).
