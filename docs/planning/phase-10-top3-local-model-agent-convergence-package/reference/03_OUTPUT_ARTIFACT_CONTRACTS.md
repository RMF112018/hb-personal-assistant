# Reference — Output Artifact Contracts

## Browser brief

Must include the **Model Enriched Intelligence** section when the model-enrichment path is safe and available.

Must not include:

- raw bodies
- raw model prompts
- raw model responses
- unsafe HTML
- full URLs
- signed/download/join links
- credential-shaped strings
- email dumps

Must escape content and pass the existing egress scan.

## Obsidian brief

Must include the same **Model Enriched Intelligence** section in markdown.

Must use marker-bounded / governed output rules already present in repo.

## Status JSON

Must include safe metadata only:

```json
{
  "model_enriched_intelligence": {
    "enabled": true,
    "available": true,
    "label": "Model Enriched Intelligence",
    "candidate_count": 0,
    "source_link_count": 0,
    "bullets_kept": 0,
    "bullets_dropped": 0,
    "pending_followup_count": 0,
    "route_selected_profile": "...",
    "terminal_profile_id": "...",
    "withheld_reason": null,
    "degraded": false
  }
}
```

Do not include row-level raw text. Do not include raw prompts/responses.

## CLI JSON

May include structured diagnostics, counts, source IDs/hashes, route metadata, and skip reasons. It must not include raw private content.
