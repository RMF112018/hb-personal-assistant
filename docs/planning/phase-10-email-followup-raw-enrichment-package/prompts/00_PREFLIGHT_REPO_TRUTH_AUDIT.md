# Prompt 00 — Preflight Repo-Truth Audit

## Objective

Verify the live local repository state before implementation. This prompt must not modify code except for optional audit notes if the repo already has a planning/evidence convention that requires them. Prefer no file modifications in this prompt unless needed for final evidence.

## Required Commands

Run exactly from the local repo:

```bash
cd /Users/bobbyfetting/hb-personal-assistant
pwd
git fetch origin
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git status --short
git branch --contains HEAD
git rev-parse main
git rev-parse origin/main
git ls-remote origin experiment/phase-10-intelligence-daily-brief-remediation || true
git cat-file -e c49caedc^{commit} && echo "c49caedc exists locally" || echo "c49caedc missing locally"
git log --oneline --decorate --graph -30 --all
```

Check config explicitly:

```bash
test -e config/config.yml && echo "config/config.yml exists" || echo "config/config.yml absent"
git ls-files --error-unmatch config/config.yml >/dev/null 2>&1 && echo "config/config.yml tracked" || echo "config/config.yml untracked_or_absent"
```

Check schema head:

```bash
grep -R "LATEST_SCHEMA_VERSION" -n src tests | head -20
```

Search for relevant existing modules:

```bash
find src/hb_assistant -path '*second_brain*' -type f | sort | sed -n '1,240p'
find tests -type f | grep -E 'email|follow|daily|local|model|schema|guard|raw|brief' | sort | sed -n '1,240p'
find docs -type f | grep -E 'phase-10|daily|email|follow|raw|local|intelligence' | sort | sed -n '1,240p'
```

## Required Repo State Decision

If the working tree is not clean, stop unless the only untracked file is clearly local configuration such as `config/config.yml`. Do not delete or alter foreign files.

If not already on fresh `main`, run:

```bash
git switch main
git pull --ff-only origin main
git status --short
```

Then create the implementation branch:

```bash
git switch -c experiment/phase-10-email-followup-raw-enrichment
```

If the branch already exists, inspect it. If it contains unrelated or incomplete work, stop and report.

## Required Findings to Record in Working Notes / Final Handoff

Record:

- current branch before switching
- implementation branch
- starting HEAD
- `main` HEAD
- `origin/main` HEAD
- dirty tree status
- untracked files
- whether `config/config.yml` exists and whether it is tracked
- whether `c49caedc` exists locally
- whether the old remediation branch ref still exists remotely
- whether PR #11 / remediation work appears merged into main
- current schema head
- local model routing files found
- email/follow-up/raw/daily-brief modules found
- test files found

## Stop Conditions

Stop if:

- `git pull --ff-only origin main` fails.
- The working tree has unrelated tracked modifications.
- `main` is not reachable or cannot be fetched.
- Schema head is not discoverable.
- The repo does not appear to contain the Phase 10 substrate described in this package.

## Exit Criteria

- Clean implementation branch created from fresh main.
- Repo truth recorded.
- No production DB touched.
- No code committed unless this repo has an established evidence/audit-note convention and the file is raw-free.
