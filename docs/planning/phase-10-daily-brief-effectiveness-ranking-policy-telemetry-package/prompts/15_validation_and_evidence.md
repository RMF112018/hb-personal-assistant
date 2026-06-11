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

# 15 — Validation and Evidence

## Objective

Run full validation on code and `/tmp` DB copies only. Produce raw-free evidence.

## Required Commands

```bash
cd /Users/bobbyfetting/hb-personal-assistant

git status --short
git branch --show-current
git rev-parse HEAD

python -m compileall src tests | tee docs/evidence/phase-10-daily-brief-effectiveness-ranking-policy-telemetry/21-compile.txt
.venv/bin/ruff check src tests | tee docs/evidence/phase-10-daily-brief-effectiveness-ranking-policy-telemetry/19-ruff.txt
.venv/bin/mypy src | tee docs/evidence/phase-10-daily-brief-effectiveness-ranking-policy-telemetry/20-mypy.txt
```

Focused pytest command, adjusted to repo truth:

```bash
.venv/bin/pytest   tests/test_phase_10_daily_brief_effectiveness_schema.py   tests/test_phase_10_daily_brief_effectiveness_packets.py   tests/test_phase_10_daily_brief_effectiveness_metrics.py   tests/test_phase_10_ranking_policy_evaluator.py   tests/test_phase_10_model_profile_evaluator.py   tests/test_phase_10_procore_noise_evaluator.py   tests/test_phase_10_effectiveness_rollups.py   tests/test_phase_10_daily_brief_effectiveness_cli.py   tests/test_phase_10_daily_brief_effectiveness_report.py   2>&1 | tee docs/evidence/phase-10-daily-brief-effectiveness-ranking-policy-telemetry/18-pytest-focused.txt
```

## DB Copy Validation

Run `templates/db_copy_validation_commands.md`.

## Evidence

Populate every file listed in `references/evidence_bundle_manifest.md`.

## Merge Gates

Block merge if:

- prerequisite is missing but implementation proceeded;
- any test fails without documented quarantine;
- dry-run writes rows;
- apply does not require `--max-persist`;
- source-ref coverage is hidden or misrepresented;
- telemetry mutates lifecycle/source refs;
- no-raw scan finds unsafe content;
- production DB SHA changes.
