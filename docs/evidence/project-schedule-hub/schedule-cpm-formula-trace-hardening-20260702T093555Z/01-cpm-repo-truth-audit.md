# CPM repo-truth audit

Date: 2026-07-02

## Scope

Formula-trace hardening for schedule CPM evidence export prior to full 14-stage clean-DB validation.

## Existing CPM surfaces (repo-truth)

| Surface | Path |
|---------|------|
| Recompute orchestration | `src/hb_assistant/construction/analytics/schedule_cpm_recompute_service.py` |
| Graph service | `src/hb_assistant/construction/analytics/schedule_cpm_service.py` |
| Forward / backward / float / longest-path / criticality | `schedule_cpm_forward_pass.py`, `schedule_cpm_backward_pass.py`, `schedule_cpm_float.py`, `schedule_cpm_longest_path.py`, `schedule_cpm_criticality.py` |
| Persistence | `src/hb_assistant/store/schedule_cpm_tables.py`, `schedule_cpm_repository.py` |
| Import trigger | project + global schedule import commit paths |

## Chain model

Terminal `--latest` resolves from **criticality** and walks `source_run_id` backward:

`criticality → longest_path → float → backward_pass`, with `forward_pass` matched by shared `import_id`.

## Gap closed

Prior observability persisted stage outputs but lacked an independent **formula-level computation ledger** with triple diff (persisted vs engine-recomputed vs shadow formulas).

## New modules

- `schedule_cpm_shadow_formula_evaluator.py` — independent shadow math + candidate audit
- `schedule_cpm_formula_trace.py` — lineage resolver, trace builder, exporter
- `scripts/dev_schedule_cpm_formula_trace_export.py` — read-only CLI with exit codes 0–4
