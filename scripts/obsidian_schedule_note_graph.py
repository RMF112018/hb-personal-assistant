#!/usr/bin/env python3
"""Phase 20 — Schedule note graph linking (discovery, review, fixture apply).

Schedule-specific only. Does not route through source-card gc-graph-links, apply, indexing, or
source-card mutation. Default: dry-run, deterministic candidates, ollama_calls=0, no vault writes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (_REPO_ROOT / "src", _REPO_ROOT / "subrepos/construction-financial-review/src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from hb_assistant.obsidian_mcp.schedule_note_graph import (  # noqa: E402
    build_schedule_graph_candidates,
    discover_safe_source_cards,
    discover_schedule_notes,
    render_graph_link_lines,
    tag_recommendations,
)
from hb_assistant.obsidian_mcp.schedule_note_graph_llm_validation import (  # noqa: E402
    build_suggestion_prompt,
    validate_llm_suggestions,
)
from hb_assistant.obsidian_mcp.schedule_note_graph_review import (  # noqa: E402
    build_review_payload,
    render_review_markdown,
)
from hb_assistant.obsidian_mcp.schedule_note_graph_writer import (  # noqa: E402
    apply_schedule_graph_links,
)

DEFAULT_MODEL = "qwen2.5:14b"


def _vault_apply_allowed(
    vault_root: Path,
    *,
    evidence_dir: Path | None,
    allow_live_vault: bool,
    confirm_live_vault_apply: bool,
) -> tuple[bool, str]:
    resolved = vault_root.resolve()
    if evidence_dir is not None:
        try:
            resolved.relative_to(evidence_dir.resolve())
            return True, "fixture_evidence_dir"
        except ValueError:
            pass
    if "fixture-vault" in resolved.parts:
        return True, "fixture_vault_path"
    if allow_live_vault and confirm_live_vault_apply:
        return True, "live_explicit_confirmation"
    return False, "live_vault_blocked"


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Schedule note graph linking (Phase 20)")
    parser.add_argument("--vault-path", required=True)
    parser.add_argument("--project-key")
    parser.add_argument("--portfolio", action="store_true")
    parser.add_argument("--evidence-dir")
    parser.add_argument("--json-output")
    parser.add_argument("--markdown-output")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply-links", action="store_true")
    parser.add_argument("--confirm-graph-apply", action="store_true")
    parser.add_argument("--allow-live-vault", action="store_true")
    parser.add_argument("--confirm-live-vault-apply", action="store_true")
    parser.add_argument("--suggest-links", action="store_true")
    parser.add_argument("--confirm-local-llm", action="store_true")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args(argv)

    dry_run = not args.apply_links
    if args.apply_links and not args.confirm_graph_apply:
        print("apply-links requires --confirm-graph-apply", file=sys.stderr)
        return 3
    if args.suggest_links and not args.confirm_local_llm:
        print("suggest-links requires --confirm-local-llm", file=sys.stderr)
        return 3

    vault_root = Path(args.vault_path).expanduser().resolve()
    evidence_dir = Path(args.evidence_dir).expanduser().resolve() if args.evidence_dir else None
    allowed, allow_reason = _vault_apply_allowed(
        vault_root,
        evidence_dir=evidence_dir,
        allow_live_vault=args.allow_live_vault,
        confirm_live_vault_apply=args.confirm_live_vault_apply,
    )
    if args.apply_links and not allowed:
        print(
            "fixture apply only: use evidence fixture vault or "
            "--allow-live-vault --confirm-live-vault-apply",
            file=sys.stderr,
        )
        return 3

    facts = discover_schedule_notes(
        vault_root,
        project_key=args.project_key,
        portfolio_only=args.portfolio,
    )
    source_cards = discover_safe_source_cards(vault_root, project_key=args.project_key)
    cards_by_path = {c.note_rel_path: c for c in source_cards}
    candidates = build_schedule_graph_candidates(facts, source_cards=source_cards)
    facts_by_path = {f.note_rel_path: f for f in facts}
    lines_by_source = render_graph_link_lines(
        candidates,
        facts_by_path,
        source_cards=cards_by_path,
        recommended_only=True,
    )

    ollama_calls = 0
    llm_report: dict[str, Any] = {"enabled": False}
    if args.suggest_links:
        from hb_assistant.construction.classification.client import list_ollama_models
        from hb_assistant.obsidian_mcp.llm import OllamaChatClient

        models = list_ollama_models()
        if args.model not in models:
            print(f"model not installed: {args.model}", file=sys.stderr)
            return 4
        client = OllamaChatClient(model=args.model)
        prompt = build_suggestion_prompt(candidates)
        raw = client.generate_text(prompt)
        ollama_calls = 1
        llm_report = {
            "enabled": True,
            "model": args.model,
            **validate_llm_suggestions(raw, candidates),
            "report_only": True,
        }

    write_results = apply_schedule_graph_links(
        vault_root=vault_root,
        lines_by_source=lines_by_source,
        dry_run=dry_run,
    )
    notes_modified = sum(1 for r in write_results if r.action == "updated")
    links_written = sum(r.links_written for r in write_results if r.action == "updated")
    write_attempts = 0 if dry_run else len([r for r in write_results if r.action == "updated"])
    apply_summary = {
        "dry_run": dry_run,
        "vault_apply_allowed": allowed,
        "vault_apply_reason": allow_reason,
        "notes_modified": notes_modified,
        "links_written": links_written,
        "write_attempts": write_attempts,
        "results": [
            {
                "relative_path": r.relative_path,
                "action": r.action,
                "links_written": r.links_written,
                "conflict": r.conflict,
                "message": r.message,
            }
            for r in write_results
        ],
    }

    payload = build_review_payload(
        facts=facts,
        candidates=candidates,
        tag_recommendations=tag_recommendations(facts),
        llm_report=llm_report,
        apply_summary=apply_summary,
    )
    payload["ollama_calls"] = ollama_calls
    payload["schedule_graph_phase"] = "20"

    if args.json_output:
        Path(args.json_output).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown_output:
        Path(args.markdown_output).write_text(render_review_markdown(payload), encoding="utf-8")
    if not args.json_output and not args.markdown_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
