# 05 — NAS Placement Proof

## Access resolution

Operator provisioned a dedicated passphrase-protected key `~/.ssh/hb_nas_bfetting_ed25519`
(`SHA256:fO8qltIXKduhtY93PGG/qXvgzsq5DJP9ijkoySNYXwk`), loaded into the ssh-agent, into bfetting's
`authorized_keys`. Key-only SSH (`PasswordAuthentication=no`) confirmed working via the agent.

## Transport note

NAS sshd has **no SFTP subsystem** (`scp` → "subsystem request failed on channel 0") and rsync's
ssh transport fell back to password. The plain ssh **exec** channel works, so the copy was streamed
with `ssh bfetting@nas "cat > <tmp>" < LOCAL_COPY`.

## Pre-placement probe (read-only, no sudo)

| Item | Result |
|---|---|
| bfetting identity | uid=1026, groups users + administrators |
| `/volume1` free | 13 TB (of 16 TB) — ample for 3.9 GB |
| target `…/db/hb-personal-assistant.sqlite` | **absent** (`TARGET_EXISTS=no`) → stop-and-ask #1 not triggered; placed at final intended path |
| db dir perms/owner | `drwxrwxrwx+` bfetting:users — bfetting writes directly, no sudo for placement |
| non-interactive sudo (`sudo -n true`) | **NO** (password required) — see finalization steps handed to operator |

## Placement sequence

1. Streamed to temp: `…/db/.hb-personal-assistant.sqlite.n3-upload-20260704T060648Z.tmp` (219 s, size 4,151,631,872 B).
2. SHA-256 of temp == local copy SHA (`4b2d8aab…eccc3`) — **match**.
3. `chmod 600` temp → atomic `mv` to final `…/db/hb-personal-assistant.sqlite` → `chmod 600`.
4. Final: `size=4,151,631,872 mode=600 owner=bfetting:users`; SHA unchanged.
5. Removed the 0-byte `-wal` + `-shm` sidecars created by the read-only validation open (main file fully checkpointed; SHA identical before/after removal) → clean single-file placement.

Final NAS DB path: `/volume1/personal-assistant/app-support/db/hb-personal-assistant.sqlite`
(final intended path, not a staged path). SHA in `local-sensitive/nas-copy.sha256`.

## Pending (operator sudo — password-gated)

Ownership is currently `bfetting:users` (600); the target end-state `personal-assistant-svc:users` requires
`sudo chown`, which cannot be done non-interactively. See `09-n3-verdict-and-next-phase.md` for the exact operator commands.
