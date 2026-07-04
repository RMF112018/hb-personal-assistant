# 00 — N4A Closeout (Text Vault key/blob copy + NAS coherence proof)

**Phase:** N4A — Text Vault key/blob copy to NAS + NAS-side coherence proof
**Result: PASS** · Timestamp `20260704T072304Z` · Worktree `ops/nas-copied-db-n3-20260704T060648Z` (HEAD `39961a35`)

## What happened
The Text Vault Fernet key + all encrypted `.enc` blobs were copied from the Mac source app-support root to the
NAS app-support `security/` root and proven coherent against the copied DB's encrypted references, read as the
demoted service user. The bounded write was split: the agent performed the non-privileged half (revalidation,
build a clean `ustar` bundle, stage to a bfetting-writable NAS tmp, verify by hash); the operator performed the
privileged half via interactive sudo (extract into `security/`, chown/chmod to least-privilege, cleanup, run the
service-user coherence proof). Both halves are recorded here.

## Result — PASS criteria met
| Criterion | Result |
|---|---|
| Source Text Vault coherence revalidated | ✔ 7,198/7,198 refs backed, 0 missing |
| Key copied to NAS `security/text-vault.key` | ✔ mode 600, owner `personal-assistant-svc:users`, size 44 |
| Blobs copied to NAS `security/text-vault/` | ✔ blob_count 7,202 |
| Least-privilege perms | ✔ `security/` 700, `security/text-vault/` 700, key 600, blobs 600, owner svc:users |
| NAS DB opened read-only only | ✔ `mode=ro`; main file unchanged (size/mtime = N3 placement) |
| NAS DB refs match NAS blobs | ✔ `distinct_refs=7198`, `refs_with_blob=7198`, `refs_missing_blob=0`, `COHERENT=YES` (orphans=4) |
| SQLite checks | ✔ `quick_check=ok`, `integrity_check=ok`, `schema=98`, `table_count=506` |
| Temp transfer artifacts removed | ✔ NAS tar + coherence helper removed; local tar removed |
| Redaction | ✔ no key/decrypted/refs/full-hash/IP in committable evidence |

## What was NOT done (out of scope, held)
No backend/MCP/scheduler/watcher start · no Cloudflare · no vault/source-root migration · no MSAL/Procore
re-provision (deferred to N5) · no direct svc SSH · no broad passwordless sudo · **no push / no PR**.

## Verdict rationale
Copy succeeded and NAS-side count coherence proves 0 missing blobs → **PASS**. No decrypt smoke was performed
(existence/count coherence is sufficient per scope; a bounded no-print decrypt smoke is deferred to N5 on a scratch root).

Evidence left **uncommitted** (commit is a separate authorization). Detail: `05`, `06`, `07`, `09`.
