# 13 — `syn-work` ACL Read-Only Enforcement + Write-Denial Proof

Bounded follow-up verification (2026-07-04) after a read-only ACL was assigned to `personal-assistant-svc` on the
`syn-work` NAS-native path. **Read/stat + write-denial only — nothing activated, nothing copied, no full enumeration.**

Target: `/volume1/homes/bfetting/Work` (+ known top segments `NAS - HB`, `Altman`).

## ACL proof (Synology `synoacltool -get`)
```
Owner: [bfetting(user)]
 [0] user:personal-assistant-svc:allow:r-x---a-R-c--:fd--  (level:0)
 [1] user:bfetting:allow:rwxp-DaARWc--:fd--                (level:1)
 [2] group:users:allow:r-x---a-R-c--:fd--                  (level:1)
 [3] everyone::allow:r-x---a-R-c--:fd--                    (level:1)
```
- Entry **[0]** is an explicit `personal-assistant-svc` ACE granting **`r-x`** (read + traverse) plus attribute/ACL
  read bits (`a-R-c`). It grants **no `w` (write), no `p` (append/create-child), no `D` (delete-child), no `d`
  (delete)**. Inheritance `fd--` applies it to files and directories beneath `Work`.
- No ACE anywhere in the list grants write to svc (bfetting alone has `rwxp…`). The path carries a `+` (ACL present),
  so the ACL is authoritative over the compat `777` mode bits.
- **Conclusion:** the ACL enforces read-only for the service user at the filesystem layer, and the empirical test below
  confirms it in practice.

## Service-user read/stat proof
```
svc_read_Work=yes
svc_read_NAS_HB=yes
svc_read_Altman=yes
svc_list_Work=yes
```
`personal-assistant-svc` can stat/read `Work` and both known top segments, and list `Work`. Read access intact.

## Service-user write-denial proof (PASS iff writes FAIL)
Each attempt tried to create a unique hidden probe file `.hb-pa-write-proof-denied-<UTC-TS>` **as
`personal-assistant-svc`**:
```
WRITE_DENIED[Work]=yes      (Permission denied)
WRITE_DENIED[NAS - HB]=yes  (Permission denied)
WRITE_DENIED[Altman]=yes    (Permission denied)
```
All three writes were **denied**. No probe file was created.

## Leak check (no artifact left behind)
```
leaked_svc_view=0
leaked_bfetting_view=0
```
Neither the service-user view nor the control-user view finds any probe file → the denied writes created nothing;
nothing needs removal.

## Outcome
The `syn-work` read-only control now exists and is enforced at the **filesystem/ACL** layer: svc reads and traverses,
svc cannot write/append/delete. The prior N5B WARN driver — "no enforceable read-only protection on `syn-work`" — is
**RESOLVED**. (The missing `ExternalSourceRoot.read_only` schema field remains a code-quality / future-activation
hardening item; see `05`/`11`. It is no longer the active filesystem-control blocker.)
