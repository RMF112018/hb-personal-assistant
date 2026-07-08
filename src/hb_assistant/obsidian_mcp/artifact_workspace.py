"""N8C-23 Structured Intelligence Artifact Workspace — repository + staging/review/validation logic.

The server-side records authority behind the connected-client drafting UI: session capture, artifact
proposal staging, versioned revision, operator review (with SERVER-MINTED approval ids), advisory promotion
planning, and plan-binding validation. Canonical promotion + Obsidian materialization live in
``artifact_promotion.py``; this module never writes to the vault.

Trust model (N8C-23 amendments): approval ids are minted here from recorded review decisions and never
accepted from the client; validation computes a ``validation_hash`` over the exact promotion plan and
persists a validation receipt; idempotency keys are server-derived.
"""

from __future__ import annotations

from typing import Any

from hb_assistant.store.connection import borrow_connection, open_connection, transaction

from .memory_models import bound_text, sha256_hex
from .vault_path_resolver import resolve_relative_path

# --- caps (reject unbounded / oversized inputs) ---
MAX_TITLE = 200
MAX_SUMMARY = 8000
MAX_BODY = 20000
MAX_EXCERPT_TOTAL = 20000
MAX_EXCERPTS = 50
MAX_CANDIDATES = 40
# Fields that would smuggle in a full raw transcript — rejected outright.
_FORBIDDEN_CAPTURE_KEYS = ("raw_transcript", "full_transcript", "transcript", "messages", "chat_log")

ARTIFACT_PREFIX: dict[str, str] = {
    "session_note": "NOTE", "decision": "DEC", "preference": "PREF", "open_loop": "LOOP",
    "workflow": "WF", "research_packet": "RSCH", "answer_draft": "DRFT", "architecture_note": "ARCH",
    "source_card_annotation": "SCA", "review_item": "REV", "feedback": "FB", "action_stage": "ACT",
    "quality_finding": "QUAL", "person_note": "PERS", "company_note": "CO", "project_context": "PROJ",
    "knowledge_note": "KN",
}

# Only these review outcomes make a proposal eligible for canonical promotion.
PROMOTABLE_REVIEW_STATUS = "approved"


class ArtifactWorkspaceError(ValueError):
    """Fail-closed workspace error (bad input, unknown record, unsafe request)."""


def _now() -> str:
    from datetime import datetime, timezone  # noqa: PLC0415

    return datetime.now(timezone.utc).isoformat()


def _today(now: str) -> str:
    return now[:10].replace("-", "")


def _sha(*parts: Any) -> str:
    return sha256_hex("|".join("" if p is None else str(p) for p in parts))[:24]


def _cjson(obj: Any) -> str | None:
    import json  # noqa: PLC0415

    return None if obj in (None, {}, []) else json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _content_hash(artifact_type: str, title: str, body: str, payload: Any) -> str:
    return _sha("artifact-v1", artifact_type, title, body, _cjson(payload) or "")


def _row(cur: Any, cols: tuple[str, ...]) -> dict[str, Any] | None:
    r = cur.fetchone()
    return dict(zip(cols, r, strict=True)) if r else None


def _rows(cur: Any, cols: tuple[str, ...]) -> list[dict[str, Any]]:
    return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


_SESSION_COLS = ("session_id", "source_client", "source_client_session_ref", "operator_id", "capture_trigger",
                 "captured_at", "session_title", "session_summary", "selected_excerpts_json", "content_hash",
                 "redaction_state", "created_at", "updated_at")
_PROPOSAL_COLS = ("proposal_id", "proposal_bundle_id", "session_id", "artifact_type", "proposed_title",
                  "proposed_summary", "proposed_body_markdown", "structured_payload_json", "confidence",
                  "rationale", "supporting_excerpt", "source_refs_json", "candidate_links_json",
                  "affected_existing_artifacts_json", "proposed_domain", "proposed_vault_path",
                  "proposed_tags_json", "proposed_backlinks_json", "review_status", "review_notes", "version",
                  "supersedes_proposal_id", "operator_approval_id", "content_hash", "created_at", "updated_at")
