# Reference — Repo Truth Baseline from Prior Audit

The prior audit established the following baseline facts for this package. The local agent must re-verify before implementing.

## Verified from live GitHub during planning

- PR #13 merged Phase 10 full-candidate implementation into `main`.
- PR #12 merged V45 email follow-up raw enrichment into `main`.
- PR #11 merged daily-brief intelligence remediation into `main`.
- PR #10 merged Procore endpoint contracts and persistence into `main`.
- PR #9 merged Procore live refresh degradation fixes into `main`.
- Schema head was V45 after V45 email follow-up enrichment.
- Phase 10 full-candidate implementation added read-model/report surfaces without migration.
- Known unresolved repo gap: daily-brief intelligence adapter and existing synthesis path remained separate; convergence was explicitly identified as natural follow-up.
- Known V45 limitation: production-copy evidence had no naturally occurring email-source-linked accepted follow-up candidates; raw enrichment readiness/eligibility must make this condition explicit and actionable.

## Must re-verify locally

Run the exact commands in Prompt 00. Local working tree state is authoritative.
