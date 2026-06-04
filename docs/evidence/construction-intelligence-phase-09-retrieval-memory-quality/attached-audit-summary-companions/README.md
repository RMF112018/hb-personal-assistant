# Attached-Audit Summary Companions (Gap G-11)

**Gap:** G-11 — *"Large evidence files were too large for prior connector fetch; summarized companions needed."*
**Resolution:** compact, inspectable summary companions for the oversized field-profile / completeness
evidence files in the attached Phase 08D agent data-quality evaluation packet.

The **originals are not modified** (the historical 08D packet is immutable); each companion below carries
the original's byte size, line count, and **SHA-256** so the summary is verifiably tied to its source.
Companions contain **counts and structure only** — no per-field or per-row dumps, no raw content.

Originals live in: `docs/evidence/construction-intelligence-phase-08d-agent-data-quality-evaluation/`

| Companion | Original (`…json`) | Original size | Companion size | Headline |
|---|---|---|---|---|
| `01-sqlite-structure-inventory.summary.json` | `01-sqlite-structure-inventory.json` | 149,258 B / 4,971 lines | 6,594 B | 165 tables, 375,853 total rows, 75 empty tables, 25 high-row tables, schema V37 |
| `02-sqlite-field-profile.summary.json` | `02-sqlite-field-profile.json` | 4,528,050 B / 118,213 lines | 979 B | 2,761 fields profiled across 165 tables; 648 raw-content-risk fields flagged |
| `06-data-completeness-freshness-shape.summary.json` | `06-data-completeness-freshness-shape.json` | 1,738,702 B / 49,947 lines | 1,051 B | 2,761 field usefulness indicators; 75 operationally-unused tables; row counts for 165 tables |
| `08-financial-data-structure-quality-evidence.summary.json` | `08-financial-data-structure-quality-evidence.json` | 337,687 B / 9,669 lines | 1,061 B | 502 financial field indicators across 24 financial tables (169,401 rows); no determinations made |
| `12-data-dictionary-and-evaluator-index.summary.json` | `12-data-dictionary-and-evaluator-index.json` | 476,683 B / 18,327 lines | 1,300 B | 2,761-field dictionary, 165-table dictionary, 9-evaluator use map, 15 source families |

Each `*.summary.json` records: `companion_for`, `original_files` (bytes / lines / sha256 for both `.json`
and `.md`), and a `headline` block (top-level scalars verbatim; arrays/dicts reduced to `{_type,_len}`).

Referenced from: `../02-agent-data-quality-gap-preflight-remediation.md` (and the Phase 09 closeout).
