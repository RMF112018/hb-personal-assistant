Repository: `RMF112018/hb-personal-assistant`  
Local path: `/Users/bobbyfetting/hb-personal-assistant`  
Branch: `experiment/phase-10-top3-local-model-agent-convergence`  
Evidence root: `docs/evidence/phase-10-top3-local-model-agent-convergence`

Hard constraints apply from `../README.md`, `../STOP_CONDITIONS.md`, and `../reference/02_SAFETY_CONTRACT.md`.

# Prompt 03 — Model Enriched Intelligence Render Surfaces

## Objective

Render the unified model-enriched object into the final browser HTML, Obsidian markdown, and status JSON surfaces with the exact label:

```text
Model Enriched Intelligence
```

## Browser requirements

The browser brief must:

- render **Model Enriched Intelligence** before or near the top of the brief body;
- include model enrichment metadata in safe summarized form;
- include source links/source identifiers as safe candidate/source IDs or hashes;
- include pending V45 email follow-up enrichments as a subsection when available;
- clearly label low-confidence/pending-review items;
- omit the section body if model enrichment is withheld;
- show a degraded/withheld banner when applicable;
- pass existing HTML egress scan.

## Obsidian requirements

The Obsidian brief must:

- render the same section label;
- include the same source-linked advisory content;
- preserve marker-bounded write behavior;
- never include raw content;
- clearly show if the section is withheld/degraded.

## Status JSON requirements

Add a compact status block, recommended path:

```json
{
  "model_enriched_intelligence": {
    "enabled": true,
    "available": true,
    "label": "Model Enriched Intelligence",
    "degraded": false
  }
}
```

Status JSON must not include row-level raw content or raw model output.

## Evidence

Create:

- `06-browser-model-enriched-intelligence-proof.html`
- `07-obsidian-model-enriched-intelligence-proof.md`
- `08-status-json-proof.json`

## Tests

Add render tests verifying:

- label exactness
- safe source identifiers are present
- raw/private patterns are absent
- withheld state renders honestly
- browser auto-open remains false
