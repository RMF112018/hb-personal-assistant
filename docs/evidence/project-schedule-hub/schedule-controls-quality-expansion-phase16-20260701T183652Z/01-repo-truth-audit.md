# Phase 16 repo-truth audit

## Preflight

- Phase 15 **not merged** to `origin/main` at implementation start; Phase 16 branched from `feature/schedule-identity-review-trust-gating-phase15-20260701T165632Z` (`a15998c8`).
- Phase 15 PR: https://github.com/RMF112018/hb-personal-assistant/pull/255
- Phase 15 smoke/API + browser evidence captured under Phase 15 evidence `phase15-smoke/`.

## Quality engine (existing)

- `schedule_quality_engine.py` persists DCMA metrics, sparse findings, scorecards with `downstream_readiness_json`.
- Aggregate logic counts (open starts/finishes, duplicate/self ties) live in metric `evidence_json`; not per-activity finding rows.

## Phase 16 additions

- `project_schedule_quality_controls_service.py` — PM-safe quality read model with 9 control groups + capability limitations.
- `project_schedule_controls_service.py` — wires quality controls, PM redaction (`include_technical` for operator), expanded sections.
- `project_schedule_review_cue_service.py` — project-level quality preview cues from aggregate metric evidence only.
- `project_schedule_memo_service.py` — `## Schedule Quality Controls` export section.
- `ScheduleControlsPanel.tsx` — scorecard, trust, expandable quality groups, limitations, recommended actions.
- `project_schedule_narrative_qa.py` — `validate_rendered_text()` for Controls/Export copy QA.

## Non-fabrication rules enforced

- No per-activity findings synthesized from aggregate evidence.
- OOS progress remains capability limitation via `default_capability_limitations()`.
- Identity/analytics gates cap `quality_trust_status`.
