# Phase 10 — Ollama-Assisted Feedback-Calibrated Candidate Ranking and Daily Brief Assembly

## Objective

Implement the next Phase 10 slice as an additive, deterministic-first, raw-safe, source-linked, local-only intelligence layer:

**Phase 10 — Ollama-Assisted Feedback-Calibrated Candidate Ranking and Daily Brief Assembly**

The implementation must improve:

- candidate ranking
- daily-brief grouping
- duplicate / semantic similarity detection
- “why this matters” explanations
- feedback calibration
- operator-usefulness scoring
- narrative brief assembly
- local-model fallback / degradation reporting

The model is **advisory and bounded**. Deterministic rules, source refs, lifecycle state, raw-safety gates, and human review state remain authoritative.

## Non-Negotiable Constraints

Do not:

- mutate production DB during development or validation
- run live Graph, Procore, email, calendar, SharePoint, OneDrive, Obsidian, or external writeback paths
- send emails, create drafts, or create calendar events
- expose raw private content in CLI, artifacts, tests, receipts, prompts, logs, status files, or rendered briefs
- use cloud LLMs or non-local model endpoints
- let model output create, accept, reject, suppress, merge, close, reopen, or snooze candidates
- let model output override deterministic lifecycle filtering or source-ref requirements
- persist raw model prompts, raw model responses, email bodies, full URLs, tokens, local paths, database files, or secrets

Work only on a feature branch. Do not touch `main` except by a future PR.

## Assumed Prior State

This package assumes the following slices have already landed and been validated:

1. Daily-brief candidate projection is active, source-linked, and guarded.
2. Email follow-up / task / commitment projections are active and source-linked.
3. Candidate lifecycle / review queue / feedback read model exists and is authoritative.

If any of those assumptions fail in repo truth, stop and update this package before implementation.

## Repo-Truth Findings to Preserve

The repo already has substantial local-model substrate. Do not duplicate it.

Known existing surfaces to audit and reuse before writing code:

- `hb-assistant second-brain local-model status`
- `hb-assistant second-brain ai-jobs ...`
- `hb-assistant second-brain action-intel ...`
- `hb-assistant second-brain daily-brief ...`
- `hb-assistant second-brain candidates ...`
- `src/hb_assistant/construction/classification/client.py`
- `src/hb_assistant/construction/second_brain/local_ai/provider.py`
- `src/hb_assistant/construction/second_brain/local_ai/structured_output.py`
- `src/hb_assistant/construction/second_brain/local_ai/daily_brief_intelligence.py`
- `src/hb_assistant/construction/second_brain/local_ai/model_enriched_intelligence.py`
- `src/hb_assistant/construction/second_brain/local_ai/daily_brief_synthesis.py`
- `src/hb_assistant/retrieval/embedder.py`
- V49/V50 migration and lifecycle/read-model code
- existing raw/no-leak scanner utilities
- existing usefulness gate and daily-run status surfaces

Run, at minimum:

```bash
cd /Users/bobbyfetting/hb-personal-assistant

rg -n "ollama|Ollama|local model|local_model|model|model_name|model_config|readiness|daemon|localhost:11434|generate|chat|json_schema|schema|timeout|fallback|degraded|withheld|prompt|response|receipt" src tests docs

rg -n "daily_brief_action_candidates|candidate_source_refs|candidate_lifecycle|candidate_feedback|review_queue|accepted|rejected|snooze|suppression|merged|source_ref|source refs|usefulness_gate|Model Enriched Intelligence|daily_brief_intelligence|brief_synthesis|local_model_run_receipts" src tests docs

rg -n "guard columns|zero guard|no-raw|raw leak|leak|token|signed URL|email body|full body|prompt_hash|output_hash|receipt" src tests docs
```

Document repo-truth findings in `docs/evidence/phase-10-ollama-assisted-candidate-ranking-brief-assembly/00-repo-truth-audit.md`.

## Implementation Strategy

Add a **ranking / assembly overlay**, not a new extraction engine.

