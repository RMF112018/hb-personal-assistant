"""Phase 04B enriched Obsidian register.

Projects the second-brain V7 enrichment tables (action signals, change events,
text intelligence) into one deterministic, source-linked Obsidian note per
project — eight sections: open actions, last-48h changes, inspection unanswered
items, safety/compliance queue, meeting decisions/actions, RFI response changes,
submittal workflow changes, schedule risk signals.

Read-only / local. Dry-run builds the rendered note; ``--apply`` writes the single
marker-bounded note alongside the other ``procore-*`` artifacts in ``01_Projects/``.
Output carries only already-redacted columns + source ``record_key`` /
``procore_record_id`` + a local query-command reference — never raw payload
bodies, signed URLs, or tokens.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..store.procore_enrichment import get_procore_action_signals, get_procore_text_intelligence
from ..store.procore_history import get_procore_changes
from .obsidian import PROCORE_GUARDRAILS, _write_procore_artifact

_MARKER_KIND = "ENRICHED-REGISTER"
_FILENAME_SUFFIX = "procore-memory-register.md"

_INSPECTION_UNANSWERED = {"inspection_has_unanswered_items", "inspection_item_unanswered"}
_SAFETY_SIGNAL_TYPES = {"observation_open_safety", "inspection_open_safety"}
_RFI_ENDPOINTS = {"rfis", "rfi-responses"}
_SUBMITTAL_ENDPOINTS = {"submittals", "submittal-responses", "submittal-approvers"}
_MEETING_ENDPOINTS = {"meetings", "meeting-detail", "meeting-topics"}


def _table(headers: List[str], rows: List[List[str]], *, empty: str) -> str:
    if not rows:
        return f"_{empty}_"
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = "\n".join("| " + " | ".join(_cell(c) for c in r) + " |" for r in rows)
    return "\n".join([head, sep, body])


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _section(title: str, query: str, table_md: str) -> str:
    return f"## {title}\n\n_Query: `{query}`_\n\n{table_md}\n"


def _decode_list(value: Any) -> str:
    if not value:
        return ""
    try:
        items = json.loads(value)
    except (TypeError, ValueError):
        return ""
    if isinstance(items, list):
        return ", ".join(str(i) for i in items)
    return str(items)


# --------------------------------------------------------------------------- #
# Section builders
# --------------------------------------------------------------------------- #


def _signal_rows(signals: List[Dict[str, Any]]) -> List[List[str]]:
    return [
        [
            s.get("signal_type"),
            s.get("importance"),
            s.get("signal_status"),
            s.get("endpoint_id"),
            s.get("record_key"),
            s.get("due_at_utc") or "",
            s.get("title_redacted") or "",
        ]
        for s in signals
    ]


_SIGNAL_HEADERS = ["Signal", "Importance", "Status", "Endpoint", "Record Key", "Due", "Title"]
_CHANGE_HEADERS = ["Detected", "Endpoint", "Record ID", "Field", "Category", "Type", "Record Key"]


def _change_rows(changes: List[Dict[str, Any]]) -> List[List[str]]:
    return [
        [
            c.get("detected_at_utc"),
            c.get("endpoint_id"),
            c.get("procore_record_id"),
            c.get("field_path"),
            c.get("change_category"),
            c.get("change_type"),
            c.get("record_key"),
        ]
        for c in changes
    ]


def build_enriched_registers(
    project_key: str,
    *,
    since_utc: str,
    now_utc: str,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build the eight enriched register sections for a project (pure read)."""
    signals = get_procore_action_signals(project_key=project_key, db_path=db_path)
    changes = get_procore_changes(project_key=project_key, db_path=db_path)
    recent = [c for c in changes if (c.get("detected_at_utc") or "") >= since_utc]
    meeting_ti = [
        t
        for t in get_procore_text_intelligence(
            project_key=project_key,
            with_action_candidates=True,
            db_path=db_path,
        )
        if t.get("endpoint_id") in _MEETING_ENDPOINTS
    ]

    open_signals = [s for s in signals if (s.get("signal_status") or "") == "open"]
    insp_unanswered = [s for s in signals if s.get("signal_type") in _INSPECTION_UNANSWERED]
    safety = [s for s in signals if s.get("signal_type") in _SAFETY_SIGNAL_TYPES]
    schedule_risk = [s for s in signals if str(s.get("signal_type") or "").startswith("activity_")]
    rfi_changes = [c for c in changes if c.get("endpoint_id") in _RFI_ENDPOINTS]
    submittal_changes = [c for c in changes if c.get("endpoint_id") in _SUBMITTAL_ENDPOINTS]

    sections: Dict[str, str] = {
        "open_actions": _section(
            "Open Actions",
            f"hb-assistant procore live actions --project {project_key} --status open --json",
            _table(_SIGNAL_HEADERS, _signal_rows(open_signals), empty="No open action signals."),
        ),
        "recent_changes": _section(
            "Last 48h Changes",
            f'hb-assistant procore live changes --project {project_key} --since "48 hours ago" --json',
            _table(_CHANGE_HEADERS, _change_rows(recent), empty="No changes in the window."),
        ),
        "inspection_unanswered": _section(
            "Inspection Unanswered Items",
            f"hb-assistant procore live actions --project {project_key} --endpoint inspections --json",
            _table(
                _SIGNAL_HEADERS,
                _signal_rows(insp_unanswered),
                empty="No unanswered inspection items.",
            ),
        ),
        "safety_queue": _section(
            "Safety / Compliance Queue",
            f"hb-assistant procore live actions --project {project_key} --json",
            _table(
                _SIGNAL_HEADERS, _signal_rows(safety), empty="No open safety/compliance signals."
            ),
        ),
        "meeting_actions": _section(
            "Meeting Decisions / Actions",
            f'hb-assistant procore live timeline --project {project_key} --since "7 days ago" --json',
            _table(
                ["Record Key", "Field", "Action Candidates", "Excerpt"],
                [
                    [
                        t.get("record_key"),
                        t.get("source_field_path"),
                        _decode_list(t.get("action_candidates_json")),
                        t.get("excerpt_redacted") or "",
                    ]
                    for t in meeting_ti
                ],
                empty="No meeting decisions/actions detected.",
            ),
        ),
        "rfi_response_changes": _section(
            "RFI Response Changes",
            f'hb-assistant procore live changes --project {project_key} --endpoint rfis --since "7 days ago" --json',
            _table(_CHANGE_HEADERS, _change_rows(rfi_changes), empty="No RFI response changes."),
        ),
        "submittal_workflow_changes": _section(
            "Submittal Workflow Changes",
            f'hb-assistant procore live changes --project {project_key} --endpoint submittals --since "7 days ago" --json',
            _table(
                _CHANGE_HEADERS,
                _change_rows(submittal_changes),
                empty="No submittal workflow changes.",
            ),
        ),
        "schedule_risk": _section(
            "Schedule Risk Signals",
            f"hb-assistant procore live actions --project {project_key} --endpoint activities --json",
            _table(_SIGNAL_HEADERS, _signal_rows(schedule_risk), empty="No schedule risk signals."),
        ),
    }

    counts = {
        "open_actions": len(open_signals),
        "recent_changes": len(recent),
        "inspection_unanswered": len(insp_unanswered),
        "safety_queue": len(safety),
        "meeting_actions": len(meeting_ti),
        "rfi_response_changes": len(rfi_changes),
        "submittal_workflow_changes": len(submittal_changes),
        "schedule_risk": len(schedule_risk),
    }
    rendered = _render_note(project_key, now_utc=now_utc, since_utc=since_utc, sections=sections)
    return {
        "project_key": project_key,
        "generated_utc": now_utc,
        "since_utc": since_utc,
        "sections": sections,
        "rendered": rendered,
        "counts": counts,
        "review_sensitive": False,
        "guardrails": dict(PROCORE_GUARDRAILS),
    }


