---
title: "Proportional Test Selection and No-Known-Failure Integration"
artifact_id: "DECISION-PROPORTIONAL-TEST-SELECTION-001"
classification: "Decisions"
artifact_type: "Operator Decision Candidate"
version: "1.2"
status: "Review Pending — Corrective Revision"
date_created: "2026-07-21"
date_updated: "2026-07-21"
decision_owner: "Bobby Fetting"
author: "OpenAI ChatGPT, operator-directed"
repository: "RMF112018/hb-personal-assistant"
branch_pr_commit: "chore/proportional-test-selection-policy-v2 / PR #319 / corrective head resolved externally"
decision_scope: "Repository-wide test selection, failure disposition, parallel corrective work, and permanent-identity goal test requirements"
prior_review:
  reviewed_head_sha: "3f008f4ba7e64a0036ecee913a9eaab24cfa1e75"
  disposition: "REVISE"
  findings:
    - PR319-GOV-F-001
    - PR319-GOV-F-002
    - PR319-GOV-F-003
    - PR319-GOV-F-004
    - PR319-GOV-F-005
    - PR319-GOV-F-006
    - PR319-GOV-F-007
    - PR319-GOV-F-008
acceptance_state: "NOT ACCEPTED — exact-head re-review and separate operator acceptance required"
supersedes:
  - title: "PI-WI-03-ARC-PLAN.md"
    revision: 4
    drive_id: "1iPaw4yjgdXP_VvXb7XwNKn8gIiPyMWk_"
    sha256: "419ef24a3139214b761ab682190adb23ce1147ae3ec6dbe344a2eda45a648a64"
    scope: "Test-selection-only override of blanket schedule-canary language in the PI-WI-03 arc plan"
    affected_clauses:
      - section: "Governance (AEOS) — role-separated, applies to EACH unit"
        item: 3
        anchor: "focused tests + ruff + mypy + scripts/test-schedule.sh"
      - section: "Verification (each unit)"
        anchor: "scripts/test-schedule.sh + the dropped 2/9 failures re-confirmed pre-existing"
superseded_by: []
related_artifacts:
  - ".ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md"
  - ".ai/project-sources/07_AEOS_LOCAL_AGENT_OPERATING_CONTRACT.md"
  - "scripts/test-safe.sh"
  - "docs/governance/test-failure-triage.md"
  - "docs/testing/forecasting-and-schedule-test-bundles.md"
  - "GOAL-SOURCE-INDEX-PERMANENT-IDENTITY-CORRECTIVE-001"
tags: [testing, evidence, aeos, source-index, corrective-work, governance]
---

# Proportional Test Selection and No-Known-Failure Integration

**Classification:** Decisions  
**Artifact Type:** Operator Decision Candidate  
**Version:** 1.2  
**Status:** Review Pending — Corrective Revision

## Lifecycle and authority

This document is a corrective decision candidate. The prior exact-head review of
`3f008f4ba7e64a0036ecee913a9eaab24cfa1e75` returned `REVISE`. This revision is
not accepted or effective merely because it is committed, mergeable, or
operator-directed.

It becomes accepted only when:

1. a fresh independent review approves the exact corrective head;
2. the operator separately accepts that exact reviewed head through a durable
   GitHub record; and
3. any merge is separately authorized.

The exact review and acceptance identities are external GitHub records so they
can bind the commit without creating a self-referential metadata change.

## Decision candidate

The repository shall use proportional test selection and failure disposition
governed by `.ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md` after
this candidate is accepted.

Expensive suites and cross-domain canaries are required only when mapped to an
acceptance criterion, changed dependency, shared infrastructure, named risk, or
exact gate. They are not required after every edit or agent turn.

The canonical merge-safe repository gate is:

```bash
bash scripts/test-safe.sh
```

No integrated candidate may be declared merge-ready while an applicable
required safe test is known to fail. A proven pre-existing failure outside the
active work item receives durable triage identity and separate corrective
ownership; it is not ignored or silently absorbed into the primary scope.

## Handoff and standard precedence

Standard 07 and Standard 11 apply jointly. A mapped test in an approved handoff
remains binding. An unmapped or conflicting broad-suite mandate triggers a stop
and deviation report; the agent may not silently omit it or execute it as a
ritual baseline. Only an exact later operator decision or higher-authority
repository source resolves the conflict.

