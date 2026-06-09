# Daily-brief consumption proof — no duplicate/conflicting sections

The follow-up watch report and the daily brief's V45 **pending email follow-up** section (Prompt 01) are **complementary, non-overlapping** surfaces:

| Surface | Source | Grouping | Where |
|---|---|---|---|
| V45 pending section | `email_followup_enrichments` (model-enriched email follow-ups) | by review label | daily brief (browser/Obsidian) |
| Follow-up watch report | `accepted_tasks` / `accepted_commitments` lifecycle | by operator action | `follow-up-watch report` CLI |

The watch report is a dedicated operator CLI surface; it does **not** add a second section to the daily brief, so there is no duplicate or conflicting brief section. Both feed the operator's review flow from different inputs (email-enrichment queue vs accepted-item lifecycle).
