#!/usr/bin/env python3
"""Phase 10G/10H correction: reconcile Tropical source-card identity + inventory duplicates.

Bounded, deterministic, idempotent operations over the Tropical Work source-card set:

* ``--remove-duplicate-links`` (10G) — remove ONLY the offending gc-graph-links entries (relationship
  type in REVIEW_ONLY_TYPES, or a same-source/same-email DUPLICATE pair) from BOTH sides
  (reciprocal-or-neither). A valid link is never deleted; the block is removed only when it becomes
  empty. Graph tags stripped only when NO valid graph link remains.
* ``--reconcile-identity`` (10G) — reconcile Tropical EMAIL source cards (defined by the hb-email block)
  to their authoritative hb-project-identity block.
* ``--reconcile-all-tropical-identity`` (10H) — reconcile ALL Tropical Work source cards whose
  frontmatter or visible ``## Related Project`` text disagrees with an authoritative single
  hb-project-identity block resolving EXACTLY 23-435-01 / tropical / 2525840. Scope is the identity
  block (NOT the drift-prone analyzer document_type). Only frontmatter project fields + one
  ``project/23-435-01`` tag + the visible Related Project line may change; every managed block
  (hb-local-summary / hb-project-identity / hb-email / hb-email-attachment(s) / gc-graph-links /
  unknown) is byte-preserved; graph links/tags are never added, removed, or reordered.
* ``--duplicate-review-inventory`` (10H) — count-only inventory of duplicate-review pairs/clusters over
  the bounded set. Creates/changes nothing.

No source-file read, no scan, no queue/DB/runtime-JSON mutation, no card create/delete, no cloud model.
Backend on :8000 must be down for --apply. Dry-run default.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (_REPO_ROOT / "src", _REPO_ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import obsidian_source_first_indexing_dryrun as dryrun  # noqa: E402
import obsidian_source_note_apply_graph as ag  # noqa: E402  (reuse gates/fingerprint/selection helpers)

from hb_assistant.obsidian_mcp import source_note_graph as ng  # noqa: E402
from hb_assistant.obsidian_mcp import source_project_identity as pid  # noqa: E402
from hb_assistant.obsidian_mcp.mutations import create_note, sha256_file  # noqa: E402
from hb_assistant.obsidian_mcp.source_email_archive import parse_email_marker  # noqa: E402
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository  # noqa: E402

GraphError = ag.GraphError
_GRAPH_TAGS = sorted(ng.RELATED_TAGS | {"review/qwen-vetted"})
_TROPICAL = {"project_number": "23-435-01", "project_key": "tropical", "procore_project_id": "2525840"}


def _resolves_tropical(ident: dict[str, Any] | None) -> bool:
    return bool(ident and ident.get("project_number") == _TROPICAL["project_number"]
                and ident.get("project_key") == _TROPICAL["project_key"]
                and ident.get("procore_project_id") == _TROPICAL["procore_project_id"])


def _identity_block_count(text: str) -> int:
    return text.count(pid.IDENTITY_BEGIN_PREFIX)


def _link_target_rel(line: str) -> str | None:
    m = re.search(r"\[\[([^\]|]+)\|", line)
    if not m:
        return None
    tgt = m.group(1).strip()
    return tgt if tgt.endswith(".md") else tgt + ".md"


def _link_rel_type(line: str) -> str | None:
    m = re.search(r"—\s*([a-z_]+)\s*·", line)
    return m.group(1) if m else None


def _select(repo: SourceIndexRepository, vault_root: Path, args: argparse.Namespace,
            ) -> tuple[dict[str, ng.NoteFact], dict[str, str]]:
    """Bounded Tropical Work selection (mirrors the applier)."""
    prefix = "Source Notes/Work/"
    rows = sorted((r for r in repo.list_generated_notes(statuses=("generated",))
                   if str(r.get("note_rel_path") or "").startswith(prefix)),
                  key=lambda r: str(r["note_rel_path"]))
    facts: dict[str, ng.NoteFact] = {}
    text_by_id: dict[str, str] = {}
    for row in rows:
        target = vault_root / str(row["note_rel_path"])
        if not target.is_file():
            raise GraphError("selected card file is missing")
        text = target.read_text(encoding="utf-8")
        f = ng.note_fact_from(repo, row, text)
        if not ag._matches_project(f, args):
            continue
        facts[f.note_id] = f
        text_by_id[f.note_id] = text
    return facts, text_by_id


def _plan_removals(facts: dict[str, ng.NoteFact], text_by_id: dict[str, str],
                   detail_rows: list[dict[str, Any]],
                   ) -> tuple[dict[str, str], dict[str, Any]]:
    """Build {note_id: new_text} removing offending entries reciprocally + conditional tag strip."""
    rel_to_id = {f.note_rel: nid for nid, f in facts.items()}
    offending: dict[frozenset[str], str] = {}
    for nid, f in facts.items():
        entries = ng.related_block_entries(text_by_id[nid])
        if not entries:
            continue
        for line in entries:
            tgt = _link_target_rel(line)
            partner = rel_to_id.get(tgt) if tgt else None
            if partner is None:
                continue
            rtype = _link_rel_type(line)
            reason = None
            if rtype in ng.REVIEW_ONLY_TYPES:
                reason = f"banned_type:{rtype}"
            elif ng.is_duplicate_pair(ng._pair_signals(f, facts[partner])):
                reason = "duplicate_pair"
            if reason:
                offending[frozenset((nid, partner))] = reason

    plan: dict[str, str] = {}
    tags_stripped = 0
    for pair, reason in offending.items():
        a_id, b_id = tuple(pair)
        detail_rows.append({"pair": sorted(x[:12] for x in (a_id, b_id)), "reason": reason})
        for x, y in ((a_id, b_id), (b_id, a_id)):
            base = plan.get(x, text_by_id[x])
            nt, r = ng.remove_related_link(base, target_rel=facts[y].note_rel)
            if nt is None:
                raise GraphError(f"remove_related_link:{r}")
            # strip graph tags ONLY when no valid graph link remains on this card
            if not ng.related_block_entries(nt):
                tnt, tr = ng.remove_frontmatter_tags(nt, _GRAPH_TAGS)
                if tnt is None:
                    raise GraphError(f"remove_frontmatter_tags:{tr}")
                if tr == "removed":
                    tags_stripped += 1
                nt = tnt
            plan[x] = nt
    return plan, {"offending_pairs": len(offending),
                  "reasons": dict(sorted(Counter(offending.values()).items())),
                  "graph_tag_notes_stripped": tags_stripped}


def _plan_identity(facts: dict[str, ng.NoteFact], text_by_id: dict[str, str],
                   plan: dict[str, str]) -> dict[str, Any]:
    """Reconcile disagreeing Tropical email cards to their authoritative identity block."""
    scanned = disagreeing = reconciled = skipped = 0
    for nid in facts:
        base = plan.get(nid, text_by_id[nid])
        # An EMAIL source card is defined by the presence of the managed hb-email block (Phase 10E) —
        # NOT the live analyzer document_type, which can drift and mislabel general_document/submittal
        # cards as "email". Scoping on the block prevents modifying non-email cards.
        if parse_email_marker(base) is None:
            continue
        scanned += 1
        ident = pid.parse_identity_marker(base)
        if not ident or not ident.get("project_key") or not ident.get("project_number"):
            skipped += 1  # no resolving identity block -> out of scope, never touched
            continue
        if (ident["project_number"] != _TROPICAL["project_number"]
                or ident["project_key"] != _TROPICAL["project_key"]):
            raise GraphError("email card resolves a non-Tropical identity")
        nt, r = pid.reconcile_card_identity(base)
        if r == "reconciled":
            disagreeing += 1
            reconciled += 1
            plan[nid] = nt
        elif r == "already_consistent":
            pass
        else:
            skipped += 1
    return {"email_cards_scanned": scanned, "email_cards_disagreeing": disagreeing,
            "email_cards_reconciled": reconciled, "email_cards_skipped": skipped}


def _plan_all_tropical_identity(facts: dict[str, ng.NoteFact], text_by_id: dict[str, str],
                               plan: dict[str, str]) -> dict[str, Any]:
    """Reconcile ALL Tropical Work source cards to their authoritative identity block (Phase 10H).

    Scope is the hb-project-identity block (NOT analyzer document_type): eligible iff exactly one block
    resolving EXACTLY Tropical AND frontmatter/visible text disagrees. Reuses the 10G block-authoritative
    reconcile helper, so the visible line + frontmatter format match the already-reconciled cards.
    """
    scanned = with_block = disagreeing = corrected = 0
    fm_dis = vt_dis = email_dis = nonemail_dis = 0
    email_corr = nonemail_corr = tags_added = 0
    skip_no_id = skip_ambiguous = skip_other = 0
    for nid in facts:
        base = plan.get(nid, text_by_id[nid])
        scanned += 1
        nblocks = _identity_block_count(base)
        if nblocks == 0:
            skip_no_id += 1
            continue
        ident = pid.parse_identity_marker(base)
        if nblocks > 1 or not ident or not ident.get("project_key") or not ident.get("project_number"):
            skip_ambiguous += 1  # duplicate / malformed / unparseable identity block
            continue
        if not _resolves_tropical(ident):
            skip_other += 1  # resolves a different project (or missing procore)
            continue
        with_block += 1
        num, key = ident["project_number"], ident["project_key"]
        fm_changed = pid.reconcile_frontmatter_identity(base, project_number=num, project_key=key) != base
        vt_changed = pid.reconcile_related_project_text(base, project_number=num, project_key=key) != base
        if not (fm_changed or vt_changed):
            continue  # already_consistent — byte-identical, never re-touched
        is_email = parse_email_marker(base) is not None
        fm_dis += int(fm_changed)
        vt_dis += int(vt_changed)
        disagreeing += 1
        email_dis += int(is_email)
        nonemail_dis += int(not is_email)
        _ok, tags_before, _f, _l = ng.parse_frontmatter_tags(base)
        nt, r = pid.reconcile_card_identity(base)
        if r != "reconciled" or nt is None:
            skip_ambiguous += 1  # defensive: unexpected non-reconcile despite detected disagreement
            continue
        _ok2, tags_after, _f2, _l2 = ng.parse_frontmatter_tags(nt)
        if "project/23-435-01" in tags_after and "project/23-435-01" not in tags_before:
            tags_added += 1
        corrected += 1
        email_corr += int(is_email)
        nonemail_corr += int(not is_email)
        plan[nid] = nt
    return {"cards_scanned": scanned, "tropical_identity_cards": with_block,
            "cards_disagreeing": disagreeing, "frontmatter_disagreements": fm_dis,
            "related_project_text_disagreements": vt_dis,
            "email_cards_disagreeing": email_dis, "non_email_cards_disagreeing": nonemail_dis,
            "cards_corrected": corrected, "email_cards_corrected": email_corr,
            "non_email_cards_corrected": nonemail_corr, "project_tags_added": tags_added,
            "cards_skipped_no_identity": skip_no_id,
            "cards_skipped_ambiguous_identity": skip_ambiguous,
            "cards_skipped_other_project": skip_other}


def _duplicate_inventory(facts: dict[str, ng.NoteFact],
                         detail_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Count-only duplicate-review inventory over the bounded set. Creates/changes nothing.

    A pair sharing multiple duplicate signals counts ONCE in duplicate_review_pairs while contributing
    to each applicable per-signal count. Clusters are connected components over duplicate edges.
    """
    fl = list(facts.values())
    pairs: dict[frozenset[str], set[str]] = {}
    for i, a in enumerate(fl):
        for b in fl[i + 1:]:
            sigs = {s for s in ng._pair_signals(a, b) if s in ng.DUPLICATE_SIGNALS}
            if sigs:
                pairs[frozenset((a.note_id, b.note_id))] = sigs
    per = {"same_source_sha256": 0, "same_message_id_hash": 0, "same_attachment_sha256": 0}
    for sigs in pairs.values():
        for s in sigs:
            if s in per:
                per[s] += 1
    # union-find over duplicate edges
    parent = {nid: nid for nid in facts}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for key in pairs:
        a, b = tuple(key)
        parent[find(a)] = find(b)
    nodes_in_pairs: set[str] = set()
    for key in pairs:
        nodes_in_pairs |= set(key)
    clusters: dict[str, list[str]] = {}
    for n in nodes_in_pairs:
        clusters.setdefault(find(n), []).append(n)
    sizes = [len(v) for v in clusters.values()]
    detail_rows.append({
        "duplicate_pairs": [{"pair": sorted(x[:12] for x in k), "signals": sorted(v)}
                            for k, v in pairs.items()],
        "clusters": [sorted(x[:12] for x in v) for v in clusters.values()]})
    return {"duplicate_review_pairs": len(pairs),
            "same_source_sha256_pairs": per["same_source_sha256"],
            "same_email_message_id_pairs": per["same_message_id_hash"],
            "same_attachment_sha_pairs": per["same_attachment_sha256"],
            "duplicate_clusters": len(clusters),
            "largest_cluster_size": max(sizes) if sizes else 0}


