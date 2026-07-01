#!/usr/bin/env python3
"""Phase 10I — Graph review + operator controls (READ-ONLY).

Read-only inspection surfaces over the bounded Tropical Work source-card graph. Reports COUNTS and
distributions only (never titles/paths/subjects/addresses/message-ids/attachment-names/bodies/qwen text)
and renders a design spec for FUTURE operator controls. Executes NOTHING: no graph link/tag apply or
removal, no duplicate delete/merge/rename/move, no identity write, no card generation, no source
indexing, no attachment extraction, no advisory summaries, no Qwen/Ollama call, no DB write, no runtime
JSON write.

Reading generated Work source-card note text (the `.md` cards under ``Source Notes/Work/``) IS allowed;
reading original source files / attachment binaries / ``.eml`` / ``Email Archive/`` notes / source
payloads is NOT — this tool only reads generated cards (via the DB index) plus read-only DB counts.

Modes (compose under ``--all``): ``--duplicate-clusters`` ``--relationship-candidates``
``--existing-links`` ``--identity-quality`` ``--isolated-high-value``.
Output: ``--json-output`` (default; sorted count-only dict to stdout) and/or ``--markdown-report``.
Safety: ``--dry-run`` (default; writes nothing) vs ``--write-review-report`` (writes ONLY the safe
evidence report + local-sensitive detail rows under ``--evidence-dir``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (_REPO_ROOT / "src", _REPO_ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import obsidian_source_first_indexing_dryrun as dryrun  # noqa: E402
import obsidian_source_note_apply_graph as ag  # noqa: E402  (reuse gates/fingerprint/classify)
import obsidian_source_note_correct_graph as cg  # noqa: E402  (reuse selection/inventory/identity)

from hb_assistant.obsidian_mcp import source_note_graph as ng  # noqa: E402
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository  # noqa: E402

GraphError = ag.GraphError

# High-value source-card document types for the isolated-card scorecard (deterministic analyzer types).
_HIGH_VALUE_DOCTYPES = frozenset({
    "email", "submittal", "rfi", "meeting_minutes", "cost_report", "cost_document", "pay_application",
    "change_order", "potential_change_order", "contract", "subcontract", "purchase_order", "schedule",
    "architectural_drawing", "structural_drawing", "mep_drawing", "civil_drawing", "drawing",
    "invoice", "bid_package", "scope_of_work",
})
_VALID_GRAPH_TAGS = ng.RELATED_TAGS | ng.REVIEW_TAGS

# Future operator controls (Phase 10J). Pure data: Phase 10I lists these, executes NONE.
OPERATOR_CONTROL_DESIGN: dict[str, list[str]] = {
    "duplicate": ["mark_duplicate", "mark_not_duplicate", "choose_canonical", "defer", "merge_later",
                  "delete_later"],
    "relationship": ["accept_relationship", "reject_relationship", "defer_relationship",
                     "rollback_relationship", "explain_relationship"],
    "identity": ["mark_identity_verified", "mark_identity_wrong", "request_reconcile"],
    "rollback": ["preview_rollback", "apply_rollback", "export_rollback_bundle"],
}


def _link_target_rel(line: str) -> str | None:
    m = re.search(r"\[\[([^\]|]+)\|", line)
    if not m:
        return None
    tgt = m.group(1).strip()
    return tgt if tgt.endswith(".md") else tgt + ".md"


def _link_rel_type(line: str) -> str | None:
    m = re.search(r"—\s*([a-z_]+)\s*·", line)
    return m.group(1) if m else None


# --------------------------------------------------------------------------- review analyzers (read-only)

def _identity_quality(facts: dict[str, ng.NoteFact], text_by_id: dict[str, str]) -> dict[str, Any]:
    """Identity scorecard over the bounded set. Reuses the 10H planner purely for its stats — the throwaway
    plan is discarded and NOTHING is written."""
    st = cg._plan_all_tropical_identity(facts, text_by_id, {})  # plan dict discarded → no write
    scanned = st["cards_scanned"]
    inconsistent = st["cards_disagreeing"]
    ambiguous = st["cards_skipped_ambiguous_identity"]
    missing = st["cards_skipped_no_identity"]
    other = st["cards_skipped_other_project"]
    consistent = scanned - inconsistent - ambiguous - missing - other
    return {"cards_checked": scanned, "identity_consistent": consistent,
            "identity_inconsistent": inconsistent, "ambiguous_identity_blocks": ambiguous,
            "missing_identity_blocks": missing, "non_tropical_in_selection": other}


def _duplicate_clusters(facts: dict[str, ng.NoteFact],
                        detail_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Duplicate-review inventory (reuses the 10H count-only helper) + size buckets + stable cluster ids."""
    stats = cg._duplicate_inventory(facts, detail_rows)  # appends {duplicate_pairs, clusters} detail row
    clusters = detail_rows[-1]["clusters"] if detail_rows else []
    s2 = sum(1 for c in clusters if len(c) == 2)
    s35 = sum(1 for c in clusters if 3 <= len(c) <= 5)
    s6 = sum(1 for c in clusters if len(c) >= 6)
    # deterministic cluster ids from the sorted member-hash set (stable across runs; no persistence)
    ids = sorted(hashlib.sha256("|".join(sorted(c)).encode()).hexdigest()[:12] for c in clusters)
    detail_rows.append({"cluster_ids": ids})
    return {**stats, "clusters_size_2": s2, "clusters_size_3_to_5": s35, "clusters_size_6_plus": s6}


