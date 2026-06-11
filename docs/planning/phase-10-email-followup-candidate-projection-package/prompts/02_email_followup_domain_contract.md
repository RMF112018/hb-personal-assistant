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

# 02 — Email Follow-Up Domain Contract

## Objective

Define the domain-level contract before implementation so extractor, persistence, daily brief, status, and tests agree.

## Required Contract

Create or update a reference document in-tree:

`docs/architecture/phase-10-email-followup-candidate-projection.md`

Also update this package evidence:

`docs/evidence/phase-10-email-followup-candidate-projection/02-domain-contract.md`

## Candidate Families

Implement or map to these deterministic candidate families:

1. `waiting_on_response`
   - External or non-Bobby party appears to owe a response.
   - Thread/message is stale beyond threshold.
   - Bounded redacted title.
2. `response_needed`
   - Bobby/HB appears to owe a response.
   - Recent inbound message or directed request.
3. `stale_thread_nudge`
   - Thread has business context but no recent activity.
   - Nudge candidate, not a claim of obligation.
4. `user_commitment`
   - Bobby/HB committed to provide/send/review/confirm.
   - Must persist to commitment target if in scope.
5. `third_party_commitment`
   - External party committed to provide/send/review/confirm.
6. `project_action_item`
   - Action-like email item tied to a project or review-required project-like signal.
7. `time_sensitive_followup`
   - Due date, meeting date, or imminent timing signal from safe structured metadata.

## Required Candidate Fields

Every internal candidate object must include:

- deterministic candidate key
- candidate family
- source family: `email_message` or `email_thread`
- thread ref and/or message hash
- source table
- source ref string to be hashed by the source-ref writer
- project key or `None`
- project resolution status:
  - `resolved`
  - `review_required`
  - `not_project_related`
- bounded title
- bounded summary/reason
- recommended next action
- priority
- confidence
- due/staleness bucket if applicable
- raw access used: yes/no
- raw access audit event count if raw access was used

## Thresholds

Use conservative deterministic defaults:

- stale thread default: 3 business days since latest inbound or latest message, unless repo truth already has thresholds.
- response-needed confidence floor: 0.65.
- waiting/nudge confidence floor: 0.55.
- commitment confidence floor: 0.70 for persistence to `commitment_candidates`.
- daily-brief candidate confidence floor: 0.55.
- max title length: 120 chars.
- max reason/summary length: 240 chars.
- no raw body/HTML in title/reason.

## Output Decision

Decide whether candidate rows are first written to domain tables, directly to daily-brief candidates, or both.

Default package position:

- Write domain rows for durable review/read-model use.
- Write daily-brief rows for immediate operator utility.
- Use the central source-ref writer for every daily-brief row.
- Keep both idempotent.

Do not edit implementation code until this contract is written.
