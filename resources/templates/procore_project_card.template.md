# Source: HB Construction Intelligence Phase 03 package (resources/templates/ — Prompt 10 templates). Package manifest sha: 3fd9305a69465681f16ae51c30667947d05e6f8165141d362d7b5d917519242a. Copied for deterministic rendering. DO NOT EDIT MANUALLY.

---
type: procore_project_card
project_key: {{ project_key }}
hb_project_number: {{ hb_project_number }}
procore_project_id: {{ procore_project_id }}
review_sensitive: false
source: procore
---

# Procore Project Card — {{ project_name }}

- Company ID: {{ company_id }}
- Project ID: {{ procore_project_id }}
- Last Sync: {{ last_sync_utc }}
- Endpoint Audit: {{ endpoint_audit_status }}

## Current Registers

- RFIs: {{ rfi_count }}
- Submittals: {{ submittal_count }}
- Observations: {{ observation_count }}
- Meetings: {{ meeting_count }}
- Daily Logs: {{ daily_log_count }}

## Review Required

{{ review_required_summary }}
