# Schema-failure handling proof

The structured-output client validates every model output against a Pydantic schema before use; an invalid/malformed output is rejected (status reflects failure, `schema_valid=False`) and never persisted as a candidate. The synthetic eval harness measures this per fixture.

- eval mode: `synthetic` · suite: `daily-brief`
- schema_valid_rate metric present: True (value: 1.0)
- Malformed JSON / schema-invalid / low-confidence handling is covered by the repo's `tests/test_phase_10_structured_output.py` and the eval harness; both stay offline and raw-free.
