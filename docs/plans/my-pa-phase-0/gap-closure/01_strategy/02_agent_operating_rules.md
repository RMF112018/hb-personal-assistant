# Agent Operating Rules

## Primary Rule

Do not trust prior closeout claims. Trust only repo truth and commands run in the current remediation session.

## Required Startup Behavior

At the start of every prompt in this package, the agent must:

1. Print the current branch and commit.
2. Confirm whether the working tree is clean.
3. Confirm whether the previous prompt’s commit exists.
4. Avoid re-reading files already in its current context unless:
   - the file changed,
   - a command output contradicts the assumed state,
   - a test failure points to the file,
   - or the prompt explicitly requires re-inspection.

## Required Evidence Behavior

For every prompt, the agent must create or update:

- `docs/evidence/remediation/prompt-XX-*/`
- `docs/evidence/remediation/prompt-XX-*/commands.md`
- `docs/evidence/remediation/prompt-XX-*/results.json`
- `docs/evidence/remediation/prompt-XX-*/known-issues.md`

Evidence must include command output summaries and exact pass/fail status. Do not write “green” or “clean” unless the command actually passed.

## Required Git Behavior

Each prompt should end with one conventional commit unless the prompt is explicitly read-only.

Suggested sequence:

1. `chore(audit): reconcile repo truth and closeout evidence`
2. `fix(cli): align auth and run command groups with canonical grammar`
3. `fix(automation): correct launchd executable and command rendering`
4. `fix(validation): make tests lint and type checks pass`
5. `test(graph): refresh delegated graph proof for current runtime`
6. `feat(mail): add bounded in-memory body mention detection`
7. `feat(graph): add bounded paging to read clients`
8. `fix(files): require source provenance for file ingestion`
9. `feat(brief): wire daily brief to current context sources`
10. `fix(security): implement bounded content sensitive scan`
11. `chore(closeout): regenerate truthful final remediation evidence`

## Refusal Conditions

The agent must stop and report rather than proceed if:

- It cannot determine the current repo/ref.
- It detects raw secrets in the repo.
- It would need to enable Microsoft 365 writeback.
- It would need to persist full email bodies.
- It would need to download/parse a file without source provenance.
- It cannot make validation green but is being asked to claim closeout.