def run(args: argparse.Namespace) -> dict[str, Any]:
    vault_root = Path(args.vault_path).resolve()
    config = dryrun._load_config(args.config_path)
    if Path(str(config.vault_root or "")).resolve() != vault_root:
        raise GraphError("config vault_root does not match --vault-path")
    if not (args.project_number or args.project_key or args.procore_project_id):
        raise GraphError("correction requires bounded project selection")
    repo = SourceIndexRepository(args.db_path)
    fp_before = ag._db_fingerprint(args.db_path)
    q0, p0 = ag._queue_counts(args.db_path)

    facts, text_by_id = _select(repo, vault_root, args)
    detail_rows: list[dict[str, Any]] = []
    result: dict[str, Any] = {"mode": "apply" if args.apply else "dry-run",
                              "notes_selected": len(facts),
                              "db_before": fp_before, "db_mutations": 0, "queue_delta": 0,
                              "created": 0, "deleted": 0, "new_cards": 0,
                              "links_added": 0, "links_removed": 0, "tags_added": 0,
                              "runtime_json_mutated": False, "ollama_calls": 0}

    plan: dict[str, str] = {}
    if args.remove_duplicate_links:
        rplan, rstats = _plan_removals(facts, text_by_id, detail_rows)
        plan.update(rplan)
        result.update(rstats)
        result["links_removed"] = rstats["offending_pairs"] * 2
    if args.reconcile_identity:
        result.update(_plan_identity(facts, text_by_id, plan))
    if args.reconcile_all_tropical_identity:
        stats = _plan_all_tropical_identity(facts, text_by_id, plan)
        result.update(stats)
        result["tags_added"] = stats["project_tags_added"]
    if args.duplicate_review_inventory:
        result.update(_duplicate_inventory(facts, detail_rows))
    result["notes_modified"] = len(plan)

    if args.apply:
        if not (args.confirm_db_path == args.db_path and args.confirm_vault_path == args.vault_path):
            raise GraphError("--apply requires matching --confirm-db-path/--confirm-vault-path")
        if not ((args.confirm_project_number or None) == (args.project_number or None)
                and (args.confirm_project_key or None) == (args.project_key or None)
                and (args.confirm_procore_project_id or None) == (args.procore_project_id or None)):
            raise GraphError("--apply requires matching --confirm-project-* flags")
        if any(getattr(config, f, False) for f in ag._FROZEN_FLAGS):
            raise GraphError("runtime frozen flags are not all false")
        if ag._backend_listening():
            raise GraphError("backend listening on port 8000")
        if args.require_empty_queue and (q0 or p0):
            raise GraphError(f"queue not empty (queued={q0}, processing={p0})")

        backup_root = Path(args.backup_dir)
        written: list[tuple[Path, Path]] = []
        try:
            for nid, content in plan.items():
                target = vault_root / facts[nid].note_rel
                if not target.is_file():
                    raise GraphError("target vanished")
                # apply-time ambiguity guard: any card we write that carries an identity block MUST
                # still have exactly one block resolving EXACTLY Tropical — else hard-stop + rollback.
                if pid.IDENTITY_BEGIN_PREFIX in content and (
                        content.count(pid.IDENTITY_BEGIN_PREFIX) != 1
                        or not _resolves_tropical(pid.parse_identity_marker(content))):
                    raise GraphError("identity ambiguity or non-Tropical resolve at write time")
                bpath = backup_root / facts[nid].note_rel
                bpath.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, bpath)
                out = create_note(config, path=facts[nid].note_rel, content=content, overwrite=True,
                                  create_parent_dirs=False, expected_sha256=sha256_file(target),
                                  caller_surface="mcp", tool_name="correct_note_graph",
                                  principal_kind="local")
                if out.get("created"):
                    raise GraphError("correction created a new card (expected 0)")
                written.append((target, bpath))
        except Exception as exc:
            for target, bpath in written:
                try:
                    shutil.copy2(bpath, target)
                except OSError:
                    raise GraphError(f"rollback_failed after {exc}") from None
            raise GraphError(f"correction_failed_rolled_back ({exc})") from None

        q1, p1 = ag._queue_counts(args.db_path)
        fp_after = ag._db_fingerprint(args.db_path)
        result.update({"queue_delta": q1 - q0, "db_mutations": 0 if fp_after == fp_before else 1})
        if (q1 - q0) or (p1 - p0):
            raise GraphError("queue changed during correction")
        if fp_after != fp_before:
            raise GraphError("DB metadata changed during correction")
        # backlink integrity: no offending link (and thus no one-way link) may remain
        remaining = _plan_removals(*_reload(facts, vault_root), [])[1]["offending_pairs"] \
            if args.remove_duplicate_links else 0
        result["offending_links_remaining"] = remaining
        if remaining:
            raise GraphError("offending links remain after correction")
    return {"safe": result, "detail_rows": detail_rows}


