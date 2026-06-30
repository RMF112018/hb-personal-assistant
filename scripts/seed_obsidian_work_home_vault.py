#!/usr/bin/env python3
"""Seed the clean Work/Home Obsidian vault with durable Markdown templates, dashboards, MOCs, and
README/frontmatter standards. DRY-RUN BY DEFAULT.

Safety model (mirrors scripts/obsidian_vault_quarantine_reset.py):
* Refuses unsafe vault paths and — outside tests — any non-default path.
* Refuses ``--apply`` while a backend listens on port 8000 (writes shouldn't race a live watcher).
* Writes ONLY Markdown files into the active vault. Never copies from a quarantine, never touches
  external source roots, never writes the production DB, never starts a backend.
* Idempotent: an existing file is skipped unless it carries the managed marker AND
  ``--overwrite-generated`` is given. A user-authored file (no marker) is NEVER overwritten.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_VAULT_PATH = "/Users/bobbyfetting/Documents/Obsidian Vault"
BACKEND_PORT = 8000
MANAGED_MARKER = "<!-- hb-managed: obsidian-work-home-seed v1 -->"

_UNSAFE_EXACT = {
    "", "/", str(Path.home()), str(Path.home() / "Documents"),
    "/Users/bobbyfetting", "/Users/bobbyfetting/Documents",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _backend_listening(port: int = BACKEND_PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


class SeedError(Exception):
    """Refusal — printed as a controlled error, exit code 3."""


def _validate_vault_path(vault: Path, *, allow_nonstandard: bool) -> None:
    resolved = str(vault)
    if resolved.strip() in ("", "."):
        raise SeedError("Refusing empty/'.' vault path.")
    if resolved in _UNSAFE_EXACT or resolved.rstrip("/") in _UNSAFE_EXACT:
        raise SeedError(f"Refusing unsafe vault path: {resolved!r}")
    if not allow_nonstandard and resolved != DEFAULT_VAULT_PATH:
        raise SeedError(
            f"Refusing non-standard vault path {resolved!r} (expected {DEFAULT_VAULT_PATH!r}). "
            "Pass --allow-nonstandard-vault-path to override (tests/operator-explicit only)."
        )


def _doc(body: str) -> str:
    """Prepend the managed marker so the file can be safely re-seeded with --overwrite-generated."""
    return f"{MANAGED_MARKER}\n{body.lstrip()}"


# ---- seed content -----------------------------------------------------------------------------
_ROOT_README = _doc("""
# Obsidian Vault — Work/Home Second Brain

This vault is a **curated Markdown knowledge system**, not a storage dump.

- **Raw project files** (PDFs, drawings, models, spreadsheets, archives) belong in **external source
  roots**, NOT in this vault.
- **`Work`** and **`Home`** are the two primary life domains.
- **`Source Notes`** holds GENERATED source cards and summaries (one per external file), subdivided
  into `Work/`, `Home/`, and `Shared/`.
- **`Attachments`** is for lightweight, intentional, Markdown-referenced files only — it is NOT a
  project-file dump.
- `Daily`, `MOCs`, `Templates`, and `99 System` round out the structure.
""")

_WORK_DASHBOARD = _doc("""
# Work Dashboard

## Active Projects

## Meetings This Week

## Decisions Requiring Review

## Open Actions

## Recent Source Notes

## Project Controls / Schedule / Cost Watchlist

## People and Companies

## Useful MOCs
""")

_HOME_DASHBOARD = _doc("""
# Home Dashboard

## Personal Admin

## Home Projects

## Family

## Finance

## Health / Fitness

## Travel

## Learning

## Open Actions

## Useful MOCs
""")

_SOURCE_CARD_TEMPLATE = _doc("""---
note_type: source_card
domain: work
source_id: ""
source_kind: external_file
source_root_key: ""
source_path: ""
source_sha256: ""
source_mtime_ns: ""
generated_at: ""
updated_at: ""
stale: false
project_key: ""
project_number: ""
document_type: ""
source_disposition: ""
source_confidence: ""
review_status: unreviewed
summary_advisory: false
template_version: "source-card-v1"
card_version: ""
tags:
  - source/external-file
  - domain/work
