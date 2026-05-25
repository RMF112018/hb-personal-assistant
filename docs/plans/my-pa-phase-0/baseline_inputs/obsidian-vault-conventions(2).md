# Obsidian Vault Convention Discovery Report

## 1. Executive Summary
The vault uses a single-vault structure with clear top-level domains (`Work`, `Side Hustle`, `Knowledge`) and dedicated operational folders (`Daily Notes`, `Templates`, `AI Outputs`, `Agent Briefs`). A standardized frontmatter contract is present across core notes and ingested architecture notes. Internal linking is primarily Obsidian wikilinks with supplemental relative Markdown links in mirrored source content.

The strongest observed conventions are currently driven by the HB Intel architecture ingestion layer (`Work/HB Intel/Architecture/MASTER/**`), which dominates note volume. Recommendations below intentionally de-bias toward user-operational folders where evidence exists so Daily Brief output does not inherit machine-ingest noise.

## 2. Inspection Scope and Method
- Scope inspected: `/Users/bobbyfetting/Documents/Obsidian Vault` (read-only inspection).
- Methods used: directory and file inventories, sampled markdown/header/frontmatter reads, regex-based pattern scans for links/tags/tasks/markers, and `.obsidian` config/plugin inspection.
- Evidence handling: repeated-pattern preference over single-file inference; confidence labels applied (`High`, `Medium`, `Low`).
- Sensitive-content handling: no large note excerpts; only concise structural patterns and representative paths.
- Bias control: patterns classified as:
  - Operational/User-authored likely: `Daily Notes`, `Knowledge`, `Templates`, `AI Outputs`, `Agent Briefs`, high-level MOCs.
  - Generated/Ingested likely: `Work/HB Intel/Architecture/MASTER/**` and `Work/HB Intel/Architecture/_agent/tmp/**`.

## 3. Vault Folder Structure
Observed top-level folders:
- `AI Outputs/`
- `Agent Briefs/`
- `Archive/`
- `Daily Notes/`
- `Inbox/`
- `Knowledge/`
- `People/`
- `Side Hustle/`
- `Templates/`
- `Work/`
- `.obsidian/` (system config)
- `copilot/` (tooling/config)

Patterns:
- Operational structure is already in place for generated output (`AI Outputs`, `Agent Briefs`) and daily context (`Daily Notes`).
- `Work/` is dominated by ingested architecture mirrors.
- `Archive`, `Inbox`, `People` currently exist but have little/no markdown content yet.

Likely safe Daily Brief locations:
- Primary: `Daily Notes/` (if brief is integrated into daily note workflow).
- Secondary generated artifact: `AI Outputs/` (for system-produced synthesis outputs).

Folders that should not be touched by Daily Brief writer (except read/link):
- `.obsidian/`
- `Work/HB Intel/Architecture/_agent/tmp/`
- `Work/HB Intel/Architecture/MASTER/` (canonical mirrored corpus)

Generated-output folder recommendation:
- Reuse existing `AI Outputs/` and `Agent Briefs/`; do not create new top-level generated folders.

## 4. Daily Note Conventions
Evidence of daily notes exists but is limited.

Observed:
- Daily notes folder: `Daily Notes/`
- Observed filename pattern: `YYYY-MM-DD.md` (`Daily Notes/2026-05-24.md`)
- Obsidian daily note config points to:
  - folder: `Daily Notes`
  - template: `Templates/Template - Project Note`
- Current daily note sample uses project-style frontmatter/sections (likely template mismatch with true daily workflow intent).

Not sufficiently evidenced:
- Year/month subfolder partitioning.
- Weekday/weekend differences.
- Stable recurring daily-note body sections authored by user.

Recommended Daily Brief naming/location (based on current evidence):
- Use daily-note anchored date format `YYYY-MM-DD`.
- If standalone brief note is needed: `AI Outputs/Daily Knowledge Brief - YYYY-MM-DD.md` (already present pattern).
- If embedded in daily notes: bounded generated section inside `Daily Notes/YYYY-MM-DD.md`.

