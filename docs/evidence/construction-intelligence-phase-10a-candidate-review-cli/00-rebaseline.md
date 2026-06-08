# Phase 10A Candidate Review CLI — Prompt 00 Repo-Truth Rebaseline

**Date:** 2026-06-08
**Scope:** Fresh local repo-truth audit before any edits for the Phase 10A candidate review CLI.
**Verdict:** Repo truth does **not** materially differ from the implementation package. Proceed to subsequent prompts. One latent compatibility defect documented below for the implementation phase to address (audit-event dead write).

---

## 1. Local state at audit time

```
$ git rev-parse HEAD
2a045d2f4544a8542f95ed1d9ed57d7722023f6f

$ git status --short
 M docs/evidence/construction-intelligence-phase-08b-automation-hardening/phase-08b-final-no-writeback-proof.md
?? docs/planning/HB_Construction_Intelligence_Phase_10A_Candidate_Review_CLI_Implementation_Package/
```

- HEAD `2a045d2f` = "Phase 10A: move batch command to second-brain extract-packets (drop phase-10)".
- Dirty state is pre-existing and unrelated: a modified phase-08b evidence file (not touched by this work) plus the untracked 10A planning package. No source/test files are dirty.

## 2. Schema head

```
$ python -c "from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION; print(LATEST_SCHEMA_VERSION)"
LATEST_SCHEMA_VERSION= 42
```

- **Confirmed `V42`**, matching the package's "current audited schema head: `V42`" assertion.
- The optional Phase 10A migration would land as **`V43`** (additive only — never rewrite existing tables, per repo migration policy).

## 3. Batch command path

- Confirmed: the batch extraction command is `hb-assistant second-brain extract-packets` (`@app.command("extract-packets")`, `src/hb_assistant/cli/second_brain.py:7840`; `command` string `"second-brain extract-packets"` at `:7901` and `batch_extraction.py:278`). Matches the package's observed path.
- Prompt 00 does **not** authorize new extraction runs; review must operate only on already-persisted candidate rows.

## 4. Persisted candidate model (V41 tables, present at V42)

Migrator (`src/hb_assistant/store/migrator.py:5450+`) defines the action-intelligence tables:

| Table | Key columns relevant to review |
|---|---|
| `task_candidates` | `candidate_id` PK, `stable_key` UNIQUE, `title_redacted`, `project_key`, `assignee_class`, `due_at_utc`, `urgency`, `waiting_state`, `safety_category`, `confidence`, `recommended_next_action`, **`review_status` (DEFAULT 'pending')**, `created_utc`, `updated_utc` |
| `commitment_candidates` | `candidate_id` PK, `stable_key` UNIQUE, `title_redacted`, `commitment_actor_class`, `promised_at_utc`, `due_at_utc`, `urgency`, `waiting_state`, `safety_category`, `confidence`, `recommended_next_action`, **`review_status` (DEFAULT 'pending')**, `created_utc`, `updated_utc` |
| `candidate_source_refs` | `source_ref_id` PK, `candidate_type`, `candidate_id`, `source_family`, `source_ref_hash`, `source_table`, `source_primary_key_hash`, `evidence_redacted` (bounded excerpt), `confidence` |
| `candidate_review_events` | `review_event_id` PK, `candidate_type`, `candidate_id`, **`action`**, **`prior_status`**, **`new_status`**, **`user_note_redacted`**, `created_utc` |

Indexes already exist for review filtering: `ix_task_candidates_review_status`, `ix_commitment_candidates_review_status` (`migrator.py:5694-5695`).

All five tables carry the `_P10_GUARDS` CHECK guard block (no raw-body/token/url columns), consistent with the no-raw invariant.

## 5. Existing review surfaces (what already exists vs. what 10A must add)

### 5a. `second-brain review` group already exists — but for Phase 09 burden marts, not candidate triage
`src/hb_assistant/cli/second_brain.py:105` registers `review_app` (name `review`) with commands: **`policy-status`, `burden`, `queue`, `clusters`** (review-burden / advisory-promotion marts, read-only). The target 10A verbs in the README — `summary`, `list`, `show`, `accept`, `ignore`, `reject`, `snooze`, `edit`, `export` — **do not collide** with any of these existing four. 10A can add the candidate-triage verbs to this same `review_app` group cleanly.

> Note: a second, unrelated `review_app` (name `review`) also exists in `cli/construction.py:160` (`construction-agent review evaluate|list`). Different CLI group; not in scope.

