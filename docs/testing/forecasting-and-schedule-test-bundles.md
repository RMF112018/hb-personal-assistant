# Forecasting and Schedule Test Bundles

The forecasting and schedule bundles are focused domain validation. They do not
replace the canonical merge-safe repository gate and are not default canaries
for unrelated work.

Governing sources:

```text
.ai/project-sources/07_AEOS_LOCAL_AGENT_OPERATING_CONTRACT.md
.ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md
docs/decisions/DECISION-PROPORTIONAL-TEST-SELECTION-001.md
```

## Canonical commands

```bash
scripts/test-forecasting.sh
scripts/test-schedule.sh
bash scripts/test-safe.sh
```

`bash scripts/test-safe.sh` is the complete merge-safe gate. It runs Python
`tests/` with `integration`, `manual`, and `live` excluded, then the frontend
Vitest suite. It fails when required frontend dependencies are unavailable.

Diagnostic modes:

```bash
bash scripts/test-safe.sh --collect-only   # Python collection only; not a full gate
bash scripts/test-safe.sh --python-only    # Python component only
bash scripts/test-safe.sh --frontend-only  # Frontend component only
```

The canonical script rejects selected test paths, node IDs, custom marker
expressions, and arbitrary pytest arguments. Those are targeted diagnostic or
acceptance commands, not the full merge-safe gate. Unfiltered `pytest` requires
an exact authorization because it may include external, manual, or live tests.

## Selection matrix

| Change surface or gate | Forecasting | Schedule | Merge-safe gate |
|---|---:|---:|---:|
| Isolated source-index repository, connector model/service, or direct tests | Only with demonstrated dependency | Only with demonstrated dependency | No during implementation; yes when exact merge gate applies |
| Forecast generation/config/read models/gates/API/UI/financial normalization | Yes | Only with demonstrated dependency | No during inner loop |
| Schedule ingestion/parsing/quality/CPM/mapping/projection/migration | Only with demonstrated dependency | Yes | No during inner loop |
| `src/hb_assistant/store/migrator.py`, shared schema/bootstrap, or common DB used by both | Yes | Yes | At applicable candidate/merge gate |
| Shared CLI/API/data contract spanning both domains | Yes | Yes | At applicable candidate/merge gate |
| Global fixtures, discovery, dependencies, packaging, runtime bootstrap | Affected bundles | Affected bundles | Yes |
| Broad cross-domain refactor, merge, or release | Affected bundles | Affected bundles | Yes |
| Governance-only change | No | No | No application execution; validate governance scripts/contracts |

Every mandatory bundle maps to an acceptance criterion, changed dependency,
shared-infrastructure risk, named regression risk, or exact gate. Prior use or a
generic evidence template does not establish a trigger.

## Execution frequency

- Inner loop: smallest relevant node, class, file, or changed-module check.
- Coherent slice: directly affected tests and integration seams.
- Candidate: complete bounded work-item acceptance suite.
- Committed checkpoint: triggered suites once per materially different SHA.
- Merge/release: `bash scripts/test-safe.sh` and any gate-specific evidence.
- Bookkeeping-only turns do not rerun unchanged evidence.

## Forecasting bundle

`scripts/test-forecasting.sh` uses an explicit pytest target allowlist and the
marker expression `not integration and not manual and not live`. Run it for
forecast generation, configuration, read models, semantic/readiness gates,
forecast API/UI, forecast-related financial normalization, or demonstrated
shared dependencies.

## Schedule bundle

`scripts/test-schedule.sh` uses an explicit pytest target allowlist and the same
safe marker exclusion. Run it for schedule ingestion, XER/XML/MSP parsing,
schedule quality, critical path/float, mapping, cost controls, projections,
migrations, or demonstrated shared dependencies.

Its migrator/schema targets make it an appropriate cross-domain canary for
changes to `src/hb_assistant/store/migrator.py` or verified common
schema/bootstrap behavior. It is not a default canary for isolated source-index
runtime work.

## Maintaining bundles

The domain bundles use explicit allowlists. Add, rename, or remove targets when
matching tests change and preserve intentional exclusions with reasons. Validate
bundle changes with shell syntax and collect-only commands for the affected
bundle only. Do not add integration/manual/live or external-service tests to a
focused bundle.

## Failure disposition

Preserve every failure and create durable triage identity under
`docs/governance/test-failure-triage.md`.

- Candidate regression: stop and fix within current authorized scope.
- Reproducible pre-existing defect: preserve equivalent base evidence and request
  separate corrective authority.
- Invalid/stale test: request bounded test correction; do not weaken or delete it.
- Flaky/nondeterministic: preserve repeated-run evidence and request stabilization.
- Environment/configuration: correct or document environment; do not claim green.
- Unknown relationship: treat as potentially related and stop the checkpoint.

Parallel corrective work requires separate authorization and isolated
branch/worktree, files, evidence, review, and integration. No integrated
candidate is merge-ready while an applicable required test remains unresolved.