The existing system already discovers and persists candidates. This slice should consume existing structured/redacted candidate rows, lifecycle feedback, and source-ref metadata to produce an advisory ranking and assembly view.

### Target Architecture

```
daily_brief_action_candidates
        + candidate_source_refs
        + lifecycle/read-model/feedback
        + deterministic project/date/urgency signals
        + optional local Ollama ranking advice
        + optional redacted-title semantic similarity
        ↓
candidate packet builder
        ↓
deterministic ranking engine
        ↓
feedback calibration layer
        ↓
bounded Ollama advisory layer
        ↓
duplicate/similarity advisory layer
        ↓
final ranked daily-brief assembly
        ↓
renderer/status/usefulness gate
```

Model output must be post-validated, source-linked, and bounded. If the model is unavailable, invalid, unsafe, unsourced, or remote, preserve the deterministic ranked brief and mark the model layer degraded/withheld.

## Required Deliverables

Create or update the following, adjusted to repo truth.

### 1. Additive schema migration

Use the next schema version after repo head. If V50 is current, create V51. If repo moved, use `LATEST_SCHEMA_VERSION + 1`.

Additive tables only. Do not alter or drop prior tables except by additive indexes/columns that are safe and required.

Suggested tables:

#### `daily_brief_ranking_runs`

Purpose: one raw-free metadata row per ranking attempt.

Minimum columns:

- `ranking_run_id TEXT PRIMARY KEY`
- `brief_date TEXT NOT NULL`
- `policy_version TEXT NOT NULL`
- `algorithm_version TEXT NOT NULL`
- `candidate_set_hash TEXT NOT NULL`
- `feedback_digest_hash TEXT NOT NULL`
- `model_profile_id TEXT`
- `model_name TEXT`
- `model_status TEXT NOT NULL`
- `model_receipt_id TEXT`
- `deterministic_fallback_used INTEGER NOT NULL DEFAULT 0`
- `degraded_reason TEXT`
- `candidate_count INTEGER NOT NULL DEFAULT 0`
- `ranked_count INTEGER NOT NULL DEFAULT 0`
- `source_ref_coverage REAL NOT NULL DEFAULT 0`
- `usefulness_score REAL NOT NULL DEFAULT 0`
- `created_utc TEXT NOT NULL`
- the same Phase 10 guard columns used in existing candidate/lifecycle tables, with `CHECK(... = 0)`

#### `daily_brief_ranked_candidates`

Purpose: per-candidate raw-free ranking overlay for a run.

Minimum columns:

- `ranking_run_id TEXT NOT NULL`
- `daily_brief_action_candidate_id TEXT NOT NULL`
- `rank_position INTEGER NOT NULL`
- `section_key TEXT NOT NULL`
- `group_key TEXT`
- `duplicate_cluster_id TEXT`
- `deterministic_score REAL NOT NULL`
- `feedback_score REAL NOT NULL`
- `model_advisory_score REAL`
- `final_score REAL NOT NULL`
- `why_this_matters_redacted TEXT`
- `model_reason_codes_json TEXT`
- `source_ref_count INTEGER NOT NULL DEFAULT 0`
- `lifecycle_state_snapshot TEXT`
- `created_utc TEXT NOT NULL`
- `PRIMARY KEY (ranking_run_id, daily_brief_action_candidate_id)`
- guard columns with zero checks

#### `candidate_similarity_edges`

Purpose: raw-free advisory semantic/duplicate edges. This must never auto-merge or auto-suppress.

Minimum columns:

- `similarity_edge_id TEXT PRIMARY KEY`
- `brief_date TEXT NOT NULL`
- `candidate_a_id TEXT NOT NULL`
- `candidate_b_id TEXT NOT NULL`
- `similarity_score REAL NOT NULL`
- `similarity_method TEXT NOT NULL`
- `cluster_id TEXT`
- `deterministic_features_json TEXT`
- `model_label TEXT`
- `review_recommendation TEXT NOT NULL DEFAULT 'review_duplicate_candidate'`
- `created_utc TEXT NOT NULL`
- guard columns with zero checks

