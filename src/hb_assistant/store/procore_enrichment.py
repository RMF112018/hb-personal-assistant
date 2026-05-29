"""Phase 04B cross-endpoint enrichment extractors.

Reusable repository primitives that extract people / company / location entities,
attachment refs, typed custom-field values, relationship edges, action signals,
and text intelligence from normalized Procore records and persist them into the
V7 enrichment tables.

Redaction is enforced here: personal PII (login / name) is reduced to a SHA-256
prefix and never stored raw; attachment + file URLs are reduced to path-only plus
a hash (signed-URL query strings carrying ``company_id`` / ``prostore_file_id`` /
tokens never persist); free text is stored as a hash + length only. Organisation
and place labels (company / vendor / trade / location names) are kept verbatim —
they are not personal PII and operators triage on them — matching the existing
``inspection.py`` / ``punch_item.py`` posture.

All keys / ids are deterministic and every write is a conflict-upsert or
``INSERT OR IGNORE``, so re-extracting the same data records no duplicates
(idempotent; entity ``source_count`` simply increments). Self-contained: no
import from ``hb_assistant.procore`` (store layer independence, mirroring
``procore_history.py``).
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional
from urllib.parse import urlparse

from .connection import get_connection, transaction

# Custom-field data types whose values are safe to preserve verbatim. Everything
# else (string, rich_text, login_information, prostore_files, unknown, ...) is
# reduced to a hash so no free text / PII / signed URL persists.
_PRESERVE_TYPES = {"boolean", "integer", "decimal", "datetime", "lov_entry", "lov_entries"}
_ATTACHMENT_URL_KEYS = ("url", "share_url", "viewable_url", "download_url")


def _open(db_path: Optional[Path]) -> sqlite3.Connection:
    return get_connection(db_path)


def _hash(*parts: Any) -> str:
    return hashlib.sha256("|".join("" if p is None else str(p) for p in parts).encode("utf-8")).hexdigest()[:32]


def _hash12(value: Any) -> Optional[str]:
    if value is None or (isinstance(value, str) and not value):
        return None
    if not isinstance(value, str):
        value = json.dumps(value, default=str, sort_keys=True)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _url_path(value: Any) -> Optional[str]:
    """Return the path component only — never scheme/host/query (drops signed-URL tokens)."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return urlparse(value).path or None
    except ValueError:
        return None


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


_EMAIL_RE = re.compile(r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\s().-]?){7,}\d")
_URL_RE = re.compile(r"https?://\S+")


def _redact_excerpt(text: str, max_chars: int) -> Optional[str]:
    """Mask emails / phones / URLs, collapse whitespace, truncate — a short
    preview that carries no contact PII or signed URLs."""
    if not text:
        return None
    masked = _URL_RE.sub("[url]", text)
    masked = _EMAIL_RE.sub("[email]", masked)
    masked = _PHONE_RE.sub("[phone]", masked)
    masked = re.sub(r"\s+", " ", masked).strip()
    if not masked:
        return None
    return masked[:max_chars]


# ---------------------------------------------------------------------------
# Entity extractors
# ---------------------------------------------------------------------------


def extract_people_refs(
    people: Any, *, now_utc: str, db_path: Optional[Path] = None
) -> List[str]:
    """Upsert person entities from Procore person dicts (``{id, login, name}``).

    PII (login / name) is hashed; names are never stored. Returns the list of
    ``person_entity_key`` values. ``source_count`` increments on re-extraction.
    """
    keys: List[str] = []
    conn = _open(db_path)
    with transaction(conn):
        for person in _as_list(people):
            if not isinstance(person, dict):
                continue
            procore_user_id = person.get("id")
            login_hash = _hash12(person.get("login") or person.get("name"))
            if procore_user_id is None and login_hash is None:
                continue
            key = _hash("person", procore_user_id if procore_user_id is not None else login_hash)
            conn.execute(
                """
                INSERT INTO procore_people_entities (
                  person_entity_key, procore_user_id, login_hash, display_name_redacted,
                  company_name_redacted, first_seen_at_utc, last_seen_at_utc, source_count,
                  raw_body_persisted
                ) VALUES (?, ?, ?, NULL, NULL, ?, ?, 1, 0)
                ON CONFLICT(person_entity_key) DO UPDATE SET
                  last_seen_at_utc = excluded.last_seen_at_utc,
                  source_count = procore_people_entities.source_count + 1,
                  procore_user_id = COALESCE(procore_people_entities.procore_user_id, excluded.procore_user_id),
                  login_hash = COALESCE(procore_people_entities.login_hash, excluded.login_hash)
                """,
                (key, str(procore_user_id) if procore_user_id is not None else None, login_hash, now_utc, now_utc),
            )
            keys.append(key)
    return keys


