# Model Routing and Extraction Specification

Prepared: 2026-05-25

## Model Roles

| Role | Purpose |
| --- | --- |
| Triage | Fast relevance/noise scoring. |
| Extraction | Actions, commitments, deadlines, prep, file review. |
| Synthesis | Daily Brief and meeting prep narratives. |
| Validator | Schema repair/challenge. |
| Embeddings | Supplemental semantic retrieval. |

## Rules

- Ollama/local models only by default.
- Structured JSON outputs required for extraction.
- Validate with JSON Schema/Pydantic before persistence.
- Every item must include source_record_ids and confidence.
- Inferred dates must identify date source and inference flag.
- Models cannot mutate Microsoft 365, write to Obsidian directly, or invent sources.

See `resources/model-routing.example.yml` and JSON schemas.
