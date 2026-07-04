# 03 — NAS Target Preflight

Performed against the NAS (`<nas-host>`, SSH port 10021, user `bfetting`) before any placement.

## Target state before placement
- `/volume1/personal-assistant/vault/obsidian` — **ABSENT** (guard requirement). The mirror creates a fresh tree;
  it does not overwrite or merge an existing one.
- `/volume1/personal-assistant/app-support/tmp/` — present and **bfetting-writable** (staging for the tar stream).
- `/volume1/personal-assistant/app-support/` — owner/managed per N3/N4A (DB + Text Vault already placed here).

## Transfer constraints (unchanged from N4A)
- NAS sshd exposes **no SFTP subsystem** → `scp`/`rsync`/`sftp` fail. Transfer uses the SSH **exec channel**
  (`ssh "cat > <dest>" < <tarfile>`) with the dedicated passphrase-protected agent-only key via ssh-agent.
- The staged tar lands as bfetting-owned in the writable temp dir; the operator then extracts under
  `vault/obsidian` with `sudo` and applies svc ownership/perms.

## Guard
The extraction block explicitly refused to proceed if `vault/obsidian` already existed
(`if sudo test -e "$VT"; then echo STOP; exit 20; fi`). Guard passed (target was absent).