def _company_id_name(ref: Mapping[str, Any]) -> tuple[Any, Any]:
    company = ref.get("company") if isinstance(ref.get("company"), dict) else {}
    cid = ref.get("id") if ref.get("id") is not None else company.get("id")
    name = ref.get("name") or company.get("name")
    return cid, name


def extract_company_refs(
    companies: Any, *, now_utc: str, db_path: Optional[Path] = None
) -> List[str]:
    """Upsert company entities from vendor / responsible_contractor / company refs.

    Organisation names are kept (not personal PII). Returns ``company_entity_key`` list.
    """
    keys: List[str] = []
    conn = _open(db_path)
    with transaction(conn):
        for ref in _as_list(companies):
            if not isinstance(ref, dict):
                continue
            cid, name = _company_id_name(ref)
            if cid is None and not name:
                continue
            key = _hash("company", cid if cid is not None else _hash12(name))
            conn.execute(
                """
                INSERT INTO procore_company_entities (
                  company_entity_key, procore_company_id, name_redacted,
                  first_seen_at_utc, last_seen_at_utc, source_count
                ) VALUES (?, ?, ?, ?, ?, 1)
                ON CONFLICT(company_entity_key) DO UPDATE SET
                  last_seen_at_utc = excluded.last_seen_at_utc,
                  source_count = procore_company_entities.source_count + 1,
                  procore_company_id = COALESCE(procore_company_entities.procore_company_id, excluded.procore_company_id),
                  name_redacted = COALESCE(procore_company_entities.name_redacted, excluded.name_redacted)
                """,
                (key, str(cid) if cid is not None else None, name, now_utc, now_utc),
            )
            keys.append(key)
    return keys


def extract_location_refs(
    locations: Any, *, project_key: str, now_utc: str, db_path: Optional[Path] = None
) -> List[str]:
    """Upsert location entities from nested location payloads
    (``{id, name, node_name, parent_id}``). Place labels are kept."""
    keys: List[str] = []
    conn = _open(db_path)
    with transaction(conn):
        for loc in _as_list(locations):
            if not isinstance(loc, dict):
                continue
            loc_id = loc.get("id")
            if loc_id is None and not loc.get("name"):
                continue
            key = _hash("location", project_key, loc_id)
            parent_id = loc.get("parent_id")
            conn.execute(
                """
                INSERT INTO procore_location_entities (
                  location_entity_key, project_key, procore_location_id, name_redacted,
                  node_name_redacted, parent_location_id, path_redacted,
                  first_seen_at_utc, last_seen_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(location_entity_key) DO UPDATE SET
                  last_seen_at_utc = excluded.last_seen_at_utc,
                  name_redacted = COALESCE(procore_location_entities.name_redacted, excluded.name_redacted),
                  node_name_redacted = COALESCE(procore_location_entities.node_name_redacted, excluded.node_name_redacted),
                  parent_location_id = COALESCE(procore_location_entities.parent_location_id, excluded.parent_location_id),
                  path_redacted = COALESCE(procore_location_entities.path_redacted, excluded.path_redacted)
                """,
                (
                    key,
                    project_key,
                    str(loc_id) if loc_id is not None else None,
                    loc.get("name"),
                    loc.get("node_name"),
                    str(parent_id) if parent_id is not None else None,
                    loc.get("name"),
                    now_utc,
                    now_utc,
                ),
            )
            keys.append(key)
    return keys


