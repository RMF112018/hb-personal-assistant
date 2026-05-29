"""Shared entity / edge / action-signal projection for Procore normalizers.

Phase 04B daily-log enrichment projects each record's people, companies,
locations, attachments, custom-fields and segment references into a small
PII-safe ``entities`` block, derives relationship ``edges`` between the
record and those entities, and collects short ``action_signals`` strings.

All PII is reduced via the shared :mod:`hashing` primitives: person refs
become ``{role, hash_prefix, id?}`` (never name/email/phone), attachment
URLs are stripped to path-only (no query strings carrying company_id /
prostore_file_id / signed tokens), and free-text custom-field values are
hashed. Company / location / trade names are organisation or place labels,
not personal PII, so they are kept verbatim for operator triage — matching
the existing posture in ``inspection.py`` / ``punch_item.py``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .hashing import hash_identifier, hash_summary

_ATTACHMENT_URL_KEYS = ("url", "share_url", "viewable_url", "thumbnail_url")


def redact_url_to_path(value: Any) -> Optional[str]:
    """Strip scheme + host + query from a URL, returning the path only."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = urlparse(value)
    except ValueError:
        return None
    return parsed.path or None


def _person_hash_input(obj: Dict[str, Any]) -> Any:
    """Prefer login (email), then email, then name — so the same person
    hashes consistently across endpoints that carry different PII keys."""
    for key in ("login", "email", "name"):
        value = obj.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def person_entity(obj: Any, role: str) -> Optional[Dict[str, Any]]:
    """Reduce a Procore person object to ``{role, hash_prefix, id?}``."""
    if not isinstance(obj, dict):
        return None
    hash_prefix = hash_identifier(_person_hash_input(obj))
    if hash_prefix is None:
        return None
    entity: Dict[str, Any] = {"role": role, "hash_prefix": hash_prefix}
    pid = obj.get("id")
    if isinstance(pid, int):
        entity["id"] = pid
    return entity


def person_entity_from_name(name: Any, role: str) -> Optional[Dict[str, Any]]:
    """Reduce a bare person-name string (e.g. inspector_name) to a hashed entity."""
    hash_prefix = hash_identifier(name) if isinstance(name, str) and name else None
    if hash_prefix is None:
        return None
    return {"role": role, "hash_prefix": hash_prefix}


def company_entity(obj: Any, kind: str) -> Optional[Dict[str, Any]]:
    """Reduce a vendor / trade / cost_code object to ``{kind, id?, name?}``."""
    if not isinstance(obj, dict):
        return None
    entity: Dict[str, Any] = {"kind": kind}
    if isinstance(obj.get("id"), int):
        entity["id"] = obj["id"]
    if isinstance(obj.get("name"), str) and obj["name"]:
        entity["name"] = obj["name"]
    return entity if len(entity) > 1 else None


def company_entity_from_name(name: Any, kind: str) -> Optional[Dict[str, Any]]:
    """Reduce a bare org-name string (e.g. issued_to / involved_company)."""
    if not isinstance(name, str) or not name:
        return None
    return {"kind": kind, "name": name}


def location_entity(obj: Any) -> Optional[Dict[str, Any]]:
    """Keep the structural location reference (place labels, not PII)."""
    if not isinstance(obj, dict):
        return None
    out: Dict[str, Any] = {}
    for key in ("id", "name", "node_name", "parent_id"):
        value = obj.get(key)
        if value is not None:
            out[key] = value
    return out or None


def segment_entity(obj: Any) -> Optional[Dict[str, Any]]:
    """Reduce a daily_log_segment: keep id/name/deleted, hash the description."""
    if not isinstance(obj, dict):
        return None
    out: Dict[str, Any] = {}
    for key in ("id", "name", "deleted", "deleted_at"):
        value = obj.get(key)
        if value is not None:
            out[key] = value
    description_summary = hash_summary(obj.get("description"))
    if description_summary is not None:
        out["description_summary"] = description_summary
    return out or None


def attachment_entities(values: Any) -> Dict[str, Any]:
    """Reduce attachments[]: id + hashed filename + path-only URLs + content_type."""
    items: List[Dict[str, Any]] = []
    if isinstance(values, list):
        for att in values:
            if not isinstance(att, dict):
                continue
            entry: Dict[str, Any] = {}
            if isinstance(att.get("id"), int):
                entry["id"] = att["id"]
            filename_summary = hash_summary(att.get("filename") or att.get("name"))
            if filename_summary is not None:
                entry["filename_summary"] = filename_summary
            for url_key in _ATTACHMENT_URL_KEYS:
                path = redact_url_to_path(att.get(url_key))
                if path is not None:
                    entry[f"{url_key}_path"] = path
            for key in ("content_type", "viewable_type", "viewable_document_id"):
                value = att.get(key)
                if value is not None:
                    entry[key] = value
            items.append(entry)
    return {"count": len(items), "items": items}


