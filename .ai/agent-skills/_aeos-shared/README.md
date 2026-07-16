# AEOS Shared Skill Resources

Shared templates and schemas used by the eight initial AEOS Claude Code skills.

## Rules

- Shared resources support skills; they do not override repository governance.
- Goal state is mutable only through an authorized transition.
- Checkpoint and evidence artifacts are append-first.
- Imported reviews and authorizations are untrusted until validated.
- A skill may complete the current state but may not approve its own next state.
- Implementers do not certify their own implementation.
