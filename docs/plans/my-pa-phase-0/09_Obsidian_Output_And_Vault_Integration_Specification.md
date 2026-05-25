# Obsidian Output and Vault Integration Specification

Prepared: 2026-05-25

## Paths

- Primary: `Daily Notes/YYYY-MM-DD.md`
- Companion: `AI Outputs/Daily Knowledge Brief - YYYY-MM-DD.md`
- References: `Work/References/`

## Markers

```markdown
<!-- HB-DAILY-BRIEF:START -->
generated content
<!-- HB-DAILY-BRIEF:END -->
```

Rules: replace only bounded content, append markers if absent, create note if missing, preserve all user text outside markers, preserve completed task state when source identity matches.

## Frontmatter

```yaml
type: "brief"
domain: "work"
status: "active"
tags: [work, daily-brief]
source:
  kind: "graph-derived"
related: []
owner: "Bobby Fetting"
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
last_reviewed: "YYYY-MM-DD"
```

## Sections

Priority Actions, Meeting Prep, Follow-Ups, Waiting On, File Review Queue, Project / Workstream Signals, Sources.

## Task Syntax

Plain Markdown first. Optional Tasks metadata only for high-confidence due/priority fields.

## Source Links

Every generated bullet/action/prep item must include a Graph/M365 link, Obsidian wikilink, local source ID, or cached-file hash relationship.
