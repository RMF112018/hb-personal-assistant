# Prompt 01A — PDF high-fidelity extraction (LlamaParse request → local pdfplumber)

**Generated (UTC):** 2026-06-01
**HEAD (pre-commit):** `921c52a87362a84ae0cacc8dfd38a966829c9fc6`
**Package:** `1.3.0` · **Schema:** `24` (no migration) · **Runtime:** Python 3.12 (venv)
**Verdict:** The requested **cloud LlamaParse** integration was **not** implemented — it violates this repo's
enforced local-first / no-upload guardrails and the prompt's own stop conditions. The objective's intent
(high-fidelity table/layout PDF extraction) is delivered with a **local, offline** engine (`pdfplumber`
primary, `pypdf` fallback), additively and backward-compatibly. All guardrail proofs remain green.

---

## 1. Why not LlamaParse (stop condition, classified)

LlamaParse is a cloud API: it uploads the source PDF to `api.cloud.llamaindex.ai` and needs
`LLAMA_CLOUD_API_KEY`. That is incompatible with the non-negotiable runtime guardrails and the prompt's own
guardrails ("Local-first and read-only", "No external-system… upload", "LlamaParse must… not perform any
external actions"):

- It would transmit SharePoint/OneDrive construction documents (contracts, financials, personnel) to a
  third party — the most-forbidden action in this codebase.
- It would break enforced proofs: `tests/test_mutation_lockout.py` (greps `src/hb_assistant/files` for
  `.post(`/network), and `construction-agent data-quality no-writeback-proof` (`no_live_calls=true`; scans
  for network imports) → `proof_passed` would flip to `false`.
- It is unvalidatable in this offline environment (default suite is `not live`; no key/network).

This matched the prompt's stop conditions ("requires external writeback", "raw content… persisted
[externally]") and the standing rule "Repository truth… overrides package intent." Per operator decision, a
**local high-fidelity engine** was implemented instead.

---

## 2. Repo-truth preflight

| Fact | Value |
|---|---|
| `git rev-parse HEAD` (pre-commit) | `921c52a87362a84ae0cacc8dfd38a966829c9fc6` |
| `git status --short` | intended edits (pyproject, pdf.py) + new test/fixture/docs; untracked `.claude/` |
| Runtime | venv `python3.12` (the interpreter `pip`/`pytest`/`mypy` use; the `python` symlink → 3.14 is unused by the toolchain) |
| `hb-assistant --version` | `1.3.0` |
| Schema version | `24` (no migration in this prompt) |
| Ancestry | `921c52a` (Prompt 01), `65760e5` (Prompt 00), `733ffed` (07C closeout) — all ancestors of HEAD |

Repo-truth corrections to the prompt's assumptions: there is **no `ParsedDocument` model** (the parser
contract is a plain `dict`: `text_excerpt`/`char_count`/`failure_code`/`page_count`) and **no
`hb-assistant files parse --type pdf --sample 20` command** (the file CLI is `files ingest` / `files sample`
and `graph files extract`). The integration uses the real dict contract; the missing CLI was **not** invented
(no local PDF corpus to sample).

---

## 3. Change set (smallest additive; no migration)

| File | Change |
|---|---|
| `pyproject.toml` | add `pdfplumber>=0.11` to `[project] dependencies` (local lib; `mypy`/`ruff` already exclude `src/hb_assistant/files/`, so no override needed) |
| `src/hb_assistant/files/parsers/pdf.py` | engine-selecting `PDFParser`: pdfplumber primary (text + `extract_tables()` → bounded `[table]` rows) with pypdf fallback (optional import guard); same dict contract + additive `table_count` / `extraction_engine` |
| `tests/test_pdf_parser_pdfplumber.py` (new) | 9 tests: structured-table extraction, bounded-excerpt, idempotency, pypdf fallback (monkeypatch), measured-improvement guard, error isolation (missing/non-PDF), fixture presence |
| `tests/fixtures/sample_table.pdf` (new, 2339 B) | synthetic construction-schedule PDF with a ruled table; generated via reportlab **transiently** (reportlab uninstalled after; **not** a project dep); synthetic content, no secrets |
| `docs/architecture/44-pdf-high-fidelity-local-extraction.md` (new) | design record |

