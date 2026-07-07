# 07 — Budget & Truncation

`PacketBudget` dataclass (`research_packet_models.py`): max_items, max_chars, max_chars_per_item,
max_citations, max_citations_per_item, max_trusted, max_candidates, max_open_questions, plus include-flags
(include_candidates / include_deferred / include_stale / include_excluded_manifest / include_evidence /
include_metadata). `.clamped()` / `.to_dict()` / `.from_dict()` / `.for_type()`.

## Deterministic truncation
Budget is applied in a stable order (answer-role rank → confidence desc → target). Caps enforced:
max_items, max_trusted, max_candidates, max_open_questions, max_chars, max_chars_per_item, max_citations,
max_citations_per_item. When a cap drops items the header `truncated` flag is set and the receipt records
`dropped_count`.

## Excluded items minimized
Items that don't make the trusted/candidate cut are minimized to `None` summary/evidence but keep
ids / state / digest / exclusion_reason — enough for an auditable "why excluded" manifest without carrying
content.

Proof: `test_research_packet_builder.py` asserts max_items / max_chars / max_chars_per_item / max_citations /
max_citations_per_item / max_trusted / max_candidates and the excluded-minimized invariant. All pass.
