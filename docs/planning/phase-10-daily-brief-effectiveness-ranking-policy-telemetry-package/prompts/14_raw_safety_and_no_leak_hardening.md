You are the local code agent working in Bobby's `RMF112018/hb-personal-assistant` repository.

Package: `docs/planning/phase-10-daily-brief-effectiveness-ranking-policy-telemetry-package/`

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
- Use `/tmp` DB copies for apply validation.
- Do not send/draft/reply/forward email.
- Do not mutate calendar, Graph, Procore, SharePoint, OneDrive, Obsidian, or any external system.
- Do not mutate lifecycle state or source refs from telemetry.
- Do not expose raw bodies, HTML, private URLs, tokens, secrets, local paths, raw Procore payloads, model prompts, or model responses.
- Telemetry is observational only.

# 14 — Raw Safety and No-Leak Hardening

## Objective

Prove telemetry, CLI, reports, evidence, and persisted rows are raw-free.

## Tasks

1. Reuse repo-true scanner helper/CLI.
2. Add planted raw/leak tests for URL, email, join link, JWT-like, access token, bearer token, private key, local path if supported, raw Procore-like shape, raw email body-like content.
3. Ensure findings expose only category codes.
4. Add SQL-visible leak smoke checks.
5. Ensure `include_raw` render output cannot enter telemetry.

## Evidence

Write `15-no-raw-leak-scan.json` and `16-guard-columns-zero-proof.json`.
