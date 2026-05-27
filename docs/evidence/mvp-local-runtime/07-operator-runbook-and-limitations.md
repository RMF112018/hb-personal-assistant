# Prompt 07 — MVP Operator Runbook and Known Limitations (Process Record)

**Phase**: 15 — MVP Local Runtime Hardening  
**Objective**: Deliver the operator-facing documentation so the local MVP can be run, inspected, and troubleshot without reading code. Produce the three required files and full coverage of the 12 mandated topics.  
**Repository**: RMF112018/hb-personal-assistant (never hb-intel)  
**Graph / Prompt 9**: Explicitly deferred pending admin consent. No workarounds attempted.

## Starting State (Captured Before Any Modifications)

- **Actual HEAD**: `d15610e0e2566ea42fb6be719804beb44202344f` ("docs(evidence): add migration summary and P06 validation output captures")
- **Expected phase HEAD**: `baac7b5cf61d461d3b544262d02ad4c051aa9fa1` (present in history)
- **Branch**: main (ahead of origin by 2 at start of checks)
- **Working tree**: Minor unrelated pre-existing noise only (vault-package-migration untracked artifacts from earlier evidence work). No P07 changes at start of checks.
- **docs/operations/**: Did not exist (created during this prompt).
- **Evidence tree**: Full P06 artifacts present (06-local-runtime-evidence-harness.md + all required outputs/ JSONs + P06 verifier validation-outputs/).
- **Internal phase assets** (targeted reference only): `runbooks/MVP_Local_Runtime_Operator_Runbook.md`, `07_Deferred_Graph_Consent_Closeout_Runbook.md`, `manifest.json`, `PACKAGE_INDEX.md`, `09_Source_Truth_Checklists.md`.

All mandatory starting checks were executed using only allowed targeted methods (git, ls, safe `hb-assistant` / `python -m` CLI with `--json`/`--dry-run`, terminal grep/sed strictly limited to `docs/plans/ph-15-MVP-Local-Runtime-Hardening/` (including runbooks/) + `docs/evidence/mvp-local-runtime/`). No `read_file` on any src/ or prior heavy context files.

Raw capture written to: `docs/evidence/mvp-local-runtime/validation-outputs/07-starting-checks.txt`.

## Key Facts Discovered (Safe CLI + Targeted Grep Only)

**Real local paths** (from `diagnostics env --json` + `paths`):
- App support: `~/Library/Application Support/HB Personal Assistant`
- DB, auth (700), cache/*, logs/{run-logs,error-logs}, evidence all under it.
- Obsidian vault: `~/Documents/Obsidian Vault` (Daily Notes + AI Outputs ready).
- Venv python: `~/hb-personal-assistant/.venv/bin/python`.

**CLI surface** (top-level + diagnostics):
- `diagnostics` subcommands: env, paths, auth, automation, scan-sensitive, proof, store, graph, etc.
- `run morning --dry-run --json`: Graph stages correctly report `skipped_no_token`; local stages (path/store readiness, local_signal_load, classification, action_extraction, workstream_context, ...) succeed.
- `automation` group: install/uninstall/kickstart launchd (label `com.hb.personal-assistant.morning`, 05:00 America/New_York, `catch_up: true`, `weekend_behavior: manual_only`).
- `automation uninstall-launchd --dry-run`: emits exact `launchctl unload -w` + `rm -f` commands.

**Targeted language hits** (phase docs + runbooks + evidence only):
- venv/activate, launchd details, dry-run "never writes" semantics, Graph deferred + Prompt 9 post-consent command chain, 09 checklist (P06 flips already present for local stages continuing + proofs captured), internal draft runbook content — all available via targeted methods.

## Deliverables Created

1. `docs/operations/mvp-local-runtime-operator-guide.md` (primary polished guide)
   - Covers all 12 mandated topics exactly.
   - Uses real captured paths, command output, and behavior.
   - Strong safety language ("prefer --dry-run", "what gets written / what never", marker boundaries, Graph deferred warnings).
   - Cross-reference to `07_Deferred_Graph_Consent_Closeout_Runbook.md` for Prompt 9 readiness.
   - Explicit "Known Limitations & Future" section.

2. `docs/evidence/mvp-local-runtime/06-known-limitations.md` (dedicated extractable limitations document — see separate file).

3. This 07- process record + coverage matrix (below).

## 12-Topic Coverage Matrix

| # | Topic (from Prompt 07)                          | Covered in Operator Guide | Evidence / Source Used (targeted) |
|---|-------------------------------------------------|-----------------------------|-----------------------------------|
| 1 | How to activate venv                            | Yes (exact `source .venv/bin/activate`) | Internal runbook (targeted), diagnostics env |
| 2 | How to run diagnostics                          | Yes (full env/paths/automation/scan-sensitive/auth/store examples) | Safe CLI runs during checks |
| 3 | How to run morning dry-run                      | Yes (`run morning --dry-run --json` + stage explanations) | CLI run + P06 harness precedent |
| 4 | How to run apply/write mode, if supported       | Yes (caution section + marker-bounded reality + recommendation to use --dry-run first) | 03_Hardening dry-run semantics (targeted) + CLI behavior |
| 5 | What gets written locally (apply paths)         | Yes (ledger/evidence, source links, marker-bounded Obsidian sections, cache, logs) | 03_Hardening + diagnostics paths output |
| 6 | What never gets written                         | Yes (full bodies, M365 without consent, outside markers, anything in --dry-run) | 03_Hardening dry-run guarantees (targeted) |
| 7 | Where logs/evidence live                        | Yes (exact `.../logs/` and `.../evidence/` under app support) | diagnostics env + paths |
| 8 | Where SQLite/auth/cache files live              | Yes (exact subpaths + permissions) | diagnostics env + paths |
| 9 | How to disable launchd                          | Yes (exact `automation uninstall-launchd --dry-run` + real commands) | CLI run |
|10 | How to inspect errors                           | Yes (5-step process: JSON, error-logs, diagnostics env/paths, scan-sensitive, automation) | Synthesis of all diagnostics surface |
|11 | What remains blocked by IT/admin consent        | Yes (full Prompt 9 / delegated Graph; graceful local degradation documented) | 00_Project_Context, 07_Deferred_Graph runbook, 09 checklist, README (targeted) |
|12 | How to run Prompt 9 after consent               | Yes (high-level + explicit pointer to `07_Deferred_Graph_Consent_Closeout_Runbook.md` + post-consent command chain) | 07_Deferred_Graph runbook (targeted) + 09 checklist |

All 12 topics are fully addressed with accurate, safe, operator-usable content.

## Decisions Made

- **Noise handling**: Pre-existing vault-package-migration untracked files ignored (unrelated to P07).
- **Internal runbooks/**: Used only via targeted grep + the data already captured in starting checks. The public `docs/operations/` guide is the canonical polished version.
- **Evidence split**: 07- md = process + matrix + decisions; 06-known-limitations.md = clean, extractable limitations list (including Graph deferred + operational ones surfaced here).
- **No new code**: Pure documentation + evidence (as required).
- **Graph discipline**: Every relevant section contains explicit "deferred / no workarounds" language and cross-reference.

## Known Limitations Surfaced or Reinforced During This Prompt

(See the dedicated `06-known-limitations.md` for the full extracted list.)

High-level:
- Graph delegated mail/calendar + Prompt 9 proof fully blocked pending admin consent.
- Apply/write paths remain narrow and always respect Obsidian marker boundaries.
- Weekend automation is intentionally manual_only.
- Operator must rely on `--dry-run` + diagnostics for safe daily operation until consent lands.

## Verification Performed (Pre-Commit)

- All three required files created at exact paths.
- Operator guide covers 12/12 topics with real captured data.
- Sensitive scan will be run on the new tree (see next steps / verifier spawns).
- Commands documented in the guide were executed during checks and match the examples.
- 09 checklist will be updated (P07 section + flips).
- Architecture docs will receive minimal pointer (if major docs trigger applies).

**Next in this prompt**: validation of the new files via re-runs + sensitive scan, minimal arch/checklist updates, verifier spawns (with identical strict guardrails), full verification, and the final commit whose *only* user-visible output will be the traditional manifest summary + description.

---

*Generated during Phase 15 Prompt 07 execution on HEAD d15610e (post-P06).*  
*All work used only targeted methods after mandatory starting checks.*