`ParserRouter` and the other 7 parsers are untouched. Downstream (`FileIngestionService`,
`ControlledExtractor` redaction, retrieval) is unchanged — it already forwards extra parser keys into
`parser_meta` and bounds/redacts the excerpt.

---

## 4. Measured improvement (fixture `tests/fixtures/sample_table.pdf`)

| Engine | `extraction_engine` | `table_count` | `char_count` | structured row `A-300 | Structural Steel` |
|---|---|---|---|---|
| Primary | `pdfplumber` | `1` | `810` | **preserved** (`[table]` pipe-delimited rows) |
| Fallback | `pypdf_fallback` | n/a | `539` | **lost** (flattened text) |

The ruled activity/duration/responsible table is captured as structured rows under pdfplumber and flattened
under pypdf — the fidelity gain the objective sought, achieved entirely locally. A regression test
(`test_pdfplumber_beats_pypdf_on_table_fidelity`) locks this in.

---

## 5. Validation matrix (HEAD `921c52a`, schema 24)

| Command | Exit | Excerpt |
|---|---|---|
| `python -m compileall src tests` | `0` | clean |
| `ruff check .` | `0` | `All checks passed!` |
| `mypy src` | `0` | `Success: no issues found in 176 source files` |
| `pytest -m "not live and not integration and not manual"` | `0` | **2080 passed** (2072 + 8 new) |
| `construction-agent validate --json` | `0` | 4/4, schema 24 |
| `procore validate --json` | `0` | 28/28 |
| `graph files status --json` | `0` | `ok=true` |
| `graph files no-writeback-proof --json` | `0` | `ok=true`; `mutation_method_calls_found=0` |
| `graph calendar status --json` / `graph mail status --json` | `0` | `ok=true` |
| `construction-agent data-quality no-writeback-proof --json` | `0` | `proof_passed=true`, `no_raw_values_persisted=true`, `no_live_call_performed=true` |

(The prompt's `files parse --type pdf --sample 20 --json` is not implemented in this repo — documented, not
invented. Engine validation is via unit tests + the synthetic before/after comparison above.)

---

## 6. No-writeback / no-raw-content / offline attestation

- **No SQLite migration** (schema stays V24).
- pdfplumber + pdfminer + pypdfium2 are **local** libraries: no upload, no API key, no network in the
  extraction path. Our `pdf.py` issues no `.post(`/`.put(`/HTTP calls — `test_mutation_lockout` and the
  no-writeback import scans stay clean (`proof_passed=true`, `no_live_call_performed=true`, 0 mutating calls).
- Output is a **bounded excerpt** (≤ 8000 chars, first 5 pages); downstream redaction
  (`ControlledExtractor._bounded_redact`, 2000 chars) is unchanged. No full document text, signed/download
  URLs, tokens, or secrets are persisted. The committed fixture is synthetic (no secrets). All document cards
  remain `review_required`; nothing is auto-promoted.

---

## 7. Handoff

- **Changed:** `pyproject.toml`, `src/hb_assistant/files/parsers/pdf.py`; new
  `tests/test_pdf_parser_pdfplumber.py`, `tests/fixtures/sample_table.pdf`, `docs/architecture/44-…`, this
  evidence file.
- **Gates:** all validation commands exit 0; pytest 2080 passed; guardrail proofs `proof_passed=true`.
- **Measured improvement:** structured table extraction (1 table, structured rows) under pdfplumber vs
  flattened text under pypdf.
- **Next prompt allowed?** **Yes.** PDFs now yield higher-fidelity, structured, still-bounded/redacted
  excerpts to the existing `parser_outputs` / document-card / retrieval consumers with no contract change.
- **Recommended follow-ups:** (1) persist per-file `extraction_engine` via a future additive migration if
  provenance-in-SQLite is desired; (2) optional local OCR for `scanned_pdf_no_text` PDFs; (3) the same
  structured-table treatment could enrich document-card materialization and LlamaIndex/local retrieval
  ranking — all must remain local-first.
