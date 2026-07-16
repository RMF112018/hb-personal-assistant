# Claude Code Adapter

The user's Claude configuration is global at:

```text
~/.claude/
```

The repository's canonical AEOS skill corpus remains:

```text
<repo>/.ai/agent-skills/
```

The architecture installer backs up and replaces only these global entries:

```text
~/.claude/skills/_aeos-shared
~/.claude/skills/aeos-goal-controller
~/.claude/skills/aeos-repository-truth
~/.claude/skills/aeos-checkpoint-manager
~/.claude/skills/aeos-implementation-planner
~/.claude/skills/aeos-work-package-executor
~/.claude/skills/aeos-evidence-packager
~/.claude/skills/aeos-independent-auditor
~/.claude/skills/aeos-finding-reconciler
```

Each entry becomes a symlink to the canonical repository folder. Existing
unrelated global skills, agents, settings, tasks, plugins, history, telemetry,
and runtime data are not modified.

Install from the package root:

```bash
python3 scripts/install_agent_harness_architecture.py   --repo /Users/bobbyfetting/hb-personal-assistant   --apply
```

The skills are globally discoverable but must fail closed unless the active
repository provides valid AEOS governance, goal state, and authorization.
