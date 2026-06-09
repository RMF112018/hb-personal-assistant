# Phase 10 — Local Model Evaluation + Routing for Daily-Brief Intelligence (evidence)

Date: 2026-06-09 · Local-only · No cloud LLM · No external writeback · No raw-content egress

Branch `experiment/local-model-routing-daily-brief-intelligence` (base HEAD `7815cfd2`, schema head
**V44 — no migration added**). All numbers below are **metrics-only and redacted**: no raw prompt,
raw model response, candidate title, URL, email, join link, or token is reproduced here.

## What was proven

A repeatable local model **evaluation harness**, a deterministic task → profile **router**, and an
optional **daily-brief intelligence** enrichment layer — all local-only, fail-closed, and raw-safe.

## Environment

| Item | Value |
| --- | --- |
| Ollama daemon | reachable, ready |
| Present models | `gpt-oss:20b`, `llama3.1:8b`, `mistral-nemo:12b`, `qwen2.5:14b`, `nomic-embed-text` |
| Working DB | copy of the **(Dev)** app-support DB → `/tmp/hb_model_routing_brief_quality.sqlite` |
| DB schema | V44 (unchanged; this work adds **no** migration) |
| Candidates (2026-06-09) | 20 rows in `daily_brief_action_candidates` |

## 1. Routing (live)

`local-model route --task-family daily_brief_synthesis_quality`

| Field | Value |
| --- | --- |
| selected_profile | `brief_synthesis` |
| available | true |
| reason_code | `selected_routed` |
| fallback_chain | `brief_synthesis → default_extract` |
| no_cloud | true |

Fail-closed proof — `route ... --mock` (daemon unreachable): `blocked=true`, `reason_code=daemon_unreachable`,
exit code 1, decision still reported (would-be primary `brief_synthesis`).

## 2. Evaluation

### 2a. Synthetic suite (offline, decisive) — `eval --suite daily-brief --models auto --synthetic`

| Metric | Value |
| --- | --- |
| json_valid_rate | 1.0 |
| schema_valid_rate | 1.0 |
| redaction_pass_rate | 1.0 |
| blocked_families | none |

Every task family receives a recommendation; `use_next_run` is populated. (In synthetic mode all
profiles replay identical canned output, so the harness — not model differentiation — is what's
proven here.)

### 2b. Live suite (real models) — `eval --task-family daily_brief_synthesis_quality --models mistral-nemo:12b --live`

| profile | schema_valid_rate | redaction_pass_rate | latency_ms |
| --- | --- | --- | --- |
| brief_synthesis (mistral-nemo:12b) | 1.0 | 1.0 | ~1796 |
| default_extract (mistral-nemo:12b) | 1.0 | 1.0 | ~2487 |

Decisive recommendation: **`brief_synthesis`** (equal schema reliability, lower latency).
`usefulness_mean` is ~0.0 on the *minimal* synthetic fixture (little to synthesize); real-data
usefulness is shown in §3.

## 3. Daily-brief intelligence (live, DB copy, dry-run)

`daily-brief intelligence --date 2026-06-09 --db <copy> --dry-run`

| Run | Outcome | Key metrics |
| --- | --- | --- |
| Sample A (enriched) | `enriched=true`, status `ok`, `brief_synthesis`/mistral-nemo:12b | bullets_kept **3**, dropped 0, **source_link_coverage 1.0**, usefulness **0.83**, latency ~34s, fallback_used false, redaction passed |
| Sample B (integrated `daily-run --with-intelligence`) | `enriched=false`, status `schema_invalid` → **withheld → deterministic brief preserved** | redaction passed; run still `ok` |
| Fallback (`--mock`) | `enriched=false`, status `model_unavailable`, `withheld=daemon_unreachable` | run still `ok` (deterministic fallback) |

**Finding:** the local 12B model is not *consistently* schema-valid for the richer intelligence
schema across calls (one call enriched in 34s; another withheld). Both outcomes are safe —
enrichment is advisory and **fail-closed**: on any model/JSON/schema/source-link/redaction failure
the deterministic brief is preserved. This run-to-run variance is exactly what the eval/routing
layer exists to measure.

## 4. Guardrail proof

| Guard | Result |
| --- | --- |
| Candidate rows after dry-runs | 20 (unchanged) |
| Guard-column sum (`raw_*_persisted`, `*_writeback_performed`, `email_send`, `calendar_mutation`) | **0** |
| `local_model_run_receipts` written by my dry-runs | **0** (the 1 existing receipt is pre-existing in the source Dev DB; receipts are hash-only) |
| Redaction scan of every surfaced JSON (route/eval/intelligence/daily-run) | **clean** (no URL/email/join-link/token/PEM) |
| Cloud route | none (router is local Ollama only; `no_cloud=true`) |
| External writeback / email / calendar mutation | none |

## 5. Limitations / honest notes

- `--models auto` evaluates enabled non-heavy profiles; `gpt-oss:20b` (disabled) and `qwen3:30b`
  (heavy, absent) are excluded unless explicitly enabled.
- Live eval measures **schema/redaction/latency reliability** decisively; **usefulness** needs real
  input and is best read from the real daily-brief run (§3), not the minimal synthetic fixtures.
- Intelligence reliability on a 12B model varies run-to-run; the safe posture is advisory +
  fail-closed. A more reliable profile (or `--heavy-enabled` reasoning model) is the natural next
  tuning step, measured by this same harness.

## Reproduce (local only)

```bash
cp "<(Dev) app-support db>" /tmp/hb_model_routing_brief_quality.sqlite
.venv/bin/hb-assistant second-brain local-model route --task-family daily_brief_synthesis_quality --json
.venv/bin/hb-assistant second-brain local-model eval --suite daily-brief --models auto --synthetic --json
.venv/bin/hb-assistant second-brain local-model eval --task-family daily_brief_synthesis_quality --models mistral-nemo:12b --live --json
.venv/bin/hb-assistant second-brain daily-brief intelligence --date <YYYY-MM-DD> --db /tmp/hb_model_routing_brief_quality.sqlite --dry-run --json
.venv/bin/hb-assistant second-brain daily-run run --db /tmp/hb_model_routing_brief_quality.sqlite --date <YYYY-MM-DD> --dry-run --with-intelligence --no-open-browser --no-generate-browser --json
```

Raw local outputs (the model bullet text) are intentionally **not** committed — only the metrics
above. The `/tmp` JSON receipts are local-only and must not be added to the repo.
