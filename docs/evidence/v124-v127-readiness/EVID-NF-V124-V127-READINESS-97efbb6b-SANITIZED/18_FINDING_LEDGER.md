# 18 — Finding Ledger — v6 (remediation-corrected)

generated_utc: 2026-07-16 (v6)
**Four separate fields, never conflated:** Finding status ∈ {OPEN, FIX CLAIMED, VERIFIED FIXED, DEFERRED WITH
ACCEPTED RISK, REJECTED WITH RATIONALE, NOT REPRODUCIBLE} · Evidence trust ∈ {trusted, partially_trusted,
untrusted, conflicting, not_evaluated} · related AC status (from 17) · Independent verification.
**The evidence agent marks findings no higher than `FIX CLAIMED`.** A fresh independent reviewer owns any
`VERIFIED FIXED`. Findings never disappear; IDs and disposition history are preserved.

## Part A — Original readiness findings (carried, statuses corrected)

| ID | Severity | Finding status | Evidence trust | Related AC | Title / note |
|---|---|---|---|---|---|
| **NF-DEP-001** | High | OPEN | trusted | AC-24 | V127 deployment artifact + authorized V124→V127 managed migration not yet performed in production. Evidence collected (candidate image, rehearsed migration, backup/restore); deployment NOT performed (out of scope). Independent deployment-readiness review + maintenance-window execution required. |
| **NF-ENV-001** | Medium | OPEN | partially_trusted | AC-22 | Candidate/current-main opened-connection classification on the live managed target. Live probe bound the real inode + denied unauthorized/spoofed/snapshot targets, but the single **live canonical-path** MANAGED_PRODUCTION observation was not obtained (host NAS deep-mount quirk); canonical proof is local only. Combining is inference. Independent corrective review owns VERIFIED-FIXED. |
| **NF-DOC-001** | Medium | OPEN | trusted | — | NF-F-001 design/plan/plan-review/impl-audit/corrective-review/runbook not committed anywhere; artifact trail is git history + external governance review v1.2 only. |
| **NF-GOV-001** | Medium | OPEN | trusted | — | `main` has no branch protection and no rulesets (governance decision, not a code task). |
| **NF-DOC-002** | Low | **RESOLVED (against current main)** | trusted | — | Was: AGENTS.md / AI_OPERATING_MANUAL.md pointed to `.ai/00_AEOS_MASTER_INDEX.md` (actual `.ai/project-sources/00_AEOS_MASTER_INDEX.md`). Per PR #314 (current main e0f3650b), both now route correctly to `.ai/project-sources/00_AEOS_MASTER_INDEX.md` — obsolete against current repository truth (CORR-AUD-004). |
| **NF-IMG-001** | **Medium** (raised from Informational) | OPEN | trusted | AC-08 | No registry repository digest / environment-authoritative deployment-artifact identity. A hashed, **offline-integrity-verified** private image archive (W7; archive metadata integrity PASS, 15/15 blobs; **Docker reloadability NOT VERIFIED**) preserves the candidate and binds it to source commit 97efbb6b, but the **final deployment artifact identity is NOT VERIFIED**. Closure needs a private-registry repo digest (or approved equivalent) + proof the exact retained candidate is the deployed artifact. |
| **NF-ENV-002** | Low (info) | OPEN | trusted | — | host container platform deep-`<nas-vol2>` bind destination yields an EMPTY mount; blocks a single-call live canonical proof (worked around by short-path mount + local canonical semantics). |
| **NF-DB-001** | Low (info) | OPEN | trusted | — | Live DB `journal_mode=delete` yet a stale non-empty `-shm` beside it; cosmetic (immutable read used `-wal=0`). |
| **GOV-GIT-001** | Medium | OPEN | trusted | — | Evidence-production governance: during v4 assembly a branch holding the initial v4 commit (`3779bcca…a31b`) was **deleted** — a prohibited destructive Git operation performed without authorization. Remediated for GC-risk only in v5 via a durable local archival ref `refs/archive/failed-gate-b/3779bccae912a4ed17aba28b9116fe530906a31b` (operator-authorized preservation; not pushed). Preservation does **not** ratify the deletion; this finding remains OPEN pending separate operator adjudication + independent review. |

