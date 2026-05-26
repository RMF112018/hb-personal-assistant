# 08 — Obsidian Output and Provenance Specification

## Objective

Upgrade the Obsidian output flow so generated daily notes and AI outputs carry source-linked provenance while preserving user-authored note content.

## Existing Writer Requirements To Preserve

- Marker bounded writes using:
  - `<!-- HB-DAILY-BRIEF:START -->`
  - `<!-- HB-DAILY-BRIEF:END -->`
- Preserve all content outside markers.
- Merge frontmatter without deleting unrelated user keys.
- Preserve task completion state where possible.
- Support dry-run mode.

## Phase 14 Additions

### 1. Source Map Section

Generated brief content should include a bounded source map:

```md
## Sources
- src=42 links=mentions, waiting_on
- src=57 links=parsed_from
```

### 2. Action Section Enhancements

Action lines should include stable source identity without exposing sensitive content:

```md
- [ ] Review redacted source item <!-- action:action:review:42:abc123 src:42 -->
```

### 3. `written_to_note` Provenance

When not in dry-run mode, the writer or caller should create `written_to_note` links from source records/actions to the generated note source record or note target record, depending on existing schema design.

If the schema does not currently model notes as source records, add a local `source_record` of type `obsidian:note` or equivalent only if repo truth supports this cleanly.

### 4. Dry-Run Provenance Preview

Dry-run must report what it would write and what links it would create.

## Frontmatter Requirements

Minimum frontmatter:

```yaml
type: brief
domain: work
status: active
tags:
  - work
  - daily-brief
source:
  kind: graph-derived + extraction
owner: Bobby Fetting
updated: YYYY-MM-DD
last_reviewed: YYYY-MM-DD
```

## Acceptance Criteria

- User content outside markers is unchanged in tests.
- Frontmatter is merged, not replaced wholesale.
- Re-running the same generated content is idempotent.
- Dry-run performs no file write and no DB mutation.
- Apply mode writes the note and records/updates source-link provenance.
- No full email bodies or full file contents appear in output.
