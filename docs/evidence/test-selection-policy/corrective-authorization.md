# PR #319 Corrective Authorization Record

## Corrective cycle R1

**Authorization ID:** `AUTH-PR319-GOV-CORRECTIVE-20260721-001`  
**Repository:** `RMF112018/hb-personal-assistant`  
**Branch:** `chore/proportional-test-selection-policy-v2`  
**Parent SHA:** `3f008f4ba7e64a0036ecee913a9eaab24cfa1e75`  
**Pull request:** `#319`  
**Status:** Consumed by bounded corrective implementation  
**Authority:** Direct operator instruction in the Software Delivery Control Room project on 2026-07-21

### Authorized objective

Resolve `PR319-GOV-F-001` through `PR319-GOV-F-008` from the independent
review of exact head `3f008f4ba7e64a0036ecee913a9eaab24cfa1e75`.

### Authorized scope

- lifecycle identity semantics and branch registration evidence;
- canonical safe-suite command and documentation;
- Standard 07/11 precedence;
- durable test-failure triage controls;
- decision review status;
- Phase A authority-status reconciliation;
- exact permanent-identity plan traceability;
- governance validation and exact-head evidence;
- PR description and external validation receipt.

## Corrective cycle R2

**Authorization ID:** `AUTH-PR319-GOV-CORRECTIVE-R2-20260721-001`  
**Repository:** `RMF112018/hb-personal-assistant`  
**Branch:** `chore/proportional-test-selection-policy-v2`  
**Parent SHA:** `43abb04a549d927334959fd2e40745296a6281c2`  
**Pull request:** `#319`  
**Status:** CONSUMED — bounded corrective implementation complete; fresh re-review required  
**Authority:** Direct operator instruction, “resolve the remaining failing items,” issued 2026-07-21 at approximately 11:29 America/New_York

### Review basis

The fresh independent re-review of exact head
`43abb04a549d927334959fd2e40745296a6281c2` returned `REVISE` and preserved
these blocking lineages:

- `PR319-GOV-F-002` / `PR319-RR-F-001` — non-portable interpreter resolution;
- `PR319-GOV-F-004` / `PR319-RR-F-002` — invalid GitHub issue-form top-level schema;
- `PR319-GOV-F-008` / `PR319-RR-F-003` — insufficient semantic validation;
- `PR319-RR-F-004` — inaccurate forecasting evidence classification (non-blocking alone).

### Authorized R2 scope

- `scripts/test-safe.sh`;
- `.github/ISSUE_TEMPLATE/test-failure.yml`;
- `scripts/validate-test-selection-governance.py`;
- `.github/workflows/test-selection-governance.yml`;
- `docs/evidence/test-selection-policy/branch-registration.yaml`;
- this authorization record;
- PR #319 description and exact-head evidence references.

### Implemented correction

- removed generic and operator-specific Python fallback paths;
- required an explicit interpreter or active-worktree `.venv`, executable status,
  Python 3.12+, and the complete canonical safe-suite dependency set;
- replaced invalid issue-form `about` metadata with `description` and added exact
  candidate, command, environment, base evidence, review, integration, and
  closure fields;
- replaced token-only assertions with issue-form semantic validation, negative
  fixtures, safe-suite invalid-input probes, fake-interpreter probes, exact
  lifecycle-state checks, complete governed YAML/front-matter parsing, and
  explicit receipt command and exit code;
- added exact-head CI installation, bounded `--collect-only --python-only`
  execution, always-uploaded diagnostics, and final exit-code enforcement;
- required forecasting CI to be described as synthetic PR merge-result evidence,
  not exact-head governance or full-suite evidence.

### Preserved validation lineage

1. **Run 24 at `65e30e7435e10153c4862ed6b70b8e7bb5d2a048`:** failed during bounded
   collection before validator execution. No tests ran. The failure was preserved.
2. **Run 25 at `63a355480dcfebfbaa1f8b3d960d0f45f96ca3ae`:** diagnostic artifact
   `8501091180` proved validator exit `0` and collection exit `2`; collection
   reported 75 import errors caused only by absent `mcp`, `fastapi`, and `numpy`
   prerequisites. No tests ran.
3. **Run 27 at `2572454ec1cd3c0f43a7d548c569075ce3e9e169`:** complete declared
   environment installed; collection exit `0`; validator exit `0`; enforcement
   passed. Collection result: `10039/10100 tests collected (61 deselected)` with
   zero collection errors and no test execution. Artifact `8501204875`, archive
   digest `sha256:2bcda99bac659e50bde296556f19a50b9701e0559df88a73c5e11185ba8486e0`,
   receipt evidence SHA-256
   `23e6268c2240fb65e6347a170e22dcec81aeb42a269e160d96ce3ae85a4f29db`.

### Canonical Python prerequisite command

```bash
python -m pip install -e '.[dev]'
python -m pip install -e '.[mcp,analytics-ui]' \
  -e 'subrepos/construction-financial-review[dev]'
```

This installs the root development, MCP, and analytics UI dependencies and the
construction subpackage's declared NumPy/SciPy dependencies. The safe script
fails closed when these prerequisites are unavailable.

### Required final validation

- shell syntax validation;
- Python syntax validation;
- complete GitHub issue-form semantic validation with negative fixtures;
- fail-closed interpreter, minimum-version, and dependency probes;
- safe-suite invalid-argument and contradictory-mode probes;
- bounded canonical Python collection only, with no application tests executed;
- exact-head governance workflow and artifact receipt;
- accurate distinction between head-SHA governance evidence and synthetic
  pull-request merge-result forecasting evidence.

## Exclusions

Neither corrective cycle authorizes merge, cleanup, Phase B activation,
deployment, migration, production mutation, secret changes, destructive Git
operations, risk acceptance, or self-review. A fresh independent re-review must
assess the final corrective head.
