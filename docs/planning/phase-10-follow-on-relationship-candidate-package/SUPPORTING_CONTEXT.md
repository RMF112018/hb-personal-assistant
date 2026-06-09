# Supporting Context

## Correction Applied

The daily pipeline pilot is treated as already in progress. This package is for the best candidate **after** that work.

## Repo Evidence Used to Select Candidate

The current Phase 10 architecture indicates the branch is an experimental local-only agent family and that the family converges on `daily_brief_action_candidates`. It lists email extraction/promotion/follow-up, Procore digest, calendar meeting prep, daily-brief synthesis/render, and pipeline orchestration as implemented surfaces.

The architecture also states that `second-brain pipeline run` chains follow-up-watch, Procore digest, calendar prep, daily-brief synthesis, and render. The render stage is read-only; raw mode is local-consumption only.

The evidence bundle reports:

- Dev DB schema V43.
- Email raw context is populated enough for model-ready work.
- Calendar raw content is populated enough for meeting prep.
- Procore action signals are populated enough for digesting.
- `daily_brief_action_candidates` is the convergence table.
- Checkpoint 5 pipeline proof is green on DB copies with guard columns zero.

The repo already has:

- V41 `phase10_relationship_candidates` table listed as part of the Phase 10 schema.
- Deterministic `relationship_scoring.py` for email-thread ↔ calendar-event relationships.
- Bounded `related_context_action_packet` and `triage_batch_packet` builders.

## Candidate Rationale

Once daily pipeline automation lands, Bobby will receive a daily brief. The next ROI problem is not delivery; it is intelligence density. The brief should connect related email threads, meetings, and project signals so the system can surface context clusters and prep packets instead of isolated rows.

## Candidate Selected

**Relationship candidate engine + cross-source context enrichment.**

Initial mandatory slice:

- email ↔ calendar relationships;
- deterministic-first scoring;
- source-linked reviewable candidates;
- dry-run/apply/capped/idempotent CLI;
- optional daily brief enrichment.

Conditional/deferred slice:

- Procore relationships only if safe source-linking and redacted read-models are proven in repo/DB truth.

## Candidates Considered After Excluding Daily Pipeline

1. Polished browser presentation — lower because daily pipeline delivery work already covers it.
2. Obsidian vault output — lower because daily pipeline delivery work already covers it.
3. Scheduler / launchd automation — excluded as daily pipeline work.
4. Pipeline health / run status — useful but likely part of daily pipeline pilot.
5. Local model evaluation/routing — valuable later, but current default model path is viable enough.
6. Email follow-up/raw enrichment — useful, but narrower and riskier raw-content boundary.
7. Inbox classification/prioritization — useful, but less source-linked than relationship candidates.
8. Procore deeper summarization — useful but siloed; relationships should come first.
9. Calendar deeper meeting prep — high value but depends on relationship context.
10. File/document parsing — data-blocked unless files/parser outputs are populated.
11. Obsidian indexing/organization — lower ROI and more mutation-sensitive.
12. MCP context packet builder — useful later; current no-raw-MCP policy makes it premature.
13. Entity normalization/deduplication — foundational but less immediate to daily brief usefulness.
14. Relationship candidate engine — selected.
15. Review/API/dashboard surfacing — useful later when CLI is insufficient.
16. Production/main integration planning — important but not a local-agent family implementation.

