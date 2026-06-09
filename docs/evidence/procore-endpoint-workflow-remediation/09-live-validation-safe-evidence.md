# 09 — Live Validation (Safe Evidence)

Prompt: `09_LIVE_VALIDATION_AND_EVIDENCE.md`. Bobby explicitly approved this live
production run. Safe evidence only — counts, statuses, endpoint names, reason
codes, timestamps, table names. No tokens, headers, payloads, signed URLs, or
private response bodies.

## Pre-live gates (all satisfied)

| Gate | Result |
| --- | --- |
| Bobby approval | **Granted** (AskUserQuestion: "Approve live run now") |
| Working tree | clean (only untracked `docs/planning/**`; all code committed) |
| Production DB path | resolved (redacted): `~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite` |
| DB backup | `/tmp/hb-personal-assistant-before-procore-endpoint-remediation-1781025948.sqlite` — size-verified match (251,191,296 bytes) |
| Stale loop | none running (`ps` clean; launchd agents loaded but idle) |
| No-writeback proof | `proof_passed: true` (`/tmp/procore-no-writeback-proof.json`) |
| Auth | `env_present`, ready; access token was expired → approved `procore auth refresh` → valid (~90 min). No token values emitted. |

## Commands (exit codes)

```
hb-assistant scheduler status --environment production --json          # exit 0
hb-assistant procore auth status --json                                # exit 0 (token expired)
hb-assistant procore live no-writeback-proof --json                    # exit 0 (proof_passed)
hb-assistant procore auth refresh --json                               # exit 0 (approved)
hb-assistant scheduler run daily-source-refresh --environment production --json   # exit 0
```

## Live run result

| Field | Before (2026-06-08 run57) | After (2026-06-09 run58) |
| --- | --- | --- |
| overall status | **degraded** | **ok** |
| failure_count | 4 stages (28 endpoint errors) | **0** |
| persistence path | `procore_sync_*` | `procore_live_*` |
| endpoints succeeded | 3 of 10 / project | **73** executions |
| contract-bug failures | 7 / project (400/404) | **0** |
| externally blocked | — | **0** |

### Endpoint outcome matrix (by_status)

```
success: 73
skipped_company_level_already_handled: 3   (projects fetched once; other 3 pilots)
skipped_tool_not_enabled: 1                (list-drawings — no canonical adapter)
contract_bug_*: 0
transport_error_*: 0
```

Per project: `tropical` 19 ok / 0 failed; `pga-modern-garage`, `alton-hilltop-pbg`,
`the-wellington` 18 ok / 1 skipped (company dedup) / 0 failed each.

## Post-run DB proof (safe SQL)

```
procore_live_records total: 30059 (latest last_seen 2026-06-09T17:29:52Z)
procore_live_sync_runs today: state=success x73 (0 error / 0 partial)
procore_live_sync_watermarks advanced today: 73
```

Previously-failing endpoints, now fresh (canonical `procore_live_records`):

| endpoint | count | latest last_seen_at_utc |
| --- | --- | --- |
| projects | 21 | 2026-06-09T17:26:31Z |
| change-events | 195 | 2026-06-09T17:28:54Z |
| subcontractor-invoices | 220 | 2026-06-09T17:29:34Z |
| prime-contracts | 5 | 2026-06-09T17:29:39Z |
| punch-items | 4 | 2026-06-09T17:29:39Z |
| daily-log-weather | 127 | 2026-06-09T17:29:43Z |
| daily-log-manpower | 962 | 2026-06-03 (no new rows in the bounded window — run succeeded) |

Legacy path (retired, untouched): `procore_synced_entities=1185`, `procore_sync_runs=0`, `procore_sync_errors=0`.

## Guardrails

- GET-only (no Procore writeback): `no-writeback-proof` passed; `run_live_sync` uses the GET-only client.
- No M365 writeback; no cloud LLM.
- `raw_body_persisted=0` across all 73 new runs (V6 CHECK constraint).
- stderr empty; no token/payload/signed-URL/private-body in any captured artifact.

## External blockers

**None.** All previously-failing endpoints now succeed via the canonical
adapters; `list-drawings` is explicitly classified `skipped_tool_not_enabled`
(no adapter; tool not enabled for these pilots) — a classification, not a blocker.
