# AGENTS.md

This repository uses AEOS-governed AI-assisted software delivery.

## Required Entry Point

Before performing substantive planning, review, audit, or implementation work, read:

```text
.ai/00_AEOS_MASTER_INDEX.md
```

Then follow the governing sources for the active workflow mode.

## Authority Order

1. Current repository and runtime evidence.
2. Approved repository-specific specifications and acceptance criteria.
3. Repository-local ADRs and policies.
4. AEOS governance standards under `.ai/`.
5. Current operator instructions.
6. Prior conversations or memory.

## Agent Rules

Agents must:

- report branch, HEAD SHA, and worktree state before editing;
- preserve approved scope and architecture;
- produce evidence for claims;
- run required tests or explain why not;
- report deviations before proceeding;
- leave findings traceable.

Agents must not, without explicit approval:

- push;
- force push;
- merge;
- rewrite history;
- delete branches or worktrees;
- reset hard;
- modify secrets;
- deploy;
- run irreversible migrations;
- remove unrelated safeguards or tests.

## Required Final Report

Implementation agents must provide:

1. Disposition.
2. Repository state.
3. Base/head SHAs.
4. Files changed.
5. Implementation summary.
6. Acceptance-criteria matrix.
7. Tests executed and exact results.
8. Evidence.
9. Deviations.
10. Known issues and unverified areas.
11. Final git status.
12. Recommended next gate.
