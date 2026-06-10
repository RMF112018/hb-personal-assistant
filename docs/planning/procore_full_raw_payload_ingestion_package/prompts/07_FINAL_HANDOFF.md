# 07 — Final handoff

## Objective

Commit the completed implementation and provide a concise handoff.

## Pre-commit checks

```bash
cd /Users/bobbyfetting/hb-personal-assistant

git status --short
git diff --name-only
git diff --stat

find . -path ./.git -prune -o \
  \( -name "*.sqlite" -o -name "*.db" -o -name "*.pyc" -o -name "__pycache__" -o -name ".env" \) \
  -print
```

Do not commit forbidden artifacts.

## Commit

Stage only relevant changed paths.

```bash
git add \
  src/hb_assistant/procore \
  src/hb_assistant/cli/procore.py \
  src/hb_assistant/store/migrator.py \
  tests \
  docs/architecture \
  docs/evidence/procore_full_raw_payload_ingestion

git status --short
git commit -m "fix(procore): populate raw tables from full endpoint payloads"
```

## Push

```bash
git push -u origin fix/procore-full-raw-payload-ingestion
```

## Final response must include

1. Branch name.
2. Commit SHA.
3. Changed files.
4. Schema version decision: V46 retained or V47 added.
5. Implementation summary.
6. Proof that full raw endpoint payloads are persisted to DB.
7. Proof that redacted legacy replay is fallback only.
8. Proof that structured tables project from full raw values.
9. Proof that legacy replay cannot downgrade full rows.
10. No-leak proof.
11. Validation commands and results.
12. Evidence bundle path.
13. Exact post-merge production apply commands.
14. Known limitations.

End with one label:

- `READY FOR REVIEW`
- `PARTIAL — NEEDS FOLLOW-UP`
- `BLOCKED`