def extract_attachment_refs(
    attachments: Any,
    *,
    project_key: str,
    source_record_key: str,
    source_endpoint_id: str,
    procore_record_id: Optional[str] = None,
    parent_record_key: Optional[str] = None,
    sensitivity: str = "medium",
    now_utc: str,
    db_path: Optional[Path] = None,
) -> List[str]:
    """Upsert attachment refs. Filenames are hashed; the first available URL
    (url/share_url/viewable_url) is reduced to path-only + hash — query strings
    (signed tokens / company_id / prostore_file_id) are never persisted."""
    ids: List[str] = []
    conn = _open(db_path)
    with transaction(conn):
        for att in _as_list(attachments):
            if not isinstance(att, dict):
                continue
            att_id = att.get("id")
            filename_hash = _hash12(att.get("filename") or att.get("name"))
            url_value = next((att.get(k) for k in _ATTACHMENT_URL_KEYS if att.get(k)), None)
            url_hash = _hash12(url_value)
            url_path = _url_path(url_value)
            if att_id is None and filename_hash is None and url_hash is None:
                continue
            ref_id = _hash("attachment", source_record_key, att_id if att_id is not None else (filename_hash or url_hash))
            conn.execute(
                """
                INSERT INTO procore_attachment_refs (
                  attachment_ref_id, project_key, source_record_key, source_endpoint_id,
                  parent_record_key, procore_attachment_id, filename_redacted, filename_hash,
                  url_hash, url_path_redacted, content_type, size_bytes, download_eligibility,
                  sensitivity, first_seen_at_utc, last_seen_at_utc, raw_body_persisted
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, 'metadata_only', ?, ?, ?, 0)
                ON CONFLICT(attachment_ref_id) DO UPDATE SET
                  last_seen_at_utc = excluded.last_seen_at_utc,
                  content_type = COALESCE(procore_attachment_refs.content_type, excluded.content_type),
                  size_bytes = COALESCE(procore_attachment_refs.size_bytes, excluded.size_bytes)
                """,
                (
                    ref_id,
                    project_key,
                    source_record_key,
                    source_endpoint_id,
                    parent_record_key,
                    str(att_id) if att_id is not None else None,
                    filename_hash,
                    url_hash,
                    url_path,
                    att.get("content_type"),
                    att.get("size_bytes") if isinstance(att.get("size_bytes"), int) else att.get("size"),
                    sensitivity,
                    now_utc,
                    now_utc,
                ),
            )
            ids.append(ref_id)
    return ids


def extract_custom_field_values(
    custom_fields: Any,
    *,
    project_key: str,
    record_key: str,
    endpoint_id: str,
    procore_record_id: str,
    now_utc: str,
    db_path: Optional[Path] = None,
) -> List[str]:
    """Persist typed custom-field values. boolean/integer/decimal/datetime/lov_entry/
    lov_entries are preserved verbatim; string/rich_text/login_information/prostore_files/
    unknown are reduced to a hash (no raw value)."""
    ids: List[str] = []
    if not isinstance(custom_fields, dict):
        return ids
    conn = _open(db_path)
    with transaction(conn):
        for cf_key, payload in custom_fields.items():
            if not isinstance(payload, dict):
                continue
            data_type = payload.get("data_type") or "unknown"
            value = payload.get("value")
            value_json: Optional[str] = None
            value_hash: Optional[str] = None
            value_label: Optional[str] = None
            if data_type in _PRESERVE_TYPES:
                if value is not None:
                    value_json = json.dumps(value, default=str, sort_keys=True)
                if data_type == "lov_entry" and isinstance(value, dict):
                    value_label = str(value.get("label"))[:120] if value.get("label") is not None else None
                elif data_type == "lov_entries" and isinstance(value, list):
                    labels = [str(v.get("label")) for v in value if isinstance(v, dict) and v.get("label") is not None]
                    value_label = ", ".join(labels)[:120] if labels else None
            else:
                value_hash = _hash12(value) if value is not None else None
            cfv_id = _hash("cf", record_key, cf_key)
            conn.execute(
                """
                INSERT INTO procore_custom_field_values (
                  custom_field_value_id, project_key, record_key, endpoint_id, procore_record_id,
                  custom_field_key, data_type, value_json_redacted, value_hash, value_label_redacted,
                  updated_at_utc, first_seen_at_utc, last_seen_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(custom_field_value_id) DO UPDATE SET
                  data_type = excluded.data_type,
                  value_json_redacted = excluded.value_json_redacted,
                  value_hash = excluded.value_hash,
                  value_label_redacted = excluded.value_label_redacted,
                  last_seen_at_utc = excluded.last_seen_at_utc
                """,
                (
                    cfv_id,
                    project_key,
                    record_key,
                    endpoint_id,
                    str(procore_record_id),
                    str(cf_key),
                    data_type,
                    value_json,
                    value_hash,
                    value_label,
                    now_utc,
                    now_utc,
                    now_utc,
                ),
            )
            ids.append(cfv_id)
    return ids


