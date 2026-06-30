# Controls Language QA

- `validate_controls_text()` scans summary headline/supporting points, top_controls copy, and section headlines
- Reuses forbidden-term detection with negation/disclaimer awareness (`_contains_forbidden_term`)
- Controls service attaches `controls_language_qa` to every payload
- Tests: `test_controls_language_qa_passes_for_fixture_payload`, `test_controls_language_qa_fails_on_forbidden_terms`