#### `daily_brief_assembly_runs`

Purpose: one metadata row for assembled daily brief.

Minimum columns:

- `assembly_run_id TEXT PRIMARY KEY`
- `brief_date TEXT NOT NULL`
- `ranking_run_id TEXT`
- `assembly_policy_version TEXT NOT NULL`
- `model_layer_status TEXT NOT NULL`
- `deterministic_fallback_used INTEGER NOT NULL DEFAULT 0`
- `section_count INTEGER NOT NULL DEFAULT 0`
- `candidate_count INTEGER NOT NULL DEFAULT 0`
- `withheld_reason TEXT`
- `created_utc TEXT NOT NULL`
- guard columns with zero checks

#### `daily_brief_assembly_sections`

Purpose: section-level raw-free candidate ordering.

Minimum columns:

- `assembly_run_id TEXT NOT NULL`
- `section_key TEXT NOT NULL`
- `display_order INTEGER NOT NULL`
- `title_redacted TEXT NOT NULL`
- `candidate_ids_json TEXT NOT NULL`
- `section_score REAL NOT NULL DEFAULT 0`
- `degraded_reason TEXT`
- `created_utc TEXT NOT NULL`
- `PRIMARY KEY (assembly_run_id, section_key)`
- guard columns with zero checks

Add indexes for brief date, candidate id, run id, cluster id, and model status.

All new persistence must be idempotent on stable keys. Re-running against the same candidate set, feedback digest, policy version, and model receipt/hash should not duplicate rows.

### 2. Pydantic contracts

Add new strict schemas in the existing local-ai model area, either in `models.py` or a new module if repo style prefers:

- `CandidateRankingPacket`
- `CandidateRankingPacketItem`
- `CandidateRankingAdvice`
- `CandidateRankingAdviceItem`
- `CandidateBriefGroupAdvice`
- `CandidateSimilarityAdvice`
- `CandidateRankingResult`
- `DailyBriefAssemblyResult`

Rules:

- `extra = "forbid"` for model-facing schemas unless existing repo pattern requires carefully bounded `ignore`.
- Clamp all model strings.
- Reject or drop any item citing unknown candidate aliases.
- Reject or drop any `why_this_matters` text that trips raw/no-leak scanners.
- `source_refs` are never invented by the model; the model can cite only candidate aliases supplied in the packet.
- Candidate aliases (`c1`, `c2`, …) must map back to canonical `daily_brief_action_candidate_id`.

### 3. Candidate packet builder

Create:

`src/hb_assistant/construction/second_brain/local_ai/candidate_ranking_packets.py`

Responsibilities:

- Load eligible `daily_brief_action_candidates` for `brief_date`.
- Join candidate source-ref counts from `candidate_source_refs`.
- Join lifecycle/read-model state from the V50 lifecycle/review/feedback read model.
- Exclude rejected, suppressed, merged-away, closed, and snoozed-until-future candidates.
- Keep accepted/stale/review-required items visible and labeled honestly.
- Include only raw-free fields:
  - candidate alias
  - canonical candidate id
  - family/source type
  - section
  - title_redacted
  - reason_redacted
  - project_key
  - due bucket / age bucket / urgency / waiting_state if present
  - confidence
  - lifecycle state
  - source-ref count
  - feedback signals / calibration bucket summaries
- Never include raw excerpt, email body, calendar body, full URL, token, secret, raw Procore payload, external id, or local path.
- Compute:
  - `candidate_set_hash`
  - `feedback_digest_hash`
  - `packet_char_count`
  - `source_ref_coverage`
  - `packet_guard_clean`

Fail closed if:

- any surfaced actionable candidate lacks source refs
- lifecycle contradictions are detected
- raw/leak scanner flags any packet field
- no eligible candidates exist: return honest `no_eligible_candidates` result, not success theater

### 4. Deterministic ranking engine

