# N8C-20 — no execution / no external / no repair / no LLM

Source-level guardrails on `quality_evaluator.py` (asserted by `test_quality_evaluator.py`):

- **`test_evaluator_imports_no_forbidden_module`** — AST import scan finds none of: `agent_bridge`, `ollama`,
  `requests`, `httpx`, `smtplib`, `subprocess`, `source_content_provider`.
- **`test_evaluator_has_no_execution_entrypoint`** — no function name contains: `execute`, `apply_action`,
  `repair`, `send`, `dispatch`, `schedule`, `accept`, `reject`, `defer`, `dispose`, `write_back`.
- **`test_evaluator_never_calls_source_file_read`** — the source contains none of: `source_file_read`,
  `read_file_absolute`, `SourceContentProvider`, `def _repair`, `UPDATE `, `DELETE `, `INSERT INTO`.
  (All writes go through `QualityRepository`, which alone touches the quality tables.)

## Consequences

- No action is executed and no external system (email / calendar / task / reminder / Slack) is contacted:
  the evaluator only reads existing N8C repositories and emits advisory findings.
- No N8D job is created and `agent_bridge` is never imported.
- No live LLM / Qwen / Ollama call: the evaluator is purely deterministic (rule-based checks + digests).
- No source file is read and no source scan/reindex or source-card generation occurs: source-ref validity is
  checked via the already-indexed `SourceIndexRepository.get_source_detail` (metadata only), never by reading
  the file on disk.
- No review disposition is written: findings may RECOMMEND operator review but the evaluator never calls a
  review-disposition writer, and there is no such path in the quality layer.
