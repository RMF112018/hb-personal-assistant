# Model Provider Contract

`enrichment_model_provider.ModelProvider.generate(prompt, *, model, timeout_s) -> str`.
- `FakeModelProvider`: deterministic canned JSON keyed off a `[[job_type:...]]` prompt marker; used
  by ALL automated tests (no live Ollama required for CI).
- `OllamaModelProvider`: wraps the existing `construction/classification/client.OllamaChatClient`
  (`generate_json`, model `qwen2.5:14b`) — the same client `source_local_summary` uses. `requests` is
  imported LAZILY inside `.generate` so importing the module never pulls `requests`.

Live-Ollama runs are an operator path (documented, deferred): `hb-assistant qwen-worker run-batch
--apply` on the MacBook with Ollama serving qwen2.5:14b. Distributed MacBook/NAS execution is not
required for N8C-5 acceptance — the queue/worker contract is proven with FakeModelProvider.
