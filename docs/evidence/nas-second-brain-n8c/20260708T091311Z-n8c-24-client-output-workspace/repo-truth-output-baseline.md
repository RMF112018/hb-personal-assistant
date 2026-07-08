# N8C-24 repo-truth output baseline

Branch A off N8C-23 HEAD e6f5aa9c (schema V112 -> V113).
Legacy scratch writer hb_output_write_file/hb_output_create_dir: local-only, hard-denied remotely, KEPT as legacy.
ai_outputs_card_upsert: unchanged, separate markdown-card write.
New: pa_output_* (10 tools), client_output_write_enabled() gate default ON, GATEWAY_ALLOWLIST expanded to reach all write tools (operator-authorized).
