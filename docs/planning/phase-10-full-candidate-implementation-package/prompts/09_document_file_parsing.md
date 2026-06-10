# Prompt 09 — Document / File Parsing

## Objective

Implement a safe, local-first document/file parsing candidate for Phase 10.

The prior audit found this area lower-ROI and possibly data-blocked, but this package now directs implementation of the safest viable slice.

The candidate must parse or index file contents using local tooling only, produce review-safe read models, and generate final output evidence using synthetic or sanitized fixture files if live file corpus is absent.

## Required repo-truth audit before implementation

Inspect:

- file/source tables
- SharePoint/Drive source refresh paths
- any document extraction or file review modules
- existing file metadata tables
- daily-brief/file review consumers
- tests/evidence for file parsing
- local dependencies already present for PDF/DOCX/XLSX parsing

Record findings in:

```text
docs/evidence/phase-10-full-candidate-implementation/09-document-file-parsing/00-repo-truth-audit.md
```

## Implementation requirements

1. Select the safest viable local parsing slice.

   Prefer deterministic metadata/text extraction over model interpretation.

   Support only formats that can be handled safely with existing or lightweight local dependencies. Likely candidates:

   - `.txt`
   - `.md`
   - `.pdf` if local parser exists or acceptable dependency is already present
   - `.docx` if local parser exists or acceptable dependency is already present
   - `.xlsx` if local parser exists or acceptable dependency is already present

2. Avoid raw-content leakage.

   Do not commit extracted live document text. Evidence should use synthetic fixture documents or sanitized snippets.

3. Provide a review-safe file parsing/read-model output.

   Output should include:

   - file/source ID
   - file name or sanitized title
   - extension/MIME type
   - parsed status
   - extraction method
   - text length/hash
   - section/table counts if applicable
   - error/degraded reason
   - source refs
   - redaction/safety flags

4. Integrate with daily brief or file review only if safe.

   Do not present unreviewed document interpretation as fact.

5. Add local-model classification only if repository routing and safety gates already support it.

   If implemented, it must be advisory, source-linked, local-only, and fail-closed.

## Required final output evidence

Generate in:

```text
docs/evidence/phase-10-full-candidate-implementation/09-document-file-parsing/
```

Required files:

- `README.md`
- `00-repo-truth-audit.md`
- `fixtures/README.md`
- `01-file-parse-final-output.md`
- `02-file-parse-final-output.json`
- `03-pdf-or-supported-format-proof.json`
- `04-docx-or-supported-format-proof.json`
- `05-xlsx-or-supported-format-proof.json`
- `06-unsupported-format-proof.json`
- `07-daily-brief-or-file-review-consumption-proof.md`
- `08-no-raw-live-content-proof.txt`
- `09-safety-scan-results.txt`
- `10-production-db-unchanged-proof.txt`
- `validation-commands.txt`
- `validation-results.md`
- `final-output-manifest.md`
- `changed-files.txt`
- `branch-state.txt`

If a listed format is unsupported by repo truth, create the proof file explaining the unsupported status and showing the graceful degraded output. Do not force risky dependency additions.

## Validation

At minimum:

```bash
python -m compileall src tests
pytest -q tests -k "file or document or parse or extract or sharepoint or drive"
```

Run lint/type checks on changed files.

## Commit

Suggested commit:

```text
feat(second-brain): add phase 10 local document parsing
```

After committing, wait exactly 10 minutes before Prompt 10:

```bash
sleep 600
```
