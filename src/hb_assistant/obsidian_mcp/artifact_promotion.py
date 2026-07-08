"""N8C-23 canonical promotion + Obsidian materialization (the one new controlled canonical write).

Trust gates (amendments): requires the server-minted ``operator_approval_id`` stored on the promotion
bundle, a passed validation receipt, a RECOMPUTED validation hash that still matches (else
``revalidation_required``), and a server-derived idempotency key. Write order (Part 15): DB-first with a
pending materialization state → render + atomic card write → mark canonical + final path → receipt card →
canonical manifest. Idempotent: a completed promotion returns its existing receipt with no duplicate
rows/cards. Partial failure leaves ``needs_materialization_repair`` + a repair task and a ``partial_failure``
receipt.
"""

from __future__ import annotations

from typing import Any

from hb_assistant.store.connection import open_connection, transaction

from .artifact_card_renderer import (
    render_artifact_card,
    render_canonical_manifest_md,
    render_receipt_card,
)
from .artifact_vault_writer import create_card, md_config, write_manifest_pair
from .artifact_workspace import (
    ArtifactWorkspaceError,
    ArtifactWorkspaceRepository,
    _cjson,
    _insert,
    _now,
    _sha,
)
from .vault_path_resolver import RECEIPTS_FOLDER, resolve_relative_path, resolve_write_path

_TOOL = "pa_artifact_promotion_apply"


def _existing_receipt(repo: ArtifactWorkspaceRepository, promotion_bundle_id: str) -> dict[str, Any] | None:
    from hb_assistant.store.connection import borrow_connection  # noqa: PLC0415

    with borrow_connection(None, repo._path()) as c:
        row = c.execute("SELECT promotion_receipt_id FROM pa_promotion_receipts WHERE promotion_bundle_id=? "
                        "ORDER BY created_at DESC LIMIT 1", (promotion_bundle_id,)).fetchone()
    return {"promotion_receipt_id": row[0]} if row else None


