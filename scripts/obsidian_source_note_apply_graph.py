#!/usr/bin/env python3
"""Bounded local note-graph applier (Phase 10C): vetted reciprocal wiki links + controlled tags.

Deterministically builds candidate related-note pairs from existing index/card metadata, has local
qwen2.5:14b VET each candidate (advisory only), then deterministic code writes approved reciprocal
`[[wiki links]]` (managed `hb-related-notes` block) + approved-enum tags (frontmatter) to BOTH notes.
No source-file read, no source-root scan, no queue enqueue/drain, no DB mutation, no runtime JSON
mutation, no card create/delete, no cloud model. Dry-run default (no Ollama unless --vet).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import socket
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (_REPO_ROOT / "src", _REPO_ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import obsidian_source_first_indexing_dryrun as dryrun  # noqa: E402

from hb_assistant.construction.classification.client import (  # noqa: E402
    OllamaChatClient,
    OllamaUnavailable,
    list_ollama_models,
)
from hb_assistant.obsidian_mcp import source_note_graph as ng  # noqa: E402
from hb_assistant.obsidian_mcp.mutations import create_note, sha256_file  # noqa: E402
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository  # noqa: E402

BACKEND_PORT = 8000
_FROZEN_FLAGS = ("external_source_watch_enabled", "source_card_auto_generate_enabled",
                 "source_summary_auto_generate_enabled", "source_note_auto_refresh_enabled")


class GraphError(Exception):
    """Refusal — printed as a controlled error, exit code 3."""


def _backend_listening(port: int = BACKEND_PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _ro(db: str):
    return sqlite3.connect(f"file:{quote(db)}?mode=ro", uri=True)


def _queue_counts(db: str) -> tuple[int, int]:
    c = _ro(db)
    try:
        r = c.execute("SELECT COALESCE(SUM(status='queued'),0),COALESCE(SUM(status='processing'),0) "
                      "FROM source_intelligence_events").fetchone()
    finally:
        c.close()
    return int(r[0] or 0), int(r[1] or 0)


def _db_fingerprint(db: str) -> dict[str, Any]:
    c = _ro(db)
    try:
        by_status = dict(c.execute("SELECT generation_status,COUNT(*) FROM "
                                   "source_intelligence_generated_notes GROUP BY generation_status").fetchall())
        summaries = c.execute("SELECT COUNT(*) FROM source_intelligence_summaries").fetchone()[0]
        rows = c.execute("SELECT source_id,note_rel_path,generation_status,generated_at FROM "
                         "source_intelligence_generated_notes ORDER BY source_id,note_rel_path").fetchall()
    finally:
        c.close()
    q, p = _queue_counts(db)
    return {"by_status": {str(k): int(v) for k, v in by_status.items()}, "summaries_rows": int(summaries),
            "queued": q, "processing": p,
            "meta_sha12": hashlib.sha256(repr(rows).encode()).hexdigest()[:12]}


def _link_line(target: ng.NoteFact, rel_type: str, conf: float) -> str:
    return f"- {ng.build_wiki_link(target)} — {rel_type} · qwen-vetted · confidence {conf:.2f}"


def _default_client_factory(model: str, timeout: float) -> OllamaChatClient:
    return OllamaChatClient(model=model, timeout=timeout)


# Matches the parent-email link written by source_email_attachments (hb-email-attachment block):
#   "- Parent email card: [[<rel-without-.md>|<display>]]"
_PARENT_EMAIL_RE = re.compile(r"parent email card:\s*\[\[([^\]|]+)", re.IGNORECASE)


def _n(s: str | None) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def _classify(f: ng.NoteFact) -> str:
    """Bounded card-type classification from graph-safe facts only (never bodies/paths)."""
    if f.attachment_extension or f.parent_email_hash:
        return "attachment"
    if f.thread_topic or f.subject_norm:
        return "email"
    return "project"


def _matches_project(f: ng.NoteFact, args: argparse.Namespace) -> bool:
    """True iff the card belongs to the requested bounded project (number/key/procore-id)."""
    if args.project_number and f.project == _n(args.project_number):
        return True
    if args.project_key and (f.canonical_project_key == _n(args.project_key)
                             or f.project == _n(args.project_key)):
        return True
    return bool(args.procore_project_id and f.procore_project_id == _n(args.procore_project_id))


def _parent_email_rel(text: str) -> str | None:
    """Parse the attachment card's parent-email-card wiki link target (with .md) for lineage exclusion."""
    m = _PARENT_EMAIL_RE.search(text)
    if not m:
        return None
    target = m.group(1).strip()
    return target if target.endswith(".md") else target + ".md"