## Durable failure ownership

Every observed failure receives a stable GitHub issue or equivalent governed
finding-ledger identity, triage owner, classification state, base/candidate
evidence, affected gate, disposition, authorization state, corrective identity,
review result, integrated-candidate result, and closure evidence. The preferred
procedure and issue form are:

```text
docs/governance/test-failure-triage.md
.github/ISSUE_TEMPLATE/test-failure.yml
```

Creating the triage record is not corrective authority. The primary agent may
request or create the record but may not authorize or activate a corrective
agent.

## Active permanent-identity goal

This candidate applies to:

```text
Goal: GOAL-SOURCE-INDEX-PERMANENT-IDENTITY-CORRECTIVE-001
Historical plan title: PI-WI-03-ARC-PLAN.md
Revision: 4
Drive ID: 1iPaw4yjgdXP_VvXb7XwNKn8gIiPyMWk_
SHA-256: 419ef24a3139214b761ab682190adb23ce1147ae3ec6dbe344a2eda45a648a64
```

It supersedes only these rev-4 clauses:

- `Governance (AEOS) — role-separated, applies to EACH unit`, item 3, the
  committed-SHA evidence sequence containing `focused tests + ruff + mypy +
  scripts/test-schedule.sh`; and
- `Verification (each unit)`, the bullet beginning `scripts/test-schedule.sh +
  the dropped 2/9 failures re-confirmed pre-existing`.

The original plan remains unchanged and preserved. Future plan revisions and
work-item authorizations must consume this decision explicitly once accepted.

1. **PI-WI-02B schema/migrator work:** retain the schedule bundle because shared
   migrator/schema behavior is changed.
2. **PI-WI-03a runtime re-key:** the schedule bundle is not required while the
   diff remains within source-index repository, connector model/service, and
   direct tests. It becomes required when shared migrator/schema/bootstrap,
   schedule code, or demonstrated schedule dependencies are affected.
3. **PI-WI-03b move continuity:** apply the same conditional rule. Direct
   source-index acceptance, move/drain tests, static guards, and integration seams
   remain mandatory.
4. **Merge/release:** the canonical safe suite and every applicable gate must
   finish with zero unresolved failures.

This override changes test selection only. It does not alter architecture,
feature scope, acceptance criteria, authorization boundaries, review
requirements, prior evidence, implementation authority, deployment authority,
or production authority.

## Failure classification

A failing test is classified as candidate regression, reproducible pre-existing
product defect, invalid/stale test, flaky/nondeterministic test,
environment/configuration failure, or relationship unknown.

Pre-existing status requires materially equivalent base-SHA reproduction or
equivalent direct causal evidence. Filename and domain labels are insufficient.
Candidate regressions remain in the active work item. Unknown relationships
block the affected checkpoint.

## Parallel corrective work

Parallel correction requires proven base reproduction, separate explicit
authorization, separate branch/worktree registration, non-overlapping edit and
evidence ownership, no shared schema/migrator/bootstrap/global fixture/test
discovery/dependency/security/common surface, independent evidence and review,
separate integration authority, and combined-candidate reruns through all
applicable gates.

The primary agent may continue only when those conditions are satisfied and may
not self-authorize the corrective stream.

## Execution frequency and evidence reuse

- Inner-loop validation uses the smallest relevant tests.
- Candidate validation uses the complete bounded acceptance suite.
- Triggered expensive canaries normally run once per materially different
  committed candidate SHA.
- Bookkeeping-only turns do not rerun evidence when SHA, command, dependencies,
  environment, inputs, and purpose are unchanged.
- Parent-baseline evidence may be reused only when immutable identity and
  material environment remain unchanged and reuse is declared.

## Non-effects

This candidate does not waive failures, authorize blanket unrelated correction,
weaken safeguards, approve implementation, authorize merge, activate Phase B,
authorize cleanup, deployment, migration, production activation, or accept risk.

## Required next gate

Fresh independent governance re-review of the exact corrective PR #319 head,
followed—only if approved—by a separate operator acceptance decision.