Create:

`src/hb_assistant/construction/second_brain/local_ai/candidate_ranking.py`

Required deterministic base score components:

- lifecycle state
  - accepted and stale accepted items receive a boost
  - review-required remains visible but not blindly elevated
  - pending remains lower unless urgency/source/project signals justify it
  - rejected/suppressed/merged/closed/future-snoozed are excluded before scoring
- urgency / due proximity
- waiting state
  - `waiting_on_me` boost
  - stale `waiting_on_others` / follow-up boost when a response is needed
- candidate family / safety category
  - schedule, safety, financial, payment, claim/entitlement, contract risk receive bounded boosts
- meeting prep timing
  - today/tomorrow meetings are prioritized
- project identity
  - project-linked beats unlinked when otherwise tied
- source-ref strength
  - source-linked required; more independent refs may add a small bounded boost
- confidence
- duplicate penalty
  - exact deterministic duplicates are clustered; do not rank each copy as separate top priority

Recommended scoring:

```text
deterministic_score = clamp(0..100)
feedback_score = clamp(0..100)
model_advisory_score = clamp(0..100) or null

final_score =
  0.75 * deterministic_score
+ 0.20 * feedback_score
+ 0.05 * model_advisory_score

If model unavailable/invalid/withheld:
  final_score = 0.80 * deterministic_score + 0.20 * feedback_score
```

The model must not be able to move an item more than a bounded number of rank positions unless deterministic scores are already close. Use stable tie-breakers:

1. final_score desc
2. deterministic_score desc
3. lifecycle priority
4. due bucket
5. project_key
6. candidate id

### 5. Feedback calibration

Create:

`src/hb_assistant/construction/second_brain/local_ai/feedback_calibration.py`

Responsibilities:

- Build a compact feedback digest from the lifecycle feedback read model:
  - accepted/rejected/snoozed/merged/suppressed counts
  - by family
  - by section
  - by project_key
  - by reason_code / recommended_next_action where available
  - stale accepted items
- Apply calibration only when sample size is sufficient.
- Clamp calibration effect.
- Never personalize with private/raw content; use only structured outcome categories.
- Never punish a candidate solely because a different project/family had rejections.
- Store or surface only aggregate, raw-free calibration metadata.

### 6. Ollama advisory ranking layer

Create:

`src/hb_assistant/construction/second_brain/local_ai/ollama_candidate_ranking.py`

Use existing:

- local model profiles
- model router if appropriate
- `StructuredOutputClient`
- hash-only receipt pattern
- local-model readiness/status code
- `StaticOutputClient` for tests

Task type: `candidate_ranking_brief_assembly`

Prompt requirements:

- The model receives only the redacted structured packet.
- The prompt says the deterministic score/lifecycle/source-ref gates are authoritative.
- The model returns JSON only.
- The model may:
  - suggest relative priority within bounded range
  - assign grouping labels
  - identify possible semantic duplicates
  - produce short `why_this_matters_redacted`
  - suggest narrative section phrasing
- The model may not:
  - invent source refs
  - invent names, dates, amounts, URLs, emails, claims, commitments, or project facts
  - change lifecycle state
  - create new candidates
  - suppress/merge/close/reopen/snooze/accept/reject
  - recommend external writeback
  - include raw content

Use `format` JSON or JSON schema if the existing client is extended. If extending the client, keep compatibility with current callers.

Fail closed to deterministic ranking if:

- Ollama daemon unavailable
- required model missing
- endpoint is not loopback/local
- generation times out
- JSON invalid
- schema invalid
- output contains raw/leaky content
- output cites unknown aliases
- output references candidates excluded by lifecycle filters
- output has no usable sourced advice

Persist only hash-only receipts and ranking metadata.

### 7. Semantic duplicate / similarity layer

Create:

`src/hb_assistant/construction/second_brain/local_ai/candidate_similarity.py`

Responsibilities:

