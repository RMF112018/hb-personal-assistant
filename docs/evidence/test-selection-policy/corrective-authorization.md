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

## Corrective cycle R3

**Authorization ID:** `AUTH-PR319-GOV-CORRECTIVE-R3-20260721-001`  
**Repository:** `RMF112018/hb-personal-assistant`  
**Branch:** `chore/proportional-test-selection-policy-v2`  
**Parent SHA:** `a5b1cdb0220982db6d6c956e45d532b0c6187a5c`  
**Pull request:** `#319`  
**Status:** CONSUMED — bounded R3 implementation complete; final exact-head validation and fresh independent re-review required  
**Authority:** Direct operator instruction, “resolve the remaining blockers,” issued 2026-07-21 at approximately 12:43 America/New_York

### R3 review basis

The fresh independent R2 re-review of exact head
`a5b1cdb0220982db6d6c956e45d532b0c6187a5c` returned `REVISE`. It verified
all prior lineages except `PR319-GOV-F-008` / `PR319-RR-F-003`, and opened:

- `PR319-RR2-F-001` — changed-path validation did not enforce the exact authorized 19-path set;
- `PR319-RR2-F-002` — receipt schema 2 omitted the collection command and collection exit code;
- `PR319-RR2-F-003` — required negative fixtures and dependency-failure probes were incomplete.

### Authorized R3 scope

- `scripts/validate-test-selection-governance.py`;
- `.github/workflows/test-selection-governance.yml`;
- `docs/evidence/test-selection-policy/branch-registration.yaml`;
- this authorization record;
- PR #319 description and replacement exact-head evidence references.

### Implemented R3 correction

- separated required read sources from the exact authorized 19-path comparison and
  required exact set equality;
- added executable extra-path and missing-path negative fixtures;
- added receipt schema-2 collection and validator sections carrying exact commands,
  exit codes, collection counts, zero application-test execution, and stored-byte
  hashes for logs and exit-code files;
- added finalizer and verifier modes that cross-check receipt content against
  captured evidence before the workflow may pass;
- added negative fixtures for duplicate issue-form IDs, missing discovery fields,
  malformed dropdown options, alternate generic interpreter fallbacks, interpreter
  without pytest, and missing declared dependency imports;
- validated dependency declarations in the root and construction subrepository
  package metadata;
- preserved failed R3 CI runs rather than relabeling them as successful.

### Preserved R3 diagnostic lineage

1. **Run 34 at `65df3ccab6984cfe943ab8beb73fe277c01f4660`:** exact-head checkout,
   dependency installation, syntax, and bounded collection passed. The validator
   rejected the alternate generic-fallback mutation through the required-token
   assertion before the intended fallback diagnostic. Artifact `8503171052`,
   archive digest
   `sha256:cc11e38f0dba1e1c2060fd9a1e3af277bdf9f9667b45928d1b2551c79cc0102d`.
2. **Run 35 at `f3ceebfb771445d654212368cefa0e8a304319a9`:** exact-head checkout,
   dependency installation, syntax, and bounded collection passed. The validator
   rejected the legacy issue-form mutation through the missing-description check
   before the intended legacy-`about` diagnostic. Artifact `8503311397`, archive
   digest
   `sha256:d0123cd8904b0cf10bf5bdf959711f74ca72c38615f2a2c20b776ea31e6bec69`.

Both failures were preserved and corrected by reordering semantic checks so the
negative fixtures prove the intended invariant and diagnostic.

### Required R3 completion evidence

- exact-head syntax and bounded collection success;
- all static, semantic, dependency, lifecycle, and adversarial checks passing;
- finalized schema-2 receipt containing both command/exit-code pairs and evidence hashes;
- verifier success against the captured log and exit-code files;
- uploaded artifact bound to the final exact head;
- fresh independent re-review before operator acceptance or merge consideration.

### R3 exclusions

R3 does not authorize changes to `scripts/test-safe.sh`, the issue form,
application source, application tests, dependency declarations, schemas,
migrations, runtime, deployment, credentials, secrets, or production surfaces.

## Exclusions

No corrective cycle authorizes merge, cleanup, Phase B activation, deployment,
migration, production mutation, secret changes, destructive Git operations,
risk acceptance, or self-review. A fresh independent re-review must assess the
final corrective head.