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

# 09 — Raw Safety and No-Leak Hardening

## Objective

Prove the email follow-up projection path does not leak private raw content.

## Required Test Sentinels

Use synthetic fixture values only. Add obvious sentinels such as:

- `EMAIL_FOLLOWUP_BODY_SENTINEL`
- `<p>EMAIL_FOLLOWUP_HTML_SENTINEL</p>`
- `https://teams.microsoft.com/l/EMAIL_FOLLOWUP_JOIN_SENTINEL`
- `https://example.invalid/private/EMAIL_FOLLOWUP_SIGNED_URL_SENTINEL?token=SECRET`
- `Bearer EMAIL_FOLLOWUP_TOKEN_SENTINEL`
- recipient array values with `EMAIL_FOLLOWUP_RECIPIENT_SENTINEL`

Tests must prove none of these appear in:

- extractor output
- persisted domain candidate rows
- `daily_brief_action_candidates`
- `candidate_source_refs`
- stage receipts
- status JSON
- rendered daily brief/browser output
- evidence files

## Required Scans

Use existing scan if available:

```bash
.venv/bin/hb-assistant email-calendar raw no-raw-leak-scan \
  --path docs/evidence/phase-10-email-followup-candidate-projection \
  --json
```

If command shape changed, use repo truth.

Also add targeted Python/pytest assertions.

## Raw Access Audit

If any raw body access occurs:

- Verify a `raw_content_access_events` row is written.
- Verify evidence contains only count deltas, not body content.
- Verify raw access is not used in default deterministic metadata-only path unless justified.

## Evidence

Write:

`docs/evidence/phase-10-email-followup-candidate-projection/09-no-raw-leak.md`
