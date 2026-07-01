# Known limitations (Phase 16)

- Phase 15 must merge to `main` before production rollout; Phase 16 branch stacks on Phase 15.
- Quality preview cues are project-level aggregates when only metric evidence exists.
- Per-activity quality findings only appear when persisted in `schedule_quality_findings`.
- OOS progress is not measured; listed under capability limitations only.
- Full in-app CPM recalculation remains `not_implemented` in downstream readiness.
- Operator technical IDs available only with `include_technical` / operator role on controls API.