- Deterministically cluster exact duplicates:
  - same canonical source id
  - same group key
  - same title/reason normalized
  - lifecycle merge links
- Optionally compute semantic similarity on redacted candidate text only:
  - use existing `DeterministicEmbedder` for hermetic tests
  - use Ollama embedder only when local and safe
  - never persist raw vector text
  - do not persist raw vectors to SQLite unless existing embedding policy explicitly permits it; prefer transient vectors + persisted metadata edges
- Output `candidate_similarity_edges` with `review_duplicate_candidate`, never auto-merge/suppress.
- Existing lifecycle merge/suppression rules remain authoritative.

### 8. Brief assembly layer

Create:

`src/hb_assistant/construction/second_brain/local_ai/daily_brief_assembly.py`

Responsibilities:

- Consume ranked candidate overlay.
- Build sections in deterministic order, with model grouping only as a bounded advisory.
- Render:
  - top priorities
  - waiting on me
  - waiting on others / follow-ups
  - meeting prep
  - project / Procore risk
  - review queue / needs decision
  - accepted stale items
  - data gaps / degraded model status
- Every item must carry:
  - title_redacted
  - project_key if present
  - source indicator / candidate id short hash
  - lifecycle state
  - why_this_matters_redacted when safely available
- The deterministic brief remains authoritative. Model narrative is clearly labeled advisory.
- If model layer withheld, the operator sees the deterministic ranking and an honest withheld/degraded banner.

### 9. CLI

Add a read-only/dry-run-first CLI under the existing daily-brief/local-model surface. Suggested:

```bash
hb-assistant second-brain daily-brief rank-candidates \
  --brief-date YYYY-MM-DD \
  --dry-run \
  --json
```

Options:

- `--apply/--dry-run` default dry-run
- `--max-persist N` required with apply
- `--profile PROFILE_ID`
- `--model MODEL_NAME`
- `--provider ollama`
- `--timeout-seconds N`
- `--no-client` for tests / deterministic-only mode
- `--mock-output PATH_OR_STRING` if existing pattern supports it
- `--include-similarity/--no-similarity`
- `--db PATH` for isolated tests and `/tmp` DB validation
- `--json/--no-json`

Exit codes:

- `0`: deterministic ranking succeeded; model may be available or degraded with honest fallback
- `2`: invalid CLI usage
- `3`: fail-closed safety/contract/schema violation
- `1`: unexpected implementation error

### 10. Daily-run integration

Integrate after candidate projection/lifecycle filtering and before final rendering.

Required behavior:

- If candidate projection has no eligible candidates, preserve existing honest data-gap behavior.
- If model ranking succeeds, include `ranking_run` and `assembly_run` status blocks.
- If model ranking fails/degrades/withholds, preserve deterministic ranked brief and mark:
  - `model_layer_status`
  - `degraded_reason`
  - `deterministic_fallback_used=true`
- Daily-run success must not be overstated:
  - candidate projection failure still fails/degrades according to existing rules
  - model unavailable is not a hard failure when deterministic fallback succeeds
  - model output safety violation should fail closed and be reflected in usefulness gate

### 11. Usefulness gate additions

Extend existing usefulness gate with contradictions:

- model-ranked item has no source refs
- model-ranked item is rejected/suppressed/merged-away/closed/future-snoozed
- model output references unknown candidate alias
- model ranking succeeded but all model advice was dropped
- model narrative contains raw/leaky content
- daily brief claims “model enriched” without receipt/status metadata
- source-ref coverage below 1.0 for surfaced actionable items
- deterministic fallback used but status says clean model success
- duplicate cluster auto-hid an item without lifecycle merge/suppression authority

### 12. Tests

Add focused tests first, then implementation.

Required unit tests:

