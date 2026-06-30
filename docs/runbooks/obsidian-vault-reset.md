# Runbook — Obsidian Vault Quarantine Reset

Resets the polluted Obsidian vault into a clean Work/Home Markdown-first structure **without
deleting anything as a first move**. The current vault is *renamed aside* to a quarantine path; a
fresh vault is created at the same path. External source roots (OneDrive/Synology) are never
touched — the script only operates within `--vault-path`.

Script: `scripts/obsidian_vault_quarantine_reset.py` (stdlib only, **dry-run by default**).

## Preconditions
- Stop the backend first. The reset **refuses `--apply` while a backend listens on port 8000**
  (a running watcher must not race the rename).
- Default vault path: `/Users/bobbyfetting/Documents/Obsidian Vault`. A non-default path is refused
  unless `--allow-nonstandard-vault-path` is passed (tests / explicit operator use).

## Step 1 — Dry-run preview (safe, changes nothing)
```bash
python3 scripts/obsidian_vault_quarantine_reset.py \
  --vault-path "/Users/bobbyfetting/Documents/Obsidian Vault" \
  --evidence-dir docs/evidence/obsidian-source-runtime-reset/<TS> \
  --session-id <SESSION>
```
Writes a top-level **summary manifest** and prints the planned quarantine path + target tree.

## Step 2 — Full recursive manifest (REQUIRED review step before apply)
```bash
python3 scripts/obsidian_vault_quarantine_reset.py \
  --vault-path "/Users/bobbyfetting/Documents/Obsidian Vault" \
  --evidence-dir docs/evidence/obsidian-source-runtime-reset/<TS> \
  --session-id <SESSION> --full-manifest
```
Records every file (relative path, kind, ext, size, mtime, top folder, classification, planned
disposition). No content hashing. Review it before applying.

## Step 3 — Apply (destructive; quarantine-first)
`--apply` **refuses** unless the full manifest for the exact vault path + this `--session-id`
already exists (Step 2).
```bash
python3 scripts/obsidian_vault_quarantine_reset.py \
  --vault-path "/Users/bobbyfetting/Documents/Obsidian Vault" \
  --evidence-dir docs/evidence/obsidian-source-runtime-reset/<TS> \
  --session-id <SESSION> --apply
# add --copy-safe-obsidian-settings to carry over app/appearance/hotkeys only
```
Renames the old vault to `Obsidian Vault - QUARANTINED - <SESSION>`, creates the clean tree +
README seeds, and writes a reset receipt (evidence dir + `99 System/Receipts/`).

## Rollback
```bash
# stop the backend, then:
rm -rf "/Users/bobbyfetting/Documents/Obsidian Vault"     # only if no new content was added
mv "/Users/bobbyfetting/Documents/Obsidian Vault - QUARANTINED - <SESSION>" \
   "/Users/bobbyfetting/Documents/Obsidian Vault"
```

## Quarantine deletion (separate, explicit, last)
```bash
python3 scripts/obsidian_vault_quarantine_reset.py \
  --evidence-dir docs/evidence/obsidian-source-runtime-reset/<TS> --session-id <SESSION> \
  --delete-quarantine \
  --confirm-path "/Users/bobbyfetting/Documents/Obsidian Vault - QUARANTINED - <SESSION>"
```
Requires both `--delete-quarantine` and an exact `--confirm-path` whose name contains
` - QUARANTINED - `. Writes a deletion receipt.

## Target tree
`00 Inbox/` · `Work/{00 Dashboard…09 Archive}` · `Home/{00 Dashboard…09 Archive}` ·
`Source Notes/{Work,Home,Shared}` · `Daily/{Work,Home}` · `MOCs/{Work,Home,Shared}` ·
`Templates/{Source Cards,Meetings,Decisions,Projects,Daily,People,Companies}` · `Attachments/` ·
`90 Archive/` · `99 System/{Manifests,Receipts,Runbooks}`.
