"""Phase 05 shared financial normalization + redaction utilities.

The single toolkit the per-endpoint financial normalizers (Prompts 04-09) and
the live-sync dispatch reuse. Posture (Phase 04B carried forward):

- **Money / quantities / rates** are preserved as decimal-safe **strings** —
  ``parse_amount`` never coerces through ``float``/``Decimal`` in a way that
  drops trailing zeros or sign, so source precision survives for aggregation
  and comparison.
- **Currency config, WBS / cost-code identifiers and labels** are structural
  business facts and are kept.
- **Person PII** (name / login / email) is hashed (``person_hash_summary`` /
  ``hash_identifier``); **company / vendor / trade labels** are organisation
  metadata and are kept verbatim (``company_entity``).
- **Free text / HTML** (descriptions, notes) never persists raw — it is reduced
  to a ``{hash_prefix, length, excerpt}`` summary with the excerpt PII-masked.
- **Attachment URLs** are reduced to path-only (no scheme/host/query, so signed
  URL tokens never persist).

This module is pure (no DB / no I/O). It re-exposes the shared
``hashing`` / ``entities`` primitives so callers have one import.
"""

from __future__ import annotations

import html
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .entities import (
    attachment_entities,
    company_entity,
    company_entity_from_name,
    custom_field_entities,
    redact_url_to_path,
)
from .hashing import hash_identifier, hash_summary, person_hash_summary

_EMAIL_RE = re.compile(r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\s().-]?){7,}\d")
_URL_RE = re.compile(r"https?://\S+")
_TAG_RE = re.compile(r"<[^>]+>")
# Secret-shaped tokens must never survive even in a masked excerpt (Phase 04B /
# Prompt 10 no-secret posture): Bearer/OAuth tokens and PEM key blocks.
_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._\-+/=]+", re.IGNORECASE)
_PEM_RE = re.compile(r"-----BEGIN[^\n]*")


