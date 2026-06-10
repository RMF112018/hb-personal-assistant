# Final Output Manifest — <candidate-name>

## Intended operator-facing output

Describe the output this candidate is meant to produce in real usage.

## Generated proof artifacts

| Artifact | Path | Generated from | Safe to commit? | Notes |
|---|---|---:|---:|---|
| <name> | `<path>` | synthetic / sanitized / temp DB / live read-only | yes/no | <notes> |

## Output acceptance criteria

- It is understandable to Bobby/operator without inspecting internals.
- It includes source IDs or citations where required.
- It distinguishes model inference from confirmed source facts.
- It is redacted/sanitized.
- It does not contain forbidden content.
- It has a stable path or stable CLI invocation when applicable.

## Manual verification command

```bash
<command>
```
