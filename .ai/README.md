# HB Personal Assistant `.ai/` Control Plane

This directory contains repository-local AEOS governance, reusable agent skills,
harness adapters, goal state, templates, schemas, deterministic validators, and
non-canonical reference material.

## Canonical paths

| Purpose | Canonical path |
|---|---|
| AEOS normative sources | `.ai/project-sources/` |
| Shared agent skills | `.ai/agent-skills/` |
| Harness adapters | `.ai/agent-harnesses/` |
| Goal state and authorizations | `.ai/aeos/goals/` |
| Deterministic AEOS utilities | `.ai/aeos/bin/` |
| Schemas | `.ai/schemas/` |
| Templates | `.ai/templates/` |
| Convenience combined manual | `.ai/reference-bundles/` |

## Repository authority

`.ai/` is part of the repository-local engineering control plane. Apply these
sources in conjunction with:

```text
AI_OPERATING_MANUAL.md
AGENTS.md
docs/decisions/ADR-019-github-first-engineering-control-plane.md
docs/governance/branch-worktree-lifecycle-policy.md
docs/implementation-plans/github-first-control-plane-migration.md
```

The repository and authenticated GitHub state are canonical for active
engineering identity and lifecycle. Runtime evidence is canonical for deployed
behavior. Google Drive is an approved publication/reference surface and must
not independently maintain a competing active-state ledger.

Do not copy the Google Drive root-control documents or Drive inventory into
`.ai/`. Generic AEOS standards may define publication requirements, but
repository-specific Drive IDs belong in the Drive Workspace controls.

## Authority and duplication

`project-sources/` is the canonical AEOS source set. The combined manual under
`reference-bundles/` is a convenience artifact and must not override or replace
the individual normative sources.

The canonical skill corpus exists only under `agent-skills/`. Global Claude and
repository-local Codex receive symlinks; Grok receives thin loader adapters. Do
not maintain independent copies per harness.

The root goal-loop templates and schemas under `.ai/templates/goal-loop/` and
`.ai/schemas/goal-loop/` must remain byte-identical to their canonical shared
copies under `.ai/agent-skills/_aeos-shared/`.

## GitHub-first lifecycle invariants

- Register each non-canonical branch and worktree before substantive editing.
- Bind authorization, review, audit, and evidence to exact repository identity.
- A later head commit invalidates current-head approval.
- Merge transitions work to `MERGED_PENDING_CLEANUP`, not directly to `CLOSED`.
- Inventory, no-prune fetch, preservation, and integration proof precede
  pruning or deletion.
- Worktree removal, local branch deletion, remote branch deletion, worktree
  metadata pruning, and remote-reference pruning are separate actions.
- Post-merge validation and a cleanup, retention, or blocker receipt are
  required before closure.
- Phase B, cleanup, deployment, production activation, and risk acceptance
  require separate explicit operator authorization.

## Install harness links

```bash
python3 scripts/install_agent_harness_architecture.py --repo "$PWD" --apply
```

The installer never replaces real directories. Use `--replace` only to refresh
existing symlinks.

## Validate

```bash
python3 .ai/agent-skills/_aeos-shared/scripts/validate_skill_package.py
python3 .ai/aeos/bin/validate_ai_layout.py
python3 .ai/aeos/bin/generate_checksums.py
```

Validation must reject recursive macOS metadata, prohibited legacy schemas,
root/shared schema or template divergence, missing GitHub-first policy
pointers, invalid manifests, and checksum drift.

## Start a goal

Create a governed package under:

```text
.ai/aeos/goals/<goal-id>/
```

Use the templates under `.ai/templates/goal-loop/`.

Then invoke the harness-specific goal controller. The model may complete only
the currently authorized state and must stop at the next external-review or
operator-authorization gate.

## Root instruction alignment required

Repository-root instruction files should consistently reference:

```text
.ai/project-sources/00_AEOS_MASTER_INDEX.md
```

Do not alternate between `.ai/00_AEOS_MASTER_INDEX.md` and the canonical path.
