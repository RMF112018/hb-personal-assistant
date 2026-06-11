# Prompt 00 — Repo-Truth Audit

## Objective

Establish current repo truth before implementation. Do not edit code in this prompt.

## Commands

```bash
cd /Users/bobbyfetting/hb-personal-assistant

git fetch origin
git status --short
git branch --show-current
git rev-parse HEAD
git rev-parse main
git rev-parse origin/main
git log --oneline --decorate -30
git log --merges --oneline --decorate -20
```

## Required searches

```bash
rg -n "daily_brief_action_candidates|candidate_source_refs|task_candidates|commitment_candidates|follow_up_watch_items|accepted_tasks|accepted_commitments|candidate_id|stable_key|source_ref|source_ref_hash" src tests docs

rg -n "review|review_queue|accepted|rejected|reject|snooze|snoozed|merge|merged|duplicate|dedupe|suppress|suppressed|closed|complete|handled|lifecycle|disposition|feedback" src tests docs

rg -n "daily_run|daily_brief|daily_brief_action_candidates|Model Enriched Intelligence|model_enriched|context_packet|source_ref_gate|executive|waiting|follow_up|actions|review_required|data_gap" src tests docs

rg -n "usefulness_gate|stage_context|contradiction|degraded|failed|coverage|source_ref_coverage|project_key_coverage|review_required|data_gap|status" src tests docs

rg -n "construction_project_identity|construction_project_keyword_registry|construction_project_source_matches|project_alias|resolve_project|project_key|review_required|identity backfill|promotion" src tests docs

rg -n "raw_body|body_html|body_text|raw_html|recipient|recipients_json|attendees_json|join_url|signed_url|webLink|token|secret|Authorization|Bearer|no-raw-leak|raw leak|egress|guard|prompt|response" src tests docs

rg -n "Typer|click|argparse|second-brain|local-ai|daily-run|validate|--db|--json|dry-run|apply" src tests docs

find tests -maxdepth 3 -type f | sort | rg "candidate|task|commitment|follow|daily_brief|source_ref|usefulness|review|accepted|lifecycle|projection|email|calendar|procore|identity"

find docs -maxdepth 5 -type f | sort | rg "phase-10|daily-brief|candidate|follow|commitment|review|lifecycle|feedback|projection|evidence|planning"
```

## Questions to answer

1. What branch and commit are active?
2. Is the email follow-up candidate projection slice merged/reachable?
3. What existing review/lifecycle primitives exist?
4. What existing CLI commands already cover review?
5. What candidate/domain tables and accepted-action tables exist?
6. What tests already protect existing behavior?
7. What implementation must be convergence/extension instead of rebuild?

## Evidence

Write `docs/evidence/phase-10-candidate-lifecycle-review-queue/00_repo_truth.md`.

No raw data. Paths, commit SHAs, test names, and code references only.

