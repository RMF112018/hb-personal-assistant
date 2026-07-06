"""Sole reader/writer of the V100 claim tables (N8C-4).

Writes only to ``assistant_claims`` / ``assistant_claim_events`` (never a source/import table).
Enforces, before touching the DB, the invariants the schema also backstops: a claim must be
source-backed, evidence is present + bounded, confidence is a probability, and enum fields are valid.
Re-extraction is idempotent (deterministic ``claim_id`` → upsert). Read helpers are bounded.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.store.connection import borrow_connection, transaction

from .claim_models import (
    CLAIM_EXTRACTED_BY,
    CLAIM_REVIEW_STATES,
    CLAIM_STATUSES,
    CLAIM_TYPES,
    STATUS_CANDIDATE,
    STATUS_STALE,
    ClaimCandidate,
    ClaimValidationError,
    bound_evidence,
    clamp_confidence,
    compute_claim_id,
)

_MAX_LIMIT = 200
_DEFAULT_LIMIT = 50

_COLUMNS = (
    "claim_id", "claim_type", "claim_text", "normalized_subject", "normalized_predicate",
    "normalized_object", "source_id", "card_id", "note_rel_path", "source_kind", "source_root_key",
    "source_rel_path", "evidence_excerpt", "evidence_location", "source_state", "confidence",
    "status", "review_state", "extracted_by", "extractor_version", "model_name", "superseded_by",
    "created_at", "updated_at", "observed_at", "valid_from", "valid_until", "stale_after",
    "metadata_json",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp_limit(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return _DEFAULT_LIMIT
    return max(1, min(n, _MAX_LIMIT))


class ClaimRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else None

    # ----- write ---------------------------------------------------------------------------
    def ingest_candidates(
        self,
        candidates: list[ClaimCandidate],
        *,
        source_id: str | None = None,
        note_rel_path: str | None = None,
        card_id: str | None = None,
        source_kind: str | None = None,
        source_root_key: str | None = None,
        source_rel_path: str | None = None,
        source_state: str | None = None,
        extracted_by: str = "rule_based",
        extractor_version: str | None = None,
        model_name: str | None = None,
        status: str = STATUS_CANDIDATE,
        review_state: str = "unreviewed",
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        """Validate + upsert claim candidates anchored to one source. Returns counts + rejections.

        Provenance is mandatory: at least one of ``source_id`` / ``note_rel_path`` must be present, or
        the whole batch is refused (:class:`ClaimValidationError`) — no trusted unsupported claims.
        Per-candidate problems (bad type/empty evidence) are collected into ``rejected`` and skipped;
        the rest are written.
        """
        if not source_id and not note_rel_path:
            raise ClaimValidationError("unsupported_claim_batch: source_id or note_rel_path required")
        if extracted_by not in CLAIM_EXTRACTED_BY:
            raise ClaimValidationError(f"invalid extracted_by: {extracted_by}")
        if status not in CLAIM_STATUSES:
            raise ClaimValidationError(f"invalid status: {status}")
        if review_state not in CLAIM_REVIEW_STATES:
            raise ClaimValidationError(f"invalid review_state: {review_state}")

        ingested = 0
        updated = 0
        rejected: list[dict[str, Any]] = []
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            for cand in candidates:
                problem = self._validate_candidate(cand)
                if problem:
                    rejected.append({"reason": problem, "claim_text": (cand.claim_text or "")[:120]})
                    continue
                claim_id = compute_claim_id(source_id, note_rel_path, cand.claim_type, cand.claim_text)
                existed = c.execute(
                    "SELECT 1 FROM assistant_claims WHERE claim_id=?", (claim_id,)
                ).fetchone() is not None
                c.execute(
                    "INSERT INTO assistant_claims "
                    "(claim_id, claim_type, claim_text, normalized_subject, normalized_predicate, "
                    " normalized_object, source_id, card_id, note_rel_path, source_kind, "
                    " source_root_key, source_rel_path, evidence_excerpt, evidence_location, "
                    " source_state, confidence, status, review_state, extracted_by, extractor_version, "
                    " model_name, created_at, updated_at, observed_at, valid_from, valid_until, "
                    " stale_after, metadata_json) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(claim_id) DO UPDATE SET "
                    " confidence=excluded.confidence, evidence_excerpt=excluded.evidence_excerpt, "
                    " evidence_location=excluded.evidence_location, source_state=excluded.source_state, "
                    " normalized_subject=excluded.normalized_subject, "
                    " normalized_predicate=excluded.normalized_predicate, "
                    " normalized_object=excluded.normalized_object, "
                    " observed_at=excluded.observed_at, valid_until=excluded.valid_until, "
                    " stale_after=excluded.stale_after, metadata_json=excluded.metadata_json, "
                    " updated_at=excluded.updated_at",
                    (
                        claim_id, cand.claim_type, cand.claim_text.strip(), cand.normalized_subject,
                        cand.normalized_predicate, cand.normalized_object, source_id, card_id,
                        note_rel_path, source_kind, source_root_key, source_rel_path,
                        bound_evidence(cand.evidence_excerpt), cand.evidence_location, source_state,
                        clamp_confidence(cand.confidence), status, review_state, extracted_by,
                        extractor_version, model_name, now, now, cand.observed_at, cand.valid_from,
                        cand.valid_until, cand.stale_after,
                        _json_or_none(cand.metadata),
                    ),
                )
                self._log_event(c, claim_id, "updated" if existed else "created", None, status, now)
                if existed:
                    updated += 1
                else:
                    ingested += 1
        return {"ingested": ingested, "updated": updated, "rejected": rejected,
                "count": ingested + updated}

    @staticmethod
    def _validate_candidate(cand: ClaimCandidate) -> str | None:
        if cand.claim_type not in CLAIM_TYPES:
            return f"invalid_claim_type:{cand.claim_type}"
        if not (cand.claim_text or "").strip():
            return "empty_claim_text"
        if not bound_evidence(cand.evidence_excerpt):
            return "missing_evidence_excerpt"
        return None

    def set_status(self, claim_id: str, status: str, *, review_state: str | None = None,
                   superseded_by: str | None = None, detail: str | None = None,
                   conn: sqlite3.Connection | None = None) -> bool:
        if status not in CLAIM_STATUSES:
            raise ClaimValidationError(f"invalid status: {status}")
        if review_state is not None and review_state not in CLAIM_REVIEW_STATES:
            raise ClaimValidationError(f"invalid review_state: {review_state}")
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            row = c.execute("SELECT status FROM assistant_claims WHERE claim_id=?", (claim_id,)).fetchone()
            if row is None:
                return False
            from_status = row[0]
            sets = ["status=?", "updated_at=?"]
            params: list[Any] = [status, now]
            if review_state is not None:
                sets.append("review_state=?")
                params.append(review_state)
            if superseded_by is not None:
                sets.append("superseded_by=?")
                params.append(superseded_by)
            params.append(claim_id)
            c.execute(f"UPDATE assistant_claims SET {', '.join(sets)} WHERE claim_id=?", params)
            evt = {"stale": "marked_stale", "accepted": "accepted", "rejected": "rejected",
                   "superseded": "superseded"}.get(status, "updated")
            self._log_event(c, claim_id, evt, from_status, status, now, detail=detail)
        return True

    def mark_stale(self, claim_id: str, *, reason: str | None = None,
                   conn: sqlite3.Connection | None = None) -> bool:
        return self.set_status(claim_id, STATUS_STALE, detail=reason, conn=conn)

    @staticmethod
    def _log_event(c: sqlite3.Connection, claim_id: str, event_type: str, from_status: str | None,
                   to_status: str | None, now: str, *, detail: str | None = None) -> None:
        c.execute(
            "INSERT INTO assistant_claim_events "
            "(event_id, claim_id, event_type, from_status, to_status, detail, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (uuid.uuid4().hex, claim_id, event_type, from_status, to_status, detail, now),
        )

    # ----- read (bounded) ------------------------------------------------------------------
    def get_claim(self, claim_id: str, *, conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                f"SELECT {', '.join(_COLUMNS)} FROM assistant_claims WHERE claim_id=?", (claim_id,)
            ).fetchone()
        return self._row(row)

    def list_claims(self, *, limit: int = _DEFAULT_LIMIT, claim_type: str | None = None,
                    status: str | None = None, source_id: str | None = None,
                    note_rel_path: str | None = None,
                    conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        for col, val in (("claim_type", claim_type), ("status", status), ("source_id", source_id),
                         ("note_rel_path", note_rel_path)):
            if val:
                clauses.append(f"{col}=?")
                params.append(val)
        where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
        params.append(_clamp_limit(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_COLUMNS)} FROM assistant_claims {where}"
                "ORDER BY created_at DESC, claim_id DESC LIMIT ?",
                params,
            ).fetchall()
        return [self._row(r) for r in rows if r is not None]  # type: ignore[misc]

    def get_claims_for_source(self, source_id: str, *, limit: int = _DEFAULT_LIMIT,
                              conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        return self.list_claims(source_id=source_id, limit=limit, conn=conn)

    def get_claims_for_note(self, note_rel_path: str, *, limit: int = _DEFAULT_LIMIT,
                            conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        return self.list_claims(note_rel_path=note_rel_path, limit=limit, conn=conn)

    def count_claims(self, *, conn: sqlite3.Connection | None = None) -> int:
        with borrow_connection(conn, self.db_path) as c:
            return int(c.execute("SELECT COUNT(*) FROM assistant_claims").fetchone()[0])

    def list_events(self, claim_id: str, *, conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                "SELECT event_id, claim_id, event_type, from_status, to_status, detail, created_at "
                "FROM assistant_claim_events WHERE claim_id=? ORDER BY created_at, event_id",
                (claim_id,),
            ).fetchall()
        return [{"event_id": r[0], "claim_id": r[1], "event_type": r[2], "from_status": r[3],
                 "to_status": r[4], "detail": r[5], "created_at": r[6]} for r in rows]

    @staticmethod
    def _row(row: Any) -> dict[str, Any] | None:
        if row is None:
            return None
        return dict(zip(_COLUMNS, row, strict=True))


def _json_or_none(metadata: dict[str, Any] | None) -> str | None:
    if not metadata:
        return None
    import json
    return json.dumps(metadata, sort_keys=True)