def _render_note(
    project_key: str, *, now_utc: str, since_utc: str, sections: Dict[str, str]
) -> str:
    frontmatter = "\n".join(
        [
            "---",
            "type: procore_enriched_register",
            f"project_key: {project_key}",
            "source: procore_second_brain_sqlite",
            "review_sensitive: false",
            f"generated_utc: {now_utc}",
            "---",
        ]
    )
    order = [
        "open_actions",
        "recent_changes",
        "inspection_unanswered",
        "safety_queue",
        "meeting_actions",
        "rfi_response_changes",
        "submittal_workflow_changes",
        "schedule_risk",
    ]
    body = "\n\n".join(sections[k] for k in order)
    guardrails = "\n".join(f"- {k}: {v}" for k, v in PROCORE_GUARDRAILS.items())
    return (
        f"{frontmatter}\n\n# Procore Memory Register — {project_key}\n\n"
        f"_Window since: {since_utc}. Local SQLite second-brain projection — no Procore call._\n\n"
        f"{body}\n\n## Guardrails\n\n{guardrails}\n"
    )


def apply_enriched_register(
    project_key: str,
    *,
    since_utc: str,
    now_utc: str,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build + write the single enriched-register note (marker-bounded). Returns
    the build result with ``written_paths`` populated (or a vault-not-configured
    marker when no vault root is set)."""
    from ..construction.manifests.vault_writer import ConstructionVaultWriter

    result = build_enriched_registers(
        project_key, since_utc=since_utc, now_utc=now_utc, db_path=db_path
    )
    writer = ConstructionVaultWriter()
    if not writer.configured:
        result["written_paths"] = []
        result["vault_configured"] = False
        return result
    path = _write_procore_artifact(
        writer.root,
        f"{project_key}.{_FILENAME_SUFFIX}",
        result["rendered"],
        _MARKER_KIND,
    )
    result["written_paths"] = [str(path)]
    result["vault_configured"] = True
    return result


__all__ = ["build_enriched_registers", "apply_enriched_register"]