def run(args: argparse.Namespace, *,
        client_factory: Callable[[str, float], Any] = _default_client_factory) -> dict[str, Any]:
    vault_root = Path(args.vault_path).resolve()
    config = dryrun._load_config(args.config_path)
    if Path(str(config.vault_root or "")).resolve() != vault_root:
        raise GraphError("config vault_root does not match --vault-path")
    repo = SourceIndexRepository(args.db_path)
    fp_before = _db_fingerprint(args.db_path)

    # ---- bounded selection --------------------------------------------------------------------
    # Only generated `.md` cards under Source Notes/Work/ (excludes Email Archive/, stale, binaries).
    # When project filters are set, keep ONLY cards of that one project (number/key/procore-id).
    prefix = "Source Notes/Work/"
    project_scoped = bool(args.project_number or args.project_key or args.procore_project_id)
    all_rows = sorted((r for r in repo.list_generated_notes(statuses=("generated",))
                       if str(r.get("note_rel_path") or "").startswith(prefix)),
                      key=lambda r: str(r["note_rel_path"]))
    facts: dict[str, ng.NoteFact] = {}
    text_by_id: dict[str, str] = {}
    excluded_outside_project = 0
    selection_truncated = False
    for row in all_rows:
        target = vault_root / str(row["note_rel_path"])
        if not target.is_file():
            raise GraphError("selected card file is missing")
        text = target.read_text(encoding="utf-8")
        f = ng.note_fact_from(repo, row, text)
        if project_scoped and not _matches_project(f, args):
            excluded_outside_project += 1
            continue
        if len(facts) >= args.max_notes:
            selection_truncated = True
            break
        facts[f.note_id] = f
        text_by_id[f.note_id] = text

    fact_list = list(facts.values())
    card_types = Counter(_classify(f) for f in fact_list)

    mode = "primary_secondary" if project_scoped else "default"
    candidates = ng.build_candidates(fact_list, max_per_note=args.max_candidates_per_note,
                                     max_relationships=args.max_relationships, mode=mode)

    # ---- amendment 1: exclude direct parent-email <-> its-own-attachment lineage pairs -----------
    # (already linked via hb-email-attachment(s); same_parent_email still supports SIBLING pairs).
    rel_to_id = {f.note_rel: f.note_id for f in fact_list}
    lineage_pairs: set[frozenset[str]] = set()
    for nid, f in facts.items():
        if _classify(f) != "attachment":
            continue
        parent_rel = _parent_email_rel(text_by_id[nid])
        if parent_rel and parent_rel in rel_to_id:
            lineage_pairs.add(frozenset((nid, rel_to_id[parent_rel])))
    lineage_pairs_excluded = 0
    kept: list[ng.Candidate] = []
    for c in candidates:
        if frozenset((c.a.note_id, c.b.note_id)) in lineage_pairs:
            lineage_pairs_excluded += 1
            continue
        kept.append(c)
    candidates = kept

    # ---- amendment 2 (+ 10G correction): duplicate/same-source evidence = review-only ------------
    # Any pair sharing attachment/source content SHA or email message-id hash is a duplicate pair; it is
    # VETOED from durable candidacy (see is_candidate) even when it also shares thread/subject/etc, and
    # is counted here for review — separately from the applied relationship types.
    duplicate_review_candidates = 0
    for i, a in enumerate(fact_list):
        for b in fact_list[i + 1:]:
            if ng.is_duplicate_pair(ng._pair_signals(a, b)):
                duplicate_review_candidates += 1

    result: dict[str, Any] = {
        "mode": "apply" if args.apply else "dry-run", "model": args.model,
        "eligibility_mode": mode,
        "project_number": args.project_number, "project_key": args.project_key,
        "procore_project_id": args.procore_project_id,
        "notes_selected": len(facts), "selection_truncated": selection_truncated,
        "project_cards": card_types.get("project", 0), "email_cards": card_types.get("email", 0),
        "attachment_cards": card_types.get("attachment", 0),
        "excluded_outside_project": excluded_outside_project,
        "candidate_pairs": len(candidates),
        "lineage_pairs_excluded": lineage_pairs_excluded,
        "duplicate_review_candidates": duplicate_review_candidates,
        "candidate_basis_counts": ng.candidate_basis_counts(candidates),
        "vetted_pairs": 0, "approved_pairs": 0, "ollama_calls": 0,
        "relationships_applied": 0, "notes_modified": 0,
        "reciprocal_links_applied": 0, "tags_added": 0, "created": 0, "deleted": 0,
        "applied_relationship_types": {}, "rejection_reasons": {},
        "backlink_integrity_passed": None, "backlinks_verified": 0,
        "queue_delta": 0, "db_mutations": 0, "db_before": fp_before, "ollama_called": False,
    }
    detail_rows: list[dict[str, Any]] = []

    do_vet = args.vet or args.apply
    if not do_vet:
        return {"safe": result, "detail_rows": detail_rows}

    # ---- vetting (local Ollama) ----------------------------------------------------------------
    timeout = float(args.timeout_seconds or config.source_summary_ollama_timeout_seconds)
    client = client_factory(args.model, timeout)
    if args.apply:
        if not (args.confirm_db_path == args.db_path and args.confirm_vault_path == args.vault_path
                and args.confirm_model == args.model):
            raise GraphError("--apply requires matching --confirm-db-path/--confirm-vault-path/--confirm-model")
        # When bounded project selection is used, its confirm flags must match exactly (Phase 10G).
        if not ((args.confirm_project_number or None) == (args.project_number or None)
                and (args.confirm_project_key or None) == (args.project_key or None)
                and (args.confirm_procore_project_id or None) == (args.procore_project_id or None)):
            raise GraphError("--apply requires matching --confirm-project-number/-key/-procore-project-id")
        if any(getattr(config, f, False) for f in _FROZEN_FLAGS):
            raise GraphError("runtime frozen flags are not all false")
        if _backend_listening():
            raise GraphError("backend listening on port 8000")
        q0, p0 = _queue_counts(args.db_path)
        if args.require_empty_queue and (q0 or p0):
            raise GraphError(f"queue not empty (queued={q0}, processing={p0})")
        try:
            models = list_ollama_models(base_url=getattr(client, "base_url", None))
        except OllamaUnavailable as exc:
            raise GraphError(f"ollama_unavailable ({exc})") from None
        if args.model not in models:
            raise GraphError(f"model_unavailable: {args.model}")

    result["ollama_called"] = True
    approved: list[tuple[ng.NoteFact, ng.NoteFact, dict[str, Any]]] = []
    rejections: Counter[str] = Counter()
    for cand in candidates:
        result["vetted_pairs"] += 1
        result["ollama_calls"] += 1
        vet, reason = ng.vet_candidate(client, cand, threshold=args.confidence_threshold)
        if vet is not None:
            approved.append((cand.a, cand.b, vet))
        else:
            rejections[reason] += 1
    result["approved_pairs"] = len(approved)
    result["rejection_reasons"] = dict(sorted(rejections.items()))

    # ---- amendment 3: post-vet apply checkpoint (hard-stop before any write) --------------------
    if args.apply and len(approved) > 0:
        if args.confirm_apply_approved_count is None:
            raise GraphError("--apply with approved>0 requires --confirm-apply-approved-count")
        if int(args.confirm_apply_approved_count) != len(approved):
            raise GraphError(
                f"confirm_apply_approved_count mismatch: got {args.confirm_apply_approved_count}, "
                f"vetted approved={len(approved)}")
        if len(approved) > args.max_apply_relationships:
            raise GraphError(
                f"approved {len(approved)} exceeds --max-apply-relationships {args.max_apply_relationships}")

    # ---- plan per-note edits (deterministic) --------------------------------------------------
    links: dict[str, set[str]] = {nid: set() for nid in facts}
    tags: dict[str, set[str]] = {nid: set() for nid in facts}
    rel_of_note: dict[str, set[str]] = {nid: set() for nid in facts}
    pair_notes: list[tuple[str, str, dict[str, Any]]] = []
    for a, b, vet in approved:
        rt, conf = vet["relationship_type"], float(vet["confidence"])
        links[a.note_id].add(_link_line(b, rt, conf))
        links[b.note_id].add(_link_line(a, rt, conf))
        for nid, qtags in ((a.note_id, vet["tags_for_source"]), (b.note_id, vet["tags_for_target"])):
            tags[nid].update(ng.relationship_tags_for(rt))
            tags[nid].update(qtags)
            rel_of_note[nid].add(rt)
        pair_notes.append((a.note_id, b.note_id, vet))

    affected = {nid for nid in facts if links[nid]}
    for nid in affected:
        tags[nid].update(ng.content_tags_for(facts[nid]))

    # compute final content; drop notes that can't be safely updated, then drop their relationships
    def _compute(nid: str) -> tuple[str | None, str]:
        text = text_by_id[nid]
        t2, r1 = ng.apply_tags(text, sorted(tags[nid]))
        if t2 is None:
            return None, f"tags:{r1}"
        t3, r2 = ng.upsert_related_block(t2, sorted(links[nid]),
                                         section=ng.choose_section(rel_of_note[nid]))
        if t3 is None:
            return None, f"block:{r2}"
        return t3, "ok"

    unwritable: set[str] = set()
    for _ in range(len(affected) + 1):
        plan: dict[str, str] = {}
        bad: set[str] = set()
        for nid in (affected - unwritable):
            content, reason = _compute(nid)
            if content is None:
                bad.add(nid)
                detail_rows.append({"note_id12": nid[:12], "skipped": reason})
            else:
                plan[nid] = content
        if not bad:
            break
        unwritable |= bad
        # drop relationships touching unwritable notes (no one-way links), then recompute
        kept = [(x, y, v) for (x, y, v) in pair_notes if x not in unwritable and y not in unwritable]
        links = {nid: set() for nid in facts}
        tags = {nid: set() for nid in facts}
        rel_of_note = {nid: set() for nid in facts}
        for x, y, v in kept:
            rt, conf = v["relationship_type"], float(v["confidence"])
            links[x].add(_link_line(facts[y], rt, conf))
            links[y].add(_link_line(facts[x], rt, conf))
            for nid, qtags in ((x, v["tags_for_source"]), (y, v["tags_for_target"])):
                tags[nid].update(ng.relationship_tags_for(rt))
                tags[nid].update(qtags)
                rel_of_note[nid].add(rt)
        pair_notes = kept
        affected = {nid for nid in facts if links[nid]}
        for nid in affected:
            tags[nid].update(ng.content_tags_for(facts[nid]))

    applied_pairs = len(pair_notes)
    result["relationships_applied"] = applied_pairs
    result["reciprocal_links_applied"] = applied_pairs * 2
    result["notes_modified"] = len(plan)
    # amendment 6: applied relationship types are the qwen-approved types — reported SEPARATELY from
    # candidate_basis_counts (the deterministic signals). A basis is never the applied relationship.
    result["applied_relationship_types"] = dict(sorted(
        Counter(v["relationship_type"] for (_x, _y, v) in pair_notes).items()))
    result["tags_added"] = sum(
        len([t for t in tags[nid] if t not in facts[nid].existing_tags][:8]) for nid in plan)

    if not args.apply:
        result["would_modify_notes"] = len(plan)
        result["would_add_reciprocal_links"] = applied_pairs * 2
        return {"safe": result, "detail_rows": detail_rows}

    # ---- APPLY: backup all, write all, rollback on any failure ---------------------------------
    backup_root = Path(args.backup_dir)
    written: list[tuple[Path, Path]] = []
    try:
        for nid, content in plan.items():
            target = vault_root / facts[nid].note_rel
            if not target.is_file():
                raise GraphError("apply would create a new card (target vanished)")
            bpath = backup_root / facts[nid].note_rel
            bpath.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, bpath)
            out = create_note(config, path=facts[nid].note_rel, content=content, overwrite=True,
                              create_parent_dirs=False, expected_sha256=sha256_file(target),
                              caller_surface="mcp", tool_name="apply_note_graph", principal_kind="local")
            if out.get("created"):
                raise GraphError("apply created a new card (expected 0)")
            written.append((target, bpath))
    except Exception as exc:
        for target, bpath in written:  # rollback
            try:
                shutil.copy2(bpath, target)
            except OSError:
                raise GraphError(f"rollback_failed after {exc}") from None
        raise GraphError(f"apply_failed_rolled_back ({exc})") from None

    q1, p1 = _queue_counts(args.db_path)
    fp_after = _db_fingerprint(args.db_path)
    result.update({"queue_after": q1, "queue_delta": q1 - q0,
                   "db_after": fp_after, "db_mutations": 0 if fp_after == fp_before else 1})
    if (q1 - q0) or (p1 - p0):
        raise GraphError("queue changed during apply")
    if fp_after != fp_before:
        raise GraphError("DB metadata changed during apply")

    # ---- backlink integrity: every applied relationship must be reciprocal on BOTH cards ----------
    verified, integrity_ok = 0, True
    for a_id, b_id, _v in pair_notes:
        a_text = (vault_root / facts[a_id].note_rel).read_text(encoding="utf-8")
        b_text = (vault_root / facts[b_id].note_rel).read_text(encoding="utf-8")
        if ng.build_wiki_link(facts[b_id]) in a_text and ng.build_wiki_link(facts[a_id]) in b_text:
            verified += 1
        else:
            integrity_ok = False
    result["backlinks_verified"] = verified
    result["backlink_integrity_passed"] = integrity_ok
    if not integrity_ok:
        raise GraphError("backlink_integrity_failed")
    return {"safe": result, "detail_rows": detail_rows}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db-path", required=True)
    p.add_argument("--config-path",
                   default=str(Path.home() / "Library/Application Support/HB Personal Assistant"
                              / "analytics/obsidian_mcp_config.json"))
    p.add_argument("--vault-path", required=True)
    p.add_argument("--model", default=ng.LOCAL_MODEL)
    p.add_argument("--max-notes", type=int, default=25)
    p.add_argument("--max-candidates-per-note", type=int, default=10)
    p.add_argument("--max-relationships", type=int, default=50)
    p.add_argument("--max-apply-relationships", type=int, default=25,
                   help="post-vet cap on relationships actually applied (distinct from candidate cap)")
    p.add_argument("--confidence-threshold", type=float, default=0.80)
    # bounded project selection (Phase 10G) — restricts the run to one project's Work source cards
    p.add_argument("--project-number", default="")
    p.add_argument("--project-key", default="")
    p.add_argument("--procore-project-id", default="")
    p.add_argument("--confirm-project-number", default="")
    p.add_argument("--confirm-project-key", default="")
    p.add_argument("--confirm-procore-project-id", default="")
    p.add_argument("--confirm-apply-approved-count", type=int, default=None,
                   help="post-vet checkpoint: must equal the vetted approved count when applying")
    p.add_argument("--timeout-seconds", type=float, default=None)
    p.add_argument("--backup-dir", default=None)
    p.add_argument("--evidence-dir", default=None)
    p.add_argument("--json-output", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--vet", action="store_true")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--confirm-db-path", default="")
    p.add_argument("--confirm-vault-path", default="")
    p.add_argument("--confirm-model", default="")
    p.add_argument("--require-empty-queue", action="store_true", default=True)
    p.add_argument("--no-require-empty-queue", dest="require_empty_queue", action="store_false")
    return p


