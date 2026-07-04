# 03 — Transfer Plan and Boundaries

## Method
NAS sshd has no SFTP subsystem (established in N3) → **tar-stream over the ssh exec channel**.

1. Build a local `ustar`-format tarball (key + `text-vault/*.enc`) in the session scratchpad (outside the repo).
   `ustar` chosen deliberately: macOS `bsdtar`'s default format embeds xattr pax records that GNU tar on the NAS
   lists as extra entries (a 2× count) and would extract with warnings; `COPYFILE_DISABLE=1 tar --format ustar`
   yields exactly 7,204 clean entries (1 key + 1 dir + 7,202 blobs), 0 pax.
2. Stream to a bfetting-writable NAS temp: `<app-support>/tmp/n4a-…-ustar-<TS>.tar` (`ssh "cat > tmp.tar"`), 0600.
   Integrity verified by SHA-256 match (reported boolean-only; full hash in local-sensitive) + entry-count 7,204.
3. Stage a stdlib-only coherence helper (no `_key()`/decrypt) to the same NAS temp.
4. **Operator interactive sudo** (password-gated; agent cannot supply): guard-absent → extract into `security/` →
   `chown -R personal-assistant-svc:users` → dir 700 / key+blobs 600 → `security/` 700 → remove temp tar → run
   coherence as svc → remove helper.

## Temp locations
- Local scratch: session scratchpad (outside repo; 0700 dir, 0600 tar) — full path in local-sensitive.
- NAS temp: `<app-support>/tmp/` (777 bfetting) — removed after extraction.

## Boundaries enforced
No repo tarball/key/blob commit · no key contents/refs/decrypted text printed · no writable DB open · no
backend/MCP/watcher · privileged step strictly bounded (mkdir/tar-x/chown/chmod within `security/`, no broad sudoers).

## Cleanup requirements (all satisfied — see 04/08)
Local tar removed; NAS temp tar removed (by operator sudo block); coherence helper removed; no key material left in
scratch or repo.