_BUNDLE_COLS = ("proposal_bundle_id", "session_id", "source_client", "status", "candidate_count", "created_at",
                "updated_at", "review_started_at", "review_completed_at", "promotion_receipt_id")
_CANON_COLS = ("canonical_id", "artifact_type", "title", "summary", "body_markdown", "structured_payload_json",
               "status", "domain", "source_client", "source_session_id", "source_proposal_id",
               "promotion_receipt_id", "version", "supersedes_canonical_id", "superseded_by_canonical_id",
               "vault_path", "tags_json", "backlinks_json", "content_hash", "created_at", "updated_at",
               "promoted_at", "archived_at")


def _insert(c: Any, table: str, row: dict[str, Any]) -> None:
    cols = [k for k, v in row.items() if v is not None]
    c.execute(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
        [row[k] for k in cols],
    )


class ArtifactWorkspaceRepository:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path

    # ---- session capture ----
    def stage_session_capture(self, payload: dict[str, Any]) -> dict[str, Any]:
        for key in _FORBIDDEN_CAPTURE_KEYS:
            if key in payload:
                raise ArtifactWorkspaceError(f"raw_transcript_not_allowed:{key}")
        source_client = str(payload.get("source_client") or "").strip()
        session_title = str(payload.get("session_title") or "").strip()
        capture_trigger = str(payload.get("capture_trigger") or "").strip()
        session_summary = str(payload.get("session_summary") or "").strip()
        excerpts = payload.get("selected_excerpts") or []
        if not source_client:
            raise ArtifactWorkspaceError("missing_source_client")
        if not capture_trigger:
            raise ArtifactWorkspaceError("missing_capture_trigger")
        if not session_title:
            raise ArtifactWorkspaceError("missing_session_title")
        if not session_summary:
            raise ArtifactWorkspaceError("missing_session_summary")
        if len(session_summary) > MAX_SUMMARY:
            raise ArtifactWorkspaceError("session_summary_too_large")
        if not isinstance(excerpts, list) or len(excerpts) > MAX_EXCERPTS:
            raise ArtifactWorkspaceError("too_many_excerpts")
        if sum(len(str(e)) for e in excerpts) > MAX_EXCERPT_TOTAL:
            raise ArtifactWorkspaceError("excerpts_too_large")
        now = _now()
        session_id = self._next_seq_id("pa_session_captures", "session_id", "SESSION", now)
        content_hash = _sha("session-v1", source_client, session_title, session_summary, _cjson(excerpts) or "")
        row = {
            "session_id": session_id, "source_client": bound_text(source_client, 80),
            "source_client_session_ref": bound_text(payload.get("source_client_session_ref"), 200),
            "operator_id": bound_text(payload.get("operator_id"), 80),
            "capture_trigger": bound_text(capture_trigger, 200), "captured_at": now,
            "session_title": bound_text(session_title, MAX_TITLE),
            "session_summary": bound_text(session_summary, MAX_SUMMARY),
            "selected_excerpts_json": _cjson([bound_text(e, 4000) for e in excerpts]),
            "content_hash": content_hash,
            "redaction_state": str(payload.get("redaction_state") or "redacted"),
            "created_at": now, "updated_at": now,
        }
        with open_connection(self._path()) as c, transaction(c):
            _insert(c, "pa_session_captures", row)
        return {"session_id": session_id, "content_hash": content_hash, "captured_at": now}

    def get_session_capture(self, session_id: str, *, conn: Any = None) -> dict[str, Any] | None:
        with borrow_connection(conn, self._path()) as c:
            return _row(c.execute(
                f"SELECT {', '.join(_SESSION_COLS)} FROM pa_session_captures WHERE session_id=?",
                (session_id,)), _SESSION_COLS)

    # ---- proposal staging ----
    def stage_proposal_bundle(self, session_id: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        session = self.get_session_capture(session_id)
        if not session:
            raise ArtifactWorkspaceError(f"unknown_session:{session_id}")
        if not isinstance(candidates, list) or not candidates:
            raise ArtifactWorkspaceError("no_candidate_artifacts")
        if len(candidates) > MAX_CANDIDATES:
            raise ArtifactWorkspaceError("too_many_candidates")
        now = _now()
        bundle_id = self._next_seq_id("pa_artifact_proposal_bundles", "proposal_bundle_id", "BUNDLE", now)
        source_client = session["source_client"]
        proposal_ids: list[str] = []
        with open_connection(self._path()) as c, transaction(c):
            _insert(c, "pa_artifact_proposal_bundles", {
                "proposal_bundle_id": bundle_id, "session_id": session_id, "source_client": source_client,
                "status": "proposed", "candidate_count": len(candidates), "created_at": now, "updated_at": now,
            })
            for idx, cand in enumerate(candidates):
                atype = str(cand.get("artifact_type") or "").strip()
                if atype not in ARTIFACT_PREFIX:
                    raise ArtifactWorkspaceError(f"unknown_artifact_type:{atype}")
                title = str(cand.get("title") or cand.get("proposed_title") or "").strip()
                if not title:
                    raise ArtifactWorkspaceError(f"missing_title:candidate_{idx}")
                body = bound_text(cand.get("body_markdown") or cand.get("proposed_body_markdown") or "", MAX_BODY)
                payload = cand.get("structured_payload") or {}
                domain = str(cand.get("domain") or "unknown")
                pid = self._next_seq_id("pa_artifact_proposals", "proposal_id", "PROP", now, conn=c)
                ch = _content_hash(atype, title, body, payload)
                _insert(c, "pa_artifact_proposals", {
                    "proposal_id": pid, "proposal_bundle_id": bundle_id, "session_id": session_id,
                    "artifact_type": atype, "proposed_title": bound_text(title, MAX_TITLE),
                    "proposed_summary": bound_text(cand.get("summary") or cand.get("proposed_summary"), MAX_SUMMARY),
                    "proposed_body_markdown": body, "structured_payload_json": _cjson(payload),
                    "confidence": cand.get("confidence"),
                    "rationale": bound_text(cand.get("rationale"), 2000),
                    "supporting_excerpt": bound_text(cand.get("supporting_excerpt"), 4000),
                    "source_refs_json": _cjson(cand.get("source_refs")),
                    "candidate_links_json": _cjson(cand.get("candidate_links")),
                    "affected_existing_artifacts_json": _cjson(cand.get("affected_existing_artifacts")),
                    "proposed_domain": domain,
                    "proposed_tags_json": _cjson(cand.get("tags")),
                    "proposed_backlinks_json": _cjson(cand.get("backlinks")),
                    "review_status": "proposed", "version": 1, "content_hash": ch,
                    "created_at": now, "updated_at": now,
                })
                # v1 version snapshot
                _insert(c, "pa_artifact_proposal_versions", {
                    "proposal_version_id": _sha(pid, 1, ch), "proposal_id": pid, "version": 1,
                    "body_markdown": body, "structured_payload_json": _cjson(payload),
                    "created_by_client": source_client, "content_hash": ch, "created_at": now,
                })
                proposal_ids.append(pid)
        return {
            "proposal_bundle_id": bundle_id, "session_id": session_id, "proposal_ids": proposal_ids,
            "candidate_count": len(candidates),
            "review_packet_markdown": self.render_review_packet(bundle_id),
            "review_packet": self.machine_review_packet(bundle_id),
        }

    def list_proposals(self, *, bundle_id: str | None = None, review_status: str | None = None,
                       limit: int = 50, conn: Any = None) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        clauses: list[str] = []
        args: list[Any] = []
        if bundle_id:
            clauses.append("proposal_bundle_id=?")
            args.append(bundle_id)
        if review_status:
            clauses.append("review_status=?")
            args.append(review_status)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with borrow_connection(conn, self._path()) as c:
            return _rows(c.execute(
                f"SELECT {', '.join(_PROPOSAL_COLS)} FROM pa_artifact_proposals{where} "
                f"ORDER BY created_at, proposal_id LIMIT ?", (*args, limit)), _PROPOSAL_COLS)

    def get_proposal(self, proposal_id: str, *, conn: Any = None) -> dict[str, Any] | None:
        with borrow_connection(conn, self._path()) as c:
            return _row(c.execute(
                f"SELECT {', '.join(_PROPOSAL_COLS)} FROM pa_artifact_proposals WHERE proposal_id=?",
                (proposal_id,)), _PROPOSAL_COLS)

    def get_bundle(self, bundle_id: str, *, conn: Any = None) -> dict[str, Any] | None:
        with borrow_connection(conn, self._path()) as c:
            return _row(c.execute(
                f"SELECT {', '.join(_BUNDLE_COLS)} FROM pa_artifact_proposal_bundles WHERE proposal_bundle_id=?",
                (bundle_id,)), _BUNDLE_COLS)

    def compare_proposals(self, proposal_ids: list[str]) -> dict[str, Any]:
        out = []
        for pid in proposal_ids[:20]:
            p = self.get_proposal(pid)
            if p:
                out.append({k: p[k] for k in ("proposal_id", "artifact_type", "proposed_title",
                                              "review_status", "version", "content_hash", "proposed_domain")})
        return {"proposals": out, "count": len(out)}

    # ---- revision (versioning; never overwrite v1) ----
    def revise_proposal(self, proposal_id: str, *, body_markdown: str | None = None,
                        structured_payload: Any = None, operator_instruction: str | None = None,
                        revision_summary: str | None = None, created_by_client: str | None = None) -> dict[str, Any]:
        p = self.get_proposal(proposal_id)
        if not p:
            raise ArtifactWorkspaceError(f"unknown_proposal:{proposal_id}")
        now = _now()
        new_version = int(p["version"]) + 1
        body = bound_text(body_markdown if body_markdown is not None else p["proposed_body_markdown"], MAX_BODY)
        payload = structured_payload if structured_payload is not None else None
        payload_json = _cjson(payload) if payload is not None else p["structured_payload_json"]
        ch = _content_hash(p["artifact_type"], p["proposed_title"], body, payload)
        with open_connection(self._path()) as c, transaction(c):
            _insert(c, "pa_artifact_proposal_versions", {
                "proposal_version_id": _sha(proposal_id, new_version, ch), "proposal_id": proposal_id,
                "version": new_version, "body_markdown": body, "structured_payload_json": payload_json,
                "operator_instruction": bound_text(operator_instruction, 2000),
                "revision_summary": bound_text(revision_summary, 2000),
                "created_by_client": bound_text(created_by_client, 80), "content_hash": ch, "created_at": now,
            })
            c.execute(
                "UPDATE pa_artifact_proposals SET version=?, proposed_body_markdown=?, structured_payload_json=?, "
                "review_status='revised', content_hash=?, updated_at=? WHERE proposal_id=?",
                (new_version, body, payload_json, ch, now, proposal_id))
        return {"proposal_id": proposal_id, "version": new_version, "content_hash": ch, "review_status": "revised"}

    # ---- operator review (mints server approval ids) ----
    def review_proposal(self, proposal_id: str, decision: str, *, operator_id: str | None = None,
                        review_notes: str | None = None) -> dict[str, Any]:
        p = self.get_proposal(proposal_id)
        if not p:
            raise ArtifactWorkspaceError(f"unknown_proposal:{proposal_id}")
        status_map = {
            "approve": "approved", "reject": "rejected", "request_revision": "revision_requested",
            "merge": "merged", "split": "split", "session_note_only": "session_note_only", "defer": "proposed",
        }
        if decision not in status_map:
            raise ArtifactWorkspaceError(f"unknown_decision:{decision}")
        now = _now()
        review_decision_id = _sha("rd", proposal_id, decision, now)
        # Approval id is minted ONLY on approve, bound to bundle + proposal + content_hash. Never client-supplied.
        approval_id = (_sha("appr", p["proposal_bundle_id"], proposal_id, p["content_hash"], now)
                       if decision == "approve" else None)
        with open_connection(self._path()) as c, transaction(c):
            _insert(c, "pa_artifact_review_decisions", {
                "review_decision_id": review_decision_id, "proposal_id": proposal_id,
                "proposal_bundle_id": p["proposal_bundle_id"], "operator_id": bound_text(operator_id, 80),
                "decision": decision, "review_notes": bound_text(review_notes, 2000),
                "operator_approval_id": approval_id, "created_at": now,
            })
            c.execute(
                "UPDATE pa_artifact_proposals SET review_status=?, review_notes=?, operator_approval_id=?, "
                "updated_at=? WHERE proposal_id=?",
                (status_map[decision], bound_text(review_notes, 2000),
                 approval_id if approval_id else p["operator_approval_id"], now, proposal_id))
            c.execute(
                "UPDATE pa_artifact_proposal_bundles SET status='in_review', "
                "review_started_at=COALESCE(review_started_at, ?), updated_at=? WHERE proposal_bundle_id=?",
                (now, now, p["proposal_bundle_id"]))
        return {"review_decision_id": review_decision_id, "proposal_id": proposal_id,
                "review_status": status_map[decision], "operator_approval_id": approval_id}

    def get_review_decisions(self, proposal_id: str, *, conn: Any = None) -> list[dict[str, Any]]:
        cols = ("review_decision_id", "proposal_id", "proposal_bundle_id", "operator_id", "decision",
                "review_notes", "operator_approval_id", "created_at")
        with borrow_connection(conn, self._path()) as c:
            return _rows(c.execute(
                f"SELECT {', '.join(cols)} FROM pa_artifact_review_decisions WHERE proposal_id=? "
                f"ORDER BY created_at", (proposal_id,)), cols)

    # ---- promotion planning (advisory; no write) ----
    def plan_promotion(self, bundle_id: str) -> dict[str, Any]:
        bundle = self.get_bundle(bundle_id)
        if not bundle:
            raise ArtifactWorkspaceError(f"unknown_bundle:{bundle_id}")
        approved = self.list_proposals(bundle_id=bundle_id, review_status=PROMOTABLE_REVIEW_STATUS, limit=200)
        items, duplicate_warnings = [], []
        for p in approved:
            cid = self._proposed_canonical_id(p, bundle)
            rel = resolve_relative_path(artifact_type=p["artifact_type"], domain=p["proposed_domain"],
                                        canonical_id=cid, title=p["proposed_title"])
            dup = self._find_duplicate(p)
            if dup:
                duplicate_warnings.append({"proposal_id": p["proposal_id"], "duplicate_canonical_id": dup})
            items.append({
                "proposal_id": p["proposal_id"], "artifact_type": p["artifact_type"],
                "title": p["proposed_title"], "proposed_canonical_id": cid,
                "proposed_vault_path": rel.resolved_relative_path, "domain": p["proposed_domain"],
                "tags": self._tags_for(p), "backlinks": self._backlinks_for(p, bundle),
                "content_hash": p["content_hash"], "path_warnings": list(rel.path_warnings),
            })
        return {
            "proposal_bundle_id": bundle_id, "approved_count": len(items),
            "would_create": items, "duplicate_warnings": duplicate_warnings,
            "receipt_path_folder": "99 System/Receipts", "manifest_folder": "99 System/Manifests",
            "required_approvals": "server-minted operator_approval_id from validation (Part 12)",
            "writes": False,
        }

    # ---- validation (binds the exact plan; persists a validation receipt) ----
    def validate_promotion(self, bundle_id: str, *, operator_id: str | None = None) -> dict[str, Any]:
        plan = self.plan_promotion(bundle_id)
        if not plan["would_create"]:
            raise ArtifactWorkspaceError("no_approved_proposals_to_promote")
        # Confirm every approved proposal carries a recorded approval id (server-minted).
        approved = self.list_proposals(bundle_id=bundle_id, review_status=PROMOTABLE_REVIEW_STATUS, limit=200)
        missing = [p["proposal_id"] for p in approved if not p["operator_approval_id"]]
        if missing:
            raise ArtifactWorkspaceError(f"approved_without_recorded_approval:{missing}")
        now = _now()
        approved_ids = sorted(p["proposal_id"] for p in approved)
        canonical_ids = [i["proposed_canonical_id"] for i in plan["would_create"]]
        paths = [i["proposed_vault_path"] for i in plan["would_create"]]
        validation_hash = _sha("validate-v1", bundle_id, _cjson(approved_ids), _cjson(canonical_ids),
                               _cjson(paths), _cjson([i["tags"] for i in plan["would_create"]]),
                               _cjson([i["backlinks"] for i in plan["would_create"]]),
                               _cjson([i["content_hash"] for i in plan["would_create"]]))
        # operator_approval_id for the promotion is derived from the recorded per-proposal approvals + hash.
        operator_approval_id = _sha("promote-appr", bundle_id,
                                    _cjson(sorted(p["operator_approval_id"] for p in approved)), validation_hash)
        promotion_bundle_id = self._next_seq_id("pa_artifact_promotion_bundles", "promotion_bundle_id",
                                                "PROMOB", now)
        idempotency_key = _sha("idem-v1", promotion_bundle_id, validation_hash, operator_approval_id)
        validation_receipt_id = _sha("val", promotion_bundle_id, validation_hash)
        summary = {"approved_count": len(approved_ids), "canonical_ids": canonical_ids, "paths": paths,
                   "duplicate_warnings": plan["duplicate_warnings"]}
        with open_connection(self._path()) as c, transaction(c):
            _insert(c, "pa_artifact_promotion_bundles", {
                "promotion_bundle_id": promotion_bundle_id, "proposal_bundle_id": bundle_id,
                "session_id": self.get_bundle(bundle_id, conn=c)["session_id"],
                "operator_approval_id": operator_approval_id, "status": "ready",
                "validation_summary_json": _cjson(summary), "validation_hash": validation_hash,
                "idempotency_key": idempotency_key, "created_at": now,
            })
            _insert(c, "pa_artifact_validation_receipts", {
                "validation_receipt_id": validation_receipt_id, "promotion_bundle_id": promotion_bundle_id,
                "proposal_bundle_id": bundle_id, "operator_approval_id": operator_approval_id,
                "validation_hash": validation_hash, "validation_summary_json": _cjson(summary),
                "approved_proposal_ids_json": _cjson(approved_ids),
                "proposed_canonical_ids_json": _cjson(canonical_ids), "proposed_paths_json": _cjson(paths),
                "passed": 1, "created_at": now,
            })
            c.execute("UPDATE pa_artifact_proposal_bundles SET status='approved_for_promotion', updated_at=? "
                      "WHERE proposal_bundle_id=?", (now, bundle_id))
        return {
            "promotion_bundle_id": promotion_bundle_id, "validation_hash": validation_hash,
            "operator_approval_id": operator_approval_id, "idempotency_key": idempotency_key,
            "validation_receipt_id": validation_receipt_id, "passed": True,
            "would_create": plan["would_create"], "duplicate_warnings": plan["duplicate_warnings"], "writes": False,
        }

    def recompute_validation_hash(self, promotion_bundle_id: str, *, conn: Any = None) -> str:
        pb = self._get_promotion_bundle(promotion_bundle_id, conn=conn)
        if not pb:
            raise ArtifactWorkspaceError(f"unknown_promotion_bundle:{promotion_bundle_id}")
        plan = self.plan_promotion(pb["proposal_bundle_id"])
        approved = self.list_proposals(bundle_id=pb["proposal_bundle_id"],
                                       review_status=PROMOTABLE_REVIEW_STATUS, limit=200)
        approved_ids = sorted(p["proposal_id"] for p in approved)
        canonical_ids = [i["proposed_canonical_id"] for i in plan["would_create"]]
        paths = [i["proposed_vault_path"] for i in plan["would_create"]]
        return _sha("validate-v1", pb["proposal_bundle_id"], _cjson(approved_ids), _cjson(canonical_ids),
                    _cjson(paths), _cjson([i["tags"] for i in plan["would_create"]]),
                    _cjson([i["backlinks"] for i in plan["would_create"]]),
                    _cjson([i["content_hash"] for i in plan["would_create"]]))

    # ---- canonical reads ----
    def get_canonical(self, canonical_id: str, *, conn: Any = None) -> dict[str, Any] | None:
        with borrow_connection(conn, self._path()) as c:
            return _row(c.execute(
                f"SELECT {', '.join(_CANON_COLS)} FROM pa_canonical_artifacts WHERE canonical_id=?",
                (canonical_id,)), _CANON_COLS)

    def list_canonical(self, *, artifact_type: str | None = None, limit: int = 50,
                       conn: Any = None) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        where, args = ("", [])
        if artifact_type:
            where, args = (" WHERE artifact_type=?", [artifact_type])
        with borrow_connection(conn, self._path()) as c:
            return _rows(c.execute(
                f"SELECT {', '.join(_CANON_COLS)} FROM pa_canonical_artifacts{where} "
                f"ORDER BY promoted_at DESC, canonical_id LIMIT ?", (*args, limit)), _CANON_COLS)

    def get_receipt(self, promotion_receipt_id: str, *, conn: Any = None) -> dict[str, Any] | None:
        cols = ("promotion_receipt_id", "promotion_bundle_id", "session_id", "operator_id", "created_count",
                "updated_count", "superseded_count", "archived_count", "failed_count", "created_paths_json",
                "validation_summary_json", "validation_hash", "receipt_vault_path", "status", "created_at")
        with borrow_connection(conn, self._path()) as c:
            return _row(c.execute(
                f"SELECT {', '.join(cols)} FROM pa_promotion_receipts WHERE promotion_receipt_id=?",
                (promotion_receipt_id,)), cols)

    def pending_counts(self, *, conn: Any = None) -> dict[str, int]:
        with borrow_connection(conn, self._path()) as c:
            def n(sql: str, a: tuple = ()) -> int:
                return int(c.execute(sql, a).fetchone()[0])
            return {
                "pending_proposal_count": n("SELECT COUNT(*) FROM pa_artifact_proposals WHERE review_status IN "
                                            "('proposed','revised','revision_requested')"),
                "pending_review_count": n("SELECT COUNT(*) FROM pa_artifact_proposal_bundles WHERE status IN "
                                          "('proposed','in_review','revision_requested')"),
                "pending_promotion_count": n("SELECT COUNT(*) FROM pa_artifact_promotion_bundles WHERE status IN "
                                             "('ready','validating','promoting')"),
            }

    # ---- review packets ----
    def render_review_packet(self, bundle_id: str) -> str:
        proposals = self.list_proposals(bundle_id=bundle_id, limit=200)
        lines = ["# Session Capture Review Packet", "", f"Bundle: {bundle_id}  ·  candidates: {len(proposals)}", ""]
        for i, p in enumerate(proposals, 1):
            bundle = self.get_bundle(bundle_id)
            cid = self._proposed_canonical_id(p, bundle)
            rel = resolve_relative_path(artifact_type=p["artifact_type"], domain=p["proposed_domain"],
                                        canonical_id=cid, title=p["proposed_title"])
            lines += [
                f"## Candidate {i} — {p['artifact_type']}", "",
                f"**Proposal ID:** {p['proposal_id']}", "",
                f"**Title:** {p['proposed_title']}", "",
                f"**Summary:** {p.get('proposed_summary') or '_(none)_'}", "",
                f"**Recommended action:** {self._recommend(p)}", "",
                f"**Proposed destination:** `{rel.resolved_relative_path}`", "",
                f"**Tags:** {', '.join(self._tags_for(p))}", "",
                f"**Backlinks:** {', '.join(self._backlinks_for(p, bundle)) or '_(none)_'}", "",
            ]
        return "\n".join(lines) + "\n"

    def machine_review_packet(self, bundle_id: str) -> dict[str, Any]:
        bundle = self.get_bundle(bundle_id)
        proposals = self.list_proposals(bundle_id=bundle_id, limit=200)
        out = []
        for p in proposals:
            cid = self._proposed_canonical_id(p, bundle)
            rel = resolve_relative_path(artifact_type=p["artifact_type"], domain=p["proposed_domain"],
                                        canonical_id=cid, title=p["proposed_title"])
            out.append({
                "proposal_id": p["proposal_id"], "artifact_type": p["artifact_type"],
                "title": p["proposed_title"], "summary": p.get("proposed_summary"),
                "recommended_action": self._recommend(p), "proposed_vault_path": rel.resolved_relative_path,
                "proposed_canonical_id": cid, "tags": self._tags_for(p),
                "backlinks": self._backlinks_for(p, bundle), "review_status": p["review_status"],
                "duplicate_of": self._find_duplicate(p),
            })
        return {"proposal_bundle_id": bundle_id, "candidates": out, "count": len(out)}

    # ---- internals ----
    def _path(self) -> Any:
        from pathlib import Path  # noqa: PLC0415

        return Path(self.db_path) if self.db_path else None

    def _next_seq_id(self, table: str, id_col: str, prefix: str, now: str, *, conn: Any = None) -> str:
        date = _today(now)
        like = f"{prefix}-{date}-%"
        with borrow_connection(conn, self._path()) as c:
            n = int(c.execute(f"SELECT COUNT(*) FROM {table} WHERE {id_col} LIKE ?", (like,)).fetchone()[0])
        return f"{prefix}-{date}-{n + 1:03d}"

    def _proposed_canonical_id(self, proposal: dict[str, Any], bundle: dict[str, Any] | None) -> str:
        prefix = ARTIFACT_PREFIX.get(proposal["artifact_type"], "KN")
        # deterministic per (proposal content hash) so plan/validate/apply agree; short suffix from hash.
        date = _today(proposal.get("created_at") or _now())
        suffix = proposal["content_hash"][:6].upper()
        return f"{prefix}-{date}-{suffix}"

    def _tags_for(self, p: dict[str, Any]) -> list[str]:
        base = [
            "second-brain/canonical", f"artifact/{p['artifact_type']}", "status/approved",
            f"domain/{p.get('proposed_domain') or 'unknown'}",
        ]
        import json  # noqa: PLC0415
        extra = json.loads(p["proposed_tags_json"]) if p.get("proposed_tags_json") else []
        return base + [t for t in extra if t not in base]

    def _backlinks_for(self, p: dict[str, Any], bundle: dict[str, Any] | None) -> list[str]:
        links = [p["session_id"]]
        import json  # noqa: PLC0415
        extra = json.loads(p["proposed_backlinks_json"]) if p.get("proposed_backlinks_json") else []
        return links + [b for b in extra if b not in links]

    def _recommend(self, p: dict[str, Any]) -> str:
        return {"approved": "Approve", "rejected": "Reject", "revision_requested": "Revise",
                "session_note_only": "Session note only"}.get(p["review_status"], "Review")

    def _find_duplicate(self, p: dict[str, Any]) -> str | None:
        with borrow_connection(None, self._path()) as c:
            row = c.execute(
                "SELECT canonical_id FROM pa_canonical_artifacts WHERE content_hash=? AND status='canonical' "
                "LIMIT 1", (p["content_hash"],)).fetchone()
        return row[0] if row else None

    def _get_promotion_bundle(self, promotion_bundle_id: str, *, conn: Any = None) -> dict[str, Any] | None:
        cols = ("promotion_bundle_id", "proposal_bundle_id", "session_id", "operator_approval_id", "status",
                "validation_summary_json", "validation_hash", "idempotency_key", "created_at", "promoted_at",
                "failed_at", "failure_reason")
        with borrow_connection(conn, self._path()) as c:
            return _row(c.execute(
                f"SELECT {', '.join(cols)} FROM pa_artifact_promotion_bundles WHERE promotion_bundle_id=?",
                (promotion_bundle_id,)), cols)
