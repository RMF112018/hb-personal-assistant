# RT-03–RT-06 — Audit disposition (PR-16..PR-20)

**Date:** 2026-07-11  
**Wave:** PR-16..PR-20 on top of PR-15 closeout (`01b9b00b` / `20e39150`)

## Summary

| Finding | Severity | Corpus row(s) | PR | Post-fix enforcement |
|---------|----------|---------------|-----|-------------------|
| RT-02 | High (doc) | n/a | PR-20 | Closed — dual-DB lineage doc |
| RT-03 | Medium | `audit_row_29` | PR-16 | **required** — `query` asserted |
| RT-04 | Low–Medium | `audit_row_22` | PR-17 | **required** — `plan_canonical_promotion` |
| RT-05 | Low–Medium | `audit_row_40` | PR-18 | **required** — staging authorized |
| RT-06 | Low | `audit_row_06`, `11`, `35` | PR-19 | **required** — paraphrase routing |
| §12 workflow layers | Doc | n/a | PR-20 | Documented in architecture docs |
| §13 verification | Evidence | n/a | PR-20 | `scripts/verify-routing-remediation-claims.sh` |

## Corpus enforcement (post-wave)

```text
required_count=47
accepted_partial_count=3
accepted_partial rows: 3, 4, 19 (explain/advisory education — intentional debt)
```

## Per-finding detail

### RT-03 — Topical open-loop query

- **Prompt:** “Which open loops relate to the NAS deployment?”
- **Fix:** `_extract_topic_query` + `_extract_search_query` equivalence for `relate to` / `relevant files`
- **CI gap closed:** `arguments_include.query` on row 29

### RT-04 — Hypothetical promotion

- **Prompt:** “What would happen if I promoted this?”
- **Fix:** `_MODALITY_HYPOTHETICAL` + `_prefer_hypothetical_promotion_plan` → `plan_canonical_promotion`
- **Broker parity:** advisory plan executable without pre-extracted `proposal_bundle_id`

### RT-05 — Create proposal staging

- **Prompt:** “Create a proposal but do not promote it.”
- **Fix:** `create a proposal` stage capability tokens + `stage_artifact_proposals` triggers
- **Expectation:** `staging_authorized=true`, `currently_executable=false` (`missing_arguments`)

### RT-06 — Read-only paraphrases

| Row | Prompt | Route |
|-----|--------|-------|
| 6 | Do not stage; only summarize | `context_preflight`, advisory modality |
| 11 | Do not modify files; which files relevant | `source_file_search` + `query=relevant files` |
| 35 | Find references to ID in notes | `vault_note_search` (structured ID disambiguation) |

## Validation gates

```bash
scripts/test-prompt-routing-audit.sh
bash scripts/verify-routing-remediation-claims.sh
```

Live NAS replay after image rebuild: update `04-live-50-prompt-corpus.sh` required gate to **47**.