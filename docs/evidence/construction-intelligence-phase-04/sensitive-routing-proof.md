# Phase 04 Prompt 09 — Sensitive Routing & Redaction Proof

Deterministic proof artifact for the Phase 04 sensitive-routing invariants. Generated from `tests/test_procore_sensitive_routing_proof.py` fixture blobs (`PHASE_04_SENSITIVE_TEXT_BLOBS` in `src/hb_assistant/construction/fixtures/procore.py`). All literals below are obviously-synthetic (`example.invalid`, `555-010-*` reserved prefix, and `syntheticfixturetoken*`).

## 1. Routing table (declarative parity)

| Family | YAML rule_id | Normalizer | Trigger field | Hash field | Route |
|---|---|---|---|---|---|
| RFI reply | `procore-rfi-legal-or-contractual` | `normalize_rfi_reply` (`src/hb_assistant/procore/normalizers/rfi.py:169`) | `body` | `body_summary` | `review_required` |
| Submittal response | `procore-submittal-financial-or-legal` | `normalize_submittal_response` (`src/hb_assistant/procore/normalizers/submittal.py:194`) | `comment` | `body_summary` | `review_required` |
| Observation | `procore-observation-safety` | `normalize_observation` (`src/hb_assistant/procore/normalizers/observation.py:213`) | `description` | `description_summary` | `review_required` |
| Meeting topic | `procore-meeting-sensitive-topic` | `normalize_meeting_topic` (`src/hb_assistant/procore/normalizers/meeting.py:263`) | `description` | `description_summary` | `review_required` |
| Daily log section item | `procore-daily-log-personnel-pii` | `normalize_daily_log_section_item` (`src/hb_assistant/procore/normalizers/daily_log.py:111`) | `body` | `body_summary` | `review_required` |

## 2. Invariant attestations

| Family | review_required | safety_route | hash_prefix present | raw blob absent | email absent | phone absent | token absent |
|---|---|---|---|---|---|---|---|
| RFI reply | `True` | `—` | `b25dbfaa8239` | `True` | `True` | `True` | `True` |
| Submittal response | `True` | `—` | `66c5b47f96bc` | `True` | `True` | `True` | `True` |
| Observation | `True` | `True` | `bc2f0763de4f` | `True` | `True` | `True` | `True` |
| Meeting topic | `True` | `—` | `a6ff1ba76d81` | `True` | `True` | `True` | `True` |
| Daily log section item | `True` | `—` | `4602e54995fc` | `True` | `True` | `True` | `True` |

## 3. Masked-excerpt demonstration

Demonstration of `mask_pii_in_excerpt` (`src/hb_assistant/procore/redaction.py`). The fixture excerpt below is synthetic; the masked excerpt is what would appear in an audit log.

| Family | Masked excerpt |
|---|---|
| RFI reply | `Contractor escalates legal claim regarding contract scope; contact [email-redacted] or [phone-redacted]; session id [tok` |
| Submittal response | `Cost impact and invoice dispute attached; reply payment status to [email-redacted] or [phone-redacted]; reference [token` |
| Observation | `Near miss injury reported during fall hazard inspection; PPE violation logged. Contact safety lead at [email-redacted] o` |
| Meeting topic | `Settlement and dispute claim discussed in executive session; follow-up to [email-redacted] or [phone-redacted]; agenda i` |
| Daily log section item | `Badge entry for personnel record; carrier delay logged. Contact [email-redacted] or [phone-redacted]; log id [token-reda` |

## 4. Static-scan attestation

This artifact lives under `docs/evidence/construction-intelligence-phase-04/`, which falls within the broad `docs/` allowlist in `tests/test_repo_sensitive_scan.py` (the allowlist scope was already established for prior Phase 04 evidence artifacts). All synthetic literals above are masked or contained in code-fenced excerpts where appropriate; the test asserts the repo sensitive scanner does not surface new findings.

## 5. Stop-condition matrix

| Stop condition | Where enforced | Proof |
|---|---|---|
| Sensitive fixture not routed | `tests/test_procore_sensitive_routing_proof.py::test_phase_04_family_routes_and_redacts` | Section 2: every family `review_required=True`. |
| Raw token/email/phone/full text appears in evidence or SQLite fixtures | `_assert_no_raw_leak` in the proof test + normalizer hash-summary boundaries | Section 2: all leak columns `True`; this file contains no raw literal outside masked excerpts. |
| Validate suite does not enforce family coverage | `hb-assistant procore validate --json` check `sensitive_routing_rules_cover_phase_04_families` | Check added in `src/hb_assistant/procore/validate.py`; asserts every family slug appears in a rule_id. |

## 6. Verification fingerprint

Deterministic SHA-256(12) digests of each serialized normalized record (with all synthetic literals already absent):

- `rfi`: `d95aa2e6acf9`
- `submittal`: `e3968d6f1319`
- `observation`: `8c06b8f6f551`
- `meeting`: `1fbcae1e5965`
- `daily_log`: `0c18fccbcb6e`
