# HB Personal Assistant `.ai/` Control Plane

This directory contains repository-local AEOS governance, reusable agent skills,
harness adapters, goal state, templates, schemas, and reference material.

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

## Authority and duplication

`project-sources/` is the canonical AEOS source set. The combined manual under
`reference-bundles/` is a convenience artifact and must not override or replace
the individual normative sources.

The canonical skill corpus exists only under `agent-skills/`. Global Claude
and repository-local Codex receive symlinks; Grok receives thin loader adapters. Do not maintain independent
copies per harness.

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
```

## Start a goal

Create a governed package under:

```text
.ai/aeos/goals/<goal-id>/
```

Use the templates under `.ai/templates/goal-loop/`.

Then invoke the harness-specific goal controller. The model may complete only
the currently authorized state and must stop at the next external-review gate.

## Root instruction alignment required

Repository-root instruction files should consistently reference:

```text
.ai/project-sources/00_AEOS_MASTER_INDEX.md
```

Do not alternate between `.ai/00_AEOS_MASTER_INDEX.md` and the canonical path.
