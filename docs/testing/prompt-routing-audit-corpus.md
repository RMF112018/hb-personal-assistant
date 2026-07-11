# Prompt Routing Audit Corpus (July 2026)

Versioned regression evidence for the independent prompt-routing audit (section 4 live routing matrix).

## Corpus artifact

- **File:** `tests/fixtures/prompt_routing_audit_corpus_v1.json`
- **Version:** `corpus_version = 1`
- **Cases:** 50 prompts from the July 10, 2026 audit
- **Enforcement:**
  - `required` (42) — must pass in CI (0 blocker/HIGH regressions)
  - `accepted_partial` (8) — documented usability debt; xfail if expectations drift

Each case carries `expected` route fields compatible with `scripts/route_proof_lib.py` plus optional `expected_plan` (for example `recommended_call_mode` on audit row 1).

## Commands

Run the focused bundle (offline `route_prompt` + temp-DB broker parity + legacy 49-case matrix):

```bash
scripts/test-prompt-routing-audit.sh
```

Run only the 50-case parametrized tests:

```bash
.venv/bin/python -m pytest tests/test_prompt_routing_audit_corpus.py -m "not live" -q
```

Optional live NAS/container replay (opt-in):

```bash
HB_PROMPT_ROUTING_AUDIT_LIVE=1 .venv/bin/python -m pytest tests/test_prompt_routing_audit_corpus.py -m live -q
```

Generate an offline matrix report JSON (legacy runner expects a bare case array — use pytest for the versioned wrapper):

```bash
.venv/bin/python scripts/run-audit-route-regression-matrix.py \
  --matrix scripts/audit-route-regression-matrix.json \
  --out /tmp/audit-route-regression-matrix-offline.json
```

## Related guards

- `tests/test_prompt_preflight_semantic_equivalence.py` — 49-case legacy matrix + semantic equivalence groups
- `scripts/audit-route-regression-matrix.json` — pre-audit regression matrix (subset/overlap)
- `docs/evidence/nas-second-brain-n8c/*-routing-remediation/` — deploy and live probe evidence