## 5. Frontmatter / Properties Conventions
Frontmatter usage is common in operational and ingested notes.

Strong recurring keys:
- `type`, `domain`, `status`, `tags`
- nested `source.kind` (+ `source.path`, `source.url`, `source.commit` for ingested notes)
- `related`
- `owner`
- `last_reviewed`, `created`, `updated`

Value style:
- Mostly quoted strings for scalar text/date-like fields.
- `tags` typically YAML arrays.
- `related` commonly a wikilink (sometimes scalar link value rather than array form).

Obsidian Properties:
- Core `properties` plugin enabled in `.obsidian/core-plugins.json`; vault clearly uses YAML properties heavily.

Recommended Daily Brief frontmatter fields:
- Preserve existing schema compatibility:
  - `type: "brief"`
  - `domain: "work"` (or `"knowledge"` when cross-domain synthesis)
  - `status: "active"`
  - `tags: [work, daily-brief]` (or `[knowledge, daily-brief]`)
  - `source.kind: "graph-derived"` or `"ai-generated"`
  - `related: []` with explicit links populated
  - `owner`, `created`, `updated`, `last_reviewed`

Fields to avoid introducing unless needed:
- Ad hoc incompatible date formats or custom property naming variants that diverge from existing standards.
- Parallel duplicate metadata keys when canonical equivalents exist.

## 6. Link Conventions
Observed link usage:
- Heavy use of Obsidian wikilinks `[[...]]` for internal navigation and MOC wiring.
- Markdown links `[label](relative/path.md)` heavily used in mirrored technical docs.
- External URL links present.
- Aliased wikilinks and embeds (`![[...]]`) not observed as dominant conventions in sampled operational notes.

Path style:
- Internal markdown links are relative paths in source-mirrored docs.
- Wikilinks usually path-like names anchored to vault note names.

Recommended source-link format:
- Outlook email source: stable deep link URL + human label (`[Email: Subject](https://outlook.office.com/...)`).
- Calendar event source: deep link URL + timestamp label.
- M365 file source: canonical SharePoint/OneDrive URL with descriptive label.
- Local cached file reference: relative vault path markdown link if cached under approved cache area.
- Related Obsidian notes: wikilinks (`[[Work/...]]`, `[[Daily Notes/YYYY-MM-DD]]`).

## 7. Tag and Taxonomy Conventions
Observed taxonomy guidance exists explicitly in `Knowledge/System Standards - Tag Taxonomy.md`.

Declared conventions:
- Lowercase hyphenated tags.
- Core: `#work`, `#side-hustle`, `#knowledge`
- Program: `#hb-intel`, `#construction-tech`
- Discipline: `#architecture`, `#api`, `#data-modeling`, `#integration`, `#spfx`, `#automation`
- Operational: `#risk`, `#decision`, `#operations`, `#preconstruction`, `#training`

Observed usage mode:
- Tags are primarily represented in frontmatter `tags` arrays.
- Inline hashtag usage in body exists but is less consistent and includes non-taxonomy contexts in large ingested corpus.

Recommended Daily Brief tags:
- Base: `daily-brief`
- Domain combos: `work`, `hb-intel`, `side-hustle`, `knowledge` as applicable
- Optional operational tags: `action-items`, `waiting-on`, `meeting-prep`

Tags to avoid:
- Over-granular one-off tags generated per source object (taxonomy pollution risk).

## 8. Task and Action Item Conventions
Observed task syntax:
- Standard markdown checkboxes are common in ingested architecture notes:
  - `- [ ] ...`
  - `- [x] ...`
- Strong evidence of Tasks-plugin-specific due/priority/recurrence syntax is still limited in sampled operational notes.

Plugin evidence:
- Dataview plugin installed and used.
- Tasks plugin is installed and enabled (`obsidian-tasks-plugin` in `.obsidian/community-plugins.json`).

Recommendation for generated Daily Brief action items:
- Emit standard markdown tasks first (`- [ ] ...`) for compatibility.
- Add concise source link on the same line or immediate child line.
- Optionally support Tasks syntax for due/priority fields where high-confidence values exist; keep base line valid as plain markdown task.

User edit preservation on task lines:
- Never regenerate user-edited lines outside generated marker bounds.
- Within generated sections, preserve explicitly completed checkbox states when source item identity matches.

## 9. Meeting Note Conventions
Direct meeting-note instances are not clearly established in operational folders; strongest evidence is template-level.

Template pattern (`Templates/Template - Meeting Note.md`):
- Frontmatter includes standard contract (`type: "meeting"`, domain/status/tags/source/related/owner/date fields).
- Section structure:
  - `## Attendees`
  - `## Agenda`
  - `## Notes`
  - `## Decisions`
  - `## Action Items`

Recommendation for future generated meeting-prep notes:
- Follow existing meeting template section ordering.
- Add `## Source Context` section with calendar/event links and related docs.

Confidence: Medium (template-backed, low operational sample count).

## 10. Project / Workstream Note Conventions
Observed:
- High-level MOCs under `Work/` and subdomains.
- HB Intel architecture notes use consistent metadata and strong linkage to a master MOC.
- `type` is used to classify (`moc`, `architecture`, `concept`, `brief`, etc.).

Project/workstream association recommendation:
- Use frontmatter `related` wikilinks to project MOCs and relevant domain hubs.
- Apply `domain` + `tags` for primary association rather than inventing new schema.
- For Daily Brief extracted items, include a project/workstream label in body and link to nearest MOC.

## 11. Template Conventions
Observed template folder:
- `Templates/`

Observed templates:
- `Template - Project Note.md`
- `Template - Architecture Decision.md`
- `Template - Meeting Note.md`
- `Template - Person Note.md`
- `Template - Weekly Knowledge Brief.md`

Template pattern:
- Shared frontmatter contract and structured section headings.

Recommendation:
- Add a dedicated Daily Brief template later (do not implement now), stored in `Templates/`.
- Suggested name: `Template - Daily Brief.md`.

## 12. Dataview / Plugin Compatibility
Evidence from `.obsidian`:
- Community plugins: `smart-connections`, `copilot`, `dataview`, `templater-obsidian`, `obsidian-tasks-plugin`.
- Core plugins include `daily-notes`, `templates`, `properties`.

Dataview compatibility evidence:
- `AI Outputs/00 Dataview Dashboards.md` includes Dataview queries keyed to frontmatter fields (`last_reviewed`, `type`, `domain`, `status`, `source.kind`, etc.).

Recommendations:
- Generated frontmatter should remain Dataview-friendly and schema-consistent.
- Generated tasks should remain plain markdown-task compatible first, with optional Tasks-plugin fields added only when source confidence is strong.
- Avoid custom syntax that Dataview cannot parse reliably.

## 13. Attachment and Resource Handling
Observed:
- Large volume of binary resources (`.pdf`, `.docx`, `.xlsx`, images) under `Work/HB Intel/Architecture/_agent/tmp/hb-intel/**` as mirrored source artifacts.
- No clear evidence of a dedicated user attachment folder convention for daily PKM notes.

Recommendation:
- Daily Brief system should avoid copying M365 files into vault by default.
- Prefer source URLs and reference notes over file duplication.
- If local cache is needed, isolate under a clearly scoped non-primary location and link explicitly.

## 14. Generated Content / Protected Section Recommendation
Observed:
- No established vault-wide marker pair convention detected for generated sections in operational notes.

Recommended marker format:
- `<!-- HB-DAILY-BRIEF:START -->`
- `<!-- HB-DAILY-BRIEF:END -->`

Behavior recommendation:
- Overwrite only content between marker pairs.
- If markers are missing, append a new generated block at end (or configured insertion point) without deleting user content.
- If malformed/unpaired markers are detected, do not overwrite automatically; emit a warning and create a sibling recovery note or log entry.

## 15. Recommended Daily Brief Output Convention
### Recommendation
Use `Daily Notes/YYYY-MM-DD.md` as the primary user-facing surface with a bounded generated section, and optionally maintain a companion machine summary in `AI Outputs/`.

### Rationale
`Daily Notes` is configured as the daily workspace, while `AI Outputs` already contains generated synthesis artifacts. This preserves user flow and existing generated-output patterns.

### Proposed Path / Filename Pattern
- Primary: `Daily Notes/YYYY-MM-DD.md` (inject/update generated section only)
- Optional companion: `AI Outputs/Daily Knowledge Brief - YYYY-MM-DD.md`

### Proposed Frontmatter
```yaml
---
type: "brief"
domain: "work"
status: "active"
tags: [work, daily-brief]
source:
  kind: "graph-derived"
  path: ""
  url: ""
  commit: ""
related: []
owner: "Bobby Fetting"
last_reviewed: "YYYY-MM-DD"
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
---
```

### Proposed Body Structure
- `# Daily Brief - YYYY-MM-DD`
- `## Priority Actions`
- `## Meeting Prep`
- `## Follow-Ups`
- `## Waiting On`
- `## File Review Queue`
- `## Cross-Domain Signals`
- `## Sources`

### Source-Linking Rules
- Every generated action should include at least one source link.
- Use markdown links for Graph/M365 URLs and wikilinks for vault references.
- Prefer stable deep links over transient URLs when available.

### User-Edit Preservation Rules
- Generated writes are limited to marker-bounded region only.
- User text outside markers is immutable.
- Completed user task state should be preserved where item identity matches.

### Risks / Watch Items
- Current daily note template points to `Template - Project Note`; this may produce schema/section mismatch until explicitly corrected.
- Limited existing daily-note samples reduce confidence on long-term daily layout expectations.

## 16. Recommended Reference Note Conventions
### Recommendation
Create separate reference notes for source entities (email thread, meeting/event, file review target) only when needed for reuse or multi-day tracking; otherwise keep source links inline in the daily brief.

### Rationale
Prevents note explosion while preserving traceability for high-value, recurring, or complex work items.

### Proposed Path / Filename Pattern
- Suggested folder (later): `Knowledge/References/` or `Work/References/` (final choice should align with user preference)
- Filename examples:
  - `Ref - Email - YYYY-MM-DD - <Subject>.md`
  - `Ref - Meeting - YYYY-MM-DD - <Title>.md`
  - `Ref - File - <System> - <Name>.md`

### Proposed Frontmatter
```yaml
---
type: "reference"
domain: "work"
status: "active"
tags: [work, reference]
source:
  kind: "m365"
  path: ""
  url: ""
  commit: ""
related: []
owner: "Bobby Fetting"
last_reviewed: "YYYY-MM-DD"
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
---
```

### Proposed Body Structure
- `## Summary`
- `## Key Decisions / Signals`
- `## Extracted Action Items`
- `## Linked Daily Briefs`
- `## Raw Source Links`

### Source-Linking Rules
- Include canonical source URL and immutable identifiers when available.
- Link back to each daily brief that references the note.
- Use wikilinks for in-vault cross-reference and markdown links for external systems.

### User-Edit Preservation Rules
- Writer may append new machine-extracted subsections only inside explicit generated markers.
- User-authored interpretation sections remain untouched.

### Risks / Watch Items
- No current explicit reference-note convention was found; this is an additive proposal and should be ratified before implementation.

## 17. Risks and Guardrails
Risks:
- Corpus skew: `Work/HB Intel/Architecture/MASTER/**` dominates note count and may bias conventions.
- Daily-note evidence is currently sparse (single observed file).
- Tasks plugin is enabled, but vault-level user style for advanced Tasks syntax is not yet strongly evidenced.

Guardrails:
- Keep generated outputs in existing generated folders or marker-bounded daily-note sections.
- Enforce existing frontmatter contract for Dataview compatibility.
- Never rewrite canonical mirrored architecture notes.
- Prefer links over file duplication for M365 artifacts.

## 18. Open Questions for Bobby
1. Should Daily Brief be embedded in `Daily Notes/YYYY-MM-DD.md` only, or always paired with a full note in `AI Outputs/`?
2. Should reference notes live under `Knowledge/References/` or `Work/References/`?
3. Should the daily note template be changed from `Template - Project Note` to a dedicated daily template before Daily Brief integration?

## 19. Evidence Appendix
| Convention Area | Evidence Path | Observed Pattern | Confidence |
|---|---|---|---|
| Top-level structure | `<VAULT>/` | Single-vault with `Work`, `Side Hustle`, `Knowledge`, `Daily Notes`, `Templates`, `AI Outputs`, `Agent Briefs` | High |
| Daily notes location | `Daily Notes/2026-05-24.md`; `.obsidian/daily-notes.json` | Daily note folder is `Daily Notes`; filename observed as `YYYY-MM-DD.md` | Medium |
| Daily note template config | `.obsidian/daily-notes.json` | Daily note template currently points to `Templates/Template - Project Note` | High |
| Frontmatter contract | `Knowledge/System Standards - Frontmatter.md` | Required keys documented (`type/domain/status/tags/source.kind/related/created/updated/last_reviewed`) | High |
| Frontmatter in practice | `Work/HB Intel/Architecture/MASTER/...` sample notes | Uniform YAML with nested `source` and lifecycle fields | High |
| Traceability metadata | `Work/HB Intel/Architecture/MASTER/apis/procore/phase-01/wave-02/README.md` | Includes `source.path`, `source.commit`, commit-pinned GitHub `source.url` | High |
| MOC pattern | `Work/00 Work MOC.md`, `Work/HB Intel/00 HB Intel MOC.md`, `Knowledge/00 Knowledge MOC.md` | Hub notes with `type: moc` and wikilink-based domain routing | High |
| Tag taxonomy | `Knowledge/System Standards - Tag Taxonomy.md` | Lowercase hyphenated tag convention with domain/program/discipline/operational groups | High |
| Link style (internal) | `Knowledge/00 Knowledge MOC.md`, `Work/HB Intel/Architecture/00 Architecture MASTER MOC.md` | Heavy use of wikilinks for note navigation | High |
| Link style (relative markdown) | `Work/HB Intel/Architecture/MASTER/pwa/02_Phase-1_Production-Data-Plane-and-Integration-Backbone-Plan.md` | Relative markdown links in mirrored technical docs | High |
| Task syntax | `Work/HB Intel/Architecture/MASTER/pwa/phase-0-deliverables/P0-C1-Development-Guardrail-Sheet.md` | Standard markdown tasks `- [ ]` / `- [x]` prevalent | High |
| Meeting convention basis | `Templates/Template - Meeting Note.md` | Meeting structure: Attendees/Agenda/Notes/Decisions/Action Items | Medium |
| Template system | `Templates/*.md`, `.obsidian/templates.json`, `.obsidian/plugins/templater-obsidian/data.json` | Central templates folder with Templater enabled | High |
| Dataview usage | `AI Outputs/00 Dataview Dashboards.md` | Dataview queries rely on metadata fields and stale-note checks | High |
| Plugin evidence | `.obsidian/community-plugins.json` | `copilot`, `smart-connections`, `dataview`, `templater-obsidian`, `obsidian-tasks-plugin` installed | High |
| Generated outputs location | `AI Outputs/Daily Knowledge Brief - 2026-05-24.md`, `Agent Briefs/HB Intel Ingestion Run - 2026-05-24.md` | Existing naming/location conventions for generated notes | High |
| Generated marker pattern | Vault-wide regex scan for common markers | No established HB-specific marker pair found | Medium |
| Attachment/resource pattern | `Work/HB Intel/Architecture/_agent/tmp/hb-intel/**` | Mirrored binary resources (pdf/docx/xlsx/images) kept under `_agent/tmp` | High |
