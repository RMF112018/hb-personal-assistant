# 05 — Ranked / Assembled Overlay → Render

`rank-candidates --no-client` produced a healthy deterministic overlay for 2026-06-12:

- ranked_count: **95 / 95**
- source_ref_coverage: **1.0**
- usefulness_score: **0.9**
- guard_clean: **true**
- model_status: `withheld` (no client) → deterministic_fallback_used: true (honest, authoritative)
- assembly sections: `top_priorities`(5), `review_needs_decision`(90), `data_gaps_degraded`(0)

The render now **consumes this overlay** instead of the flat `daily_brief_action_candidates`
family dump. Mapping:

| Assembly section_key | Render display group | Rendering |
|---|---|---|
| `top_priorities` | Top Priorities | individual sanitized lines (deduped) |
| (procore family, any section) | Procore Financial / Project Signals | aggregated by project + signal type |
| (calendar family, any section) | Calendar Prep | safe labels + metadata, capped |
| `review_needs_decision` (other) | Needs Review / Decisions | sanitized lines |
| `waiting_on_me` / `waiting_on_others` / `accepted_stale` | Email / Follow-up | candidates or data-gap card |
| `data_gaps_degraded` | Data Gaps / Degraded | polished status line |

Authoritative selection + order come from the assembly's `candidate_ids_json`; Procore/calendar
families are routed to their dedicated aggregated/safe-labelled sections (minus any already shown in
Top Priorities). Rendered Top Priorities:

```markdown
## Top Priorities
- alton-hilltop-pbg — RFI cost-impact signal. Confirm pricing exposure and response owner.
- tropical — payment-due invoice signal. Review payment status and confirm next payment action. (×4)
```

See `04-daily-brief-sample-deterministic.md` for the full rendered brief.