- packet builder excludes rejected/suppressed/merged/future-snoozed candidates
- packet builder includes accepted/stale/review-required candidates with lifecycle labels
- packet builder fails or degrades honestly when source refs are missing
- packet builder raw/no-leak scan catches planted email body, URL, token, local path, Procore raw payload shape
- deterministic ranking stable ordering
- feedback calibration applies only above sample threshold and clamps effects
- feedback calibration is raw-free
- model unavailable → deterministic fallback with `model_layer_status=withheld/degraded`
- model timeout → deterministic fallback with safe reason code
- schema invalid → repair attempts then fallback
- model output with unknown candidate alias is dropped
- model output citing lifecycle-excluded candidate is dropped
- model output with raw/leaky text is withheld
- model cannot move low deterministic candidate above high deterministic candidate beyond bounded influence
- duplicate/similarity edges are advisory only and do not auto-merge/suppress
- ranking receipts contain only hashes/metadata
- apply requires `--max-persist`
- dry-run performs zero writes
- all new guard columns remain zero
- renderer shows degraded/withheld banner when model layer is unavailable
- usefulness gate catches contradictions

Required integration tests:

- `/tmp` DB copy daily-run produces deterministic ranking with `--no-client`
- `/tmp` DB copy with mock valid model output produces advisory ranking overlay
- `/tmp` DB copy with mock unsafe/invalid model output preserves deterministic fallback
- lifecycle filtering + ranking + assembly preserve source refs
- no raw private content appears in JSON, markdown, HTML, receipts, artifacts, or status output

### 13. Evidence

Create evidence directory:

`docs/evidence/phase-10-ollama-assisted-candidate-ranking-brief-assembly/`

Required evidence files:

- `00-repo-truth-audit.md`
- `01-design-contract.md`
- `02-schema-migration-proof.json`
- `03-local-model-readiness-before.json`
- `04-ranking-dry-run-no-client.json`
- `05-ranking-dry-run-mock-valid.json`
- `06-ranking-dry-run-mock-invalid-fallback.json`
- `07-daily-run-integration-status.json`
- `08-source-ref-coverage-proof.json`
- `09-lifecycle-filtering-proof.json`
- `10-feedback-calibration-proof.json`
- `11-similarity-advisory-proof.json`
- `12-no-raw-leak-scan.json`
- `13-guard-columns-zero-proof.json`
- `14-pytest-focused.txt`
- `15-ruff.txt`
- `16-mypy.txt`
- `17-compile.txt`
- `18-final-summary.md`

Evidence must be raw-free. If an evidence command could emit raw data, write a summarizer that emits only counts, hashes, and safe diagnostics.

## Validation Commands

Adjust exact module names after implementation.

```bash
cd /Users/bobbyfetting/hb-personal-assistant
git status --short
git branch --show-current
git rev-parse HEAD
```

### Static checks

```bash
python -m compileall src tests
.venv/bin/ruff check src tests
.venv/bin/mypy src
```

### Focused tests

```bash
.venv/bin/pytest \
  tests/construction/second_brain/local_ai/test_candidate_ranking_packets.py \
  tests/construction/second_brain/local_ai/test_candidate_ranking.py \
  tests/construction/second_brain/local_ai/test_feedback_calibration.py \
  tests/construction/second_brain/local_ai/test_ollama_candidate_ranking.py \
  tests/construction/second_brain/local_ai/test_candidate_similarity.py \
  tests/construction/second_brain/local_ai/test_daily_brief_assembly.py \
  tests/construction/second_brain/local_ai/test_daily_brief_ranking_cli.py \
  tests/construction/second_brain/local_ai/test_daily_brief_ranking_usefulness_gate.py
```

### Local model readiness

```bash
.venv/bin/hb-assistant second-brain local-model status --json \
  | tee docs/evidence/phase-10-ollama-assisted-candidate-ranking-brief-assembly/03-local-model-readiness-before.json
```

### Dry-run / no-client proof

```bash
.venv/bin/hb-assistant second-brain daily-brief rank-candidates \
  --brief-date "$(date +%F)" \
  --dry-run \
  --no-client \
  --json \
  | tee docs/evidence/phase-10-ollama-assisted-candidate-ranking-brief-assembly/04-ranking-dry-run-no-client.json
```

