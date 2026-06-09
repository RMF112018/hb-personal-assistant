# Prompt 08 — MCP Context Packet Hardening

## Objective

Harden the MCP context packet builder for Phase 10 local-agent and daily-brief workflows.

The MCP packet must be safe, bounded, source-linked, deterministic where possible, and useful as a compact context object for local agents without exposing raw/private content.

## Required repo-truth audit before implementation

Inspect:

- MCP bridge/wrappers
- context packet builders
- daily brief context packet
- source reference model
- raw content boundaries
- tests/evidence for MCP packet behavior
- any existing MCP command or local-agent packet CLI

Record findings in:

```text
docs/evidence/phase-10-full-candidate-implementation/08-mcp-context-packet-hardening/00-repo-truth-audit.md
```

## Implementation requirements

1. Define a safe MCP packet contract.

   The contract must include:

   - packet purpose
   - generated_at
   - source window
   - source refs
   - candidate summaries
   - redaction flags
   - caps applied
   - omitted raw categories
   - freshness/quality warnings

2. Add or improve packet generation command/output.

   The final output must be directly inspectable as JSON and optionally Markdown.

3. Enforce caps and forbidden-content checks.

   The packet should fail closed or redact if content violates safety rules.

4. Integrate with daily brief/local-agent workflows where useful.

   Do not create a second contradictory packet path if one already exists.

5. Keep MCP external writeback disabled.

   This candidate is context generation/readiness only.

## Required final output evidence

Generate in:

```text
docs/evidence/phase-10-full-candidate-implementation/08-mcp-context-packet-hardening/
```

Required files:

- `README.md`
- `00-repo-truth-audit.md`
- `01-mcp-packet-final-output.json`
- `02-mcp-packet-final-output.md`
- `03-cap-enforcement-proof.json`
- `04-forbidden-content-proof.txt`
- `05-source-link-proof.json`
- `06-daily-brief-packet-alignment-proof.md`
- `07-no-external-writeback-proof.txt`
- `08-safety-scan-results.txt`
- `09-production-db-unchanged-proof.txt`
- `validation-commands.txt`
- `validation-results.md`
- `final-output-manifest.md`
- `changed-files.txt`
- `branch-state.txt`

## Validation

At minimum:

```bash
python -m compileall src tests
pytest -q tests -k "mcp or context_packet or packet or source_ref"
```

Run lint/type checks on changed files.

## Commit

Suggested commit:

```text
feat(second-brain): harden phase 10 mcp context packets
```

After committing, wait exactly 10 minutes before Prompt 09:

```bash
sleep 600
```
