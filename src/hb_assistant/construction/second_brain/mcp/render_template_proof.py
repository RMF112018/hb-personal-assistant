"""Phase 09 Addendum — Claude scheduled-task rendering template proof.

Statically validates the two operator-facing Claude prompt templates that drive daily-brief rendering
through the MCP packet tool (Daily Brief V2): each must instruct Claude to call only
``hb_daily_brief_packet``, render only the ``render_payload`` (never ``governance_metadata``), request
no raw records, call no direct database/Graph/Procore/vector/memory tools, make no final
determinations, produce the concise 5-section executive structure (Yesterday / Today / Next 7 Days /
Needs Attention / Focus) with a one-line advisory footer, write "detail unavailable" instead of bare
counts, explicitly NOT render provenance/guardrail/source-coverage/follow-up/generated-utc/dry-run/raw
json, and state the storage policy (rendered output is narrative/advisory, never imported into
source-of-truth surfaces). Read-only; the templates and proof are scanned for raw-shaped values
(fail-closed).

Public entry point:
  build_claude_render_template_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain mcp daily-brief-render-template-proof --json
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy

from ..financial_review_routing import _assert_no_raw

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-daily-brief-mcp-handoff"
_PROOF_JSON = "claude-rendering-template-proof.json"
_PROOF_MD = "claude-rendering-template-proof.md"

_TEMPLATES_RELATIVE = Path("resources") / "templates"

# canonical template filename -> evidence copy filename
_TEMPLATES: dict[str, str] = {
    "claude_daily_brief_scheduled_task.md": "claude-daily-brief-scheduled-task-template.md",
    "claude_daily_brief_manual_run.md": "claude-daily-brief-manual-run-template.md",
}

# (check label, required case-insensitive substring) — every template must satisfy all of these.
# Daily Brief V2 (Prompt 03): concise executive structure rendered from render_payload only.
_REQUIRED_SUBSTRINGS: tuple[tuple[str, str], ...] = (
    ("calls_packet_tool", "hb_daily_brief_packet"),
    ("renders_render_payload", "render_payload"),
    ("never_governance_metadata", "governance_metadata"),
    ("no_raw_records", "do not request raw records"),
    ("forbid_database", "database"),
    ("forbid_graph", "graph"),
    ("forbid_procore", "procore"),
    ("forbid_vector", "vector"),
    ("forbid_memory_mutation", "memory mutation"),
    ("no_determinations", "determinations"),
    ("brief", "brief"),
    ("descriptive", "descriptive"),
    ("executive", "executive"),
    ("use_project_names", "project names/keys"),
    ("detail_unavailable", "detail unavailable"),
    ("focus_limit", "no more than 3"),
    ("one_line_footer", "verify in source systems before final action"),
    # 5 output sections
    ("section_yesterday", "## yesterday"),
    ("section_today", "## today"),
    ("section_next_7_days", "## next 7 days"),
    ("section_needs_attention", "## needs attention"),
    ("section_focus", "## focus"),
    # explicit "do not render" prohibitions
    ("forbid_provenance", "provenance"),
    ("forbid_guardrail_matrix", "guardrail matrix"),
    ("forbid_source_coverage_body", "source coverage"),
    ("forbid_follow_up", "follow-up"),
    ("forbid_generated_utc", "generated utc"),
    ("forbid_dry_run", "dry-run"),
    ("forbid_raw_json", "raw json"),
    # storage policy
    ("storage_not_source_truth", "not source truth"),
    ("storage_no_accepted_memory", "accepted memory"),
    ("storage_no_vector_index", "vector index"),
    ("storage_no_source_manifest", "source manifest"),
    ("storage_no_source_linked_proof", "source-linked proof"),
)


class ClaudeRenderTemplateError(RuntimeError):
    """Raised when a required Claude render template is missing (fail-closed)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_sha() -> str:
    try:
        repo_root = Path(__file__).resolve().parents[5]
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, stderr=subprocess.DEVNULL, timeout=5
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


def _templates_dir() -> Path:
    return PathPolicy().resolve_repo_root() / _TEMPLATES_RELATIVE


def _check_template(text: str) -> dict[str, bool]:
    low = text.lower()
    return {label: (sub.lower() in low) for label, sub in _REQUIRED_SUBSTRINGS}


def _render_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — Claude Render Template Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- templates_present: {proof['templates_present']}",
        f"- no_raw_emitted: {proof['no_raw_emitted']}",
        "",
        "## Per-template checks",
        "",
    ]
    for name, report in proof["templates"].items():
        failed = sorted(k for k, v in report["checks"].items() if not v)
        lines.append(
            f"- {name}: all_present={report['all_present']}"
            + (f" missing={failed}" if failed else "")
        )
    lines.append("")
    return "\n".join(lines)


def build_claude_render_template_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed static proof that the Claude render templates carry the required guardrail
    instructions, output format, and storage policy (read-only)."""
    templates_dir = _templates_dir()

    templates_report: dict[str, Any] = {}
    contents: dict[str, str] = {}
    all_present = True
    templates_present = True
    no_raw_emitted = True

    for canonical in _TEMPLATES:
        path = templates_dir / canonical
        if not path.exists():
            raise ClaudeRenderTemplateError(f"required render template not found: {path}")
        text = path.read_text(encoding="utf-8")
        contents[canonical] = text
        try:
            _assert_no_raw(text, f"render template {canonical}")
        except ValueError:
            no_raw_emitted = False
        checks = _check_template(text)
        template_ok = all(checks.values())
        all_present = all_present and template_ok
        templates_report[canonical] = {"all_present": template_ok, "checks": checks}

    proof_passed = bool(all_present and templates_present and no_raw_emitted)

    proof: dict[str, Any] = {
        "proof": "phase_09_claude_render_template",
        "command": "second-brain mcp daily-brief-render-template-proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "tool_referenced": "hb_daily_brief_packet",
        "templates_present": templates_present,
        "no_raw_emitted": no_raw_emitted,
        "template_count": len(_TEMPLATES),
        "required_check_count": len(_REQUIRED_SUBSTRINGS),
        "templates": templates_report,
        "metadata_only": True,
        "guardrails": {
            "advisory_only": True,
            "claude_rendering_only": True,
            "packet_tool_only": True,
            "no_raw": True,
            "no_direct_graph_procore_db_vector_memory": True,
            "no_final_determination": True,
            "rendered_output_not_source_truth": True,
            "no_import_into_source_of_truth": True,
            "read_only": True,
            "fail_closed": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        # Faithful evidence copies of the validated templates.
        for canonical, evidence_name in _TEMPLATES.items():
            copy_text = contents[canonical]
            _assert_no_raw(copy_text, f"render template evidence {evidence_name}")
            (out_dir / evidence_name).write_text(copy_text, encoding="utf-8")
        serialized = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(serialized, "claude render template proof json")
        (out_dir / _PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "claude render template proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof
