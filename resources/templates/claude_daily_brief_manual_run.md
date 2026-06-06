# Claude Manual Run — Construction Executive Daily Brief (Testing)

> Manual one-off prompt template for testing the daily-brief rendering flow. Paste into a Claude chat.
> The MCP tool is `hb_daily_brief_packet` (also known as `construction_daily_brief_packet` /
> `get_daily_brief_handoff`). It returns the approved, metadata-only `DailyBriefHandoffPacketV2`,
> which splits a user-facing `render_payload` from internal `governance_metadata`.

## Prompt

You are producing a concise, executive-facing construction daily brief (manual test run).

Call the MCP tool `hb_daily_brief_packet`. For a specific day, pass `date` (YYYY-MM-DD) and optionally
`project_scope`; otherwise it defaults to today and all projects.

Render **only** the `render_payload`. Never render anything from `governance_metadata`. Use only that
packet. Do not request raw records. Do not call direct database, Graph, Procore, vector, calendar,
email, memory mutation, or filesystem tools. Do not make legal, financial, safety, claim, payment,
entitlement, schedule-certification, or contractual determinations.

Write a brief, descriptive, executive-facing brief. Use project names/keys. Surface record-level
detail where the packet provides it. Where a section's `detail_available` is false, write
"detail unavailable" with the section's reason instead of a bare count. Keep focus recommendations
practical and include no more than 3–5 focus items.

Produce exactly these sections, in this order:

1. Yesterday — short bullets on what happened (meetings held, notable activity).
2. Today — a table of today's agenda.
3. Next 7 Days — a table of upcoming deadlines.
4. Needs Attention — a table of what needs attention (schedule, RFIs, submittals, punch, procurement).
5. Focus — 3–5 practical, numbered focus items.

End with a single one-line advisory footer (one line only):
`Source-linked advisory brief. Verify in source systems before final action.`

### Do not render

Do not render any of the following in the brief: the packet provenance table, any packet hash /
correlation table, source coverage as a body section, the guardrail matrix, long advisory blocks or
repeated no-final-determination disclaimers, source-family lists, internal relationship-count
summaries, proof paths, the generated utc timestamp, mode / dry-run commentary, suggested follow-up
questions, or raw json. Keep it to the five sections plus the one-line footer.

This is a test run — do not treat the rendered brief as authoritative and do not persist it into any
source system.

## Output Format

```markdown
# Daily Brief — {{date}}

## Yesterday
- Bullet
- Bullet
- Bullet

## Today
| Time | Meeting | Project | Prep / Related Items |
|---|---|---|---|

## Next 7 Days
| Date | Project | Item | Type | Responsible | Why It Matters |
|---|---|---|---|---|---|

## Needs Attention
| Priority | Project | Item | Reason | Recommended Focus |
|---|---|---|---|---|

## Focus
1. Focus item
2. Focus item
3. Focus item

---
_Source-linked advisory brief. Verify in source systems before final action._
```

If a section is empty, say so in one short line (e.g. "No meetings today."). If a domain has no
record-level detail, write "detail unavailable" rather than a count. Do not invent content.

## Storage Policy

Claude-rendered output is **not source truth**. This is a manual test run — persisting is optional. If
persisted, write it only to the canonical advisory location, creating the directory if missing:

`/Users/bobbyfetting/Documents/Obsidian Vault/Work/Daily Brief/`

using the date-stable filename `YYYY-MM-DD-daily-brief.md`
(e.g. `/Users/bobbyfetting/Documents/Obsidian Vault/Work/Daily Brief/2026-06-06-daily-brief.md`).

It is advisory only. Do not persist the rendered body to SQLite. It must **not** be imported into:

- accepted memory
- vector index
- source manifest
- source-linked proof
- Procore / Graph / source systems

unless a later explicit reviewed-import workflow is implemented.
