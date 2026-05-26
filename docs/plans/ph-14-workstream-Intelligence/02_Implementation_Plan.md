# 02 — Implementation Plan

## Objective

Provide a sequenced implementation plan for Phase 14 that can be executed safely by a local code agent in `RMF112018/hb-personal-assistant`.

## Phase 14 Name

**Local Runtime Orchestration & Source-Linked Workstream Intelligence**

## Implementation Sequence

### Step 0 — Repo-Truth Revalidation

- Confirm branch, HEAD, status, remotes, and latest commits.
- Inspect current CLI, auth, graph, store, classification, files, retrieval, Obsidian, automation, docs, and evidence.
- Produce a short repo-truth scope lock before patching.

### Step 1 — Correct Blocker Taxonomy and Evidence

- Update stale DNS/no-token references where they conflict with current admin-consent context.
- Add a formal blocker taxonomy document.
- Add a current evidence note that says delegated proof is deferred pending admin consent.

### Step 2 — Add Action Module and CLI

- Add `src/hb_assistant/actions/`.
- Add a real `hb-assistant actions` Typer group.
- Implement `extract`, `list`, and `reconcile` commands if repo truth supports them.
- Keep all outputs redacted and source-linked.

### Step 3 — Add Idempotent Action Persistence

- Add or update repository helpers for action upsert by stable key.
- Create source links for every action.
- Add duplicate-prevention tests.

### Step 4 — Integrate Signals into Action Extraction

Use existing bounded sources:

- body mention flags;
- redacted bounded body excerpts;
- parser excerpts;
- calendar rows;
- file review queue;
- retrieval hits.

### Step 5 — Upgrade Workstream Context

- Ensure context builder includes actions, waiting-on items, file review items, meeting prep, body mentions, and retrieval signals.
- Every context item should reference source IDs.

### Step 6 — Upgrade Obsidian Output Provenance

- Implement `written_to_note` links.
- Include source map in the generated brief.
- Preserve user-edited content outside markers.

### Step 7 — Upgrade Morning Orchestration

- Run local-only stages even when Graph is consent-blocked.
- Emit structured JSON stage statuses.
- Record ledger status accurately.
- Write sanitized evidence.

### Step 8 — Add Deterministic Evidence Harness and CI

- Add fixtures that simulate local source records.
- Add CI workflow that runs safe local-only checks.
- Document expected command outputs.

### Step 9 — Post-Consent Delegated Proof Closeout

- Do not run until admin consent lands.
- Execute auth/proof/scan commands.
- Update acceptance classification based on evidence.

## Suggested Commit Sequence

1. `docs(evidence): correct delegated proof blocker taxonomy`
2. `feat(actions): add source-linked action extraction`
3. `feat(store): add idempotent action persistence`
4. `feat(actions): derive work items from bounded source signals`
5. `feat(context): build source-linked workstream context`
6. `feat(obsidian): record source links for generated notes`
7. `feat(run): orchestrate full local morning workflow`
8. `ci: add local assistant validation workflow`
9. `chore(evidence): close phase 14 local runtime acceptance`
10. `chore(evidence): close delegated graph proof after admin consent`

## Implementation Guardrails

- Prefer additive changes.
- Do not rewrite already-working auth/Graph/token-cache code unless prompt-specific repo truth proves a defect.
- Preserve backward-compatible command grammar.
- Keep CLI JSON stable and machine-readable.
- Do not introduce new mandatory heavyweight dependencies.
- Keep tests deterministic.

## Baseline Validation Commands

Run the relevant subset for the prompt, and run the full baseline before final closeout:

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check .
mypy src

.venv/bin/hb-assistant --version
.venv/bin/hb-assistant diagnostics paths --json
.venv/bin/hb-assistant diagnostics env --json
.venv/bin/hb-assistant diagnostics scan-sensitive --repo . --json
.venv/bin/hb-assistant actions extract --dry-run --json
.venv/bin/hb-assistant search "waiting on" --json
.venv/bin/hb-assistant files sample --json
.venv/bin/hb-assistant files ingest --dry-run --json
.venv/bin/hb-assistant run morning --dry-run --json
```

If `python` is unavailable in the shell, use `.venv/bin/python`. Do not treat that as a project failure when `.venv/bin/python` works.