# ---------------------------------------------------------------------------
# Edge / signal / text-intelligence emitters
# ---------------------------------------------------------------------------


def emit_record_edge(
    *,
    project_key: str,
    from_record_key: str,
    edge_type: str,
    source_endpoint_id: str,
    to_record_key: Optional[str] = None,
    to_entity_key: Optional[str] = None,
    confidence: float = 1.0,
    metadata: Optional[Mapping[str, Any]] = None,
    now_utc: str,
    db_path: Optional[Path] = None,
) -> str:
    """Upsert a relationship edge (record -> record / record -> entity). Idempotent."""
    edge_id = _hash("edge", project_key, from_record_key, to_record_key, to_entity_key, edge_type)
    conn = _open(db_path)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO procore_record_edges (
              edge_id, project_key, from_record_key, to_record_key, to_entity_key,
              edge_type, source_endpoint_id, confidence, first_seen_at_utc, last_seen_at_utc,
              metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(edge_id) DO UPDATE SET
              last_seen_at_utc = excluded.last_seen_at_utc,
              confidence = excluded.confidence
            """,
            (
                edge_id,
                project_key,
                from_record_key,
                to_record_key,
                to_entity_key,
                edge_type,
                source_endpoint_id,
                float(confidence),
                now_utc,
                now_utc,
                json.dumps(dict(metadata), default=str, sort_keys=True) if metadata else None,
            ),
        )
    return edge_id


def emit_action_signal(
    *,
    project_key: str,
    record_key: str,
    endpoint_id: str,
    signal_type: str,
    title: Optional[str] = None,
    importance: str = "medium",
    signal_status: str = "open",
    due_at_utc: Optional[str] = None,
    owner_entity_key: Optional[str] = None,
    summary: Optional[str] = None,
    reason_codes: Optional[Iterable[str]] = None,
    source_change_event_id: Optional[str] = None,
    metadata: Optional[Mapping[str, Any]] = None,
    now_utc: str,
    db_path: Optional[Path] = None,
) -> str:
    """Upsert an action signal. ``title_redacted`` defaults to ``signal_type``. Idempotent."""
    signal_id = _hash("signal", project_key, record_key, signal_type)
    conn = _open(db_path)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO procore_action_signals (
              action_signal_id, project_key, record_key, endpoint_id, signal_type, signal_status,
              importance, due_at_utc, owner_entity_key, title_redacted, summary_redacted,
              reason_codes_json, first_detected_at_utc, last_seen_at_utc, resolved_at_utc,
              source_change_event_id, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
            ON CONFLICT(action_signal_id) DO UPDATE SET
              last_seen_at_utc = excluded.last_seen_at_utc,
              signal_status = excluded.signal_status,
              importance = excluded.importance
            """,
            (
                signal_id,
                project_key,
                record_key,
                endpoint_id,
                signal_type,
                signal_status,
                importance,
                due_at_utc,
                owner_entity_key,
                title or signal_type,
                summary,
                json.dumps(list(reason_codes), default=str) if reason_codes else None,
                now_utc,
                now_utc,
                source_change_event_id,
                json.dumps(dict(metadata), default=str, sort_keys=True) if metadata else None,
            ),
        )
    return signal_id


