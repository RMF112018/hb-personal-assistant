#!/usr/bin/env python3
"""Phase 10K — deterministic source-card classifier repair (dry-run default; bounded, reversible).

Repairs the three known-misclassified document families (value-analysis logs, generic specification
templates, clarification/question memos) on already-generated Obsidian source cards, using the
deterministic ``source_document_classifier`` service. Updates ONLY the frontmatter ``document_type``,
the ``source/type/*`` tag, and the Source Summary / Source Basis / Why This Matters / PM Review Cues
deterministic sections. Every managed block and all source ID/SHA/path/timestamp fields are preserved
byte-for-byte (see ``source_card_repair``).

Guardrails: no Ollama, no source-file reads, no new cards, no DB writes, no runtime-JSON mutation. A
card whose preserved *generated* summary still asserts the old type is SKIPPED (``summary_refresh_
required``) — never left contradictory. Default posture is dry-run; ``--apply`` requires matching
confirm flags + ``--confirm-classifier-repair`` + ``--backup-dir`` and runs a backup→write→rollback loop
with whole-run DB/queue invariant proofs. Safe evidence is count-only (no titles/paths/ids/hashes);
per-card detail + backups stay under a git-ignored ``local-sensitive/`` dir.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (_REPO_ROOT / "src", _REPO_ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import obsidian_source_first_indexing_dryrun as dryrun  # noqa: E402  (reuse _load_config)
import obsidian_source_note_apply_graph as ag  # noqa: E402  (shared gate helpers)
import obsidian_source_note_correct_graph as cg  # noqa: E402  (reuse bounded _select)

from hb_assistant.obsidian_mcp import source_card_repair as cr  # noqa: E402
from hb_assistant.obsidian_mcp.mutations import create_note, sha256_file  # noqa: E402
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository  # noqa: E402
from hb_assistant.obsidian_mcp.source_note_graph import REVIEW_TAGS  # noqa: E402

_SAFE_COUNT_KEYS = (
    "cards_scanned", "cards_with_conflict", "repairs_planned", "repairs_applicable",
    "review_required", "skipped", "cards_modified", "db_mutations", "ollama_calls",
)
_POLISH_SAFE_KEYS = (
    "cards_scanned", "cards_changed", "followup_updated", "related_tags_pruned",
    "review_tags_added", "review_tags_removed", "review_tags_skipped", "skipped",
    "cards_modified", "db_mutations", "ollama_calls",
)


class RepairError(Exception):
    """Refusal — printed as a controlled error, exit code 3."""


def _select_targets(repo: SourceIndexRepository, vault_root: Path, args: argparse.Namespace,
                    ) -> list[tuple[str, str, dict[str, Any]]]:
    """Bounded Tropical selection (via cg._select) → [(note_rel, card_text, detail), …]."""
    facts, text_by_id = cg._select(repo, vault_root, args)
    only = set(args.note_rel or [])
    out: list[tuple[str, str, dict[str, Any]]] = []
    for nid in sorted(facts, key=lambda x: facts[x].note_rel):
        fact = facts[nid]
        if only and fact.note_rel not in only:
            continue
        detail = repo.get_source_detail(str(fact.note_id))
        if detail is None:
            continue
        out.append((fact.note_rel, text_by_id[nid], detail))
    if args.max_cards is not None:
        out = out[: args.max_cards]
    return out


def _plan_all(targets: list[tuple[str, str, dict[str, Any]]],
              ) -> list[tuple[str, cr.CardRepairPlan]]:
    return [(rel, cr.plan_card_classification_repair(text, detail)) for rel, text, detail in targets]


def _plan_all_polish(targets: list[tuple[str, str, dict[str, Any]]], add_review: tuple[str, ...],
                     remove_review: tuple[str, ...]) -> list[tuple[str, cr.CardPolishPlan]]:
    return [(rel, cr.plan_card_polish(text, detail, add_review=add_review, remove_review=remove_review))
            for rel, text, detail in targets]


def _summarize_polish(plans: list[tuple[str, cr.CardPolishPlan]],
                      ) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    skips: Counter[str] = Counter()
    changed = followup = pruned = added = removed = skipped_rev = 0
    applicable: list[str] = []
    rows: list[dict[str, Any]] = []
    for rel, p in plans:
        if p.action == "polish":
            changed += 1
            applicable.append(rel)
            followup += 1 if p.followup_changed else 0
            pruned += len(p.related_pruned)
            added += len(p.review_added)
            removed += len(p.review_removed)
        elif p.action == "skip":
            skips[p.skip_reason or "unknown"] += 1
        skipped_rev += len(p.review_skipped)
        rows.append({"note_rel": rel, "action": p.action, "document_type": p.document_type,
                     "followup_changed": p.followup_changed, "related_pruned": list(p.related_pruned),
                     "review_added": list(p.review_added), "review_removed": list(p.review_removed),
                     "review_skipped": list(p.review_skipped), "skip_reason": p.skip_reason})
    safe = {
        "cards_scanned": len(plans), "cards_changed": changed, "followup_updated": followup,
        "related_tags_pruned": pruned, "review_tags_added": added, "review_tags_removed": removed,
        "review_tags_skipped": skipped_rev, "skipped": sum(skips.values()),
        "skips_by_reason": dict(sorted(skips.items())),
        "cards_modified": 0, "db_mutations": 0, "ollama_calls": 0,
    }
    return safe, rows, applicable


def _summarize(plans: list[tuple[str, cr.CardRepairPlan]], *, include_review: bool,
               ) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    by_existing: Counter[str] = Counter()
    by_proposed: Counter[str] = Counter()
    skips: Counter[str] = Counter()
    conflict = repairs = review = 0
    applicable: list[str] = []
    rows: list[dict[str, Any]] = []
    for rel, p in plans:
        if p.classification_conflict:
            conflict += 1
        if p.action == "repair":
            repairs += 1
            by_existing[p.from_type] += 1
            by_proposed[p.to_type] += 1
            if p.confidence == "high" or include_review:
                applicable.append(rel)
        elif p.action == "review":
            review += 1
        elif p.action == "skip":
            skips[p.skip_reason or "unknown"] += 1
        rows.append({"note_rel": rel, "action": p.action, "from_type": p.from_type,
                     "to_type": p.to_type, "confidence": p.confidence,
                     "classification_conflict": p.classification_conflict,
                     "review_required": p.review_required, "skip_reason": p.skip_reason,
                     "sections_changed": list(p.sections_changed), "signals": list(p.signals)})
    safe = {
        "cards_scanned": len(plans), "cards_with_conflict": conflict, "repairs_planned": repairs,
        "repairs_applicable": len(applicable), "review_required": review, "skipped": sum(skips.values()),
        "repairs_by_existing_type": dict(sorted(by_existing.items())),
        "repairs_by_proposed_type": dict(sorted(by_proposed.items())),
        "skips_by_reason": dict(sorted(skips.items())),
        "cards_modified": 0, "db_mutations": 0, "ollama_calls": 0,
    }
    return safe, rows, applicable


def _apply_preflight(args: argparse.Namespace, config: Any) -> None:
    if not (args.confirm_db_path == args.db_path and args.confirm_vault_path == args.vault_path):
        raise RepairError("--apply requires matching --confirm-db-path/--confirm-vault-path")
    if not args.confirm_classifier_repair:
        raise RepairError("--apply requires --confirm-classifier-repair")
    if not args.backup_dir:
        raise RepairError("--apply requires --backup-dir")
    if any(getattr(config, f, False) for f in ag._FROZEN_FLAGS):
        raise RepairError("runtime frozen flags are not all false")
    if ag._backend_listening():
        raise RepairError("backend listening on port 8000")
    q, p = ag._queue_counts(args.db_path)
    if args.require_empty_queue and (q or p):
        raise RepairError(f"queue not empty (queued={q}, processing={p})")


def run(args: argparse.Namespace) -> dict[str, Any]:
    vault_root = Path(args.vault_path).resolve()
    config = dryrun._load_config(args.config_path)
    if Path(str(config.vault_root or "")).resolve() != vault_root:
        raise RepairError("config vault_root does not match --vault-path")
    if not (args.project_number or args.project_key or args.procore_project_id):
        raise RepairError("classifier repair requires bounded project selection")
    if args.polish:
        bad = [t for t in (args.add_review or []) + (args.drop_review or []) if t not in REVIEW_TAGS]
        if bad:
            raise RepairError("--add-review/--drop-review accept review/* tags only")
    if args.apply:
        _apply_preflight(args, config)

    repo = SourceIndexRepository(args.db_path)
    fp_before = ag._db_fingerprint(args.db_path)
    q0, p0 = ag._queue_counts(args.db_path)

    targets = _select_targets(repo, vault_root, args)
    if args.polish:
        plans = _plan_all_polish(targets, tuple(args.add_review or ()), tuple(args.drop_review or ()))
        safe, rows, applicable = _summarize_polish(plans)
    else:
        plans = _plan_all(targets)
        safe, rows, applicable = _summarize(plans, include_review=args.include_review_required)
    plan_by_rel = dict(plans)

    if args.apply and applicable:
        backup_root = Path(args.backup_dir) / "classifier_repair"
        written: list[tuple[Path, Path]] = []
        try:
            for rel in applicable:
                plan = plan_by_rel[rel]
                target = vault_root / rel
                if not target.is_file():
                    raise RepairError("apply would create a new card (target vanished)")
                bpath = backup_root / rel
                bpath.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, bpath)
                out = create_note(config, path=rel, content=plan.new_text, overwrite=True,
                                  create_parent_dirs=False, expected_sha256=sha256_file(target),
                                  caller_surface="mcp", tool_name="classifier_repair",
                                  principal_kind="local")
                if out.get("created"):
                    raise RepairError("apply created a new card (expected 0)")
                written.append((target, bpath))
        except Exception as exc:
            for target, bpath in written:
                try:
                    shutil.copy2(bpath, target)
                except OSError:
                    raise RepairError(f"rollback_failed after {exc}") from None
            raise RepairError(f"apply_failed_rolled_back ({exc})") from None
        safe["cards_modified"] = len(written)

    fp_after = ag._db_fingerprint(args.db_path)
    q1, p1 = ag._queue_counts(args.db_path)
    safe["invariants"] = {"db_mutations": 0 if fp_after == fp_before else 1,
                          "queue_delta": (q1 - q0) + (p1 - p0), "created": 0, "deleted": 0}
    safe["mode"] = "apply" if args.apply else "dry-run"
    safe["project_number"] = args.project_number or None
    if fp_after != fp_before:
        raise RepairError("DB metadata changed during run (unexpected DB mutation)")
    if (q1 - q0) or (p1 - p0):
        raise RepairError("queue changed during run")
    return {"safe": safe, "detail_rows": rows}


# --------------------------------------------------------------------------- count-only evidence
def render_repair_report(safe: dict[str, Any]) -> str:
    """Whitelist renderer — emits ONLY known count/enum keys, so no title/path/id can leak."""
    def g(k: str) -> Any:
        return safe.get(k, "n/a")

    def dist(d: dict[str, Any] | None) -> str:
        return ", ".join(f"{k}: {v}" for k, v in sorted((d or {}).items())) if d else "none"

    inv = safe.get("invariants") if isinstance(safe.get("invariants"), dict) else {}
    return "\n".join([
        "# Phase 10K — Classifier Repair — Review Report (safe / count-only)",
        "",
        f"- mode: {g('mode')}",
        f"- project_number: {g('project_number')}",
        "",
        "## Counts",
        f"- cards_scanned: {g('cards_scanned')}, cards_with_conflict: {g('cards_with_conflict')}",
        f"- repairs_planned: {g('repairs_planned')}, repairs_applicable: {g('repairs_applicable')}, "
        f"review_required: {g('review_required')}, skipped: {g('skipped')}",
        f"- cards_modified: {g('cards_modified')}, db_mutations: {g('db_mutations')}, "
        f"ollama_calls: {g('ollama_calls')}",
        "",
        "## Repairs by type",
        f"- from: {dist(safe.get('repairs_by_existing_type'))}",
        f"- to:   {dist(safe.get('repairs_by_proposed_type'))}",
        f"- skips: {dist(safe.get('skips_by_reason'))}",
        "",
        "## Invariants",
        f"- db_mutations: {inv.get('db_mutations', 'n/a')}, queue_delta: {inv.get('queue_delta', 'n/a')}, "
        f"created: {inv.get('created', 'n/a')}, deleted: {inv.get('deleted', 'n/a')}",
        "",
    ])


def render_polish_report(safe: dict[str, Any]) -> str:
    """Whitelist renderer for the polish pass — ONLY count/enum keys (no Follow-Up text can leak)."""
    def g(k: str) -> Any:
        return safe.get(k, "n/a")

    inv = safe.get("invariants") if isinstance(safe.get("invariants"), dict) else {}
    skips = safe.get("skips_by_reason") or {}
    return "\n".join([
        "# Phase 10K.1 — Post-Repair Polish — Review Report (safe / count-only)",
        "",
        f"- mode: {g('mode')}",
        f"- project_number: {g('project_number')}",
        "",
        "## Counts",
        f"- cards_scanned: {g('cards_scanned')}, cards_changed: {g('cards_changed')}",
        f"- followup_updated: {g('followup_updated')}, related_tags_pruned: {g('related_tags_pruned')}",
        f"- review_tags_added: {g('review_tags_added')}, review_tags_removed: {g('review_tags_removed')}, "
        f"review_tags_skipped: {g('review_tags_skipped')}",
        f"- skipped: {g('skipped')}, cards_modified: {g('cards_modified')}, "
        f"db_mutations: {g('db_mutations')}, ollama_calls: {g('ollama_calls')}",
        f"- skips: {', '.join(f'{k}: {v}' for k, v in sorted(skips.items())) if skips else 'none'}",
        "",
        "## Invariants",
        f"- db_mutations: {inv.get('db_mutations', 'n/a')}, queue_delta: {inv.get('queue_delta', 'n/a')}, "
        f"created: {inv.get('created', 'n/a')}, deleted: {inv.get('deleted', 'n/a')}",
        "",
    ])


def _safe_only(safe: dict[str, Any]) -> dict[str, Any]:
    """Project to count/enum keys only — a belt-and-braces guard against leaking into safe JSON."""
    allow = (set(_SAFE_COUNT_KEYS) | set(_POLISH_SAFE_KEYS)
             | {"mode", "project_number", "invariants", "repairs_by_existing_type",
                "repairs_by_proposed_type", "skips_by_reason"})
    return {k: v for k, v in safe.items() if k in allow}


def _write_outputs(args: argparse.Namespace, out: dict[str, Any]) -> None:
    safe = _safe_only(out["safe"])
    if args.json_output:
        Path(args.json_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_output).write_text(json.dumps(safe, indent=2, sort_keys=True), encoding="utf-8")
    renderer = render_polish_report if args.polish else render_repair_report
    if args.markdown_report:
        Path(args.markdown_report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.markdown_report).write_text(renderer(out["safe"]), encoding="utf-8")
    ls = args.local_sensitive_dir
    if not ls and args.json_output:
        ls = str(Path(args.json_output).parent / "local-sensitive")
    if ls:
        Path(ls).mkdir(parents=True, exist_ok=True)
        detail_name = ("phase10k1-polish-detail-local-sensitive.json" if args.polish
                       else "phase10k-classifier-repair-detail-local-sensitive.json")
        (Path(ls) / detail_name).write_text(
            json.dumps({"rows": out["detail_rows"]}, indent=2, sort_keys=True), encoding="utf-8")


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
    p.add_argument("--note-rel", action="append", default=None,
                   help="restrict to these exact note-rel paths (repeatable)")
    p.add_argument("--max-cards", type=int, default=None)
    p.add_argument("--max-notes", type=int, default=100000)  # cg._select/_matches_project compatibility
    p.add_argument("--include-review-required", action="store_true",
                   help="also apply medium-confidence (weak-base) repairs (default: high-confidence only)")
    p.add_argument("--polish", action="store_true",
                   help="post-repair polish: regenerate Follow-Up + prune stale related/review tags")
    p.add_argument("--add-review", action="append", default=None,
                   help="review/* tag to add where justified by the repaired type (repeatable)")
    p.add_argument("--drop-review", action="append", default=None,
                   help="review/* tag to drop where justified by the repaired type (repeatable)")
    p.add_argument("--json-output", default=None)
    p.add_argument("--markdown-report", default=None)
    p.add_argument("--local-sensitive-dir", default=None)
    p.add_argument("--dry-run", action="store_true")  # default posture; explicit flag for clarity
    p.add_argument("--apply", action="store_true")
    p.add_argument("--confirm-classifier-repair", action="store_true")
    p.add_argument("--backup-dir", default=None)
    p.add_argument("--confirm-db-path", default="")
    p.add_argument("--confirm-vault-path", default="")
    p.add_argument("--require-empty-queue", action="store_true", default=True)
    p.add_argument("--no-require-empty-queue", dest="require_empty_queue", action="store_false")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.apply and not args.backup_dir:
        print(json.dumps({"refused": True, "reason": "--apply requires --backup-dir"}), file=sys.stderr)
        return 3
    try:
        out = run(args)
    except (RepairError, cg.GraphError) as exc:
        print(json.dumps({"refused": True, "reason": str(exc)}), file=sys.stderr)
        return 3
    _write_outputs(args, out)
    print(json.dumps(_safe_only(out["safe"]), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
