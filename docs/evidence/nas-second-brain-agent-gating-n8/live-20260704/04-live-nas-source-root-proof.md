# 04 — Live NAS Bounded Source Root — CLOSEOUT

**Verdict: PASS** — executed live on 2026-07-04 with per-step approval.

This closeout records the completed live Proof 04 (bounded NAS test source root). It supersedes the
pre-live runbook at `../20260704T154735Z/04-nas-source-root-proof.md` (which remains as the HOLD plan).

## Scope executed
A single **bounded, isolated** test source root was created on the NAS with three synthetic,
non-sensitive files, and a matching `ExternalSourceRoot` fragment was recorded to the uncommitted
`local-sensitive/` runtime config. **No DB, vault, card, scheduler, watcher, tunnel, or launchd action
occurred** — Proof 04 only laid down files + a config fragment and validated the fragment against the
`ExternalSourceRoot` schema (no database opened, no vault touched).

## Parameters (structural, non-secret)
- **Service root:** `/volume2/personal-assistant`
- **Test source root:** `/volume2/personal-assistant/test-source-root/`
- **source_root_key:** `nas_test` (distinct from Home/Work/Shared — isolation guaranteed by key + path)
- **Vault target:** NAS-local under `/volume2/personal-assistant/…` (asserted ≠ Mac vault — stop condition not tripped)

## Synthetic files (content hashes — synthetic, non-sensitive)
| rel_path | bytes | sha256 |
|---|---|---|
| `note-a.txt` | 89 | `9e96f009d9f191c4f6f2ef6f03bc91985a9afb406e4855c4cd96fe8828f7ea4b` |
| `note-b.txt` | 90 | `3b8ab5b3b386732d38caff9de19bc4431eaaeb117d9bda3490df02a08519cf4e` |
| `shared/x.txt` | 97 | `db5ca28c0267d2f59601460fa7181c9ce12f40beac7343a6424736f53b964e8f` |

Exactly 3 files under exactly 1 bounded root — no other source root was created or mutated.

## Local-sensitive runtime config (uncommitted, gitignored)
- **File:** `local-sensitive/proof04-nas-test-source-root.runtime.yml`
- **Size:** 456 bytes
- **SHA-256:** `bafdd01315fb8065588a4265ae8e4acf75d9f998e42e28e77c700aaacea96fce`
- Referenced by hash only; never committed (`.gitignore`: `/local-sensitive/`, `docs/evidence/**/local-sensitive/`).

## Confirmations
- **No DB / vault / card / scheduler / watcher / tunnel / launchd action occurred** during Proof 04.
- The `ExternalSourceRoot` fragment resolved and validated against schema (`nas_test` → the test root, `enabled: true`).
- **Proofs 05–07 remained on HOLD** at the time Proof 04 completed (05 ran later, separately approved; 06/07 still HOLD).
- No secrets, tokens, or raw document bodies were printed or recorded in committed evidence.
