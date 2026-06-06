# Claude Manual Run — Construction Executive Daily Brief (Testing)

> Manual one-off prompt template for testing the daily-brief rendering flow. Paste into a Claude chat.
> The MCP tool is `hb_daily_brief_packet` (also known as `construction_daily_brief_packet` /
> `get_daily_brief_handoff`). It returns the approved, metadata-only `DailyBriefHandoffPacketV1`.

## Prompt

You are producing a human-readable construction executive daily brief (manual test run).

Call the MCP tool `hb_daily_brief_packet`. For a specific day, pass `date` (YYYY-MM-DD) and optionally
`project_scope`; otherwise it defaults to today and all projects.

Use only that packet. Do not request raw records. Do not call direct database, Graph, Procore, vector,
calendar, email, memory mutation, or filesystem tools. Do not make legal, financial, safety, claim,
payment, entitlement, schedule-certification, or contractual determinations.

Write a concise, executive-facing brief with these sections:

1. What matters today
2. Review-required items
3. Aging / stale items
4. Meeting prep
5. Risk watchlist
6. Source coverage and confidence notes
7. Suggested follow-up questions

Preserve all review-required, stale, low-confidence, advisory-only, and no-determination warnings
exactly as carried in the packet. Include the source coverage note. Include the suggested follow-up
questions from the packet. Keep the brief concise and executive-facing.

If the packet is empty or source coverage is weak, say so plainly and do not invent content. This is a
test run — do not treat the rendered brief as authoritative and do not persist it into any source system.

## Output Format

```markdown
# Daily Construction Executive Brief — {{date}}

## What Matters Today

## Review-Required Items

## Aging / Stale Items

## Meeting Prep

## Risk Watchlist

## Source Coverage and Confidence Notes

## Suggested Follow-Up Questions

## Advisory Notice
```

The **Advisory Notice** must state that this brief is advisory and source-linked, was rendered from the
approved metadata-only packet only, makes no final determinations, and that all review-required and
stale/low-confidence warnings must be confirmed against the source systems before acting.

## Storage Policy

Claude-rendered output is **not source truth**. If persisted, it must go only to an output/handoff
location marked rendered / narrative / advisory. It must **not** be imported into:

- accepted memory
- vector index
- source manifest
- source-linked proof
- Procore / Graph / source systems

unless a later explicit reviewed-import workflow is implemented.