def emit_text_intelligence(
    *,
    project_key: str,
    record_key: str,
    endpoint_id: str,
    source_field_path: str,
    text: Any,
    sensitivity: str = "medium",
    review_required: bool = False,
    topics: Optional[Iterable[str]] = None,
    mentioned_records: Optional[Iterable[Any]] = None,
    action_candidates: Optional[Iterable[Any]] = None,
    risk_terms: Optional[Iterable[str]] = None,
    store_encrypted: bool = False,
    excerpt_chars: int = 0,
    now_utc: str,
    db_path: Optional[Path] = None,
) -> Optional[str]:
    """Persist a text-intelligence row for one free-text field.

    Always stores ``text_hash`` + ``text_length`` + caller-derived (non-sensitive)
    topic / mentioned-record / action / risk tokens — never the raw body. When
    ``excerpt_chars > 0`` a short PII-masked excerpt is stored in
    ``excerpt_redacted``; when ``store_encrypted`` the full text is encrypted to
    the vault (outside the repo) and only its reference is stored in
    ``encrypted_full_text_ref``. Idempotent on ``(record_key, source_field_path,
    text_hash)``.
    """
    if text is None or (isinstance(text, str) and not text.strip()):
        return None
    text_str = text if isinstance(text, str) else json.dumps(text, default=str, sort_keys=True)
    text_hash = hashlib.sha256(text_str.encode("utf-8")).hexdigest()[:16]
    ti_id = _hash("ti", record_key, source_field_path, text_hash)

    excerpt_redacted = _redact_excerpt(text_str, excerpt_chars) if excerpt_chars > 0 else None
    encrypted_ref: Optional[str] = None
    if store_encrypted:
        from hb_assistant.security.text_vault import encrypt_text

        encrypted_ref = encrypt_text(text_str)

    def _json_list(values: Optional[Iterable[Any]]) -> Optional[str]:
        if values is None:
            return None
        items = list(values)
        return json.dumps(items, default=str) if items else None

    conn = _open(db_path)
    with transaction(conn):
        conn.execute(
            """
            INSERT OR IGNORE INTO procore_text_intelligence (
              text_intelligence_id, project_key, record_key, endpoint_id, source_field_path,
              text_hash, text_length, excerpt_redacted, topics_json, mentioned_records_json,
              action_candidates_json, risk_terms_json, sensitivity, review_required,
              encrypted_full_text_ref, created_at_utc, raw_body_persisted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                ti_id,
                project_key,
                record_key,
                endpoint_id,
                source_field_path,
                text_hash,
                len(text_str),
                excerpt_redacted,
                _json_list(topics),
                _json_list(mentioned_records),
                _json_list(action_candidates),
                _json_list(risk_terms),
                sensitivity,
                1 if review_required else 0,
                encrypted_ref,
                now_utc,
            ),
        )
    return ti_id


def get_procore_action_signals(
    *,
    project_key: str,
    signal_status: Optional[str] = None,
    endpoint_id: Optional[str] = None,
    importance: Optional[str] = None,
    signal_type: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Read action signals for a project (optionally filtered by status / endpoint
    / importance / signal type). High-importance, most-recent first."""
    clauses = ["project_key = ?"]
    params: List[Any] = [project_key]
    for column, value in (
        ("signal_status", signal_status),
        ("endpoint_id", endpoint_id),
        ("importance", importance),
        ("signal_type", signal_type),
    ):
        if value is not None:
            clauses.append(f"{column} = ?")
            params.append(value)
    conn = _open(db_path)
    rows = conn.execute(
        f"""
        SELECT action_signal_id, project_key, record_key, endpoint_id, signal_type,
               signal_status, importance, due_at_utc, owner_entity_key, title_redacted,
               summary_redacted, reason_codes_json, first_detected_at_utc, last_seen_at_utc,
               resolved_at_utc, metadata_json
          FROM procore_action_signals
         WHERE {" AND ".join(clauses)}
         ORDER BY
           CASE importance WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END ASC,
           first_detected_at_utc DESC, action_signal_id ASC
        """,
        params,
    ).fetchall()
    return [{k: row[k] for k in row.keys()} for row in rows]


def get_procore_text_intelligence(
    *,
    project_key: str,
    endpoint_id: Optional[str] = None,
    with_action_candidates: bool = False,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Read text-intelligence rows for a project (optionally one endpoint, and/or
    only rows that carry action candidates). Most-recent first."""
    clauses = ["project_key = ?"]
    params: List[Any] = [project_key]
    if endpoint_id is not None:
        clauses.append("endpoint_id = ?")
        params.append(endpoint_id)
    if with_action_candidates:
        clauses.append("action_candidates_json IS NOT NULL AND action_candidates_json != ''")
    conn = _open(db_path)
    rows = conn.execute(
        f"""
        SELECT text_intelligence_id, project_key, record_key, endpoint_id, source_field_path,
               text_hash, text_length, excerpt_redacted, topics_json, mentioned_records_json,
               action_candidates_json, risk_terms_json, sensitivity, review_required,
               created_at_utc
          FROM procore_text_intelligence
         WHERE {" AND ".join(clauses)}
         ORDER BY created_at_utc DESC, text_intelligence_id ASC
        """,
        params,
    ).fetchall()
    return [{k: row[k] for k in row.keys()} for row in rows]


__all__ = [
    "emit_action_signal",
    "emit_record_edge",
    "emit_text_intelligence",
    "extract_attachment_refs",
    "extract_company_refs",
    "extract_custom_field_values",
    "extract_location_refs",
    "extract_people_refs",
    "get_procore_action_signals",
    "get_procore_text_intelligence",
]
