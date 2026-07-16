# Codex Adapter

Codex skills are repository-local:

```text
<repo>/.agents/skills/
```

The architecture installer creates symlinks from `.agents/skills/` to the
canonical `.ai/agent-skills/` folders.

Consequential skills disable implicit invocation through `agents/openai.yaml`.
Use explicit invocation, for example:

```text
$aeos-goal-controller
```

Codex must read repository-root `AGENTS.md` and the AEOS Master Index before
substantive work.
