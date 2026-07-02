# Future: Dynamic Local Classification (Phase 10L-F)

**Status: NOT implemented in Phase 10L.** Document typing today is deterministic-only
(`source_analyzers.from_detail` + the guarded `source_document_classifier` repair). This document scopes
the future two-layer classifier.

## Architecture

1. **Deterministic classifier first** — fast, no model, current provenance controls preserved. High-
   confidence known patterns are decided here and never sent to a model.
2. **Local Ollama-assisted fallback** — only when deterministic classification is low-confidence or
   ambiguous. Reuse `OllamaChatClient.generate_json` (in `construction/classification/client.py`) via the
   `obsidian_mcp/llm.py` `_resolve_backend` seam. Tests mock the backend (never a live model).

## Output schema (target)

```json
{
  "document_type": "string",
  "domain": "work|home|shared|unknown",
  "project_identity_candidates": [
    {"project_key": "string", "project_number": "string", "confidence": 0.0,
     "evidence_kind": "folder|filename|content|metadata|operator|unknown"}
  ],
  "topic_tags": ["string"],
  "source_type_tags": ["string"],
  "review_tags": ["string"],
  "confidence": 0.0,
  "review_required": true,
  "classifier": {"mode": "deterministic|ollama", "model": "qwen2.5:14b",
                 "prompt_version": "string", "schema_version": "string"}
}
```

## Safety constraints

- Local model only (`qwen2.5:14b` default); no cloud calls.
- Schema-bound JSON, confidence-scored, review-gated.
- No freeform production tags — proposed tags go to a `review/proposed/*` namespace only.
- The local model cannot override a high-confidence deterministic classification without the explicit
  guarded repair workflow.
- Classification cannot rely on file path alone.
- Raw prompts/outputs, if captured, live only under `local-sensitive/`; safe evidence is counts + enums.

## Explicitly out of scope for Phase 10L

No classifier code, schema, or Ollama wiring for document typing is added in Phase 10L.