def parse_amount(value: Any) -> Optional[str]:
    """Return a decimal-safe string for a money/quantity/rate value.

    Source strings are preserved verbatim (trimmed) so precision, trailing
    zeros and sign survive; ints stringify exactly; a float (which JSON parsing
    may already have produced) uses its shortest round-trip repr — no precision
    is invented. ``None`` / ``bool`` / non-numeric containers return ``None``.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    return None


def extract_currency_config(raw: Any) -> Dict[str, Any]:
    """Pull currency metadata (iso code, base iso code, exchange rate).

    Handles a nested ``currency_configuration`` block and top-level fields.
    The exchange rate is run through ``parse_amount`` (decimal-safe). Missing
    keys are omitted.
    """
    if not isinstance(raw, dict):
        return {}
    nested = raw.get("currency_configuration")
    src: Mapping[str, Any] = nested if isinstance(nested, dict) else raw
    out: Dict[str, Any] = {}
    iso = src.get("currency_iso_code") or src.get("currency") or raw.get("currency_iso_code")
    if isinstance(iso, str) and iso:
        out["currency_iso_code"] = iso
    base = src.get("base_currency_iso_code") or raw.get("base_currency_iso_code")
    if isinstance(base, str) and base:
        out["base_currency_iso_code"] = base
    rate = parse_amount(
        src.get("currency_exchange_rate")
        if src.get("currency_exchange_rate") is not None
        else src.get("exchange_rate")
    )
    if rate is not None:
        out["currency_exchange_rate"] = rate
    return out


def extract_wbs_cost_code(obj: Any) -> Dict[str, Any]:
    """Extract WBS / cost-code / line-item-type / tax-code identifiers + labels.

    Codes and descriptions are business labels (not PII) and are kept. The WBS
    description is a label; the financial repository stores it in a
    ``wbs_description_redacted`` column that excerpt-masks any contact info.
    """
    if not isinstance(obj, dict):
        return {}
    out: Dict[str, Any] = {}
    wbs = obj.get("wbs_code")
    if isinstance(wbs, dict):
        if wbs.get("id") is not None:
            out["wbs_code_id"] = str(wbs["id"])
        if isinstance(wbs.get("flat_code"), str) and wbs["flat_code"]:
            out["wbs_flat_code"] = wbs["flat_code"]
        if isinstance(wbs.get("description"), str) and wbs["description"]:
            out["wbs_description"] = wbs["description"]
    for code_key, dict_key, scalar_key in (
        ("cost_code_id", "cost_code", "cost_code_id"),
        ("line_item_type_id", "line_item_type", "line_item_type_id"),
        ("tax_code_id", "tax_code", "tax_code_id"),
    ):
        nested = obj.get(dict_key)
        if isinstance(nested, dict) and nested.get("id") is not None:
            out[code_key] = str(nested["id"])
        elif obj.get(scalar_key) is not None:
            out[code_key] = str(obj[scalar_key])
    return out


def mask_excerpt(text: Any, max_chars: int = 200) -> Optional[str]:
    """Mask emails / phones / URLs, collapse whitespace, truncate.

    A short preview that carries no contact PII or signed URLs.
    """
    if text is None:
        return None
    value = text if isinstance(text, str) else str(text)
    if not value:
        return None
    masked = _PEM_RE.sub("[pem]", value)
    masked = _BEARER_RE.sub("[token]", masked)
    masked = _URL_RE.sub("[url]", masked)
    masked = _EMAIL_RE.sub("[email]", masked)
    masked = _PHONE_RE.sub("[phone]", masked)
    masked = re.sub(r"\s+", " ", masked).strip()
    if not masked:
        return None
    return masked[:max_chars]


def html_to_text(value: Any) -> str:
    """Strip HTML tags + unescape entities + collapse whitespace. Never the raw body."""
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def summarize_text(value: Any, max_excerpt: int = 120) -> Optional[Dict[str, Any]]:
    """HTML-to-text summary: ``{type, length, hash_prefix, excerpt}``.

    The raw text / HTML never persists — only a SHA-256 prefix, the text length,
    and a PII-masked excerpt.
    """
    text = html_to_text(value)
    summary = hash_summary(text) if text else None
    if summary is None:
        return None
    excerpt = mask_excerpt(text, max_excerpt)
    if excerpt:
        return {**summary, "excerpt": excerpt}
    return summary


def attachment_path(url: Any) -> Optional[str]:
    """Path-only URL (drops scheme/host/query, so signed-URL tokens never persist)."""
    return redact_url_to_path(url)


def custom_field_policy(raw_custom_fields: Any) -> Dict[str, Any]:
    """Phase 04B custom-field policy: decimal/boolean/lov preserved; strings hashed."""
    return custom_field_entities(raw_custom_fields)


def change_event_line_item_summary(raw: Any) -> Optional[Dict[str, Any]]:
    """Redacted summary of a line item's ``change_event_line_item`` linkage.

    Shared across the contract / change-order line-item normalizers (prime,
    commitment, purchase-order). Identifiers are kept (change-event line-item id,
    change-event id, change-event number — business labels, not PII) and WBS /
    cost-code metadata is preserved; the change-event title and the line-item
    description are free text and are reduced to hash-only summaries. Returns
    ``None`` when the payload carries no ``change_event_line_item`` block.
    """
    if not isinstance(raw, dict):
        return None
    cel = raw.get("change_event_line_item")
    if not isinstance(cel, dict):
        return None
    out: Dict[str, Any] = {}
    if cel.get("id") is not None:
        out["change_event_line_item_id"] = str(cel["id"])
    event = cel.get("event")
    if isinstance(event, dict) and event.get("id") is not None:
        out["change_event_id"] = str(event["id"])
    elif cel.get("event_id") is not None:
        out["change_event_id"] = str(cel["event_id"])
    if isinstance(event, dict) and event.get("number") is not None:
        out["change_event_number"] = event["number"]
    title_summary = hash_summary(event.get("title")) if isinstance(event, dict) else None
    if title_summary is not None:
        out["change_event_title_summary"] = title_summary
    description_summary = hash_summary(cel.get("description"))
    if description_summary is not None:
        out["description_summary"] = description_summary
    out.update(extract_wbs_cost_code(cel))
    return out


def build_amount_facts(
    canonical: Mapping[str, Any],
    *,
    amount_columns: Iterable[str],
    source_table: str,
) -> List[Dict[str, Any]]:
    """Generic amount-fact builder.

    For each present amount column produce a fact dict
    ``{amount_name, amount_value, source_field_path}`` (value via
    ``parse_amount`` so it stays decimal-safe). The amount_name follows the
    column / Procore field name. Absent / None amounts are skipped.
    """
    facts: List[Dict[str, Any]] = []
    for column in amount_columns:
        value = parse_amount(canonical.get(column))
        if value is None:
            continue
        facts.append(
            {
                "amount_name": column,
                "amount_value": value,
                "source_field_path": f"{source_table}.{column}",
            }
        )
    return facts


__all__ = [
    # financial-specific utilities
    "parse_amount",
    "extract_currency_config",
    "extract_wbs_cost_code",
    "mask_excerpt",
    "html_to_text",
    "summarize_text",
    "attachment_path",
    "custom_field_policy",
    "change_event_line_item_summary",
    "build_amount_facts",
    # re-exposed shared primitives (people PII hashed; company labels preserved;
    # attachments path-only)
    "person_hash_summary",
    "hash_identifier",
    "hash_summary",
    "company_entity",
    "company_entity_from_name",
    "attachment_entities",
    "custom_field_entities",
    "redact_url_to_path",
]
