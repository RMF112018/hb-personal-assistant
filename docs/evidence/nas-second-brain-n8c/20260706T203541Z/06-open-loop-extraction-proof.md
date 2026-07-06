# N8C-8 — open-loop extraction proof

## Path (deterministic, no LLM)
From pack `claim_candidate` items, by `claim_type`:
- `commitment` → `OpenLoopRecord(commitment)` (priority from confidence; `stale_after` from the claim);
- `task_candidate` → `OpenLoopRecord(task_candidate)` (`due_at` from claim `valid_until`);
- `risk` → `OpenLoopRecord(risk_followup)`;
- **question (conservative heuristic):** a `task_candidate`/`fact`/`unknown`/`assumption` claim whose
  text is clearly a question (`endswith("?")` / `Question:` prefix) → `OpenLoopRecord(question)` with
  `confidence ≤ QUESTION_CONFIDENCE_CAP (0.35)`, `priority="low"`, `review_state="needs_review"`.

From memory compilations (WEAK advisory, `compilation_derived`, `needs_review`):
- `risks_json` entries → `risk_followup`; `open_questions_json` entries → `question`
  (`confidence ≤ 0.35`).

## Proof (`test_decision_memory_extractor.py`, smoke run)
- One seeded pack produced open-loop types `{commitment, task_candidate, risk_followup, question}`
  (`test_commitment_task_risk_question_become_open_loops`) — 6 open loops total: commitment(1) +
  task_candidate(1) + risk_followup from claim(1) + question from claim "Should context packs persist?"(1)
  + risk_followup from compilation(1) + question from compilation "who owns closeout?"(1).
- Questions are conservative — `confidence ≤ 0.35` + `needs_review` (`test_question_is_conservative`).
- **N8C-8 never executes an open loop.** No email/calendar/task/reminder/notification path exists — the
  extractor only identifies, stores, lists, and labels (see `10-no-action-no-writeback-proof.md`).
- Open loops default `status=candidate`; explicit `mark_open_loop_stale` / `mark_open_loop_stale_if_
  needed` are the only lifecycle transitions (no open/close/reopen workflow).
