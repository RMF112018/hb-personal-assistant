# Repo-Truth Audit Summary — Phase 10 Ollama-Assisted Candidate Ranking

This planning package was generated from a repo-truth audit of the current GitHub-connected repository state and must be refreshed by the implementing agent before coding.

## Key findings

- The repo already has Phase 10 local-model readiness, provider, structured-output, and hash-only receipt substrate.
- Existing Ollama generation uses local `/api/generate` JSON mode through a narrow client.
- Existing readiness checks probe `/api/tags` without generation.
- Existing structured output client supports Pydantic schema validation, bounded retry/self-repair, single-hop fallback, heavy-profile blocking, and hash-only receipts.
- Existing daily-brief intelligence layer already consumes redacted daily-brief candidates and withholds unsafe/unsourced model advice.
- Existing daily-brief candidate synthesis is deterministic, source-linked, dry-run by default, and no-writeback.
- Existing raw extraction code uses bounded raw excerpts and must not be reused as the model input for this slice. This slice must consume only structured/redacted candidate packets.

## Implementation conclusion

The next slice should not add another extraction engine. It should add an additive ranking / feedback calibration / assembly overlay on top of existing candidates and lifecycle read models.

## Mandatory refresh

Before implementation, rerun the searches in `README.md` and update this file with exact file paths, schema head, CLI names, and test locations from the local working tree.
