# 08 — Tests

Invocation: `PYTHONPATH=src:subrepos/construction-financial-review/src .venv/bin/python -m pytest …`

## Targeted N8C-1 + regression set — **222 passed, 1 warning in 73s**

New / extended:
- `tests/test_nas_mcp_ai_outputs.py` — `_render_card` neutral frontmatter incl. `domain`/`created_via`;
  created-card frontmatter; **`domain` sanitizer unit test** (lowercase, bounded, traversal/empty →
  `unknown`, no separators); **`domain` sanitized + path-inert via broker** (hostile `../../etc/passwd`
  → `etcpasswd`, no escape; `///` → `unknown`); **legacy-card append not broken**; legacy-card update
  re-renders neutral.
- `tests/test_nas_mcp_remote_profile.py` — neutral frontmatter incl. `domain: work`/`created_via: mcp`
  survives create→update→append; `test_status_reports_profile_and_gates` locks `remote_cloudflare` =
  AI-Outputs-write-only (scratch + legacy-vault writes disabled).
- `tests/test_obsidian_source_card_local_summary_marker.py` — emitter stays legacy; dual-READ; interior-
  only swap; exactly-one-block invariant.

Regression (unchanged behaviour, green): `test_nas_mcp_safe_mode_limits_freshness.py`,
`test_nas_mcp_origin_auth.py`, `test_nas_mcp_readonly.py`,
`test_obsidian_source_card_local_summary_appender.py`, `test_obsidian_source_enrich.py`,
`test_obsidian_source_classifier_repair.py`, `test_obsidian_source_email_attachment_cards.py`,
`test_obsidian_source_taxonomy_phase10a.py`, `test_obsidian_source_card_quality_regression.py`,
`test_obsidian_source_tropical_identity_correction.py`.

Lone warning = pre-existing StarletteDeprecationWarning (httpx TestClient), unrelated.

## End-to-end smoke (`NasMcpBroker.dispatch`)
```
dispatch domain="Home Ownership" -> card in AI Outputs/, frontmatter domain: homeownership, created_via: mcp
dispatch domain="../../../etc/shadow" -> domain: etcshadow, /etc/shadow escaped: False
dispatch created_via="HACKED" (ignored) -> created_via: mcp, HACKED present: False
```

## Lint — `ruff check` clean
All changed files pass `ruff check` (`naming.py`, `nas_mcp/ai_outputs.py`, `nas_mcp/tool_registration.py`,
`nas_mcp/broker.py`, `obsidian_mcp/source_notes.py`, `source_local_summary.py`, `source_card_repair.py`,
`scripts/obsidian_source_card_append_local_summary.py`, and the three test files). No whole-file
`ruff format` was run (import ordering fixed by hand to avoid reformat churn).