### Mock valid model proof

Create a safe mock JSON fixture under `tests/fixtures/phase_10_candidate_ranking/mock_valid_advice.json`.

```bash
.venv/bin/hb-assistant second-brain daily-brief rank-candidates \
  --brief-date "$(date +%F)" \
  --dry-run \
  --mock-output tests/fixtures/phase_10_candidate_ranking/mock_valid_advice.json \
  --json \
  | tee docs/evidence/phase-10-ollama-assisted-candidate-ranking-brief-assembly/05-ranking-dry-run-mock-valid.json
```

### Mock invalid fallback proof

```bash
.venv/bin/hb-assistant second-brain daily-brief rank-candidates \
  --brief-date "$(date +%F)" \
  --dry-run \
  --mock-output tests/fixtures/phase_10_candidate_ranking/mock_invalid_advice.json \
  --json \
  | tee docs/evidence/phase-10-ollama-assisted-candidate-ranking-brief-assembly/06-ranking-dry-run-mock-invalid-fallback.json
```

### DB copy validation

Never mutate production. Use a timestamped `/tmp` copy.

```bash
PROD="$HOME/Library/Application Support/hb-personal-assistant/construction.db"
TS="$(date +%Y%m%d-%H%M%S)"
ROLL="/tmp/hb-phase10-ranking-$TS"
mkdir -p "$ROLL"
cp "$PROD" "$ROLL/construction.db"

.venv/bin/hb-assistant second-brain daily-brief rank-candidates \
  --brief-date "$(date +%F)" \
  --db "$ROLL/construction.db" \
  --apply \
  --max-persist 500 \
  --no-client \
  --json \
  | tee "$ROLL/ranking-apply-no-client.json"
```

Then run guard/source/no-leak checks against the copy only.

## Acceptance Criteria

The slice is complete only when all are true:

- New schema is additive, idempotent, and all new guard columns are zero.
- Dry-run performs zero writes.
- Apply requires an explicit cap.
- The ranking packet contains only structured/redacted data.
- Surfaceable actionable ranked candidates have 100% source-ref coverage.
- Lifecycle exclusions are authoritative.
- Accepted/stale/review-required lifecycle states are surfaced honestly.
- Rejected/suppressed/merged-away/closed/future-snoozed items do not appear.
- Feedback calibration is deterministic, aggregate, bounded, and raw-free.
- Ollama advisory output is local-only, schema-validated, source-linked, and bounded.
- Model unavailable/timeout/invalid/unsafe output preserves deterministic fallback and reports degradation honestly.
- Duplicate/similarity outputs are advisory and never auto-merge/suppress.
- Rendered brief is operator-useful and does not overclaim model success.
- No raw private content appears in prompts returned to CLI, receipts, artifacts, markdown, HTML, status files, or tests.
- Focused tests, compile, ruff, and mypy pass.
- Evidence bundle is complete and raw-free.
- Final handoff gives commit summary and description only.

## Implementation Order

1. Create branch.
2. Run repo-truth audit and update `00-repo-truth-audit.md`.
3. Add/update design contract.
4. Add schema migration + store repository methods + tests.
5. Add Pydantic ranking/assembly schemas.
6. Add packet builder + no-raw tests.
7. Add deterministic ranking + feedback calibration.
8. Add optional Ollama advisory layer through existing structured-output substrate.
9. Add similarity/duplicate advisory layer.
10. Add assembly renderer/status block.
11. Add CLI.
12. Integrate into daily-run and usefulness gate.
13. Run dry-run/no-client validations.
14. Run mock valid/invalid validations.
15. Run `/tmp` DB copy apply validation.
16. Run static checks and focused tests.
17. Produce evidence bundle.
18. Commit with a concise conventional commit message.

## Final Handoff Format

When complete, output only:

```text
Commit summary

<one-line conventional commit summary>

Description

<manifest title/version>
<branch>
<commit sha>

<concise bullet list of implemented behavior, validation, and safety posture>
```
