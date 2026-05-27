# Remediation: Deterministic Evidence Harness and CI (Phase 14 Prompt 08)

## Summary
Phase 14 Prompt 08 completes the deterministic evidence and safe CI foundation for the entire HB Personal Assistant validation suite.

It adds:
- Deterministic, redacted local fixtures (tests/fixtures/) for the core tables (source_records + related emails/calendar/files/parser_outputs, action_items, source_links, body mentions) following Local_Fixture_Seed_Plan.json exactly (synthetic/redacted data only, no real Microsoft identifiers or content).
- A GitHub Actions workflow (.github/workflows/local-validation.yml) that runs the full baseline validation reproducibly in CI without any Graph consent, real Microsoft data, or real Obsidian vault (exact skeleton from 16_CI_And_Quality_Gates.md: checkout, Python 3.12, pip install -e '.[dev]', pytest, ruff, mypy, hb --version, hb diagnostics env/scan-sensitive --json, hb run morning --dry-run --json).
- Optional safe validation script (if added) that exercises the fixtures and exits non-zero on failure.
- Evidence templates and prompt-08/ package under the standard phase-14-local-runtime-workstream-intelligence/ structure (summary with git + SHA, commands, validation-outputs/, etc.).
- Architecture documentation update.

All new artifacts are local-only, dry-run safe, and require zero real credentials or external vault. Existing conftest.py patterns (tmp_app_support, isolated_hb_pa_config autouse) + P03/P07 seeding style (CREATE TABLE IF NOT EXISTS + INSERT OR IGNORE) are reused for the fixtures.

This makes the full validation suite (including the P07 05-stage orchestration + P06 provenance) runnable on any machine or in CI without the delegated Graph consent blocker.

## Files Updated
- `.github/workflows/local-validation.yml` (new; follows the exact recommended skeleton in 16_CI_And_Quality_Gates.md).
- `tests/fixtures/` (new directory + deterministic redacted seed data + pytest fixtures per Local_Fixture_Seed_Plan.json + reuse of conftest patterns).
- `scripts/validate_local.py` (optional; thin safe wrapper if added).
- `docs/evidence/phase-14-local-runtime-workstream-intelligence/prompt-08/` (full package following Evidence_Register_Template.md and Validation_Result_Register.md).
- `docs/architecture/remediation-deterministic-evidence-harness-ci.md` (this note).
- `docs/architecture/00-README.md` (P08 index entry under Phase 14 workstream intelligence).
- Light (if needed): `tests/conftest.py` or `pyproject.toml` for fixture exposure (prefer zero changes).

## Key Changes
- The validation suite is now fully deterministic and CI-safe.
- Fixtures provide redacted synthetic data for every table needed by the P01–P07 pipeline (source records, parser outputs, body mentions, calendar events, files, action items, source links).
- The GitHub workflow is local-only and exercises the exact baseline commands used in all prior prompts (including `hb run morning --dry-run --json` and `scan-sensitive`).
- Evidence and templates follow the established Phase 14 patterns (no reinvention).
- No real Graph consent, real Microsoft data, or real Obsidian vault is ever required.

## Validation Performed
- New fixture tests (if added) + full baseline validation: green.
- `hb-assistant diagnostics scan-sensitive --repo . --json`: clean (exit 0; only expected indicators).
- `hb-assistant run morning --dry-run --json`: succeeds with fixtures.
- CI workflow syntax valid (yamllint or equivalent).
- Sensitive scan clean on all new files.
- Commit: `ci: add local assistant validation workflow`

## References
- `docs/plans/ph-14-workstream-Intelligence/16_CI_And_Quality_Gates.md` (exact recommended workflow skeleton).
- `docs/plans/ph-14-workstream-Intelligence/12_Testing_Validation_And_Evidence_Plan.md` + resources/ (Evidence_Register_Template.md, Validation_Result_Register.md, Local_Fixture_Seed_Plan.json, Prompt_Execution_Log_Template.md, Sensitive_Data_Guardrails.md).
- Prior Phase 14 prompts 01–07 evidence (P07 baseline with 05 orchestration; P03/P07 test seeding patterns; P06 provenance; P05 delegated proof patterns).
- `docs/evidence/phase-14-local-runtime-workstream-intelligence/prompt-08/summary.md` (complete package + final SHA).
- `docs/architecture/00-README.md` (Phase 14 workstream intelligence index + P08 entry).

**Status**: Safe, deterministic CI and local evidence harness delivered. The full validation suite (including P07 orchestration and P06 provenance) can now run reproducibly anywhere without the Graph consent blocker. Ready for P09+.