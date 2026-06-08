# Prompt 00 — Repo Truth Rebaseline

## Objective

Conduct a fresh local repo-truth audit before any edits for the Phase 10A candidate review CLI.


## Repo-truth baseline

- Repository: `RMF112018/hb-personal-assistant`
- Current audited schema head: `V42`; local agent must rebaseline.
- Target update: Phase 10A Candidate Review CLI.
- Current batch command path observed: `hb-assistant second-brain extract-packets`.
- Review workflow must operate only on persisted local candidate rows.
- Local dirty state and exact HEAD are not verifiable from this package; run `git status --short` and `git rev-parse HEAD` before editing.

Repository truth is authoritative. Stop and report if the local repo materially differs from this package.

## Global guardrails

- No email send.
- No calendar mutation.
- No Graph writeback.
- No Procore writeback.
- No external/cloud LLM dependency.
- No raw email body, raw document text, raw calendar payload, raw Procore payload, raw prompt, raw response, signed URL, download URL, token, or secret persistence/output.
- Do not broaden packet extraction scope.
- Do not alter Phase 10A extraction prompt/model/stable-key behavior unless a test failure proves a direct compatibility issue.
- Review actions are local DB updates only.


## Required commands

```bash
git status --short
git rev-parse HEAD
find src/hb_assistant -path '*second_brain*' -o -path '*store*' | sort | sed -n '1,240p'
grep -R "candidate_review_events\|review_app\|extract-packets\|task_candidates\|commitment_candidates" -n src tests | tee /tmp/phase10a-review-rebaseline-grep.txt
python - <<'PY'
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION
print('LATEST_SCHEMA_VERSION=', LATEST_SCHEMA_VERSION)
PY
```

## Deliverable

Write `docs/evidence/construction-intelligence-phase-10a-candidate-review-cli/00-rebaseline.md`. Stop before code changes if repo truth differs materially.
