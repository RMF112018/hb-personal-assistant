# N8C-8 — current-state audit (pre-implementation)

Read-only survey (via an Explore agent + direct reads) confirming what already exists so N8C-8 reuses
rather than reinvents.

## Existing signals (reused, not rebuilt)
- **Structured claim taxonomy** (`store/assistant_claim_tables.py`): `CLAIM_TYPE_VALUES` already contains
  `decision_candidate`, `preference`, `commitment`, `task_candidate`, `risk` — so extraction reads a
  structured column, no keyword parsing required.
- **A deterministic rule-based extractor** (`obsidian_mcp/claim_extraction.py::_RULES`) already turns raw
  text into those typed claims (decision / commitment / risk / assumption / preference / task). N8C-8
  consumes its OUTPUT (the claims) — it does not re-run text classification.
- **Neutral helpers** (`obsidian_mcp/memory_models.py`): `normalize_memory_name`, `bound_text`,
  `sha256_hex`, `clamp_confidence` — reused verbatim so normalization/bounding/hashing can't drift.
- **Layer scaffolding** (N8C-6/7): schema-module → models → repository → extractor → read-only
  API/CLI/MCP, the `borrow_connection`/`transaction` pattern, `_assistant_env` guardrails, the read-only
  MCP snapshot (`mode=ro&immutable=1` + `query_only=ON`), and the default-on kill-switch gate pattern.

## Gaps N8C-8 fills
- No durable **decision** / **preference** / **open-loop** records existed — claims were the terminus.
- No `question` claim_type exists → N8C-8 derives questions as a conservative, bounded, low-confidence
  open-loop signal (never a new claim_type; V100 is untouched).

## Naming caveat noted
`naming.py` has string-id constants `DECISION="decision"` / `OPEN_LOOP="open_loop"` distinct from the DB
`claim_type` enum (`decision_candidate`). N8C-8's own enums live in its schema module and do not depend
on `naming.py`, avoiding that mismatch.
