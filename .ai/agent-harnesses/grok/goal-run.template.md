# AEOS Goal Run

Goal ID: `{{ goal_id }}`
Run ID: `{{ run_id }}`
Active state: `{{ active_state }}`
Selected canonical skill: `{{ selected_skill }}`
Authorization: `{{ authorization_id }}`
Expected checkpoint: `{{ expected_checkpoint }}`

Read:

- `AGENTS.md`
- `.ai/project-sources/00_AEOS_MASTER_INDEX.md`
- `.ai/agent-skills/_aeos-shared/AEOS_SKILL_OPERATING_CONTRACT.md`
- `.ai/agent-skills/{{ selected_skill }}/SKILL.md`
- `{{ goal_charter_path }}`
- `{{ state_path }}`
- `{{ authorization_path }}`

Validate repository branch and HEAD against the authorization before work.

Execute only the active state. Generate the required checkpoint artifacts,
mark the state ready for external review, request but do not activate the next
state, and stop.
