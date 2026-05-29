"""Phase 05 shared financial projection primitives.

The store-layer bridge the per-endpoint financial projections (Prompts 04-09)
and the live-sync dispatch (Prompt 10) reuse. This module only provides the
**shared** primitives:

- ``emit_amount_facts`` — the generic amount-fact emitter. Loops a list of
  normalizer-built fact dicts into ``procore_financials.emit_financial_amount_fact``
  (deterministic id -> idempotent; amount values stored verbatim as decimal-safe
  TEXT).
- ``link_record_entities`` — hashes person refs (PII never stored) and preserves
  company / vendor labels (organisation metadata), emitting relationship edges,
  by reusing the Phase 04B enrichment primitives.

Per-endpoint ``project_*`` functions are added by later prompts. Self-contained
store module — no ``hb_assistant.procore`` import (mirrors the sibling
``procore_*_projection.py`` modules).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .procore_enrichment import emit_record_edge, extract_company_refs, extract_people_refs
from .procore_financials import emit_financial_amount_fact


def emit_amount_facts(
    *,
    project_key: str,
    record_key: str,
    endpoint_id: str,
    facts: List[Mapping[str, Any]],
    created_at_utc: str,
    currency_iso_code: Optional[str] = None,
    base_currency_iso_code: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[str]:
    """Persist normalizer-built amount facts. Returns the amount_fact_id list.

    Each fact must carry ``amount_name``, ``amount_value`` (decimal-safe string)
    and ``source_field_path``; optional ``period_start`` / ``period_end`` /
    ``wbs_code_id`` / ``cost_code_id`` are passed through. Idempotent: the
    underlying id is deterministic, so re-emitting the same fact is a no-op.
    """
    ids: List[str] = []
    for fact in facts:
        amount_value = fact.get("amount_value")
        amount_name = fact.get("amount_name")
        if amount_value is None or not amount_name:
            continue
        ids.append(
            emit_financial_amount_fact(
                project_key=project_key,
                record_key=record_key,
                endpoint_id=endpoint_id,
                amount_name=amount_name,
                amount_value=amount_value,
                source_field_path=fact.get("source_field_path") or amount_name,
                created_at_utc=created_at_utc,
                currency_iso_code=fact.get("currency_iso_code") or currency_iso_code,
                base_currency_iso_code=(
                    fact.get("base_currency_iso_code") or base_currency_iso_code
                ),
                period_start=fact.get("period_start"),
                period_end=fact.get("period_end"),
                wbs_code_id=fact.get("wbs_code_id"),
                cost_code_id=fact.get("cost_code_id"),
                db_path=db_path,
            )
        )
    return ids


def link_record_entities(
    *,
    project_key: str,
    record_key: str,
    endpoint_id: str,
    people: Optional[Mapping[str, Any]] = None,
    companies: Optional[Mapping[str, Any]] = None,
    now_utc: str,
    db_path: Optional[Path] = None,
) -> Dict[str, List[str]]:
    """Hash person refs + preserve company labels, emitting relationship edges.

    ``people`` / ``companies`` map an edge-type -> a Procore person/company ref
    (or list of refs). People are hashed via ``extract_people_refs`` (PII never
    stored); company / vendor labels are kept via ``extract_company_refs``.
    Returns the entity keys linked per edge type.
    """
    linked: Dict[str, List[str]] = {}
    for edge_type, refs in (people or {}).items():
        keys = extract_people_refs(refs, now_utc=now_utc, db_path=db_path)
        for key in keys:
            emit_record_edge(
                project_key=project_key,
                from_record_key=record_key,
                edge_type=edge_type,
                source_endpoint_id=endpoint_id,
                to_entity_key=key,
                now_utc=now_utc,
                db_path=db_path,
            )
        if keys:
            linked[edge_type] = keys
    for edge_type, refs in (companies or {}).items():
        keys = extract_company_refs(refs, now_utc=now_utc, db_path=db_path)
        for key in keys:
            emit_record_edge(
                project_key=project_key,
                from_record_key=record_key,
                edge_type=edge_type,
                source_endpoint_id=endpoint_id,
                to_entity_key=key,
                now_utc=now_utc,
                db_path=db_path,
            )
        if keys:
            linked[edge_type] = keys
    return linked


__all__ = [
    "emit_amount_facts",
    "link_record_entities",
]
