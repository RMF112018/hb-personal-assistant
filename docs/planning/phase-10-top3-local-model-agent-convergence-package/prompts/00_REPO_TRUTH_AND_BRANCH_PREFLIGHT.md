Repository: `RMF112018/hb-personal-assistant`  
Local path: `/Users/bobbyfetting/hb-personal-assistant`  
Branch: `experiment/phase-10-top3-local-model-agent-convergence`  
Evidence root: `docs/evidence/phase-10-top3-local-model-agent-convergence`

Hard constraints apply from `../README.md`, `../STOP_CONDITIONS.md`, and `../reference/02_SAFETY_CONTRACT.md`.

# Prompt 00 — Repo Truth and Branch Preflight

## Objective

Establish authoritative local repo truth before touching code.

## Required commands

```bash
cd /Users/bobbyfetting/hb-personal-assistant

git fetch origin
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git status --short --untracked-files=all
git branch --contains HEAD
git rev-parse main
git rev-parse origin/main
git log --oneline --decorate --graph -50 --all
git branch --all --sort=-committerdate | head -80
git tag --sort=-creatordate | head -20
test -e config/config.yml && (git ls-files --error-unmatch config/config.yml >/dev/null 2>&1 && echo tracked || echo foreign) || echo absent
```

## Required actions

1. If not on `main`, inspect whether the current branch has uncommitted work.
2. If clean, switch to `main`, pull fast-forward only, and create the package branch.
3. If dirty, stop unless all changes are known generated artifacts and can be safely preserved outside the repo.
4. Record whether `config/config.yml` exists and whether it is tracked or foreign.
5. Record recent Phase 10 branch/merge activity.
6. Record whether PR #13 / Phase 10 full-candidate work is present on `main`.
7. Record current schema head by reading `src/hb_assistant/store/migrator.py` and, if safe, by running schema validation on a DB copy.

## Evidence

Create:

- `00-repo-state.md`
- `01-branch-state.txt`
- `02-schema-before-after.json` initial section

## Stop conditions

- Dirty tree with unknown work.
- `main` cannot fast-forward to `origin/main`.
- Local repo does not contain merged Phase 10 full-candidate implementation.
- `config/config.yml` is tracked or would be committed.