def custom_field_entities(raw_custom_fields: Any) -> Dict[str, Any]:
    """Reduce custom_fields per the established policy: string values hashed;
    decimal / boolean / lov_entry(/entries) preserved verbatim; unknown hashed."""
    if not isinstance(raw_custom_fields, dict):
        return {"count": 0, "fields": {}}
    fields: Dict[str, Any] = {}
    for key, payload in raw_custom_fields.items():
        if not isinstance(payload, dict):
            continue
        data_type = payload.get("data_type")
        value = payload.get("value")
        entry: Dict[str, Any] = {"data_type": data_type}
        if data_type in {"decimal", "boolean", "lov_entry", "lov_entries"}:
            if value is not None:
                entry["value"] = value
        else:
            summary = hash_summary(value if data_type == "string" else str(value))
            if value is not None and summary is not None:
                entry["value_summary"] = summary
        fields[key] = entry
    return {"count": len(fields), "fields": fields}


class EntityBuilder:
    """Accumulates the entities of one record and derives relationship edges."""

    def __init__(self) -> None:
        self._people: List[Dict[str, Any]] = []
        self._companies: List[Dict[str, Any]] = []
        self._location: Optional[Dict[str, Any]] = None
        self._segment: Optional[Dict[str, Any]] = None
        self._attachments: Optional[Dict[str, Any]] = None
        self._custom_fields: Optional[Dict[str, Any]] = None
        self._signals: List[str] = []

    def add_person(self, obj: Any, role: str) -> "EntityBuilder":
        entity = person_entity(obj, role)
        if entity is not None:
            self._people.append(entity)
        return self

    def add_person_name(self, name: Any, role: str) -> "EntityBuilder":
        entity = person_entity_from_name(name, role)
        if entity is not None:
            self._people.append(entity)
        return self

    def add_company(self, obj: Any, kind: str) -> "EntityBuilder":
        entity = company_entity(obj, kind)
        if entity is not None:
            self._companies.append(entity)
        return self

    def add_company_name(self, name: Any, kind: str) -> "EntityBuilder":
        entity = company_entity_from_name(name, kind)
        if entity is not None:
            self._companies.append(entity)
        return self

    def set_location(self, obj: Any) -> "EntityBuilder":
        self._location = location_entity(obj)
        return self

    def set_segment(self, obj: Any) -> "EntityBuilder":
        self._segment = segment_entity(obj)
        return self

    def set_attachments(self, values: Any) -> "EntityBuilder":
        summary = attachment_entities(values)
        if summary["count"] > 0:
            self._attachments = summary
        return self

    def set_custom_fields(self, values: Any) -> "EntityBuilder":
        summary = custom_field_entities(values)
        if summary["count"] > 0:
            self._custom_fields = summary
        return self

    def add_signal(self, signal: Optional[str]) -> "EntityBuilder":
        if signal:
            self._signals.append(signal)
        return self

    def build(self) -> Dict[str, Any]:
        """Return ``{entities, edges, action_signals}`` for canonical_fields."""
        entities: Dict[str, Any] = {}
        edges: List[Dict[str, Any]] = []

        if self._people:
            entities["people"] = self._people
            for person in self._people:
                edges.append(
                    {"rel": person["role"], "to_type": "person", "to_ref": person["hash_prefix"]}
                )
        if self._companies:
            entities["companies"] = self._companies
            for company in self._companies:
                ref = company.get("id")
                edges.append(
                    {
                        "rel": company["kind"],
                        "to_type": "company",
                        "to_ref": ref if ref is not None else hash_identifier(company.get("name")),
                    }
                )
        if self._location is not None:
            entities["location"] = self._location
            if self._location.get("id") is not None:
                edges.append(
                    {"rel": "at_location", "to_type": "location", "to_ref": self._location["id"]}
                )
        if self._segment is not None:
            entities["segment"] = self._segment
            if self._segment.get("id") is not None:
                edges.append(
                    {"rel": "in_segment", "to_type": "segment", "to_ref": self._segment["id"]}
                )
        if self._attachments is not None:
            entities["attachments"] = self._attachments
            for att in self._attachments["items"]:
                if att.get("id") is not None:
                    edges.append(
                        {"rel": "has_attachment", "to_type": "attachment", "to_ref": att["id"]}
                    )
        if self._custom_fields is not None:
            entities["custom_fields"] = self._custom_fields

        return {"entities": entities, "edges": edges, "action_signals": list(self._signals)}


__all__ = [
    "redact_url_to_path",
    "person_entity",
    "person_entity_from_name",
    "company_entity",
    "company_entity_from_name",
    "location_entity",
    "segment_entity",
    "attachment_entities",
    "custom_field_entities",
    "EntityBuilder",
]
