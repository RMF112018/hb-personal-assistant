#!/usr/bin/env python3
"""Unified local-Ollama enrichment workflow for Obsidian source cards (Phase 10J).

The single first-class operator surface for local `qwen2.5:14b` enrichment. Composes the hardened
per-capability engines rather than reimplementing them:

- **--summaries** delegates to the Phase 10B appender (hb-local-summary blocks; sanitize + four-section
  gate);
- **--tags** runs a standalone tagging pass (model proposes related/* + review/* from the controlled
  taxonomy, grounded in deterministic facts; deterministic source/type + source/disposition added; the
  card frontmatter is updated via the shared apply_tags writer);
- **--backlinks** delegates to the Phase 10G applier (deterministic candidates -> local vetting ->
  reciprocal wiki links + tags -> backup/SHA-drift/rollback/backlink-integrity);
- **--review** delegates to the Phase 10I read-only review surfaces.

Adds the cross-cutting concerns the individual scripts lack: a canonical reject-reason taxonomy, model
observability (calls/latency/success/failure — tokens are unavailable through the client seam and are
reported null), and one unified count-only evidence bundle. Default posture is dry-run/report-only;
--apply requires exact confirm flags + --backup-dir and delegates each mutation to its engine's own
backup/rollback/invariant pipeline. No source-file read, no scan, no queue drain, no cloud model, no
runtime-JSON mutation, no card create/delete, no DB mutation.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Callable

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (_REPO_ROOT / "src", _REPO_ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import obsidian_source_card_append_local_summary as summ  # noqa: E402
import obsidian_source_first_indexing_dryrun as dryrun  # noqa: E402  (reuse _load_config)
import obsidian_source_graph_review as rev  # noqa: E402
import obsidian_source_note_apply_graph as ag  # noqa: E402
import obsidian_source_note_correct_graph as cg  # noqa: E402  (reuse bounded _select)

from hb_assistant.construction.classification.client import (  # noqa: E402
    OllamaChatClient,
    OllamaUnavailable,
    list_ollama_models,
)
from hb_assistant.obsidian_mcp import source_enrichment as enr  # noqa: E402
from hb_assistant.obsidian_mcp import source_local_summary as sls  # noqa: E402
from hb_assistant.obsidian_mcp import source_note_graph as ng  # noqa: E402
from hb_assistant.obsidian_mcp.mutations import create_note, sha256_file  # noqa: E402
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository  # noqa: E402
from hb_assistant.obsidian_mcp.source_notes import replace_local_summary_block  # noqa: E402

_MODES = ("review", "summaries", "tags", "backlinks")


class EnrichError(Exception):
    """Refusal — printed as a controlled error, exit code 3."""


# Any engine refusal is surfaced identically (all graph engines share ag.GraphError).
_REFUSALS = (EnrichError, ag.GraphError, summ.AppendError)


def _default_client_factory(model: str, timeout: float) -> OllamaChatClient:
    return OllamaChatClient(model=model, timeout=timeout)


def _selected_modes(args: argparse.Namespace) -> set[str]:
    if args.all:
        return set(_MODES)
    return {m for m in _MODES if getattr(args, m)}


# --- sub-argument builders (reuse each engine's parser for defaults, then override) --------------
def _base_sub(engine: Any, args: argparse.Namespace) -> argparse.Namespace:
    sub = engine._build_parser().parse_args(["--db-path", args.db_path, "--vault-path", args.vault_path])
    sub.config_path = args.config_path
    sub.model = args.model
    sub.timeout_seconds = args.timeout_seconds
    sub.evidence_dir = None  # the orchestrator writes the unified bundle
    return sub


def _backlink_sub_args(args: argparse.Namespace) -> argparse.Namespace:
    sub = _base_sub(ag, args)
    sub.max_notes = args.max_notes
    sub.max_apply_relationships = args.max_apply_relationships
    sub.confidence_threshold = args.confidence_threshold
    sub.project_number = args.project_number
    sub.project_key = args.project_key
    sub.procore_project_id = args.procore_project_id
    sub.confirm_project_number = args.confirm_project_number
    sub.confirm_project_key = args.confirm_project_key
    sub.confirm_procore_project_id = args.confirm_procore_project_id
    sub.confirm_apply_approved_count = args.confirm_apply_approved_count
    sub.backup_dir = str(Path(args.backup_dir) / "backlinks") if args.backup_dir else None
    sub.vet = True  # enrichment always vets (read-only in dry-run; required to apply)
    sub.apply = args.apply
    sub.dry_run = not args.apply
    sub.confirm_db_path = args.confirm_db_path
    sub.confirm_vault_path = args.confirm_vault_path
    sub.confirm_model = args.confirm_model
    sub.require_empty_queue = args.require_empty_queue
    return sub


def _review_sub_args(args: argparse.Namespace) -> argparse.Namespace:
    sub = rev._build_parser().parse_args(["--db-path", args.db_path, "--vault-path", args.vault_path])
    sub.config_path = args.config_path
    sub.project_number = args.project_number
    sub.project_key = args.project_key
    sub.procore_project_id = args.procore_project_id
    sub.all = True
    sub.evidence_dir = None
    sub.write_review_report = False
    sub.vet = False
    return sub


# --- standalone summarization workflow (Phase 10J native) ---------------------------------------
def _run_summaries(args: argparse.Namespace, repo: SourceIndexRepository, vault_root: Path,
                   config: Any, obs_factory: Callable[[str, float], Any],
                   now_iso_fn: Callable[[], str],
                   ) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, int]]:
    """Tropical-scoped, count-capped, quality-gated local summary pass.

    Unlike the Phase 10B appender (domain-scoped, no take-N cap, and it does NOT run any quality gate),
    this: selects the bounded Tropical set, filters to summary-eligible cards (pending marker / canonical
    sections / card_version via summ._eligibility), takes at most --summaries-max-cards (after
    --summaries-skip) in stable note-rel order, and builds a SOURCE-GROUNDED, classification-aware
    summary (sls.build_source_card_summary_prompt + SOURCE_CARD_SUMMARY_SYSTEM_PROMPT) gated by the
    STRICT five-section quality validator (sls.validate_summary_quality — excerpt grounding, family
    signals, classifier-conflict / generic-spec / #REF checks) BEFORE writing. An invalid or low-quality
    summary leaves the card pending. On a successful write replace_local_summary_block flips the marker
    pending -> generated, verified by re-read. Classifier document_type is surfaced/counted, not repaired.
    """
    from collections import Counter
    facts, text_by_id = cg._select(repo, vault_root, args)
    ordered = sorted(facts, key=lambda nid: facts[nid].note_rel)
    eligible_ids = [nid for nid in ordered
                    if summ._eligibility(text_by_id[nid], facts[nid].note_rel, "Work", args) is None]
    # Optional explicit targeting: restrict to exactly these note-rel paths (still subject to the same
    # eligibility gate). Used to re-summarize specific cards (e.g. a known-misclassified family) instead
    # of the alphabetically-first window. Applied BEFORE skip/cap so the cap still bounds attempts.
    # cards_eligible still reports the FULL eligible count; only the attempted window is narrowed.
    only_rels = set(getattr(args, "summaries_note_rel", None) or [])
    selected_ids = [nid for nid in eligible_ids if facts[nid].note_rel in only_rels] if only_rels \
        else eligible_ids
    skip = getattr(args, "summaries_skip", 0) or 0
    cap = getattr(args, "summaries_max_cards", None)
    window = selected_ids[skip:]
    truncated = cap is not None and len(window) > cap
    attempted_ids = window[:cap] if cap is not None else window

    detail_rows: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()

    if not args.apply:
        # Dry-run: eligibility + deterministic classifier-conflict count, NO model call.
        conflicts = 0
        for nid in attempted_ids:
            detail = repo.get_source_detail(str(facts[nid].note_id)) or {}
            conflict = sls.detect_classification_conflict(
                facts[nid].document_type, facts[nid].display, str(detail.get("text_excerpt") or ""))
            conflicts += 1 if conflict else 0
            detail_rows.append({"note_id12": nid[:12], "result": "eligible",
                                "classifier_conflict": bool(conflict)})
        safe = {
            "cards_available": len(facts), "cards_eligible": len(eligible_ids),
            "selection_truncated": truncated, "cards_attempted": len(attempted_ids),
            "summaries_generated": 0, "summaries_rejected": 0, "reject_reasons": {},
            "cards_left_pending": len(attempted_ids), "marker_transitions_pending_to_generated": 0,
            "would_attempt_cards": len(attempted_ids), "classifier_conflicts": conflicts,
        }
        return safe, detail_rows, {}

    timeout = float(args.timeout_seconds or config.source_summary_ollama_timeout_seconds)
    client = obs_factory(args.model, timeout)
    try:  # fail-safe Ollama/model probe BEFORE mutating any card
        models = list_ollama_models(base_url=getattr(client, "base_url", None))
    except OllamaUnavailable as exc:
        raise EnrichError(f"ollama_unavailable ({exc})") from None
    if args.model not in models:
        raise EnrichError(f"model_unavailable: {args.model}")

    generated_at = now_iso_fn()
    plan: dict[str, str] = {}
    classifier_conflicts = 0
    for nid in attempted_ids:
        text = text_by_id[nid]
        fact = facts[nid]
        detail = repo.get_source_detail(str(fact.note_id))
        if detail is None:
            reasons["missing_source_record"] += 1
            detail_rows.append({"note_id12": nid[:12], "result": "rejected",
                                "reason": "missing_source_record"})
            continue
        excerpt = str(detail.get("text_excerpt") or "")
        conflict = sls.detect_classification_conflict(fact.document_type, fact.display, excerpt)
        if conflict:
            classifier_conflicts += 1
        # Source-grounded, classification-aware summary path (NOT the delegated 10B run / 4-section gate).
        prompt = sls.build_source_card_summary_prompt(
            text, detail, title=fact.display, document_type=fact.document_type,
            max_input_chars=int(config.source_summary_max_input_chars))
        lines, greason = sls.generate_advisory(client, prompt,
                                               system=sls.SOURCE_CARD_SUMMARY_SYSTEM_PROMPT)
        if lines is None:  # model failure — card left unchanged (pending)
            reasons[greason] += 1
            detail_rows.append({"note_id12": nid[:12], "result": "rejected", "reason": greason,
                                "classifier_conflict": bool(conflict)})
            continue
        ok, vreason = sls.validate_summary_quality(
            lines, detail, title=fact.display, document_type=fact.document_type)
        if not ok:  # invalid / low-quality summary — card left unchanged (pending)
            reasons[vreason] += 1
            detail_rows.append({"note_id12": nid[:12], "result": "rejected", "reason": vreason,
                                "classifier_conflict": bool(conflict)})
            continue
        plan[nid] = replace_local_summary_block(text, lines, model=args.model,
                                                generated_at=generated_at)
        detail_rows.append({"note_id12": nid[:12], "result": "generated",
                            "classifier_conflict": bool(conflict)})

    attempted = len(attempted_ids)
    rejected = attempted - len(plan)

    # ---- APPLY: backup all, write all, rollback on any failure (mirrors the 10G/tags applier) -----
    backup_root = Path(args.backup_dir) / "summaries"
    written: list[tuple[Path, Path]] = []
    try:
        for nid, content in plan.items():
            target = vault_root / facts[nid].note_rel
            if not target.is_file():
                raise EnrichError("apply would create a new card (target vanished)")
            bpath = backup_root / facts[nid].note_rel
            bpath.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, bpath)
            out = create_note(config, path=facts[nid].note_rel, content=content, overwrite=True,
                              create_parent_dirs=False, expected_sha256=sha256_file(target),
                              caller_surface="mcp", tool_name="enrich_summary", principal_kind="local")
            if out.get("created"):
                raise EnrichError("apply created a new card (expected 0)")
            written.append((target, bpath))
    except Exception as exc:
        for target, bpath in written:  # rollback everything already written
            try:
                shutil.copy2(bpath, target)
            except OSError:
                raise EnrichError(f"rollback_failed after {exc}") from None
        raise EnrichError(f"apply_failed_rolled_back ({exc})") from None

    # Prove the pending -> generated transition by re-reading each written card's marker (count-only).
    transitions = sum(1 for nid in plan
                      if summ._start_marker_status(
                          (vault_root / facts[nid].note_rel).read_text(encoding="utf-8")) == "generated")

    safe = {
        "cards_available": len(facts), "cards_eligible": len(eligible_ids),
        "selection_truncated": truncated, "cards_attempted": attempted,
        "summaries_generated": len(plan), "summaries_rejected": rejected,
        "reject_reasons": dict(sorted(reasons.items())),
        "cards_left_pending": rejected, "cards_written": len(written),
        "marker_transitions_pending_to_generated": transitions,
        "classifier_conflicts": classifier_conflicts,
    }
    return safe, detail_rows, dict(reasons)


# --- standalone tagging workflow (Phase 10J native) ---------------------------------------------
def _run_tags(args: argparse.Namespace, repo: SourceIndexRepository, vault_root: Path, config: Any,
              obs_factory: Callable[[str, float], Any],
              ) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, int]]:
    from collections import Counter
    facts, text_by_id = cg._select(repo, vault_root, args)
    # Bound the pass by card count (conservative apply): process at most --tags-max-cards, in stable
    # note-rel order, and report truncation rather than silently covering everything.
    ordered = sorted(facts, key=lambda nid: facts[nid].note_rel)
    cap = getattr(args, "tags_max_cards", None)
    truncated = cap is not None and len(ordered) > cap
    selected_ids = ordered[:cap] if cap is not None else ordered
    timeout = float(args.timeout_seconds or config.source_summary_ollama_timeout_seconds)
    client = obs_factory(args.model, timeout)

    if args.apply:  # fail-safe Ollama/model probe BEFORE mutating any card
        try:
            models = list_ollama_models(base_url=getattr(client, "base_url", None))
        except OllamaUnavailable as exc:
            raise EnrichError(f"ollama_unavailable ({exc})") from None
        if args.model not in models:
            raise EnrichError(f"model_unavailable: {args.model}")

    detail_rows: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()
    plan: dict[str, str] = {}
    tags_proposed = tags_applied = failed = skipped = 0
    for nid in selected_ids:
        fact = facts[nid]
        text = text_by_id[nid]
        proposed, reason = ng.propose_tags(client, fact)
        tags_proposed += len(proposed)
        if reason != "ok":
            failed += 1
            reasons[reason] += 1
            detail_rows.append({"note_id12": nid[:12], "result": "failed", "reason": reason})
            continue
        all_tags = ng.content_tags_for(fact) + proposed
        ok_fm, existing, _f, _l = ng.parse_frontmatter_tags(text)
        if not ok_fm:
            skipped += 1
            reasons["frontmatter_not_block_style"] += 1
            detail_rows.append({"note_id12": nid[:12], "result": "skipped",
                                "reason": "frontmatter_not_block_style"})
            continue
        sanitized = [t for t in (ng.sanitize_tag(x) for x in all_tags) if t]
        to_add = [t for t in dict.fromkeys(sanitized) if t not in existing][:8]
        if not to_add:
            detail_rows.append({"note_id12": nid[:12], "result": "no_new_tags"})
            continue
        new_text, r = ng.apply_tags(text, all_tags)
        if new_text is None:
            skipped += 1
            reasons[f"tags:{r}"] += 1
            detail_rows.append({"note_id12": nid[:12], "result": "skipped", "reason": f"tags:{r}"})
            continue
        plan[nid] = new_text
        tags_applied += len(to_add)
        detail_rows.append({"note_id12": nid[:12], "result": "tagged", "added": len(to_add)})

    safe: dict[str, Any] = {
        "cards_available": len(facts), "cards_checked": len(selected_ids),
        "selection_truncated": truncated,
        "tags_proposed": tags_proposed, "tags_applied": tags_applied,
        "cards_tagged": len(plan), "failed": failed, "skipped": skipped,
        "reject_reasons": dict(sorted(reasons.items())),
    }
    if not args.apply:
        safe["would_tag_cards"] = len(plan)
        return safe, detail_rows, dict(reasons)

    # ---- APPLY: backup all, write all, rollback on any failure (mirrors the 10G applier) ---------
    backup_root = Path(args.backup_dir) / "tags"
    written: list[tuple[Path, Path]] = []
    try:
        for nid, content in plan.items():
            target = vault_root / facts[nid].note_rel
            if not target.is_file():
                raise EnrichError("apply would create a new card (target vanished)")
            bpath = backup_root / facts[nid].note_rel
            bpath.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, bpath)
            out = create_note(config, path=facts[nid].note_rel, content=content, overwrite=True,
                              create_parent_dirs=False, expected_sha256=sha256_file(target),
                              caller_surface="mcp", tool_name="enrich_tags", principal_kind="local")
            if out.get("created"):
                raise EnrichError("apply created a new card (expected 0)")
            written.append((target, bpath))
    except Exception as exc:
        for target, bpath in written:  # rollback everything already written
            try:
                shutil.copy2(bpath, target)
            except OSError:
                raise EnrichError(f"rollback_failed after {exc}") from None
        raise EnrichError(f"apply_failed_rolled_back ({exc})") from None
    safe["cards_written"] = len(written)
    return safe, detail_rows, dict(reasons)


def _apply_preflight(args: argparse.Namespace, config: Any) -> None:
    if not (args.confirm_db_path == args.db_path and args.confirm_vault_path == args.vault_path
            and args.confirm_model == args.model):
        raise EnrichError("--apply requires matching --confirm-db-path/--confirm-vault-path/--confirm-model")
    if any(getattr(config, f, False) for f in ag._FROZEN_FLAGS):
        raise EnrichError("runtime frozen flags are not all false")
    if ag._backend_listening():
        raise EnrichError("backend listening on port 8000")
    q, p = ag._queue_counts(args.db_path)
    if args.require_empty_queue and (q or p):
        raise EnrichError(f"queue not empty (queued={q}, processing={p})")


def run(args: argparse.Namespace, *,
        client_factory: Callable[[str, float], Any] = _default_client_factory,
        now_iso_fn: Callable[[], str] = summ._now_iso) -> dict[str, Any]:
    vault_root = Path(args.vault_path).resolve()
    config = dryrun._load_config(args.config_path)
    if Path(str(config.vault_root or "")).resolve() != vault_root:
        raise EnrichError("config vault_root does not match --vault-path")
    modes = _selected_modes(args)
    if not modes:
        raise EnrichError("choose at least one mode (--summaries/--tags/--backlinks/--review or --all)")
    project_scoped = bool(args.project_number or args.project_key or args.procore_project_id)
    if ({"summaries", "tags", "backlinks", "review"} & modes) and not project_scoped:
        raise EnrichError("summaries/tags/backlinks/review require bounded project selection")
    if args.apply:
        _apply_preflight(args, config)

    repo = SourceIndexRepository(args.db_path)
    fp_before = ag._db_fingerprint(args.db_path)
    q0, p0 = ag._queue_counts(args.db_path)

    rec = enr.ObservabilityRecorder()

    def obs_factory(model: str, timeout: float) -> Any:
        return enr.ObservableClient(client_factory(model, timeout), rec)

    result: dict[str, Any] = {
        "mode": "apply" if args.apply else "dry-run", "model": args.model,
        "modes_run": sorted(modes), "project_number": args.project_number or None,
        "summaries": None, "tags": None, "backlinks": None, "review": None,
    }
    detail_rows: list[dict[str, Any]] = []
    reason_dicts: list[dict[str, int] | None] = []

    # Order: read-only review first, then the write-capable workflows.
    if "review" in modes:
        out = rev.run(_review_sub_args(args))
        result["review"] = out["safe"]
        detail_rows += [{"section": "review", **r} for r in out["detail_rows"]]
    if "summaries" in modes:
        ssafe, srows, sreasons = _run_summaries(args, repo, vault_root, config, obs_factory, now_iso_fn)
        result["summaries"] = ssafe
        detail_rows += [{"section": "summaries", **r} for r in srows]
        reason_dicts.append(sreasons)
    if "tags" in modes:
        tsafe, trows, treasons = _run_tags(args, repo, vault_root, config, obs_factory)
        result["tags"] = tsafe
        detail_rows += [{"section": "tags", **r} for r in trows]
        reason_dicts.append(treasons)
    if "backlinks" in modes:
        out = ag.run(_backlink_sub_args(args), client_factory=obs_factory)
        result["backlinks"] = out["safe"]
        detail_rows += [{"section": "backlinks", **r} for r in out["detail_rows"]]
        reason_dicts.append(out["safe"].get("rejection_reasons"))

    result["reject_reasons"] = enr.merge_reasons(*reason_dicts)
    result["observability"] = rec.snapshot(model=args.model)

    # ---- whole-run invariants (each engine also asserts its own; this is the outer proof) ---------
    fp_after = ag._db_fingerprint(args.db_path)
    q1, p1 = ag._queue_counts(args.db_path)
    result["invariants"] = {"db_mutations": 0 if fp_after == fp_before else 1,
                            "queue_delta": (q1 - q0) + (p1 - p0), "created": 0, "deleted": 0}
    if fp_after != fp_before:
        raise EnrichError("DB metadata changed during run (unexpected DB mutation)")
    if (q1 - q0) or (p1 - p0):
        raise EnrichError("queue changed during run")
    return {"safe": result, "detail_rows": detail_rows}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db-path", required=True)
    p.add_argument("--config-path",
                   default=str(Path.home() / "Library/Application Support/HB Personal Assistant"
                              / "analytics/obsidian_mcp_config.json"))
    p.add_argument("--vault-path", required=True)
    p.add_argument("--model", default=ng.LOCAL_MODEL)
    # modes
    p.add_argument("--summaries", action="store_true")
    p.add_argument("--tags", action="store_true")
    p.add_argument("--backlinks", action="store_true")
    p.add_argument("--review", action="store_true")
    p.add_argument("--all", action="store_true")
    # bounded project selection (required for tags/backlinks/review)
    p.add_argument("--project-number", default="")
    p.add_argument("--project-key", default="")
    p.add_argument("--procore-project-id", default="")
    # bounds
    p.add_argument("--summaries-max-cards", type=int, default=None,
                   help="cap the summarization pass to at most N eligible cards (attempted, not just written)")
    p.add_argument("--summaries-skip", type=int, default=0,
                   help="skip the first N eligible cards before the cap (iterate bounded batches)")
    p.add_argument("--summaries-note-rel", action="append", default=None,
                   help="restrict summarization to these exact note-rel paths (repeatable); still "
                        "subject to eligibility. Targets specific cards instead of the first window")
    p.add_argument("--tags-max-cards", type=int, default=None,
                   help="cap the tagging pass to at most N cards (stable note-rel order)")
    p.add_argument("--max-notes", type=int, default=25)
    p.add_argument("--max-apply-relationships", type=int, default=25)
    p.add_argument("--confidence-threshold", type=float, default=0.80)
    p.add_argument("--timeout-seconds", type=float, default=None)
    # evidence / posture
    p.add_argument("--evidence-dir", default=None)
    p.add_argument("--markdown-report", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup-dir", default=None)
    # confirm flags (echo-back; must match under --apply)
    p.add_argument("--confirm-db-path", default="")
    p.add_argument("--confirm-vault-path", default="")
    p.add_argument("--confirm-model", default="")
    p.add_argument("--confirm-project-number", default="")
    p.add_argument("--confirm-project-key", default="")
    p.add_argument("--confirm-procore-project-id", default="")
    p.add_argument("--confirm-apply-approved-count", type=int, default=None)
    p.add_argument("--require-empty-queue", action="store_true", default=True)
    p.add_argument("--no-require-empty-queue", dest="require_empty_queue", action="store_false")
    p.add_argument("--allow-resummarize", action="store_true")
    p.add_argument("--allow-non-current-version", action="store_true")
    return p


def main(argv: list[str] | None = None, *,
         client_factory: Callable[[str, float], Any] = _default_client_factory,
         now_iso_fn: Callable[[], str] = summ._now_iso) -> int:
    args = _build_parser().parse_args(argv)
    if args.apply and not args.backup_dir:
        print(json.dumps({"refused": True, "reason": "--apply requires --backup-dir"}), file=sys.stderr)
        return 3
    try:
        out = run(args, client_factory=client_factory, now_iso_fn=now_iso_fn)
    except _REFUSALS as exc:
        print(json.dumps({"refused": True, "reason": str(exc)}, indent=2), file=sys.stderr)
        return 3
    safe, detail_rows = out["safe"], out["detail_rows"]
    if args.evidence_dir:
        enr.write_enrichment_evidence(args.evidence_dir, safe, detail_rows)
    if args.markdown_report:
        print(enr.render_enrichment_report(safe))
    else:
        print(json.dumps(safe, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
