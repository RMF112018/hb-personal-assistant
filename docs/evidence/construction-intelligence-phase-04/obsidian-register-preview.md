# Phase 04 Prompt 10 — Obsidian Register Preview Proof

Deterministic proof artifact for the Phase 04 Obsidian register coverage. Generated from `tests/test_procore_obsidian_output.py` fixture rows + a fresh temp SQLite seeded with one row per family (10 rows total). All literals below are obviously-synthetic (`example.invalid`, `proof` project_key, `procore.example.com` URLs).

## 1. Builder coverage

| Family | Marker | Builder | Category filter | Source links |
|---|---|---|---|---|
| RFI | `HB-PROCORE-RFI-REGISTER:START/:END` | `build_rfi_register` | `category = 'rfis'` | yes |
| Submittal | `HB-PROCORE-SUBMITTAL-REGISTER:START/:END` | `build_submittal_register` | `category = 'submittals'` | yes |
| Observation (new) | `HB-PROCORE-OBSERVATION-REGISTER:START/:END` | `build_observation_register` | `category = 'observations'` | yes |
| Meeting (new) | `HB-PROCORE-MEETING-REGISTER:START/:END` | `build_meeting_register` | `category IN ('meetings', 'meeting_topics')` | yes |
| Daily Log (updated) | `HB-PROCORE-DAILY-LOG:START/:END` | `build_daily_log_index` | `category LIKE 'daily_log_%'` | yes |

## 2. Idempotency attestation (renderer)

Two consecutive renders against the same seeded DB produce byte-identical output.

| Family | render call 1 SHA-256(12) | render call 2 SHA-256(12) | match |
|---|---|---|---|
| `rfi_register` | `9aea8ea41921` | `9aea8ea41921` | `True` |
| `submittal_register` | `c94460302994` | `c94460302994` | `True` |
| `observation_register` | `6495892407d3` | `6495892407d3` | `True` |
| `meeting_register` | `1e9447979a0d` | `1e9447979a0d` | `True` |
| `daily_log_index` | `7838f0abb843` | `7838f0abb843` | `True` |

## 3. Idempotency attestation (writer)

Each new marker-bounded artifact written twice in sequence; second write preserves a single START/END pair and replaces inner content only.

| Artifact | start marker count | end marker count | second-write byte-identical |
|---|---|---|---|
| `observation_register` | 1 | 1 | yes |
| `meeting_register` | 1 | 1 | yes |
| `daily_log_index` | 1 | 1 | yes |

## 4. Source-link demonstration

Markdown link emission per family — rendered rows preserve sqlite id + source_url.

```
rfi_register: | RFI-001 | Door spec | open | 2026-07-01 | [1](https://procore.example.com/rfi/1) |
submittal_register: | SUB-001 | Curtain wall shop drawings |  | open | 2026-08-01 | [2](https://procore.example.com/sub/1) |
observation_register: | OBS-001 | Minor housekeeping | open | general | low | no | [3](https://procore.example.com/obs/1) |
```

## 5. Redaction attestation

Each rendered register checked for synthetic-literal leakage. The observation register `OBS-002` (near-miss with safety_route) is absent by routing; the safety_route topic `topic-002` is absent by routing; the daily-log notes + accident sections are absent by routing.

| Family | OBS-002 absent | topic-002 absent | review item collected |
|---|---|---|---|
| observation_register | `True` | `—` | `True` |
| meeting_register | `—` | `True` | `True` |

## 6. Stop-condition matrix

| Stop condition | Where enforced | Proof |
|---|---|---|
| Duplicate marker blocks after rerun | `_procore_replace_bounded` in `src/hb_assistant/procore/obsidian.py:94` + `tests/test_procore_obsidian_output.py::test_observation_register_marker_bounded_idempotent` + `test_meeting_register_marker_bounded_idempotent` | Section 3: each artifact has exactly one START/END pair. |
| Raw sensitive text or response bodies in Markdown | `_safe_excerpt` + normalizer `_hash_summary` boundaries + `tests/test_procore_obsidian_output.py::test_no_raw_text_in_new_registers` | Section 5: synthetic literals never appear; safety_route rows excluded. |
| Write outside vault/project target | `_procore_atomic_write_text` (tempfile + os.replace under `target.parent`) + `writer.configured` short-circuit + apply-time `ConstructionVaultWriter` guard | Apply path writes only beneath `root / '01_Projects'`; vault-not-configured raises. |

## 7. Verification fingerprint

Deterministic SHA-256(12) of each rendered Phase 04 register:

- `rfi_register`: `9aea8ea41921`
- `submittal_register`: `c94460302994`
- `observation_register`: `6495892407d3`
- `meeting_register`: `1e9447979a0d`
- `daily_log_index`: `7838f0abb843`