### 5b. Candidate triage today lives under `second-brain phase-10`
`phase_10_app` (name `phase-10`, registered `second_brain.py:131`) already provides the functional core the 10A package wants to re-expose as first-class `review` verbs:

- `phase-10 list-candidates` (`:8058`) — list task/commitment candidates.
- `phase-10 candidate-source` (`:8166`) — inspect candidate + its `candidate_source_refs`; can resolve full raw content for sanctioned review-detail use.
- `phase-10 review-candidate` (`:8266`) — apply a review decision; **dry-run default**, `--emit` to persist; mirrors the memory-review pattern (advisory only, no auto-promote to `accepted_*`).

### 5c. Store helpers (additive, already present)
`src/hb_assistant/construction/store/repositories.py`:
- `list_task_candidates(...)` / `list_commitment_candidates(...)` (`:8507` / `:8559`) — support `project_key`, `review_status`, `limit` filters.
- `list_candidate_source_refs(candidate_id=...)`.
- `set_candidate_review_status(candidate_type, candidate_id, review_status)` (`:8660`) — UPDATE `review_status` + `updated_utc`; returns rowcount>0.
- `insert_candidate_review_event(...)` (`:8680`) — best-effort audit insert (see defect below).

## 6. Material finding — `candidate_review_events` audit write is currently dead (latent defect)

`insert_candidate_review_event` (`repositories.py:8696`) inserts into columns:

```
(event_id, candidate_type, candidate_id, decision, reason_redacted, reviewer_ref, created_utc)
```

but the V41 `candidate_review_events` schema (`migrator.py:5509`) defines:

```
(review_event_id, candidate_type, candidate_id, action, prior_status, new_status, user_note_redacted, created_utc)
```

Mismatches: `event_id`≠`review_event_id`, `decision`≠`action`, `reason_redacted`≠`user_note_redacted`, `reviewer_ref` has **no** column, and `prior_status`/`new_status` are never written. Because the method wraps the INSERT in a bare `except: return None`, **every audit-event write silently fails** — the `candidate_review_events` table is effectively never populated by the current `phase-10 review-candidate --emit` path. `review_status` itself is still updated correctly (separate method); only the audit trail is lost.

**Implication for Phase 10A:** the new `review accept/ignore/reject/snooze` verbs are expected to record an audit trail. The implementation phase should reconcile `insert_candidate_review_event` with the actual schema (map `action`/`prior_status`/`new_status`/`user_note_redacted`) so audit rows persist. This is a direct compatibility issue and is in-scope for the review CLI work. **Not fixed in Prompt 00** (audit-only).

## 7. Lifecycle-status contract awareness

`src/hb_assistant/resources/json/table_lifecycle_status_contract.json` already enumerates `task_candidates` (:1814), `commitment_candidates` (:1823), and `candidate_review_events` (:1841). Any V43 column additions for the optional `snooze`/`edit` verbs must keep this contract in sync.

## 8. Test baseline (clean main, pre-edit)

```
$ pytest tests/test_phase_10a_raw_content_review.py \
         tests/test_phase_10a_batch_extraction.py \
         tests/test_phase_10_schema.py -q
29 passed
```

Existing candidate-review safety tests (`test_phase_10a_packet_extraction_safety.py`, `test_phase_10a_raw_extraction_hardening.py`, `test_phase_10a_raw_action_intelligence.py`, `test_phase_10a_raw_content_review.py`) assert zero-write dry-run posture and `review_status` transitions — these are the invariants the new `review` verbs must continue to honor.

Full grep capture: `/tmp/phase10a-review-rebaseline-grep.txt` (129 matches).

## 9. Guardrail confirmation (unchanged, must hold for 10A review CLI)

- No email send / calendar mutation / Graph writeback / Procore writeback / external writeback.
- No raw body, raw doc text, raw calendar/Procore payload, raw prompt/response, signed/download URL, token, or secret persisted or output. (`_P10_GUARDS` CHECKs + redaction enforce this.)
- Review actions = **local DB updates only** (`review_status` + audit event). "Accepted" = operator-approved record, **not** authorization for external work; no auto-promotion to `accepted_*`.
- Source refs immutable; packet extraction scope unchanged; extraction prompt/model/stable-key behavior unchanged.
- No external/cloud LLM dependency.

## 10. Decision

**No material divergence.** Schema head, batch command path, candidate tables, review_status model, and existing review/phase-10 surfaces all match the package's stated baseline. Proceed to the next numbered prompt. Carry forward §6 (audit-event dead write) as a known defect for the implementation phase to reconcile, and §5a (add 10A verbs to the existing `review_app` without colliding with the Phase 09 burden verbs).
