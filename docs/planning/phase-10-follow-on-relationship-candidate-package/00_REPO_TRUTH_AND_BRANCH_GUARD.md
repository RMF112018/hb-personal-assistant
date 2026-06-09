# 00 — Repo Truth and Branch Guard

## Objective

Verify the live repo state and confirm that the correct follow-on candidate is the relationship candidate engine, **not** the daily pipeline pilot itself.

## Scope

Audit only. Do not modify files. Do not commit.


## Non-Negotiable Constraints

- Target branch: `experiment/local-agent-family-proof` unless Bobby explicitly directs otherwise.
- Do not modify `main`; do not merge; do not retarget PRs.
- Treat live repo truth and DB truth as authoritative over this package.
- This package assumes the production-like daily pipeline pilot is already in progress or complete; do **not** re-implement scheduler, polished brief delivery, Obsidian delivery, or daily pipeline automation except for minimal integration hooks explicitly scoped here.
- No cloud LLM submission unless Bobby separately approves it.
- No automatic email send.
- No calendar mutation.
- No Procore writeback.
- No Graph writeback.
- No external writeback.
- No MCP raw exposure.
- No production DB mutation unless Bobby explicitly approves it.
- No destructive migration unless Bobby explicitly approves it.
- No credential/auth changes unless Bobby explicitly approves it.
- No raw email/calendar/Procore/document body content committed to repo, tests, evidence, docs, or logs.
- No raw prompts, raw model responses, signed URLs, download URLs, join URLs, access tokens, refresh tokens, secrets, credential material, or unsafe HTML committed to repo, evidence, docs, tests, or logs.
- Default persisted rows and repo evidence must remain redacted/guarded.
- Any apply/persist behavior must be capped, bounded, idempotent, source-linked, review-safe, and disabled by default.
- Raw local content may appear only in explicitly approved local operator-consumption surfaces and never in committed evidence.


## Required Commands

```bash
cd /Users/bobbyfetting/hb-personal-assistant

git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git status --short
git branch --contains HEAD
git rev-parse main
git log --oneline --decorate -n 15
```

## Audit Checklist

1. Confirm branch/HEAD/tree state.
2. Confirm whether Checkpoint 6 / production-like daily pipeline pilot is currently in progress, complete, or absent.
3. Inspect the Phase 10 architecture/evidence docs:
   - `docs/architecture/232-phase-10-local-agent-family.md`
   - `docs/evidence/phase-10-local-agent-family/README.md`
4. Inspect current schema head and relationship table readiness:
   - `src/hb_assistant/store/migrator.py`
   - `src/hb_assistant/construction/second_brain/local_ai/schema.py`
   - `docs/architecture/207-phase-10-schema-v41.md`
5. Inspect existing relationship and packet substrate:
   - `src/hb_assistant/construction/second_brain/local_ai/relationship_scoring.py`
   - `src/hb_assistant/construction/second_brain/local_ai/packet_builders.py`
6. Inspect current CLI surfaces under second-brain commands.
7. Inspect daily pipeline implementation and tests so this follow-on does not regress it.
8. Identify conflicts with any in-progress local changes.

## Candidate Confirmation Rules

The selected follow-on remains valid if:

- daily pipeline automation work is already underway or complete;
- email/calendar raw context tables contain usable rows in Dev DB copies;
- `phase10_relationship_candidates` exists or an equivalent guarded table exists;
- deterministic `relationship_scoring.py` and bounded `related_context_action_packet` are present;
- daily brief still converges through `daily_brief_action_candidates`;
- no existing first-class `relationship-candidates scan` workflow already fully satisfies the acceptance criteria.

If an existing implementation already satisfies this package, stop and report it instead of duplicating code.

## Validation Required

- Branch/git proof in final audit memo.
- File-path evidence with line-level notes where useful.
- No code changes.

## Stop Conditions

- Wrong branch and unable to correct safely.
- Dirty tree with unrelated user work that would be overwritten.
- Daily pipeline work has uncommitted local edits in the same files this package would touch.
- Existing relationship-candidate workflow already meets acceptance criteria.

## Commit Behavior

Commit expected: no.

## Final Response Format

Return:

- branch/HEAD/tree status;
- daily pipeline status: in progress / complete / absent;
- relationship substrate status;
- implementation go/no-go;
- files likely involved;
- risks and blockers.

