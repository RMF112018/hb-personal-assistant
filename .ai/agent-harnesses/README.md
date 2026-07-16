# Agent Harness Adapters

The canonical skill corpus lives at `.ai/agent-skills/`.

Harness directories contain only discovery or invocation adapters. They must not
duplicate or reinterpret the canonical `SKILL.md` content.

- Claude Code: expose skills through `.claude/skills/`
- Codex: expose skills through `.agents/skills/`
- Grok: configure the active local harness to load canonical skills through the
  provided stable prompt and command adapters
