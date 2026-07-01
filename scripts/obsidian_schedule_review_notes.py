#!/usr/bin/env python3
"""Generate PM-safe schedule comparison Obsidian notes (Phase 19).

Default: dry-run, deterministic-only, ollama_calls=0, no vault writes.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (_REPO_ROOT / "src", _REPO_ROOT / "subrepos/construction-financial-review/src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks
from hb_assistant.construction.analytics.project_schedule_narrative_qa import validate_rendered_text
from hb_assistant.construction.analytics.project_schedule_second_brain_note_service import (
    NOTE_TYPES,
    ProjectScheduleSecondBrainNoteService,
)
from hb_assistant.obsidian_mcp.schedule_note_advisory_validation import validate_schedule_advisory
from hb_assistant.obsidian_mcp.schedule_obsidian_note_writer import apply_schedule_note_write
from hb_assistant.obsidian_mcp.schedule_review_note_generator import (
    assert_note_safe,
    note_relative_path,
    render_note_markdown,
)

DEFAULT_MODEL = "qwen2.5:14b"


def _parse_date(raw: str | None) -> date:
    if not raw:
        return datetime.now(timezone.utc).date()
    return date.fromisoformat(raw)


def _note_types(raw: str | None) -> list[str]:
    if not raw or raw == "all":
        return sorted(NOTE_TYPES - {"portfolio_snapshot"})
    return [part.strip() for part in raw.split(",") if part.strip()]


def _portfolio_types(raw: str | None, portfolio: bool) -> list[str]:
    if portfolio:
        return ["portfolio_snapshot"]
    if raw == "all":
        return sorted(NOTE_TYPES)
    return _note_types(raw)


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate schedule second-brain Obsidian notes")
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--vault-path", required=True)
    parser.add_argument("--project-key")
    parser.add_argument("--portfolio", action="store_true")
    parser.add_argument("--note-type", default="schedule_update")
    parser.add_argument("--comparison-basis")
    parser.add_argument("--status")
    parser.add_argument("--as-of")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--write-notes", action="store_true")
    parser.add_argument("--confirm-vault-write", action="store_true")
    parser.add_argument("--json-output")
    parser.add_argument("--markdown-output")
    parser.add_argument("--summarize", action="store_true")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--confirm-local-llm", action="store_true")
    args = parser.parse_args(argv)

    dry_run = not args.write_notes
    if args.write_notes and not args.confirm_vault_write:
        print("write-notes requires --confirm-vault-write", file=sys.stderr)
        return 3
    if args.summarize and not args.confirm_local_llm:
        print("summarize requires --confirm-local-llm", file=sys.stderr)
        return 3

    as_of_date = _parse_date(args.as_of)
    vault_root = Path(args.vault_path).expanduser().resolve()
    service = ProjectScheduleSecondBrainNoteService(db_path=str(Path(args.db_path).expanduser()))
    ollama_calls = 0
    advisory_failures: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    notes_planned = 0
    notes_written = 0
    notes_updated = 0
    conflicts = 0

    note_types = _portfolio_types(args.note_type, args.portfolio)
    project_keys = [args.project_key] if args.project_key else []
    if not args.portfolio and not project_keys:
        project_keys = ["tropical"]

    for note_type in note_types:
        targets = [None] if note_type == "portfolio_snapshot" else project_keys
        for project_key in targets:
            payload = service.build_note_source(
                note_type,
                project_key=project_key,
                as_of=as_of_date,
                comparison_basis=args.comparison_basis,
                status=args.status,
            )
            rel_path = note_relative_path(payload)
            markdown = render_note_markdown(payload)
            assert_note_safe(markdown)
            leaks = find_redaction_leaks({"payload": payload, "markdown": markdown})
            if leaks:
                raise RuntimeError(f"redaction_leak:{leaks}")
            language = validate_rendered_text(markdown, surface="export")
            if not language.get("passed"):
                raise RuntimeError(f"language_qa_failed:{language.get('violations')}")

            advisory_markdown: str | None = None
            if args.summarize:
                from hb_assistant.construction.classification.client import (
                    OllamaChatClient,
                    OllamaUnavailable,
                    list_ollama_models,
                )
                from hb_assistant.obsidian_mcp import source_local_summary as sls

                models = list_ollama_models()
                if args.model not in models:
                    print(f"model unavailable: {args.model}", file=sys.stderr)
                    return 3
                client = OllamaChatClient(model=args.model)
                prompt = sls.build_summary_prompt(
                    markdown,
                    {"note_type": note_type, "project_key": project_key},
                    max_input_chars=6000,
                )
                try:
                    lines, reason = sls.generate_advisory(client, prompt)
                    ollama_calls += 1
                except OllamaUnavailable as exc:
                    print(str(exc), file=sys.stderr)
                    return 3
                if not lines:
                    advisory_failures.append({"note_type": note_type, "project_key": project_key, "reason": reason})
                else:
                    advisory_text = "\n".join(lines)
                    validation = validate_schedule_advisory(advisory_text, payload=payload)
                    if validation.get("passed"):
                        advisory_markdown = advisory_text
                        markdown = render_note_markdown(payload, advisory_markdown=advisory_markdown)
                    else:
                        advisory_failures.append(
                            {
                                "note_type": note_type,
                                "project_key": project_key,
                                "violations": validation.get("violations"),
                            }
                        )

            notes_planned += 1
            result = apply_schedule_note_write(
                vault_root=vault_root,
                relative_path=rel_path,
                payload=payload,
                dry_run=dry_run,
                advisory_markdown=advisory_markdown,
            )
            entry = {
                "note_type": note_type,
                "project_key": project_key,
                "relative_path": rel_path,
                "action": result.action,
                "idempotency_key": service.idempotency_key(payload),
            }
            outputs.append(entry)
            if result.conflict:
                conflicts += 1
            elif result.action in {"created", "planned_create"} and not dry_run:
                notes_written += 1
            elif result.action in {"updated", "planned_update"} and not dry_run:
                notes_updated += 1

            if args.markdown_output:
                Path(args.markdown_output).write_text(markdown, encoding="utf-8")

    summary = {
        "mode": "dry_run" if dry_run else "write",
        "notes_planned": notes_planned,
        "notes_written": notes_written,
        "notes_updated": notes_updated,
        "conflicts": conflicts,
        "ollama_calls": ollama_calls,
        "db_mutations": 0,
        "vault_root": str(vault_root),
        "outputs": outputs,
        "advisory_failures": advisory_failures,
    }
    if args.json_output:
        Path(args.json_output).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