def promote_bundle(nas_config: Any, db_path: str, *, promotion_bundle_id: str,
                   operator_approval_id: str, idempotency_key: str | None = None,
                   operator_id: str | None = None, runtime_commit: str = "unknown") -> dict[str, Any]:
    repo = ArtifactWorkspaceRepository(db_path)
    pb = repo._get_promotion_bundle(promotion_bundle_id)
    if not pb:
        raise ArtifactWorkspaceError(f"unknown_promotion_bundle:{promotion_bundle_id}")

    # Idempotent: a completed promotion returns its receipt, no re-write.
    existing = _existing_receipt(repo, promotion_bundle_id)
    if existing and pb["status"] in ("promoted", "partial_failure"):
        rcpt = repo.get_receipt(existing["promotion_receipt_id"])
        return {"promotion_receipt_id": existing["promotion_receipt_id"], "idempotent_reuse": True,
                "status": pb["status"], "receipt": rcpt}

    # --- trust gates ---
    if operator_approval_id != pb["operator_approval_id"]:
        raise ArtifactWorkspaceError("operator_approval_mismatch")
    vr = _validation_receipt(repo, promotion_bundle_id)
    if not vr or not vr["passed"]:
        raise ArtifactWorkspaceError("validation_required")
    current_hash = repo.recompute_validation_hash(promotion_bundle_id)
    if current_hash != pb["validation_hash"]:
        _set_bundle_status(repo, promotion_bundle_id, "blocked", failure_reason="revalidation_required")
        raise ArtifactWorkspaceError("revalidation_required")
    server_idem = _sha("idem-v1", promotion_bundle_id, pb["validation_hash"], operator_approval_id)
    if server_idem != pb["idempotency_key"]:
        raise ArtifactWorkspaceError("idempotency_state_corrupt")
    if idempotency_key is not None and idempotency_key != server_idem:
        raise ArtifactWorkspaceError("idempotency_key_mismatch")

    approved = repo.list_proposals(bundle_id=pb["proposal_bundle_id"], review_status="approved", limit=200)
    if not approved:
        raise ArtifactWorkspaceError("no_approved_proposals")
    now = _now()
    receipt_id = repo._next_seq_id("pa_promotion_receipts", "promotion_receipt_id", "PROMO", now)
    proposal_bundle = repo.get_bundle(pb["proposal_bundle_id"])

    # Plan the canonical rows (deterministic ids/paths).
    plan_rows: list[dict[str, Any]] = []
    for p in approved:
        cid = repo._proposed_canonical_id(p, proposal_bundle)
        rel = resolve_relative_path(artifact_type=p["artifact_type"], domain=p["proposed_domain"],
                                    canonical_id=cid, title=p["proposed_title"]).resolved_relative_path
        plan_rows.append({"canonical_id": cid, "rel": rel, "proposal": p})
    all_cids = [r["canonical_id"] for r in plan_rows]

    # --- PHASE 1: DB-first, pending materialization state (idempotent inserts) ---
    with open_connection(repo._path()) as c, transaction(c):
        c.execute("UPDATE pa_artifact_promotion_bundles SET status='promoting' WHERE promotion_bundle_id=?",
                  (promotion_bundle_id,))
        for row in plan_rows:
            p = row["proposal"]
            c.execute(
                "INSERT OR IGNORE INTO pa_canonical_artifacts "
                "(canonical_id, artifact_type, title, summary, body_markdown, structured_payload_json, status, "
                " domain, source_client, source_session_id, source_proposal_id, promotion_receipt_id, version, "
                " tags_json, backlinks_json, content_hash, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (row["canonical_id"], p["artifact_type"], p["proposed_title"], p["proposed_summary"],
                 p["proposed_body_markdown"], p["structured_payload_json"], "needs_materialization_repair",
                 p["proposed_domain"], proposal_bundle["source_client"], p["session_id"], p["proposal_id"],
                 receipt_id, 1, _cjson(repo._tags_for(p)), _cjson(repo._backlinks_for(p, proposal_bundle)),
                 p["content_hash"], now, now))
            c.execute(
                "INSERT OR IGNORE INTO pa_artifact_links (link_id, from_canonical_id, to_canonical_id, "
                "link_type, created_by, created_at) VALUES (?,?,?,?,?,?)",
                (_sha("link", row["canonical_id"], p["session_id"], "belongs_to_session"), row["canonical_id"],
                 p["session_id"], "belongs_to_session", _TOOL, now))
            c.execute("UPDATE pa_artifact_proposals SET review_status='promoted', updated_at=? WHERE proposal_id=?",
                      (now, p["proposal_id"]))

    # --- PHASE 2: materialize each card (atomic write engine); update to canonical on success ---
    created_paths: list[str] = []
    failed = 0
    ob_cfg = md_config(nas_config)
    for row in plan_rows:
        cid, rel, p = row["canonical_id"], row["rel"], row["proposal"]
        canon = repo.get_canonical(cid)
        if canon and canon["status"] == "canonical" and canon["vault_path"]:
            created_paths.append(canon["vault_path"])  # already materialized (re-entrant)
            continue
        try:
            resolved = resolve_relative_path(artifact_type=p["artifact_type"], domain=p["proposed_domain"],
                                             canonical_id=cid, title=p["proposed_title"])
            resolve_write_path(ob_cfg, resolved)  # live-vault path safety (traversal/outside/hidden/new-top)
            related = [r["canonical_id"] for r in plan_rows if r["canonical_id"] != cid]
            history = repo.get_review_decisions(p["proposal_id"])
            card, _ = render_artifact_card(
                # A successfully written card IS canonical — render the final status, not the
                # transient needs_materialization_repair the DB row still carries pre-update.
                {**canon, "status": "canonical", "review_state": "approved", "related_artifacts": related,
                 "promoted_at": now, "promotion_receipt_id": receipt_id},
                promotion_receipt_id=receipt_id, related_artifacts=related, review_history=history)
            create_card(nas_config, rel, card, tool_name=_TOOL)
            with open_connection(repo._path()) as c, transaction(c):
                c.execute("UPDATE pa_canonical_artifacts SET status='canonical', vault_path=?, promoted_at=?, "
                          "updated_at=? WHERE canonical_id=?", (rel, now, now, cid))
            created_paths.append(rel)
        except Exception as exc:  # noqa: BLE001 — record repair, continue other artifacts
            failed += 1
            with open_connection(repo._path()) as c, transaction(c):
                c.execute("UPDATE pa_canonical_artifacts SET status='promotion_partial_failure', updated_at=? "
                          "WHERE canonical_id=?", (now, cid))
                _insert(c, "pa_artifact_repair_tasks", {
                    "repair_task_id": _sha("repair", cid, now), "canonical_id": cid,
                    "promotion_receipt_id": receipt_id, "repair_type": "materialization", "status": "open",
                    "detail": f"{type(exc).__name__}: {str(exc)[:160]}", "created_at": now})

    status = "promoted" if failed == 0 else "partial_failure"

    # --- PHASE 3: receipt card + canonical manifest, then finalize DB ---
    receipt_rel = f"{RECEIPTS_FOLDER}/{receipt_id} - Canonical Artifact Promotion Receipt.md"
    receipt_row = {
        "promotion_receipt_id": receipt_id, "promotion_bundle_id": promotion_bundle_id,
        "session_id": pb["session_id"], "operator_id": operator_id,
        "created_count": len(created_paths), "updated_count": 0, "superseded_count": 0,
        "archived_count": 0, "failed_count": failed, "created_paths_json": _cjson(created_paths),
        "validation_summary_json": pb["validation_summary_json"], "validation_hash": pb["validation_hash"],
        "receipt_vault_path": receipt_rel, "status": status, "created_at": now,
    }
    try:
        create_card(nas_config, receipt_rel, render_receipt_card(receipt_row, created_paths=created_paths),
                    tool_name=_TOOL)
    except Exception:  # noqa: BLE001 — receipt card is best-effort; DB receipt is authoritative
        receipt_row["receipt_vault_path"] = None

    manifest_paths: dict[str, Any] = {}
    try:
        all_canon = repo.list_canonical(limit=200)
        manifest_md = render_canonical_manifest_md(all_canon, generated_at=now, runtime_commit=runtime_commit)
        manifest_json = _cjson([{k: e.get(k) for k in ("canonical_id", "artifact_type", "status", "domain",
                                                       "vault_path", "content_hash")} for e in all_canon]) or "[]"
        manifest_paths = write_manifest_pair(nas_config, "canonical-artifact-manifest", manifest_md,
                                             manifest_json, tool_name=_TOOL)
    except Exception as exc:  # noqa: BLE001 — manifest is advisory; never fail the promotion on it
        manifest_paths = {"error": f"{type(exc).__name__}: {str(exc)[:120]}"}

    with open_connection(repo._path()) as c, transaction(c):
        _insert(c, "pa_promotion_receipts", receipt_row)
        c.execute("UPDATE pa_artifact_promotion_bundles SET status=?, promoted_at=? WHERE promotion_bundle_id=?",
                  (status, now, promotion_bundle_id))
        c.execute("UPDATE pa_artifact_proposal_bundles SET status=?, promotion_receipt_id=?, "
                  "review_completed_at=?, updated_at=? WHERE proposal_bundle_id=?",
                  ("promoted" if failed == 0 else "partially_promoted", receipt_id, now, now,
                   pb["proposal_bundle_id"]))

    return {
        "promotion_receipt_id": receipt_id, "status": status, "created_count": len(created_paths),
        "failed_count": failed, "created_paths": created_paths, "canonical_ids": all_cids,
        "receipt_vault_path": receipt_row["receipt_vault_path"], "manifest": manifest_paths,
        "idempotent_reuse": False,
    }


def _validation_receipt(repo: ArtifactWorkspaceRepository, promotion_bundle_id: str) -> dict[str, Any] | None:
    from hb_assistant.store.connection import borrow_connection  # noqa: PLC0415

    cols = ("validation_receipt_id", "validation_hash", "passed")
    with borrow_connection(None, repo._path()) as c:
        row = c.execute("SELECT validation_receipt_id, validation_hash, passed FROM "
                        "pa_artifact_validation_receipts WHERE promotion_bundle_id=? ORDER BY created_at DESC "
                        "LIMIT 1", (promotion_bundle_id,)).fetchone()
    return dict(zip(cols, row, strict=True)) if row else None


def _set_bundle_status(repo: ArtifactWorkspaceRepository, promotion_bundle_id: str, status: str, *,
                       failure_reason: str | None = None) -> None:
    with open_connection(repo._path()) as c, transaction(c):
        c.execute("UPDATE pa_artifact_promotion_bundles SET status=?, failure_reason=? WHERE promotion_bundle_id=?",
                  (status, failure_reason, promotion_bundle_id))