---

# {{title}}

## Source Summary

## Why This Matters

## PM Review Cues

## Key Facts

## Related Project

## Related People / Companies

## Related Decisions

## Related Meetings

## Source Basis

## Advisory Summary

## Follow-Up
""")

_WORK_PROJECT_TEMPLATE = _doc("""---
note_type: work_project
domain: work
project_key: ""
project_number: ""
project_name: ""
client: ""
status: active
tags:
  - domain/work
  - work/project
---

# {{project_name}}

## Project Snapshot

## Current Priorities

## Key Risks

## Schedule / Controls

## Cost / Change Management

## RFIs / Submittals

## Meetings

## Decisions

## Actions

## Source Notes

## People / Companies
""")

_HOME_PROJECT_TEMPLATE = _doc("""---
note_type: home_project
domain: home
project_name: ""
status: active
tags:
  - domain/home
  - home/project
---

# {{project_name}}

## Objective

## Current Status

## Next Actions

## Decisions

## References

## Notes
""")

_WORK_MEETING_TEMPLATE = _doc("""---
note_type: meeting
domain: work
meeting_date: ""
project_key: ""
project_number: ""
attendees: []
related_sources: []
action_items: []
tags:
  - domain/work
  - meeting
---

# Meeting: {{title}}

## Attendees

## Agenda

## Notes

## Decisions

## Action Items

## Related Sources
""")

_HOME_MEETING_TEMPLATE = _doc("""---
note_type: meeting
domain: home
meeting_date: ""
attendees: []
action_items: []
tags:
  - domain/home
  - meeting
---

# Check-in: {{title}}

## Attendees

## Notes

## Action Items
""")

_DECISION_TEMPLATE = _doc("""---
note_type: decision
domain: work
decision_status: proposed
decision_date: ""
project_key: ""
project_number: ""
related_sources: []
related_meetings: []
tags:
  - decision
---

# Decision: {{title}}

## Decision

## Context

## Options Considered

## Rationale

## Risks / Tradeoffs

## Source Basis

## Follow-Up
""")

_WORK_DAILY_TEMPLATE = _doc("""---
note_type: daily
domain: work
date: ""
tags:
  - domain/work
  - daily
---

# Work Daily - {{date}}

## Top Priorities

## Meetings

## Decisions

## Actions

## Project Notes

## Source Notes Reviewed

## Follow-Up
""")

_HOME_DAILY_TEMPLATE = _doc("""---
note_type: daily
domain: home
date: ""
tags:
  - domain/home
  - daily
---

# Home Daily - {{date}}

## Priorities

## Family / Personal

## Home Projects

## Finance / Admin

## Health / Fitness

## Follow-Up
""")

_PERSON_TEMPLATE = _doc("""---
note_type: person
domain: work
full_name: ""
company: ""
role: ""
email: ""
phone: ""
tags:
  - person
---

# {{full_name}}

## Role / Company

## Context

## Related Projects

## Related Meetings

## Notes
""")

_COMPANY_TEMPLATE = _doc("""---
note_type: company
domain: work
company_name: ""
company_type: ""
tags:
  - company
---

# {{company_name}}

## Overview

## Related Projects

## Key People

## Notes
""")


def _readme(title: str, purpose: str, not_here: str = "") -> str:
    body = f"# {title}\n\n{purpose}\n"
    if not_here:
        body += f"\n**Does not belong here:** {not_here}\n"
    return _doc(body)


def _moc(domain: str) -> str:
    return _doc(f"""
# {domain} MOC

A Map of Content linking the key {domain.lower()} notes — projects, people, decisions, and source notes.

## Projects

## People / Companies

## Decisions

