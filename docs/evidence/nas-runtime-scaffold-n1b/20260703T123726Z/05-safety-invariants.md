# 05 — Safety Invariants (N1B)

These are enforced by `deploy/nas/scripts/check-runtime-safety.sh` and `tests/test_nas_runtime_scaffold.py`
(both run in `06`). Path/exposure checks operate on **comment-stripped** content so explanatory comments
never mask or falsely trip a check.

| # | Invariant | Enforced by |
|---|---|---|
| 1 | Scaffold files exist (Dockerfile, compose.yaml, both example configs, .dockerignore) | script + test |
| 2 | Compose disables background workers (`HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS: "1"`) | script + test |
| 3 | Compose sets `HB_PA_CONFIG=/config/hb-pa-config.yml` | script + test |
| 4 | Compose publishes container port **8000** | script + test |
| 5 | Publish defaults to **loopback** and never `0.0.0.0` | script + test |
| 6 | Compose has **no `/Volumes`** (SMB) path | script + test |
| 7 | Compose does **not** mount the Mac app-support (`Library/Application Support`) | script + test |
| 8 | Compose does **not** mount the live Obsidian vault (`Documents/Obsidian Vault`) | script + test |
| 9 | Restart policy is **not** `always`/`unless-stopped` | script + test |
| 10 | Config mounted **read-only** (`:ro`) | script + test |
| 11 | **No scheduler/watcher** service defined | script + test |
| 12 | Dockerfile CMD uses the `create_app` **factory** and binds `0.0.0.0` (container-internal) | script + test |
| 13 | Dockerfile installs `.[analytics-ui]`, base **python >=3.12**, runs **non-root** | script + test |
| 14 | NAS example config uses NAS-local `/volume1/...app-support`; no `/Volumes`, no Mac path | script + test |
| 15 | Smoke example uses a **separate scratch** root (`app-support-smoke`), never the live root | script + test |
| 16 | `.dockerignore` excludes `config/config.yml`, `*.sqlite`, `*.key`, `auth/`, `security/` | test |
| 17 | **No secret values** in config-bearing scaffold files | script + test |
| 18 | (Optional) a rendered runtime config is NAS-local and free of `/Volumes`/Mac paths | script (arg) |

## Design notes
- The secret scan targets config-bearing files (compose/Dockerfile/yml/env), **not** the scripts —
  which legitimately contain detection keywords — and ignores comments.
- The app-support mount uses an identical host↔container path, so the safety of
  `application_support_root` (checked in the config) transfers to the mount.
- These are **static** invariants. They do not, and cannot, prove runtime behavior — that is N1C's job,
  and only against a disposable scratch root.
