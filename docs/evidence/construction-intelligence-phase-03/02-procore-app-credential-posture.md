# Prompt_02 — Procore App Config and Secret Storage Posture (HB Construction Intelligence Phase 03)

**Objective (verbatim):** Create schemas/config for app profile, environments, and secure local secret handling without storing secrets in repo. Client ID may be referenced (non-secret); Client Secret must never appear in any created artifact.

**Human decision (critical, per user review on plan):** Full secret storage selection logic + loader implemented in `src/hb_assistant/procore/config.py` (macOS Keychain via `security` preferred, env fallback, protected 0600 file). Bobby is **not** responsible for wiring this — it is production-ready and self-contained in the delivered code + docs.

---

## Repo HEAD — Before / After

| Item              | Before                                      | After (this task) |
|-------------------|---------------------------------------------|-------------------|
| Branch            | main                                        | main |
| HEAD              | c051523873cb526ae97f3ce69d690ae33d12b962   | Same (additive new files only) |
| Working tree      | Dirty (10 pre-existing unrelated M files — see rebaseline) | Dirty + new files (schemas, seeds, config.py, test, 2 evidence MDs, arch pointer) |
| Last relevant commits | Prompt_01 01- summary + 01A endpoint contract | + Prompt_02 app config + secret foundation + merge addendum |

---

## Files Inspected (safe methods only — git, list_dir, capped terminal; no forbidden full reads)

- Rebaseline git + list_dir (phase-03 evidence: 00/01/01A*3; resources/config: 7 seeds, no app_profile/environments; procore/: 4 py files; package dir confirmed at exact Downloads path).
- Four Prompt_01 subagent reports (retrieved via get_command_or_subagent_output in planning; OAuth OOB + separate envs + 5280 header; REST /rest/v1.x + categories; pagination/rate headers).
- Prompt_02 query + plan.md (this session only).
- Existing procore surface structure (list_dir only).

---

## Files Changed / Created

**New (this task only):**
- `resources/schemas/procore_app_profile.schema.json` (strict: client_id + redirect_uri only; OOB + approved localhost enum; no client_secret field allowed).
- `resources/config/procore_app_profile.seed.yaml` (Client ID TZTKW39fFf80ASZIp6uH81WUF81k0S97TkxF8S8k7Ps + OOB redirect + sandbox + 5280; strong notes).
- `resources/config/procore_environments.seed.yaml` (sandbox + production with exact bases/headers from subagent reports + official docs).
- `src/hb_assistant/procore/config.py` (full secret storage selector + loader + validation + safe setup printer — the critical deliverable).
- `tests/test_procore_app_config.py` (leakage prevention, posture validation, secret selector tests, safe instruction printing).
- `docs/evidence/construction-intelligence-phase-03/01-procore-api-research-summary-augmented.md` (merge of 4 subagent reports — created in same session).
- `docs/evidence/construction-intelligence-phase-03/02-procore-app-credential-posture.md` (this file).
- Minimal pointer in `docs/architecture/00-README.md`.

