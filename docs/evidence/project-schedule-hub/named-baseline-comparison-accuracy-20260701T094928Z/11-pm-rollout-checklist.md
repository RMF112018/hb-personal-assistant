# PM rollout checklist — Phase 13B

**Project:** `tropical` · **as_of:** `2026-07-03` · **DB:** read-only inventory in `10-tropical-real-db-readonly-inventory.txt`

| Question | Answer | Evidence |
|----------|--------|----------|
| Are Tropical named baseline slots selected? | **Yes** — 3 active slots | `10-tropical-real-db-readonly-inventory.txt` |
| Which `schedule_version_key` per slot? | Contract: `tropical\|815\|2025-08-07 08:00` · Previous: `tropical\|1069\|2026-05-26 08:00` · Secondary: `tropical\|851\|2025-11-28 08:00` | DB inventory + `13b-api-baselines.json` |
| Controls expose comparison provenance? | **Yes** — `provenance.comparison_label`, `baseline_context`, movement `comparison_basis` | `06-api-proof-controls.json` |
| Workbench cues expose comparison provenance? | **Yes** — cue summaries name anchor (read-only GET) | `07-api-proof-workbench.json` |
| Driver Detail exposes comparison provenance? | **Yes** — `baseline_context.schedule_version_key` per named basis | `08-api-proof-driver-detail.json` |
| Disposition fields in Controls? | **Partial** — `review_item_id` on drivers; `review_status` often null on controls cards | `06-api-proof-controls.json` |
| Disposition fields in Driver Detail? | **No** — P2 follow-up; does not block comparison proof | `08-api-proof-driver-detail.json`, shot `08` |
| Workbench filters preserve named comparison basis? | **Yes** — URL + filter UI (`comparison_basis` query) | `07-api-proof-workbench.json`, shot `06` |
| Drilldowns honor `comparison_basis`? | **Yes** — named slot version in drilldown payload | `13b-api-proof-drilldowns.json` |
| Export honor `comparison_basis`? | **Partial** — prior_update 200 with basis in body; contract/secondary **422** `narrative_qa_failed` (safe, no silent fallback); previous 200 but weak basis visibility in excerpt | `13b-api-proof-export.json` |
| prior_update / legacy / named scopes distinct? | **Yes** — movement 461 / legacy unavailable / 440 & 593 | `09-scope-isolation-proof.md` |
| Browser screenshots fully loaded? | See manifest | `12-browser-screenshots/screenshot-proof.json` |
| POST sync required? | **No** — read-only GET sufficient (persisted `psnbri-*` rows present) | `07-api-proof-workbench.json` |
| Blocked / deferred? | Export QA for 2 named bases; Driver Detail disposition UI; legacy `baseline` on Tropical; 1 frontend test assertion drift | `13-known-limitations.md` |

## Operator commands (only if slots were missing — not required for Tropical)

```bash
# Example — DO NOT run without operator approval
curl -X POST -H "X-HB-UI-Role: operator" \
  "http://127.0.0.1:8000/api/projects/tropical/schedule/baselines/current_contract_baseline/select" \
  -H "Content-Type: application/json" \
  -d '{"schedule_version_key": "tropical|815|2025-08-07 08:00"}'
```

Tropical slots are already selected (Phase 12/13 operator setup).
