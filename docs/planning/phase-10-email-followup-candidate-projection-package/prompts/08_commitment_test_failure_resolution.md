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

# 08 — Commitment Test Failure Resolution

## Objective

Audit and resolve the pre-existing deterministic failure:

`tests/test_phase_10_email_task_extraction.py::test_commitment_persists_to_commitment_table`

Do not repeat the prior misclassification that this is model-dependent unless current repo truth proves it.

## Required Audit

Run:

```bash
.venv/bin/python3.12 -m pytest tests/test_phase_10_email_task_extraction.py::test_commitment_persists_to_commitment_table -q -vv
```

Then inspect:

```bash
rg -n "test_commitment_persists_to_commitment_table|commitment_candidates|accepted_commitments|commitment|email_task_extraction|task_candidates" tests src docs
```

Determine:

- Is the test using deterministic fixtures?
- Does it require local model availability?
- Is the commitment extraction path bypassing persistence?
- Is the commitment persisted to a task table but not commitment table?
- Is a deterministic candidate object missing a required field?
- Is an idempotent upsert conflict preventing insert?
- Is schema mismatch causing the insert to no-op?
- Is this now directly solved by the new email follow-up candidate projection path?

## Required Outcome

One of:

1. Fix it directly if related to commitment persistence.
2. Replace/adjust the test if it is asserting obsolete behavior and add a better deterministic regression.
3. Quarantine it only if repo truth proves it is unrelated, with:
   - failure output
   - deterministic cause
   - follow-up issue text
   - reason it is not merge-blocking

Preferred package outcome:

- Fix or stabilize it as part of this slice if any commitment persistence contract is touched.
- Add a targeted test proving `user_commitment` and/or `third_party_commitment` candidates persist to `commitment_candidates` and surface in the daily brief with source refs.

## Evidence

Write:

`docs/evidence/phase-10-email-followup-candidate-projection/08-commitment-regression.md`
