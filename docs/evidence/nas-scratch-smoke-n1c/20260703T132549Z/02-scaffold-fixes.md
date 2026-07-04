# 02 — Scaffold Fixes Found During the Smoke (uncommitted)

The N1B scaffold built but the container **would not boot** until two real defects were fixed. Both are in
files already part of the committed N1B scaffold; the fixes are **uncommitted** in the worktree pending your
go-ahead to fold into the N1B commit (or a follow-up commit).

## Fix 1 — `deploy/nas/Dockerfile`: make the tree readable by the non-root user

**Symptom:** first boot crashed with `ModuleNotFoundError: No module named 'hb_assistant'`.
**Cause:** the image runs as non-root `hbsvc` (uid 1028). `COPY . /app` preserves the build context's POSIX
modes. The context was staged from an **ACL-backed Synology share** where `src/` reads as `drwxrwxrwx+` but
its underlying **POSIX mode is `0700`** (the `+` ACL grants the rest). Docker's `COPY` only sees POSIX bits,
so `/app/src` landed `700 root:root` — unreadable/untraversable by `hbsvc`.
**Fix:** after `COPY . /app`, add `RUN chmod -R a+rX /app` (read + traverse only; no write bits). This makes
the image robust regardless of how the context is staged (copy/tar/ACL share), not just `git clone`.

```
COPY . /app
RUN chmod -R a+rX /app        # readable by non-root hbsvc regardless of context source perms
RUN python -m pip install --upgrade pip && python -m pip install -e ".[analytics-ui]"
```

## Fix 2 — `.dockerignore`: stop excluding real source packages

**Symptom:** after Fix 1, boot crashed with `ModuleNotFoundError: No module named 'hb_assistant.auth'`.
**Cause:** the safety block used directory globs `**/auth/` and `**/security/` (intended to keep the runtime
**app-support** secret trees out of the image). But those globs **also match the source packages**
`src/hb_assistant/auth/` and `src/hb_assistant/security/`, so `COPY` silently dropped them.
**Verification:** both are real Python packages (`__init__.py` present) and contain **no secrets** — the only
token-ish name is `auth/token_cache_manager.py` (manager *code*). Runtime secrets live under the app-support
tree, which is **never in the build context** (context = `src deploy pyproject.toml README.md LICENSE .dockerignore`).
**Fix:** match secret *files* only; drop the two directory globs.

```
# before:  **/auth/   **/security/   **/text-vault*
# after:   (removed dir globs) — keep **/*.key  **/*.pem  **/msal-token-cache*.bin  **/text-vault.key  **/text-vault/
```

Also added (hygiene): `**/._*` and `**/.DS_Store` (macOS AppleDouble junk — 980 such files had been baked in),
and broadened `.env` → `**/.env` / `**/.env.*`.

## Why these are safe (no secret regression)
- The build context contains **only** source + packaging — no config, DB, auth, security, or vault material.
- `config/config.yml`, `**/*.key`, `**/*.pem`, `**/msal-token-cache*.bin`, `**/text-vault.key`, `**/text-vault/`
  remain excluded. A scan of `src/` confirmed **no** `*.key/*.pem/*.bin/*.enc` files and no secret content in
  `auth/` or `security/`.
- The image was rebuilt and boots + serves `/health` 200; live secrets are still supplied only at runtime via
  the `:ro` config mount and `HB_PA_CONFIG`.

## Recommendation
Fold both fixes into the N1B scaffold (amend `52d3d419` or a follow-up `fix(nas): …`). They are prerequisites
for the image to run as the intended non-root user in any staging method other than a clean `git clone`.
