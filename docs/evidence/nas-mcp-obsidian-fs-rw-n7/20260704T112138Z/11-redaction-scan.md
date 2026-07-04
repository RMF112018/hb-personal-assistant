# 11 — Redaction scan

**Run:** 20260704T112138Z (supplement pass)  
**Scanner:** `hb_assistant.security.sensitive_scan.SensitiveScanner` (Phase 12 bounded scan; no secret values emitted)

## Scope

| Path | Role |
|---|---|
| `docs/evidence/nas-mcp-obsidian-fs-rw-n7/20260704T112138Z/` | Evidence package |
| `deploy/nas/mcp/` | Compose, config, guards |
| `src/hb_assistant/nas_mcp/` | NAS MCP implementation |
| `src/hb_assistant/obsidian_mcp/mutations.py` | Support-dir env hook |
| `tests/test_nas_mcp_readonly.py` | Read-only + DB tests |
| `tests/test_nas_mcp_files_rw.py` | FS RW tests |

## SensitiveScanner result

| Metric | Value |
|---|---|
| Files considered | 44 |
| Files scanned | 44 |
| Total rule hits | 6 |
| Critical | 0 |
| High | 1 |
| Medium | 5 |

### Findings (expected / benign)

| Severity | Rule | Location | Disposition |
|---|---|---|---|
| high | SEC-ENV-001 | `tests/test_nas_mcp_readonly.py:291` | Test fixture documenting deny pattern for `.env`-style assignments — not a real secret |
| medium | SEC-MSAL-001 | `src/hb_assistant/nas_mcp/redaction.py:9` | Deny-list / redaction keyword documentation |
| medium | SEC-MSAL-001 | `src/hb_assistant/nas_mcp/config.py:14,19,20` | Config deny patterns for token/cache paths |
| medium | SEC-MSAL-001 | `tests/test_nas_mcp_readonly.py:291` | Test asserting token-path denial |

**Verdict:** **PASS** — no PEM, JWT, bearer tokens, client secrets, or real credential assignments. Hits are scanner/detector self-references and test deny fixtures only.

## Evidence path / host review (manual)

Additional grep for literals that must not leak as live secrets:

| Pattern | Hits | Disposition |
|---|---|---|
| Private IPv4 (`10.x.x.x`) | 0 | — |
| Password assignment | 0 | — |
| `hb-nas` hostname | 1 in `00-closeout.md` | Operational context only; no credentials |
| `/volume1/homes/bfetting/...` | Design docs (`02`, `04`, `05`, `10`) | Documented mount targets; not vault note content |

No note bodies, API keys, tokens, or `.enc` file contents appear in the evidence package.

## Compose static guard

`deploy/nas/mcp/check-mcp-compose.sh` → **PASS**

## Conclusion

Evidence package and N7-FS-RW code/test/deploy artifacts are safe to commit from a redaction perspective.

**NAS functional proof:** completed during the `20260704T113533Z` re-apply (see `10-nas-reapply-proof.md`). Probe artifacts (`vault/n7-fs-rw-probe.md`, `outputs/n7-fs-rw-probe.txt`) remain on NAS only — not included in this commit.
