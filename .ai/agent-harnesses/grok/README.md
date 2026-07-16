# Grok Harness Adapter

Grok does not define one universal local-agent configuration surface. Use the
adapter matching the local harness:

1. If the harness supports Agent Skills, point it at `.ai/agent-skills/`.
2. If it supports commands or prompt templates, use the files under `commands/`.
3. For a custom API harness, use `grok-system-prompt.md` as the stable prefix
   and render `goal-run.template.md` with the validated state, authorization,
   and selected canonical skill.

The controller—not the model—must select the active state and skill.
