# N5A — Obsidian Vault Mirror + Non-Activated Config Draft — Closeout

**Verdict: PASS.**

## What N5A did
1. Mirrored the small, content-safe Obsidian vault from the Mac to a **NAS-local** path
   `/volume1/personal-assistant/vault/obsidian` (copy-only; the Mac vault stays authoritative).
2. Applied least-privilege ownership/perms: owner `personal-assistant-svc:users`, dirs `750`, files `640`.
3. Produced two **NON-ACTIVATED** config drafts (NAS `hb-pa-config` YAML + `obsidian_mcp_config` JSON) pointing at the
   NAS vault and the NAS-native `syn-work` root — drafts only, not placed, not activated.
4. Proved the mirror is reachable and structurally equivalent, and readable by the demoted service user.

## Result summary
| Check | Source (Mac vault) | NAS mirror | Match |
|---|---|---|---|
| Files (excl `.DS_Store`) | 221 | `nas_file_count=221` | ✅ |
| Markdown notes | 155 | `nas_md_count=155` | ✅ |
| Directories | 63 | (tar 284 entries = 221 files + 63 dirs) | ✅ |
| Symlinks | 0 | 0 (none in tar) | ✅ |
| `.DS_Store` copied | — | 0 (excluded) | ✅ |
| Size | 4,446,272 B (~4.24 MiB) | equivalent (gnutar sha-matched on transfer) | ✅ |
| Service-user read | — | `svc_can_stat_dir=yes`, `svc_md_count=155` | ✅ |
| Ownership / perms | — | `personal-assistant-svc:users`, dirs `750` / files `640` | ✅ |

## Why PASS (vs the N5-planning WARN)
N5 planning closed WARN because the `syn-work` NAS-native path and a latent source-identity defect gated multi-root
*activation*. N5A does **not** activate anything: it mirrors the LOW-risk vault and writes non-activated drafts. Its
own acceptance criteria — mirror placed, counts equivalent, least-privilege perms, svc-readable, drafts non-activated,
boundaries held, redaction clean — are all met. The `syn-work` repoint and the identity fix remain deferred to their
established later phases and do not block this bounded mirror.

## Boundaries held (see 09)
No config activation · no source-root registration · no ingestion/card-gen · no backend/MCP/scheduler/watcher · no DB
open · no secrets/decrypted content/note bodies/source contents printed · Mac vault untouched · nothing pushed.

## Evidence index
- `01-preflight-from-n5.md` — carry-forward state from N5.
- `02-source-vault-inventory-redacted.md` — live source vault inventory.
- `03-nas-target-preflight.md` — NAS target absent-before + writable temp.
- `04-vault-transfer-execution-redacted.md` — tar-stream transfer (no SFTP) + operator sudo extract.
- `05-nas-vault-permissions-proof.md` — ownership/perms/least-privilege proof.
- `06-vault-mirror-equivalence-proof.md` — structural equivalence + svc-read proof.
- `07-config-drafts-non-activated.md` — the two drafts, explained, with the non-activation attestation.
- `08-source-root-readonly-guardrails.md` — `syn-work` read-only guardrail carried forward.
- `09-boundaries-maintained.md` — explicit non-actions.
- `10-rollback-plan.md` — how to undo (NAS-side only).
- `11-n5b-n5c-readiness.md` — what N5A unblocks.
- `12-git-status.md` — branch/HEAD/ahead + uncommitted posture.
- `drafts/` — the two non-activated config drafts.
- `local-sensitive/README.md` — where the un-redacted values live (gitignored, not committed).
