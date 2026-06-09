# Prompt 08 — Docs, Runbook, and Final Handoff

## Objective

Finalize documentation, runbook, evidence index, and implementation handoff.

## Required Docs

Update or add repo-style docs for:

- Email follow-up raw enrichment overview.
- V45 schema note.
- Raw-content boundary policy.
- CLI usage.
- Raw-local preview warning.
- Daily brief pending enrichment behavior.
- Validation/evidence summary.
- Rollback instructions.

Likely locations after repo inspection:

```text
docs/runbooks/
docs/architecture/
docs/evidence/phase-10-email-followup-raw-enrichment/
README.md or project phase ledger if this repo maintains one
```

Do not paste raw email content into docs.

## Required Runbook Sections

The runbook must include:

- Preconditions.
- Safe DB-copy setup.
- Dry-run command.
- Raw-local preview command.
- Apply command with caps.
- Daily brief dry-run command with pending enrichment.
- Evidence generation command/path.
- Failure modes.
- Rollback.
- What is never persisted.
- What operators may inspect locally.

## Rollback Plan

Document:

- Disable CLI flags / do not pass `--with-raw-enrichment`.
- Do not run raw-local preview unless needed.
- V45 table can remain inert if not consumed.
- If necessary, branch rollback by reverting commits in reverse order.
- Production DB rollback should not be needed because validation used copies and apply is capped/idempotent; if V45 reaches production later, rollback should be via migration policy and DB backup.

## Final Validation Before Handoff

Run:

```bash
git status --short
git log --oneline --decorate -12
```

Run targeted tests again if docs touched anything executable.

## Final Handoff

Use `templates/FINAL_HANDOFF_TEMPLATE.md`.

The final handoff must not include raw data.

## Commit

After docs pass:

```bash
git add <docs/runbook files>
git commit -m "docs(email): add raw enrichment runbook and evidence handoff"
```

## Exit Criteria

- Docs updated.
- Evidence index complete.
- Final handoff prepared.
- Working tree clean.
- Implementation branch contains all commits.
- Main untouched.
