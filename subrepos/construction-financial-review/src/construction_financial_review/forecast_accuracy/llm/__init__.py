"""Optional, advisory local-Ollama reasoning layer for the forecast-accuracy package.

Strictly advisory: prompts contain only deterministic numeric facts, outputs are JSON-validated,
safety-scanned (fail-closed to deterministic templates), and hash-receipted. The LLM never sets a
number that becomes a recommendation. The package completes even if Ollama is unavailable.
"""