def _reload(facts: dict[str, ng.NoteFact], vault_root: Path) -> tuple[dict[str, ng.NoteFact], dict[str, str]]:
    """Re-read the affected cards from disk (post-write) for the integrity re-scan."""
    return facts, {nid: (vault_root / f.note_rel).read_text(encoding="utf-8")
                   for nid, f in facts.items()}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db-path", required=True)
    p.add_argument("--config-path",
                   default=str(Path.home() / "Library/Application Support/HB Personal Assistant"
                              / "analytics/obsidian_mcp_config.json"))
    p.add_argument("--vault-path", required=True)
    p.add_argument("--model", default=ng.LOCAL_MODEL)  # unused; kept for parity
    p.add_argument("--project-number", default="")
    p.add_argument("--project-key", default="")
    p.add_argument("--procore-project-id", default="")
    p.add_argument("--confirm-db-path", default="")
    p.add_argument("--confirm-vault-path", default="")
    p.add_argument("--confirm-project-number", default="")
    p.add_argument("--confirm-project-key", default="")
    p.add_argument("--confirm-procore-project-id", default="")
    p.add_argument("--backup-dir", default=None)
    p.add_argument("--evidence-dir", default=None)
    p.add_argument("--remove-duplicate-links", action="store_true")
    p.add_argument("--reconcile-identity", action="store_true")
    p.add_argument("--reconcile-all-tropical-identity", action="store_true")
    p.add_argument("--duplicate-review-inventory", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--require-empty-queue", action="store_true", default=True)
    p.add_argument("--no-require-empty-queue", dest="require_empty_queue", action="store_false")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.apply and not args.backup_dir:
        print(json.dumps({"refused": True, "reason": "--apply requires --backup-dir"}), file=sys.stderr)
        return 3
    if not (args.remove_duplicate_links or args.reconcile_identity
            or args.reconcile_all_tropical_identity or args.duplicate_review_inventory):
        print(json.dumps({"refused": True, "reason": "choose at least one mode: "
                          "--remove-duplicate-links / --reconcile-identity / "
                          "--reconcile-all-tropical-identity / --duplicate-review-inventory"}),
              file=sys.stderr)
        return 3
    try:
        out = run(args)
    except GraphError as exc:
        print(json.dumps({"refused": True, "reason": str(exc)}, indent=2), file=sys.stderr)
        return 3
    safe, detail_rows = out["safe"], out["detail_rows"]
    if args.evidence_dir:
        ev = Path(args.evidence_dir)
        ev.mkdir(parents=True, exist_ok=True)
        mode = safe["mode"]
        (ev / f"note-graph-correction-{mode}-summary-safe.json").write_text(
            json.dumps(safe, indent=2, sort_keys=True), encoding="utf-8")
        (ev / f"note-graph-correction-{mode}-detail-local-sensitive.json").write_text(
            json.dumps({"rows": detail_rows}, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(safe, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