def _existing_links(facts: dict[str, ng.NoteFact], text_by_id: dict[str, str],
                    detail_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Read-only integrity of existing gc-graph-links blocks. Reports defects; fixes nothing."""
    rel_to_id = {f.note_rel: nid for nid, f in facts.items()}
    entries_by_id: dict[str, list[str]] = {}
    graph_blocks = ambiguous_blocks = relationships = 0
    duplicate_entries = invalid_relationship_types = 0
    durable_same_project = durable_duplicate = invalid_tags = 0
    for nid, text in text_by_id.items():
        bounds = ng._related_block_bounds(text.splitlines())
        if bounds == "ambiguous":
            ambiguous_blocks += 1
        entries = ng.related_block_entries(text)
        if entries:
            graph_blocks += 1
            entries_by_id[nid] = entries
            relationships += len(entries)
            seen: Counter[str] = Counter(ln.strip() for ln in entries)
            duplicate_entries += sum(n - 1 for n in seen.values() if n > 1)
            for line in entries:
                rtype = _link_rel_type(line)
                if rtype is None or rtype not in ng.RELATIONSHIP_TYPES:
                    invalid_relationship_types += 1
                elif rtype == "same_project":
                    durable_same_project += 1
                elif rtype in (ng.REVIEW_ONLY_TYPES - {"same_project"}):
                    durable_duplicate += 1
        _ok, tags, _f, _l = ng.parse_frontmatter_tags(text)
        for t in tags:
            if (t.startswith("related/") or t.startswith("review/")) and t not in _VALID_GRAPH_TAGS:
                invalid_tags += 1
    # reciprocity: every directed link A→B needs a B→A entry in the partner's block
    one_way_links = 0
    for nid, entries in entries_by_id.items():
        my_rel = facts[nid].note_rel
        for line in entries:
            tgt = _link_target_rel(line)
            partner = rel_to_id.get(tgt) if tgt else None
            back = entries_by_id.get(partner, []) if partner else []
            if not any(_link_target_rel(bl) == my_rel for bl in back):
                one_way_links += 1
    detail_rows.append({"cards_with_graph_block": sorted(nid[:12] for nid in entries_by_id)})
    return {"graph_blocks": graph_blocks, "ambiguous_graph_blocks": ambiguous_blocks,
            "relationships": relationships, "reciprocal_pass": one_way_links == 0,
            "one_way_links": one_way_links, "duplicate_entries": duplicate_entries,
            "invalid_relationship_types": invalid_relationship_types,
            "durable_same_project_links": durable_same_project,
            "durable_duplicate_links": durable_duplicate, "invalid_tags": invalid_tags}


def _relationship_candidates(facts: dict[str, ng.NoteFact]) -> dict[str, Any]:
    """Deterministic candidate review. NO model call — reports counts + basis only (ollama_calls: 0)."""
    fl = list(facts.values())
    candidate_pairs = primary_secondary = weak_only = project_only = duplicate_pairs = 0
    basis: Counter[str] = Counter()
    project_ctx = {"same_project_number", "same_project_key", "same_procore_id", "same_date_same_project"}
    for i, a in enumerate(fl):
        for b in fl[i + 1:]:
            signals = ng._pair_signals(a, b)
            if ng.is_duplicate_pair(signals):
                duplicate_pairs += 1
                continue
            default_ok, _ = ng.is_candidate(a, b, mode="default")
            ps_ok, _ = ng.is_candidate(a, b, mode="primary_secondary")
            if default_ok:
                candidate_pairs += 1
                for s in signals:
                    basis[s] += 1
            if ps_ok:
                primary_secondary += 1
            # rejection lenses (independent of the eligibility counts above): a pair with only weak
            # signals, or one whose strong signals are all project-context and thus not durable-eligible
            # (routed to the review-only same_project family), never becomes a durable link.
            strong = [s for s in signals if s not in ng._WEAK_SIGNALS]
            if signals and not strong:
                weak_only += 1
            elif strong and not ps_ok and all(s in project_ctx for s in strong):
                project_only += 1
    return {"candidate_pairs": candidate_pairs, "primary_secondary_eligible": primary_secondary,
            "weak_only_rejected": weak_only, "project_only_rejected": project_only,
            "duplicate_review_pairs": duplicate_pairs,
            "would_require_human_review": candidate_pairs, "ollama_calls": 0,
            "candidate_basis_counts": dict(sorted(basis.items()))}


def _isolated_high_value(facts: dict[str, ng.NoteFact],
                         text_by_id: dict[str, str]) -> dict[str, Any]:
    """Count high-value source cards that carry no gc-graph-links relationships. Read-only."""
    isolated = iso_high = iso_email = iso_att = iso_sub_rfi = 0
    for nid, f in facts.items():
        if ng.related_block_entries(text_by_id[nid]):
            continue  # has ≥1 graph link → not isolated
        isolated += 1
        kind = ag._classify(f)
        if f.disposition == "auto_card_high":
            iso_high += 1
        if kind == "email":
            iso_email += 1
        elif kind == "attachment":
            iso_att += 1
        if f.document_type in ("submittal", "rfi"):
            iso_sub_rfi += 1
    return {"isolated_cards": isolated, "isolated_high_value_cards": iso_high,
            "isolated_email_cards": iso_email, "isolated_attachment_cards": iso_att,
            "isolated_submittal_or_rfi_cards": iso_sub_rfi}


# --------------------------------------------------------------------------- orchestration (read-only)

def _card_shas(text_by_id: dict[str, str]) -> dict[str, str]:
    return {nid: hashlib.sha256(t.encode()).hexdigest() for nid, t in text_by_id.items()}


def run(args: argparse.Namespace) -> dict[str, Any]:
    vault_root = Path(args.vault_path).resolve()
    config = dryrun._load_config(args.config_path)
    if Path(str(config.vault_root or "")).resolve() != vault_root:
        raise GraphError("config vault_root does not match --vault-path")
    if not (args.project_number or args.project_key or args.procore_project_id):
        raise GraphError("review requires bounded project selection")
    do = {"duplicate_clusters", "relationship_candidates", "existing_links",
          "identity_quality", "isolated_high_value"} if args.all else {
        k for k in ("duplicate_clusters", "relationship_candidates", "existing_links",
                    "identity_quality", "isolated_high_value") if getattr(args, k)}
    if not do:
        raise GraphError("choose at least one mode (or --all)")
    if args.vet and not (args.confirm_local_vet and args.model):
        raise GraphError("--vet requires --model and --confirm-local-vet (vetting deferred to Phase 10J)")

    repo = SourceIndexRepository(args.db_path)
    fp_before = ag._db_fingerprint(args.db_path)
    q0, p0 = ag._queue_counts(args.db_path)
    cfg_sha_before = hashlib.sha256(Path(args.config_path).read_bytes()).hexdigest()[:12]

    facts, text_by_id = cg._select(repo, vault_root, args)
    sha_before = _card_shas(text_by_id)

    detail_rows: list[dict[str, Any]] = []
    result: dict[str, Any] = {"mode": "review", "cards_checked": len(facts),
                              "cards_modified": 0, "db_mutations": 0, "queue_delta": 0,
                              "runtime_json_mutated": False, "ollama_calls": 0,
                              "vet_requested": bool(args.vet)}
    if args.vet:
        result["vetting_status"] = "deferred_to_10j_no_model_call"

    if "identity_quality" in do:
        result.update(_identity_quality(facts, text_by_id))
    if "duplicate_clusters" in do:
        result.update(_duplicate_clusters(facts, detail_rows))
    if "existing_links" in do:
        result.update(_existing_links(facts, text_by_id, detail_rows))
    if "relationship_candidates" in do:
        result.update(_relationship_candidates(facts))
    if "isolated_high_value" in do:
        result.update(_isolated_high_value(facts, text_by_id))

    # ---- pre/post mutation proof: nothing on disk or in the DB may have changed --------------------
    after = {nid: (vault_root / facts[nid].note_rel).read_text(encoding="utf-8") for nid in facts}
    sha_after = _card_shas(after)
    result["cards_modified"] = sum(1 for nid in sha_before if sha_before[nid] != sha_after.get(nid))
    fp_after = ag._db_fingerprint(args.db_path)
    q1, p1 = ag._queue_counts(args.db_path)
    result["db_mutations"] = 0 if fp_after == fp_before else 1
    result["queue_delta"] = (q1 - q0) + (p1 - p0)
    cfg_sha_after = hashlib.sha256(Path(args.config_path).read_bytes()).hexdigest()[:12]
    result["runtime_json_mutated"] = cfg_sha_after != cfg_sha_before
    if result["cards_modified"] or result["db_mutations"] or result["queue_delta"] \
            or result["runtime_json_mutated"]:
        raise GraphError("read-only invariant violated: something changed during review")
    return {"safe": result, "detail_rows": detail_rows}


# --------------------------------------------------------------------------- safe report renderer

def _render_phase10i_report(safe: dict[str, Any]) -> str:
    """Count-only / redacted Phase 10I review report. Reads ONLY known count keys — never echoes
    arbitrary values, so sensitive strings stuffed into unknown keys can never leak."""
    def g(k: str) -> Any:
        return safe.get(k, "n/a")

    def dist(k: str) -> str:
        d = safe.get(k)
        return ", ".join(f"{kk}: {vv}" for kk, vv in sorted(d.items())) if isinstance(d, dict) else "none"

    design = "; ".join(f"{dom}: {', '.join(acts)}" for dom, acts in sorted(OPERATOR_CONTROL_DESIGN.items()))
    return "\n".join([
        "# Phase 10I Graph Review Report (safe / count-only)",
        "",
        "## Scope",
        f"- mode: {g('mode')}",
        f"- cards_checked: {g('cards_checked')}",
        "",
        "## Runtime Preconditions",
        f"- db_mutations: {g('db_mutations')}",
        f"- queue_delta: {g('queue_delta')}",
        f"- runtime_json_mutated: {g('runtime_json_mutated')}",
        f"- cards_modified: {g('cards_modified')}",
        f"- ollama_calls: {g('ollama_calls')}",
        "",
        "## Corpus Summary",
        f"- cards_checked: {g('cards_checked')}",
        "",
        "## Identity Quality",
        f"- identity_consistent: {g('identity_consistent')}",
        f"- identity_inconsistent: {g('identity_inconsistent')}",
        f"- ambiguous_identity_blocks: {g('ambiguous_identity_blocks')}",
        f"- missing_identity_blocks: {g('missing_identity_blocks')}",
        f"- non_tropical_in_selection: {g('non_tropical_in_selection')}",
        "",
        "## Existing Graph Integrity",
        f"- graph_blocks: {g('graph_blocks')}",
        f"- relationships: {g('relationships')}",
        f"- reciprocal_pass: {g('reciprocal_pass')}",
        f"- one_way_links: {g('one_way_links')}",
        f"- duplicate_entries: {g('duplicate_entries')}",
        f"- invalid_relationship_types: {g('invalid_relationship_types')}",
        f"- durable_same_project_links: {g('durable_same_project_links')}",
        f"- durable_duplicate_links: {g('durable_duplicate_links')}",
        f"- invalid_tags: {g('invalid_tags')}",
        "",
        "## Duplicate Review Inventory",
        f"- duplicate_review_pairs: {g('duplicate_review_pairs')}",
        f"- same_source_sha256_pairs: {g('same_source_sha256_pairs')}",
        f"- same_email_message_id_pairs: {g('same_email_message_id_pairs')}",
        f"- same_attachment_sha_pairs: {g('same_attachment_sha_pairs')}",
        f"- duplicate_clusters: {g('duplicate_clusters')}",
        f"- largest_cluster_size: {g('largest_cluster_size')}",
        f"- clusters_size_2: {g('clusters_size_2')}",
        f"- clusters_size_3_to_5: {g('clusters_size_3_to_5')}",
        f"- clusters_size_6_plus: {g('clusters_size_6_plus')}",
        "",
        "## Relationship Candidate Review",
        f"- candidate_pairs: {g('candidate_pairs')}",
        f"- primary_secondary_eligible: {g('primary_secondary_eligible')}",
        f"- weak_only_rejected: {g('weak_only_rejected')}",
        f"- project_only_rejected: {g('project_only_rejected')}",
        f"- would_require_human_review: {g('would_require_human_review')}",
        f"- candidate_basis_counts: {dist('candidate_basis_counts')}",
        "",
        "## Isolated High-Value Cards",
        f"- isolated_cards: {g('isolated_cards')}",
        f"- isolated_high_value_cards: {g('isolated_high_value_cards')}",
        f"- isolated_email_cards: {g('isolated_email_cards')}",
        f"- isolated_attachment_cards: {g('isolated_attachment_cards')}",
        f"- isolated_submittal_or_rfi_cards: {g('isolated_submittal_or_rfi_cards')}",
        "",
        "## Operator Control Design",
        f"- future_actions (Phase 10J; executed_in_10i: false): {design}",
        "",
        "## Recommended Next Actions",
        "- Phase 10J: implement operator actions (accept/reject queue, duplicate-cluster decisions,",
        "  explicit rollback, project graph dashboard) driven from these read-only surfaces.",
        "",
        "## Guardrails Verified",
        f"- cards_modified: {g('cards_modified')}, db_mutations: {g('db_mutations')}, "
        f"queue_delta: {g('queue_delta')}, runtime_json_mutated: {g('runtime_json_mutated')}, "
        f"ollama_calls: {g('ollama_calls')}",
        "",
    ])


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db-path", required=True)
    p.add_argument("--config-path",
                   default=str(Path.home() / "Library/Application Support/HB Personal Assistant"
                              / "analytics/obsidian_mcp_config.json"))
    p.add_argument("--vault-path", required=True)
    p.add_argument("--project-number", default="")
    p.add_argument("--project-key", default="")
    p.add_argument("--procore-project-id", default="")
    p.add_argument("--duplicate-clusters", action="store_true")
    p.add_argument("--relationship-candidates", action="store_true")
    p.add_argument("--existing-links", action="store_true")
    p.add_argument("--identity-quality", action="store_true")
    p.add_argument("--isolated-high-value", action="store_true")
    p.add_argument("--all", action="store_true")
    p.add_argument("--json-output", action="store_true")
    p.add_argument("--markdown-report", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--write-review-report", action="store_true")
    p.add_argument("--evidence-dir", default=None)
    # Vetting stays OFF (deferred to Phase 10J); the gate exists so --vet can never call a model here.
    p.add_argument("--vet", action="store_true")
    p.add_argument("--model", default="")
    p.add_argument("--confirm-local-vet", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.write_review_report and not args.evidence_dir:
        print(json.dumps({"refused": True, "reason": "--write-review-report requires --evidence-dir"}),
              file=sys.stderr)
        return 3
    try:
        out = run(args)
    except GraphError as exc:
        print(json.dumps({"refused": True, "reason": str(exc)}, indent=2), file=sys.stderr)
        return 3
    safe, detail_rows = out["safe"], out["detail_rows"]
    if args.write_review_report and args.evidence_dir:
        ev = Path(args.evidence_dir)
        ev.mkdir(parents=True, exist_ok=True)
        (ev / "phase10i-review-summary-safe.json").write_text(
            json.dumps(safe, indent=2, sort_keys=True), encoding="utf-8")
        (ev / "phase10i-review-report-safe.md").write_text(
            _render_phase10i_report(safe), encoding="utf-8")
        (ev / "local-sensitive").mkdir(parents=True, exist_ok=True)
        (ev / "local-sensitive" / "phase10i-review-detail-local-sensitive.json").write_text(
            json.dumps({"rows": detail_rows}, indent=2, sort_keys=True), encoding="utf-8")
    if args.markdown_report:
        print(_render_phase10i_report(safe))
    else:
        print(json.dumps(safe, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
