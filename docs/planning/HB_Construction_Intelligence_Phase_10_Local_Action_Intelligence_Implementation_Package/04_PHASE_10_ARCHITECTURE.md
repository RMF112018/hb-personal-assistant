# 04 Phase 10 Architecture

## Target architecture

```text
Graph / Procore / Calendar / Files / SQLite / Obsidian
        |
        v
Source refresh + local read models + data quality gates
        |
        v
Phase 10 AI job queue
        |
        +--> deterministic prefilter/rules
        +--> local model structured extraction
        +--> schema validation
        +--> candidate records + receipts
        |
        v
Review Queue / My Dashboard / Daily Brief / Obsidian / MCP packets
```

## Runtime layers

1. `local_ai.runtime`
   - provider interface;
   - Ollama provider;
   - readiness check;
   - structured JSON call;
   - timeout/fallback handling.

2. `local_ai.contracts`
   - Pydantic/JSON Schema output contracts.

3. `local_ai.jobs`
   - job queue;
   - job runs;
   - job steps;
   - receipts;
   - no-overlap lock reuse.

4. `action_intelligence`
   - task extraction;
   - commitment extraction;
   - inbox classification;
   - relationship candidates;
   - follow-up watch items;
   - Daily Brief action candidates.

5. `obsidian.manager`
   - read-only index;
   - marker-bounded writes;
   - tag/frontmatter suggestions.

6. `mcp.packets`
   - Claude context packets;
   - read-only resources;
   - packet receipts;
   - prompt templates.

## Key design rule

Models propose. Deterministic policy validates. Users approve.