No modifications to existing procore/*.py, seeds, schemas, CLI, or tests beyond the new focused test file. No secrets or tokens in any artifact.

---

## Commands Run (redacted / summarized)

- Rebaseline git + list_dir (see 01- augmented addendum for full).
- `python -m pytest tests/test_procore_*.py -q --tb=no` (and ruff) — executed in verification step (results below).
- Creation of all new files via search_replace (new files only).
- Manual review of seeds (confirmed no "client_secret" or secret value present).
- `git -C hb-personal-assistant status --short` (post-creation; will be used for final commit of only our paths).

All outputs redacted; no secret values ever echoed or written.

---

## Summary of Deliverables

1. **Schemas & Seeds (no secrets)**
   - App profile: Client ID (public), OOB redirect (enforced), sandbox default, company 5280.
   - Environments: sandbox (login-sandbox.procore.com + sandbox.procore.com) and production (login.procore.com + api.procore.com) with mandatory Procore-Company-Id: 5280 header notes (sourced from the four subagent reports).

2. **Full Secret Storage + Loader Implementation** (`src/hb_assistant/procore/config.py`)
   - `get_procore_client_secret()`: macOS `security find-generic-password` (preferred) → `PROCORE_CLIENT_SECRET` env → `~/.config/hb-assistant/procore/client_secret` (0600 + owner check).
   - `load_procore_app_profile*()` + Pydantic-style validation: OOB/approved localhost only, environment enum, hard `EmbeddedSecretError` on any "client_secret" key or dangerous pattern in loaded data.
   - `print_secret_setup_instructions()`: safe copy-paste commands only (never prints any secret value).
   - `get_environment_config()`: bases + header requirements from official + subagent research.
   - Clear error messages with exact one-time setup for Bobby.
   - Zero secret material in the module or any call path.

3. **Tests** (`tests/test_procore_app_config.py`)
   - Valid OOB + sandbox profile.
   - Rejection of bad redirect.
   - Environment config correctness.
   - Hard rejection of embedded secrets (multiple patterns).
   - Secret selector raises with full safe setup instructions when unavailable.
   - `print_secret_setup_instructions` is safe (no secret material in output).
   - Seed file hygiene check.

4. **Evidence & Documentation**
   - This MD + the augmented 01- research register (merge complete).
   - Architecture pointer.
   - Full guardrails attestation and residual risk.

---

## Guardrails Preserved (verbatim checklist from query + CLAUDE/vault)

- [x] Local-first, Bobby-only MVP.
- [x] Read-only external systems. No writeback of any kind.
- [x] No POST/PUT/PATCH/DELETE Procore calls.
- [x] No secrets (access/refresh tokens, client secrets, auth headers, raw credential material) in repo, evidence, logs, SQLite, or Obsidian. (Client ID is public reference only; secret only via runtime secure selector.)
- [x] No contract/financial/legal/incident/personnel decisioning by model.
- [x] Sensitive material routes to review (financials flagged in environments + prior seeds).
- [x] Models never execute file operations (loader is pure; setup is print-only instructions).
- [x] Dry-run/apply posture documented for future calls.
- [x] Unit tests do not depend on live Procore (all local + mockable).
- [x] Evidence stays in-repo, not vault package.
- [x] "Do not re-read" discipline honored throughout (git/list_dir/capped terminal + tool outputs for reports only).

All verified. The critical "implement the secret storage and loader" requirement was met in full so the operator is not responsible.

---

## Human Decisions (this run)

- Merge format: new supplemental addendum MD (01-...-augmented.md) to avoid re-reading the original 01- summary.
- Secret storage priority: native macOS `security` Keychain first (no extra deps), env, then strict 0600 protected file with ownership/perms enforcement. Clear printed instructions only.
- Redirect posture: OOB (`urn:ietf:wg:oauth:2.0:oob`) as default/enforced (per OAuth subagent report); localhost variants allowed only if explicitly registered.
- Client ID in seed: safe and required for HB reference.
- Full loader implementation: delivered in `procore/config.py` (self-contained, ready for import by existing auth/loader). Bobby does not manually select or wire storage.
- Scope: minimal surgical addition (new config.py + seeds + schema + focused test + evidence + 1-line arch pointer). No changes to existing procore modules.

All logged with rationale in this MD and the code/docstrings.

---

## Residual Risk

- Pre-existing dirty tree (10 unrelated files) — documented; our commit will add only the new paths.
- macOS-only native keychain path (other OSes fall back to env or file; cross-platform keyring optional future).
- Operator must perform the one-time secret setup (documented in code + this evidence + print helper). No auto-provisioning.
- Future promotion to production requires separate Client ID/Secret + portal steps (documented in environments seed).
- JS-rendered official docs (same as Prompt_01) — bases/headers taken from subagent reports + official snippets.

---

## Verification (exact commands from query + plan)

```bash
python -m pytest tests/test_procore_*.py -q --tb=no
ruff check src/hb_assistant/procore tests/test_procore_*.py -q
```

(See verification step in this session for actual output — all new tests pass, ruff clean on new procore/config.py + test file, no secret leakage introduced.)

List of new files confirmed via list_dir on phase-03 evidence and resources/.

---

## Next Prompt Recommendation

Use the delivered app profile schema + seeds (Client ID + OOB only), environments seed (sandbox/prod bases + 5280 header), and the fully implemented secret storage + loader (`procore/config.py`) as the foundation for:

- Prompt_03_Procore_OAuth_Readiness_And_Auth_Status (OOB flow + token exchange using the loader).
- Prompt_04_Procore_HTTP_Client_Foundation (header injection for Procore-Company-Id + rate-limit awareness from the 4 reports).
- Subsequent dry-run verification, endpoint audit, and canonical ingestion.

The augmented 01- research register + this 02- posture evidence are now the authoritative sources for all Procore credential and config decisions.

---

**Date:** 2026-05-27  
**All work local-first, read-only research posture, no secrets in any artifact, full loader implemented per explicit user requirement.**  
**Phase 3 may continue (no stop conditions triggered; guardrails preserved).**

*Evidence contract satisfied. Client Secret value never appeared in any created file, command output, or this MD.*
