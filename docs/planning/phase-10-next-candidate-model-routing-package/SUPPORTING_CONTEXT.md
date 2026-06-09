# Supporting Context

## User correction

The production-like daily pipeline pilot and operator runbook are currently in progress and must not be selected as the next candidate. This package therefore selects the next candidate after that operational loop.

## Repo-truth basis

Repo-truth summary used for package planning:
- Phase 10 already implemented a local-only, review-gated family converging into `daily_brief_action_candidates`.
- The documented family includes email extraction, acceptance promotion, follow-up watch, Procore digest, calendar prep, daily-brief synthesis, render, and pipeline orchestration.
- The documented Checkpoint 6 already covers weekday-aware daily-run behavior, raw Obsidian/browser consumption outputs, status files, last-good preservation, and launchd scheduler surfaces.
- Therefore, production-like daily pipeline pilot/operator runbook is excluded from candidate selection here.
- The next candidate should improve output quality and reliability across the already-operational loop rather than add another independent vertical.
- The selected candidate is local model evaluation + routing, scoped to daily-brief intelligence quality and future reusable model profile selection.


## Candidate scoring

Candidate scoring after excluding the daily pipeline pilot/operator runbook as in progress:

| Candidate family | ROI | Readiness | Data readiness | Complexity | Safety risk | Time to useful | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Local model evaluation + routing | 9 | 8 | 8 | 5 | 4 | 7 | SELECTED: improves quality across every existing daily-brief stage |
| Email follow-up/raw enrichment | 8 | 7 | 8 | 6 | 7 | 7 | Strong second; should consume model routing once available |
| Calendar deeper meeting prep | 7 | 7 | 7 | 5 | 5 | 7 | Good vertical; less cross-cutting |
| Procore deeper summarization | 7 | 7 | 7 | 5 | 5 | 7 | Good vertical; less cross-cutting |
| Inbox classification/prioritization | 7 | 6 | 8 | 6 | 6 | 6 | Useful, but adds another candidate surface before quality baseline exists |
| Entity normalization/deduplication | 6 | 6 | 7 | 7 | 5 | 5 | Valuable but not immediately visible in the brief |
| Relationship candidate engine | 6 | 6 | 7 | 7 | 5 | 5 | Useful, but repo docs say deterministic scoring already exists |
| File/document parsing/enrichment | 5 | 5 | 3 | 8 | 7 | 4 | Data-blocked until file corpus/read models are present |
| MCP context packet builder | 5 | 5 | 4 | 7 | 8 | 4 | Deferred due raw exposure risk and empty packet table |
| Review/API/dashboard surfacing | 5 | 5 | 6 | 8 | 5 | 4 | Better after quality/routing stabilizes |
| Production/main integration planning | 5 | 6 | 6 | 7 | 6 | 5 | Governance task, not the next local-agent family |
| Obsidian indexing/organization | 4 | 5 | 4 | 6 | 6 | 4 | Lower ROI now; daily-run outputs already cover operator consumption |


## Selected candidate

Local model evaluation + routing for daily-brief intelligence quality.

## Intended outcome

A daily brief should stop being a sparse content dump. The system should be able to:
- Evaluate which local model/profile is reliable for each agent task.
- Route tasks to the best local model/profile.
- Use structured JSON with schema validation.
- Withhold bad model output.
- Produce concise, source-linked executive catch-up content.
- Keep deterministic fallback intact.
- Prove no raw prompt/response egress.

## Non-goals

- No new scheduler implementation.
- No browser presentation implementation except optional integration with existing daily-run output.
- No new Obsidian vault workflow except optional integration with existing governed output.
- No cloud LLM.
- No email/calendar/Procore/Graph writeback.
- No full dashboard UI.
- No file/document parsing until data readiness exists.

## Likely future candidate after this

Email follow-up/raw enrichment is the strongest next candidate after model routing, because it can consume the router and directly improve open-loop/action-catchup quality.