## Part B — Independent-audit findings (EVID-AUD-001..007) reconciled with disposition history

> Severity note (CORR-AUD-005): the independent audit designated EVID-AUD-001..007 as **blocking** findings. The
> "High" severity below reflects that blocking origin; it is not an independent agent re-grading. Finding STATUS
> (agent-assignable) is `FIX CLAIMED` at most; a fresh reviewer owns severity confirmation and `VERIFIED FIXED`.


| ID | Severity | Finding status (agent) | Evidence trust | Corrective evidence (this remediation) | Disposition history |
|---|---|---|---|---|---|
| **EVID-AUD-001** | High | FIX CLAIMED | partially_trusted | Publication-sensitivity remediation: two-artifact redaction model (`PRIVATE_REDACTION_MAP` private, `PUBLIC_REDACTION_POLICY` public), sanitized public tier (runtime JSON/logs summarized, unrelated inventory removed, tokens redacted), two-stage fail-closed publication gate (`19b`). Raw topology kept in the private store only. | Audit: FAIL → remediation: FIX CLAIMED. Independent publication review REQUIRED before any push. |
| **EVID-AUD-002** | High | FIX CLAIMED | partially_trusted | Command receipts added (private `commands/`). NAS read-only probes + image build + <db-size> rehearsal → **RECONSTRUCTED** receipts (partially_trusted, Re-executed:No, Prod host contacted:No). No new NAS activity; no material reruns. | Audit: FAIL → "EVIDENCE COLLECTED — INDEPENDENT VERIFICATION REQUIRED." Affected NAS-probe AC stay PARTIAL/partially_trusted. |
| **EVID-AUD-003** | High | FIX CLAIMED | partially_trusted | NF-ENV-001 corrected: AC-22 → PARTIAL, NF-ENV-001 stays OPEN; `10`/`21` wording corrected (live probe ≠ single canonical observation). | Audit: FAIL → remediation: FIX CLAIMED (finding remains OPEN by design). |
| **EVID-AUD-004** | High | FIX CLAIMED | trusted | Migration-route corrected: AC-15 split — engine rehearsal PASS (trusted) vs integrated MANAGED_PRODUCTION operator-route NOT VERIFIED. Carried into `11`/`12`/`14`/`15`/`17`/`21`. | Audit: FAIL → remediation: FIX CLAIMED. |
| **EVID-AUD-005** | High | FIX CLAIMED | trusted | Mutation statement corrected (`00`/`21`): "Authorized production-host state change occurred through candidate image loading and ephemeral container lifecycle. No production service, live database, deployed configuration, or running production container was modified." | Audit: FAIL → remediation: FIX CLAIMED. |
| **EVID-AUD-006** | High | FIX CLAIMED | trusted | Durable `AUTHORIZATION_RECORD.md` (Decisions template) with verbatim operator ratification, distinct auth vs receipt timestamps, provenance, SHA-256. `00` no-commit prohibition reconciled. | Audit: FAIL → remediation: FIX CLAIMED. |
| **EVID-AUD-007** | High | FIX CLAIMED | partially_trusted | Hashed Docker image archive (private) exported from the already-identified candidate (no rebuild) + EXPORT/RELOAD receipts. Three separate claims: archive metadata integrity, reloadability, final deployment identity (NOT VERIFIED). NF-IMG-001 → Medium/OPEN. | Audit: FAIL → remediation: FIX CLAIMED; final deployment identity still NOT VERIFIED. |

## Preserved from prior review v1.2 (carried forward, not re-adjudicated)
- NF-MR-REV-002 (non-blocking): no branch protection on main — same condition as NF-GOV-001, re-confirmed.
- NF-F-001 acceptance criteria (AC-01..16) were VERIFIED-FIXED at merge per review v1.2 (authenticated in 04);
  this package does not re-open them.

## Note on rebuilt closure (operator ratification clause 5)
Any claim depending specifically on the *unavailable original* closure archive remains **NOT VERIFIED**. The
rebuilt package is successor evidence only (its own identity/provenance/SHA-256). Reflected in AC-06 (PARTIAL).
