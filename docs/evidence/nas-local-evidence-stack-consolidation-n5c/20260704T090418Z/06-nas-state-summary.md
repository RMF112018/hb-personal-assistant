# 06 — NAS State Summary (read-only consolidation snapshot)

Read-only metadata/count snapshot via the `bfetting` SSH control path (non-sudo where possible; one bounded sudo block
for the 700-svc Text Vault internals). **No DB opened; no secrets/key contents printed; no sensitive tree enumerated.**

| Item | Observed | Expected | OK |
|---|---|---|---|
| Copied DB | `-rw------- personal-assistant-svc:users`, size `4,151,631,872` | present, svc `600` (N3/N4A) | ✅ |
| Text Vault key | `mode=600 owner=personal-assistant-svc:users size=44` | 600 svc, 44 B (N4A) | ✅ |
| Text Vault blobs | `blob_count=7202` | 7202 (N4A) | ✅ |
| `security/` dir | `mode=700 owner=personal-assistant-svc:users` | 700 svc (N4A) | ✅ |
| Vault mirror | `/vault` + `/vault/obsidian` = `drwxr-x--- svc:users` | present (N5A) | ✅ |
| Vault md count | `svc_vault_md=155` (svc) / `155` (bfetting) | 155 (N5A/N5B) | ✅ |
| N5B scratch root | `app-support-smoke/n5b-20260704T082556Z` = `drwx------ svc:users` | present (N5B) | ✅ |
| `syn-work` ACL | ACE[0] `user:personal-assistant-svc:allow:r-x---a-R-c--:fd--` | read-only svc entry (N5B ACL) | ✅ |

## Consistency
- Text Vault internals (key mode/size, blob count, security perms) **match N4A exactly** → protected material intact
  and unchanged.
- Vault mirror still `155` md and svc-readable → N5A mirror intact.
- `syn-work` still carries the explicit svc read-only ACE → N5B ACL enforcement intact.
- DB present and svc-locked; **not opened** (read-only or otherwise) during this snapshot.

## Scope discipline
`ls -ld`/`stat` on directories only reveal directory metadata (owner/mode), obtained via parent-dir traversal — no
contents of `security/` or the scratch root were listed. `synoacltool -get` prints ACL entries only (no file data).
Redacted host + absolute NAS paths kept out of committable text where the convention requires; retained detail is in
`local-sensitive/`.