def _render_review_report(safe: dict[str, Any]) -> str:
    """Count-only / redacted human-review report — no titles/paths/subjects/addresses/ids/names/qwen text."""
    def _dist(d: dict[str, Any]) -> str:
        return ", ".join(f"{k}: {v}" for k, v in sorted((d or {}).items())) or "none"
    lines = [
        "# Phase 10G — Bounded Note-Graph Apply — Review Report (safe / count-only)",
        "",
        f"- mode: {safe.get('mode')}",
        f"- eligibility_mode: {safe.get('eligibility_mode')}",
        f"- project_number: {safe.get('project_number') or 'none'}",
        f"- project_key: {safe.get('project_key') or 'none'}",
        f"- procore_project_id: {safe.get('procore_project_id') or 'none'}",
        "",
        "## Selection",
        f"- notes_selected: {safe.get('notes_selected')} "
        f"(project={safe.get('project_cards')}, email={safe.get('email_cards')}, "
        f"attachment={safe.get('attachment_cards')})",
        f"- selection_truncated: {safe.get('selection_truncated')}",
        f"- excluded_outside_project: {safe.get('excluded_outside_project')}",
        "",
        "## Candidates (deterministic basis — NOT applied relationships)",
        f"- candidate_pairs: {safe.get('candidate_pairs')}",
        f"- lineage_pairs_excluded: {safe.get('lineage_pairs_excluded')}",
        f"- duplicate_review_candidates (same-content, review-only): "
        f"{safe.get('duplicate_review_candidates')}",
        f"- candidate_basis_counts: {_dist(safe.get('candidate_basis_counts'))}",
        "",
        "## Vetting (local qwen2.5:14b, advisory)",
        f"- ollama_calls: {safe.get('ollama_calls')}",
        f"- vetted_pairs: {safe.get('vetted_pairs')}",
        f"- approved_pairs: {safe.get('approved_pairs')}",
        f"- rejection_reasons: {_dist(safe.get('rejection_reasons'))}",
        "",
        "## Applied (qwen-approved relationships — separate from basis)",
        f"- relationships_applied: {safe.get('relationships_applied')}",
        f"- reciprocal_links_applied: {safe.get('reciprocal_links_applied')}",
        f"- applied_relationship_types: {_dist(safe.get('applied_relationship_types'))}",
        f"- notes_modified: {safe.get('notes_modified')}",
        f"- tags_added: {safe.get('tags_added')}",
        f"- backlink_integrity_passed: {safe.get('backlink_integrity_passed')} "
        f"(verified={safe.get('backlinks_verified')})",
        "",
        "## Invariants",
        f"- queue_delta: {safe.get('queue_delta')}",
        f"- db_mutations: {safe.get('db_mutations')}",
        f"- created: {safe.get('created')}, deleted: {safe.get('deleted')}",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None, *,
         client_factory: Callable[[str, float], Any] = _default_client_factory) -> int:
    args = _build_parser().parse_args(argv)
    if args.apply and not args.backup_dir:
        print(json.dumps({"refused": True, "reason": "--apply requires --backup-dir"}), file=sys.stderr)
        return 3
    try:
        out = run(args, client_factory=client_factory)
    except GraphError as exc:
        print(json.dumps({"refused": True, "reason": str(exc)}, indent=2), file=sys.stderr)
        return 3
    safe, detail_rows = out["safe"], out["detail_rows"]
    if args.evidence_dir:
        ev = Path(args.evidence_dir)
        ev.mkdir(parents=True, exist_ok=True)
        mode = safe["mode"]
        (ev / f"note-graph-{mode}-summary-safe.json").write_text(
            json.dumps(safe, indent=2, sort_keys=True), encoding="utf-8")
        (ev / f"note-graph-{mode}-detail-local-sensitive.json").write_text(
            json.dumps({"rows": detail_rows}, indent=2, sort_keys=True), encoding="utf-8")
        (ev / "phase10g-review-report-safe.md").write_text(
            _render_review_report(safe), encoding="utf-8")
    print(json.dumps(safe, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    print("NOTE: Phase 10J consolidated local enrichment into scripts/obsidian_source_enrich.py "
          "(--backlinks); this standalone applier remains as the internal backlink engine.",
          file=sys.stderr)
    raise SystemExit(main())
