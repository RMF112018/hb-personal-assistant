# Source: HB Construction Intelligence Phase 03 package (resources/templates/ — Prompt 10 templates). Package manifest sha: b193079f709a06e1b0f8be685cc02bca20c37720ae404ee49b6514f9ae6594cf. Copied for deterministic rendering. DO NOT EDIT MANUALLY.

---
type: procore_review_required
review_id: {{ review_id }}
project_key: {{ project_key }}
sensitivity: {{ sensitivity }}
status: open
---

# Review Required — {{ title }}

Reason: {{ reason }}

Source Table: `{{ source_table }}`
Source ID: `{{ source_id }}`
Source URL: {{ source_url }}

## Safe Summary

{{ safe_summary }}
