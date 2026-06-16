# 08 — Email / Follow-up Section (data-gap card)

On the canonical data, `accepted_tasks`, `accepted_commitments`, and `follow_up_watch_items` are
empty (the follow-up-watch scan converted 0 of 281 `email_thread_summaries`). The brief never
silently omits the email family: when no follow-up candidates are eligible and the family is in
scope, it renders a polished aggregate data-gap card (count only — no subjects, bodies, addresses,
or raw content):

```markdown
## Email / Follow-up
- Email follow-up unavailable — 281 email thread summaries exist, but none are eligible for follow-up watch. Review the email follow-up projection/watch eligibility inputs.
```

If eligible accepted tasks / commitments / follow-up watch items exist, they render as actionable
follow-up lines instead. No specific email tasks are invented from generic thread summaries.
