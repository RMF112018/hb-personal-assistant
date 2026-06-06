# Phase 09 — Rendered Daily Brief Quality Proof

- proof_passed: True
- generated_utc: 2026-06-06T10:38:53.037851+00:00
- safe_fixture_passed: True
- packet_weak_coverage: True
- packet_has_review_required: True
- packet_has_stale: True

## Tampered variants (each must fail its expected check)

- missing_advisory_notice: expected_failed_check=advisory_notice_present check_failed=True overall_passed=False
- missing_stale_warning: expected_failed_check=stale_low_confidence_warnings_present check_failed=True overall_passed=False
- final_determination_language: expected_failed_check=no_final_determinations check_failed=True overall_passed=False
- raw_shaped_value: expected_failed_check=no_raw_shaped_values check_failed=True overall_passed=False
- source_system_update_claim: expected_failed_check=no_source_system_update_claims check_failed=True overall_passed=False
- coverage_omitted_when_weak: expected_failed_check=coverage_limitations_not_omitted check_failed=True overall_passed=False
