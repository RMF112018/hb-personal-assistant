You are the local code agent working in Bobby's `RMF112018/hb-personal-assistant` repository.

Package: `docs/planning/phase-10-email-followup-candidate-projection-package/`

Before doing anything else:

```bash
cd /Users/bobbyfetting/hb-personal-assistant
git status --short
git branch --show-current
git rev-parse HEAD
```

Stop if you are on `main` or if unexplained dirty files are present.

Hard safety constraints:

- Do not mutate the production DB.
- Do not send/draft/reply/forward email.
- Do not mutate calendar, Graph, Procore, SharePoint, OneDrive, Obsidian, or any external system.
- Use `/tmp` DB copies for apply validation.
- Do not expose raw bodies, HTML, private URLs, tokens, secrets, full recipient arrays, unbounded subjects, model prompts, or model responses.

# 00 — Repo Truth Audit

## Objective

Establish the exact repo state and current implementation truth before editing.

## Required Commands

```bash
git fetch origin
git status --short
git branch --show-current
git rev-parse HEAD
git rev-parse main
git rev-parse origin/main
git log --oneline --decorate -30
git log --merges --oneline --decorate -20
git branch --contains 3e5defc550fd1f47352a183d919fabf34ed78d5b || true
git diff --name-only
git diff --cached --name-only
```

## Required Code Searches

```bash
rg -n "email_raw_message_structured|email_raw_thread_structured|email_raw_thread_messages_structured|email_message_raw_content|email_thread_raw_context|body_ref|load_body|raw_content_access_events|projection_activation|email_calendar_projection" src tests docs
rg -n "follow_up_watch_items|email_followup_enrichments|task_candidates|commitment_candidates|accepted_tasks|accepted_commitments|commitment|follow[-_ ]?up|waiting|nudge|response_needed|reply_needed|action item|task extraction" src tests docs
rg -n "daily_brief_action_candidates|candidate_source_refs|persist_candidate_with_refs|source_ref_gate|source_ref_coverage|project_key_coverage|daily_brief_source_refs|daily_run|context_packet|Model Enriched Intelligence|model_enriched" src tests docs
rg -n "usefulness_gate|stage_context|contradiction|data_gap|email_followup_readiness|build_email_followup_data_gap|degraded|misleading success|empty candidates|useful source" src tests docs
rg -n "construction_project_identity|construction_project_keyword_registry|construction_project_source_matches|project_alias|resolve_project|project_key|identity backfill|promotion|review_required" src tests docs
rg -n "raw_body|body_html|body_text|raw_html|recipient|recipients_json|attendees_json|join_url|signed_url|webLink|token|secret|Authorization|Bearer|no-raw-leak|raw leak|egress|guard" src tests docs
find tests -maxdepth 2 -type f | sort | rg "email|follow|task|commitment|daily_brief|source_ref|usefulness|projection|calendar|procore|identity"
find docs -maxdepth 4 -type f | sort | rg "phase-10|daily-brief|email|follow|commitment|projection|first-slice|evidence|planning"
```

## Report

Write raw-free evidence to:

`docs/evidence/phase-10-email-followup-candidate-projection/00-repo-truth.md`

Include:

- current branch
- HEAD
- main
- origin/main
- whether PR 23 appears merged into main
- dirty tree
- staged files
- modified files
- untracked files
- local limitations
- exact existing modules and tests relevant to this slice
- whether the existing package should use current domain tables or needs schema changes
- initial go/no-go for implementation

Do not edit code in this prompt.