## Source Notes
""")


def seed_files() -> dict[str, str]:
    """Return {vault-relative path -> Markdown content}. Every entry is a .md file."""
    files: dict[str, str] = {
        # Root + system
        "README.md": _ROOT_README,
        "00 Inbox/README.md": _readme(
            "Inbox", "Unsorted capture. Triage into Work/ or Home/ promptly.",
            "Long-term storage — move notes to their domain."),
        "Attachments/README.md": _readme(
            "Attachments", "Lightweight, intentional, Markdown-referenced files only.",
            "Project corpuses or raw source dumps."),
        "90 Archive/README.md": _readme("Archive", "Retired notes kept for reference."),
        "99 System/README.md": _readme(
            "System", "Operational notes: manifests, receipts, runbooks. Not knowledge content."),
        "99 System/Runbooks/README.md": _readme("Runbooks", "Operational runbooks for this vault."),
        "99 System/Manifests/README.md": _readme("Manifests", "Reset/seed manifests (audit)."),
        "99 System/Receipts/README.md": _readme("Receipts", "Reset/seed receipts (audit)."),
        # Work
        "Work/00 Dashboard/Work Dashboard.md": _WORK_DASHBOARD,
        "Work/01 Projects/README.md": _readme("Work Projects", "One note per active work/construction project."),
        "Work/02 Meetings/README.md": _readme("Work Meetings", "Meeting notes and prep."),
        "Work/03 Decisions/README.md": _readme("Work Decisions", "Decision logs."),
        "Work/04 Actions/README.md": _readme("Work Actions", "Open action items and follow-ups."),
        "Work/05 People/README.md": _readme("Work People", "Professional contacts."),
        "Work/06 Companies/README.md": _readme("Work Companies", "Companies / vendors / subs / clients."),
        "Work/07 Knowledge/README.md": _readme("Work Knowledge", "Lessons learned and reference knowledge."),
        "Work/08 Templates/README.md": _readme("Work Templates", "Work-specific note templates."),
        "Work/09 Archive/README.md": _readme("Work Archive", "Retired work notes."),
        # Home
        "Home/00 Dashboard/Home Dashboard.md": _HOME_DASHBOARD,
        "Home/01 Personal Admin/README.md": _readme("Personal Admin", "Personal administrative notes."),
        "Home/02 Family/README.md": _readme("Family", "Family notes."),
        "Home/03 Home Projects/README.md": _readme("Home Projects", "Personal/home projects."),
        "Home/04 Finance/README.md": _readme("Finance", "Personal finance notes."),
        "Home/05 Health Fitness/README.md": _readme("Health / Fitness", "Health and fitness notes."),
        "Home/06 Travel/README.md": _readme("Travel", "Travel planning and logs."),
        "Home/07 Learning/README.md": _readme("Learning", "Learning and study notes."),
        "Home/08 People/README.md": _readme("Home People", "Personal contacts."),
        "Home/09 Archive/README.md": _readme("Home Archive", "Retired home notes."),
        # Source Notes
        "Source Notes/README.md": _readme(
            "Source Notes", "GENERATED source cards/summaries (one per external file), by domain.",
            "Hand-authored notes — these are machine-managed and may be refreshed/retired."),
        "Source Notes/Work/README.md": _readme("Source Notes — Work", "Generated cards for work sources."),
        "Source Notes/Home/README.md": _readme("Source Notes — Home", "Generated cards for home sources."),
        "Source Notes/Shared/README.md": _readme(
            "Source Notes — Shared", "Generated cards whose domain is shared/ambiguous."),
        # Daily + MOCs
        "Daily/README.md": _readme("Daily", "Daily notes split by domain (Work/, Home/)."),
        "Daily/Work/README.md": _readme("Work Daily", "Work daily notes."),
        "Daily/Home/README.md": _readme("Home Daily", "Home daily notes."),
        "MOCs/README.md": _readme("MOCs", "Maps of Content / dashboards (Work/, Home/, Shared/)."),
        "MOCs/Work/Work MOC.md": _moc("Work"),
        "MOCs/Home/Home MOC.md": _moc("Home"),
        "MOCs/Shared/Shared MOC.md": _moc("Shared"),
        # Templates
        "Templates/README.md": _readme("Templates", "Note templates for source cards, projects, meetings, etc."),
        "Templates/Source Cards/source-card-template.md": _SOURCE_CARD_TEMPLATE,
        "Templates/Projects/work-project-template.md": _WORK_PROJECT_TEMPLATE,
        "Templates/Projects/home-project-template.md": _HOME_PROJECT_TEMPLATE,
        "Templates/Meetings/work-meeting-template.md": _WORK_MEETING_TEMPLATE,
        "Templates/Meetings/home-meeting-template.md": _HOME_MEETING_TEMPLATE,
        "Templates/Decisions/decision-log-template.md": _DECISION_TEMPLATE,
        "Templates/Daily/work-daily-template.md": _WORK_DAILY_TEMPLATE,
        "Templates/Daily/home-daily-template.md": _HOME_DAILY_TEMPLATE,
        "Templates/People/person-template.md": _PERSON_TEMPLATE,
        "Templates/Companies/company-template.md": _COMPANY_TEMPLATE,
    }
    return files


def plan_seed(vault: Path, *, overwrite_generated: bool) -> dict[str, list[str]]:
    """Classify each seed file into create / overwrite_managed / skip_existing_user /
    skip_existing_managed. Pure (no writes)."""
    plan: dict[str, list[str]] = {
        "create": [], "overwrite_managed": [], "skip_existing_user": [], "skip_existing_managed": [],
    }
    for rel in seed_files():
        target = vault / rel
        if not target.exists():
            plan["create"].append(rel)
            continue
        try:
            head = target.read_text(encoding="utf-8")[:200]
        except OSError:
            head = ""
        is_managed = MANAGED_MARKER in head
        if is_managed and overwrite_generated:
            plan["overwrite_managed"].append(rel)
        elif is_managed:
            plan["skip_existing_managed"].append(rel)
        else:
            plan["skip_existing_user"].append(rel)
    return plan


def apply_seed(vault: Path, *, overwrite_generated: bool) -> dict[str, list[str]]:
    plan = plan_seed(vault, overwrite_generated=overwrite_generated)
    files = seed_files()
    written: list[str] = []
    for rel in plan["create"] + plan["overwrite_managed"]:
        target = vault / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(files[rel] + ("\n" if not files[rel].endswith("\n") else ""), encoding="utf-8")
        written.append(rel)
    plan["written"] = written
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the Work/Home Obsidian vault (dry-run by default).")
    parser.add_argument("--vault-path", default=DEFAULT_VAULT_PATH)
    parser.add_argument("--evidence-dir", default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--overwrite-generated", action="store_true",
                        help="Overwrite files that carry the managed marker (never user-authored files).")
    parser.add_argument("--allow-nonstandard-vault-path", action="store_true")
    args = parser.parse_args(argv)

    vault = Path(args.vault_path)
    try:
        _validate_vault_path(vault, allow_nonstandard=args.allow_nonstandard_vault_path)
        if args.apply:
            if not vault.is_dir():
                raise SeedError(f"Vault path does not exist: {vault}")
            if _backend_listening():
                raise SeedError("Refusing --apply while a backend is listening on port 8000.")
            plan = apply_seed(vault, overwrite_generated=args.overwrite_generated)
            mode = "apply"
        else:
            plan = plan_seed(vault, overwrite_generated=args.overwrite_generated)
            mode = "dry_run"
    except SeedError as exc:
        print(json.dumps({"refused": True, "reason": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 3

    result: dict[str, Any] = {
        "mode": mode, "vault_path": str(vault), "generated_at": _now_iso(),
        "managed_marker": MANAGED_MARKER, "external_roots_touched": False,
        "total_seed_files": len(seed_files()),
        "create_count": len(plan["create"]),
        "overwrite_managed_count": len(plan["overwrite_managed"]),
        "skip_existing_user_count": len(plan["skip_existing_user"]),
        "skip_existing_managed_count": len(plan["skip_existing_managed"]),
        "written_count": len(plan.get("written", [])),
        "create": plan["create"],
        "overwrite_managed": plan["overwrite_managed"],
        "skip_existing_user": plan["skip_existing_user"],
    }
    if args.evidence_dir:
        ev = Path(args.evidence_dir)
        ev.mkdir(parents=True, exist_ok=True)
        (ev / f"seed-plan-{mode}.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
