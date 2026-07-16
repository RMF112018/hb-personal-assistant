# 17 — Acceptance-Criteria Matrix (V127-AC-01 … V127-AC-24) — v6 (remediation-corrected)

generated_utc: 2026-07-16 (v6 corrected)
supersedes: v1 (which reported "23 PASS" — withdrawn per EVID-AUD audit)

**Four separate fields (do not conflate).** AC status ∈ {PASS, PARTIAL, FAIL, NOT VERIFIED, NOT APPLICABLE}.
Evidence trust ∈ {trusted, partially_trusted, untrusted, conflicting, not_evaluated}. Related finding status and
Independent-verification columns are carried where relevant. These are PROVISIONAL evidence-agent statuses; the
final readiness determination belongs to an independent reviewer. PASS is used only where directly reproducible
local evidence establishes the behavior **and** no OPEN finding undercuts it.

| AC | Expected | Evidence | AC status | Evidence trust | Limitation / follow-up |
|---|---|---|---|---|---|
| V127-AC-01 | Repo identity + remote + default branch established | 02 | PASS | trusted | — |
| V127-AC-02 | PR #313 merged; parents = base(e247ad08) then candidate(51ce5f28) | 03, github-metadata | PASS | trusted | — |
| V127-AC-03 | `origin/main` == 97efbb6b at capture, not advanced | 02/03 | PASS | trusted | origin/main has since advanced; the pinned base 97efbb6b remains in main history |
| V127-AC-04 | Exact release commit = 97efbb6b (has V127 + NF-F-001 auth) | 03, 05 | PASS | trusted | — |
| V127-AC-05 | Superseding review v1.2 authenticated by SHA-256 | 01, 04 | PASS | trusted | — |
| V127-AC-06 | Missing historical closure tarball handled | 04, Stage-R closure (archive 1c5d262e, recon PASS) | **PARTIAL** | partially_trusted | Rebuilt package is a **successor with new identity**; the original archive is unavailable, so any claim depending on the original stays **NOT VERIFIED** (operator ratification clause 5) |
| V127-AC-07 | Code schema head = V127; V124→V127 chain present + well-formed | 06 | PASS | trusted | — |
| V127-AC-08 | Candidate image built, immutable id + revision label + arch | 07 (id <candidate-index-digest>, amd64, rev 97efbb6b) | PASS | trusted | not pushed to a registry (no remote digest) — NF-IMG-001 (Medium, OPEN) |
| V127-AC-09 | Image contains current-main code (LATEST_SCHEMA_VERSION=127 + auth modules) | 07, 10 | PASS | trusted | — |
| V127-AC-10 | Deployed production image identity captured; anchored at a source commit | 08 | PASS | partially_trusted | deployed identity observed via read-only NAS probe (reconstructed receipt; see commands/) |
| V127-AC-11 | Live managed DB identity + schema established read-only | 09a/09b | PASS | partially_trusted | live identity via read-only NAS probe (reconstructed receipt) |
| V127-AC-12 | Live schema == V124 | 09b (schema_migrations MAX 124) | PASS | partially_trusted | consistent across multiple records; probe chain not independently reproducible |
| V127-AC-13 | Read-only inspection caused no live mutation (before/after invariance) | 09c, 10 | PASS | partially_trusted | before/after records show no detected difference; command chain partially trusted |
| V127-AC-14 | Migration runs inside a single atomic transaction | 06 (source), 15b (rollback proof) | PASS | trusted | source + local rollback evidence |
| V127-AC-15 | V124→V127 migration succeeds on a production-derived copy | 12, 14, 16 | **PARTIAL** | partially_trusted | **Migration-engine rehearsal = PASS** (shared `SQLiteMigrator.apply()`, EXPLICIT_DEVELOPMENT target). **Integrated MANAGED_PRODUCTION operator-route rehearsal = NOT VERIFIED** (exact-path binding cannot be reproduced off-production). See 11/12/15. |
| V127-AC-16 | Migration is idempotent (re-run is a no-op) | 14 (rerun→127 in 0.1s) | PASS | partially_trusted | local rehearsal (reconstructed receipt) |
| V127-AC-17 | Post-migration integrity: schema/ledger/columns/CHECK/indexes/FK/parity | 16 | PASS | partially_trusted | local rehearsal (reconstructed receipt) |
| V127-AC-18 | Interruption/failure rolls the WHOLE migration back atomically | 15b (NULL event_id → rolled back to V124) | PASS | partially_trusted | local rehearsal (reconstructed receipt) |
| V127-AC-19 | Backup created, nonempty, hashed; restore to a new path verified | 13 (backup <db-size> sha <snapshot-db-sha256>; restore→V124 ok) | PASS | partially_trusted | local rehearsal (reconstructed receipt) |
| V127-AC-20 | Production route requires a valid non-empty backup receipt | 13b | PASS | partially_trusted | local rehearsal (reconstructed receipt) (engine gating) |
| V127-AC-21 | Ordinary/unauthorized migration on the managed target is denied | 10, 15 | PASS | partially_trusted | live-denial observed via NAS probe (reconstructed receipt) + local suite (trusted) |
| V127-AC-22 | NF-ENV-001: opened-connection binds the live inode + classifies MANAGED_PRODUCTION; declared-path spoof defeated | 10 (Part A dev/ino bind; Part C canonical MANAGED_PRODUCTION + spoof→BLOCKED) | **PARTIAL** | partially_trusted | The single live canonical-path observation was **not** obtained: the live probe classified BLOCKED (short mount, host NAS deep-mount quirk); canonical MANAGED_PRODUCTION was proven **only locally**. Combining the two is inference, not one live observation. **NF-ENV-001 stays OPEN**; independent verification required. |
| V127-AC-23 | Recovery demonstrated (restore V124 backup to a new path) | 13, 15, 11 | PASS | partially_trusted | forward-recovery via V127 image documented, not run |
| V127-AC-24 | The authorized production migration + deployment has been performed | — | NOT APPLICABLE | not_evaluated | out of scope — evidence package only; NF-DEP-001 OPEN |

## Summary (v6 — no "23 PASS")
- **PARTIAL (3):** AC-06 (rebuilt successor, original unavailable), AC-15 (engine PASS / operator-route NOT
  VERIFIED), AC-22 (NF-ENV-001 OPEN — inferred, not a single live observation).
- **NOT APPLICABLE (1):** AC-24 (actual production deployment — out of scope).
- **PASS (20):** the remainder, of which **11 carry `partially_trusted` evidence** — AC-10/11/12/13/21 (read-only
  NAS probes, reconstructed receipts) and AC-16/17/18/19/20/23 (reconstructed material-rehearsal executions;
  behavior supported, execution provenance partial per CORR-AUD-002). AC-22 is also partially_trusted but is
  PARTIAL, not PASS. The remaining 9 PASS criteria (AC-01/02/03/04/05/07/09/14) are trusted (repo/git/source/hash,
  independently reproducible).
- No FAIL. Provisional; independent deployment-readiness review owns the GO/No-Go. No AC is marked VERIFIED FIXED
  by the evidence agent.
