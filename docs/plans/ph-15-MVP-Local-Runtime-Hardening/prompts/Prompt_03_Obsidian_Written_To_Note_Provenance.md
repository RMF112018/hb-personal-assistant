# Prompt 03 — Obsidian `written_to_note` Provenance

You are the local code agent operating in the `RMF112018/hb-personal-assistant` repository.

Do not work in `hb-intel`.

Do not re-read files that are still in your current context or memory. Use targeted greps and precise reads.

Prompt 9 / delegated Graph proof remains deferred pending Microsoft Graph admin consent. Do not work around that blocker with app-only runtime mail/calendar access.

Before modifying files, run the required starting checks and capture the actual repo state.

Expected starting HEAD for this phase:

`baac7b5cf61d461d3b544262d02ad4c051aa9fa1`


## Objective

Prove and, if necessary, implement `written_to_note` source-link creation for Obsidian note writes.

## Required Greps

```bash
grep -R "written_to_note" -n src/hb_assistant tests docs || true
grep -R "record_link" -n src/hb_assistant/obsidian src/hb_assistant/automation tests || true
grep -R "write_bounded_section" -n src/hb_assistant tests || true
```

## Required Behavior

- Dry-run returns would-be content and does not write note or source link.
- Apply path writes the marker-bounded section.
- Apply path records `source_links.link_type = 'written_to_note'` for relevant source(s).
- User content outside markers is preserved.
- Existing checked task state is preserved where supported.

## Tests

Add deterministic tests for:

- dry-run no write/no link;
- apply write + link;
- idempotent repeat write;
- marker-bound preservation;
- user content outside markers.

## Evidence

Create:

```text
docs/evidence/mvp-local-runtime/03-obsidian-written-to-note-proof.md
```

## Commit Message

```text
feat(obsidian): prove written-to-note provenance on apply
```
