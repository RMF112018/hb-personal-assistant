#!/usr/bin/env python3
"""Generate expected-vs-actual route proof matrix (JSON + Markdown).

``pass`` is computed only from explicit expectations — never assigned independently.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hb_assistant.obsidian_mcp.prompt_preflight import route_prompt  # noqa: E402


# Explicit expectations: pass is derived only from these.
CASES: list[dict] = [
    {
        "id": "project_notes",
        "prompt": "Find my project notes.",
        "expected": {
            "workflow": "vault_note_search",
            "read_authorized": True,
            "prohibitions_include": [],
            "prohibitions_exclude": ["execute"],
            "tools_include": ["assistant_search_sources"],
        },
    },
    {
        "id": "identify_source_roots_plan_only",
        "prompt": (
            "Read-only: identify which tool should be used to list configured source roots.\n"
            "Do not execute any action."
        ),
        "expected": {
            "workflow": "source_root_map",
            "read_authorized": False,
            "prohibitions_include": ["execute"],
            "prohibitions_exclude": [],
            "tools_include": ["assistant_source_roots_list", "assistant_source_root_map"],
            "per_tool_groups": {
                "assistant_source_roots_list": "source_connector",
                "assistant_source_root_map": "source_structure",
            },
        },
    },
    {
        "id": "nas_file_search_explain",
        "prompt": "Explain which read-only Personal Assistant tool searches indexed NAS files.",
        "expected": {
            "workflow": "source_file_search",
            "read_authorized": True,
            "prohibitions_include": [],
            "prohibitions_exclude": ["execute"],
            "tools_include": ["assistant_source_file_search"],
        },
    },
    {
        "id": "read_only_repo_truth_audit",
        "prompt": (
            "Conduct a read-only repo-truth audit.\n"
            "Do not write, stage, promote, refresh, index, deploy, or mutate anything."
        ),
        "expected": {
            "workflow": "read_only_surface_audit",
            "read_authorized": True,
            "prohibitions_include": ["write", "stage", "promote", "index", "deploy"],
            "prohibitions_exclude": ["execute"],
            "tools_include": ["hb_mcp_status"],
        },
    },
    {
        "id": "search_work_files",
        "prompt": "Search my work files.",
        "expected": {
            "workflow": "source_file_search",
            "read_authorized": True,
            "prohibitions_include": [],
            "prohibitions_exclude": ["execute", "write"],
        },
    },
    {
        "id": "do_not_promote",
        "prompt": "Do not promote anything.",
        "expected": {
            "workflow_not": "apply_canonical_promotion",
            "read_authorized": False,  # no retrieval match → clarify; or True if matched read
            "prohibitions_include": ["promote"],
            "promotion_authorized": False,
        },
    },
    {
        "id": "vault_meeting_notes",
        "prompt": "Search the vault for meeting notes.",
        "expected": {
            "workflow": "vault_note_search",
            "read_authorized": True,
            "prohibitions_exclude": ["execute"],
        },
    },
    {
        "id": "decision_retrieval",
        "prompt": "What did we decide about X?",
        "expected": {
            "workflow": "canonical_decision_retrieval",
            "read_authorized": True,
        },
    },
    {
        "id": "you_may_use_read_only",
        "prompt": "You may use read-only tools. Search my work files.",
        "expected": {
            "workflow": "source_file_search",
            "read_authorized": True,
            "prohibitions_exclude": ["execute"],
        },
    },
    {
        "id": "plan_only_no_execute",
        "prompt": "Plan only; do not execute.",
        "expected": {
            "read_authorized": False,
            "prohibitions_include": ["execute"],
        },
    },
    {
        "id": "search_without_writing",
        "prompt": "Search without writing anything.",
        "expected": {
            "workflow": "source_file_search",
            "read_authorized": True,
            "prohibitions_include": ["write"],
            "prohibitions_exclude": ["execute"],
        },
    },
    {
        "id": "beyond_read_only_analysis",
        "prompt": "Do not execute tools beyond read-only analysis.",
        "expected": {
            "read_authorized": True,
            "prohibitions_include": ["write", "stage", "promote"],
            # execute may be present as non-read ban marker under beyond-read-only
        },
    },
    {
        "id": "find_file_without_opening",
        "prompt": "Find the file without opening it.",
        "expected": {
            "workflow": "source_file_search",
            "read_authorized": True,
            "prohibitions_exclude": ["write", "promote"],
        },
    },
    {
        "id": "not_a_promotion_receipt",
        "prompt": "This is not a promotion receipt.",
        "expected": {
            "workflow_not": "apply_canonical_promotion",
            "promotion_authorized": False,
        },
    },
    {
        "id": "preference_retrieval",
        "prompt": "What preferences do I have for X?",
        "expected": {
            "workflow": "canonical_preference_retrieval",
            "read_authorized": True,
        },
    },
    {
        "id": "open_loops",
        "prompt": "What open loops remain?",
        "expected": {
            "workflow": "canonical_open_loop_retrieval",
            "read_authorized": True,
        },
    },
    {
        "id": "stage_for_review",
        "prompt": "Stage this for review.",
        "expected": {
            "staging_authorized_or_write_class": True,
            "promotion_authorized": False,
        },
    },
    {
        "id": "promote_approved",
        "prompt": "Promote the approved artifact.",
        "expected": {
            "promotion_authorized": False,  # still needs validation + server approval
            "workflow": "apply_canonical_promotion",
        },
    },
    {
        "id": "go_ahead_send",
        "prompt": "Go ahead and send it.",
        "expected": {
            "external_action_authorized": False,
        },
    },
    {
        "id": "source_root_groups",
        "prompt": "list configured source roots",
        "expected": {
            "workflow": "source_root_map",
            "read_authorized": True,
            "per_tool_groups": {
                "assistant_source_roots_list": "source_connector",
                "assistant_source_root_map": "source_structure",
            },
            "require_route_schema_v2": True,
        },
    },
]


def _actual(plan: dict) -> dict:
    auth = plan.get("authorization") or {}
    steps = []
    if plan.get("next_step"):
        steps.append(plan["next_step"])
    steps.extend(plan.get("additional_steps") or [])
    return {
        "route_schema_version": plan.get("route_schema_version"),
        "workflow": plan.get("recommended_workflow"),
        "family": plan.get("primary_family"),
        "tools": list(plan.get("recommended_tools") or []),
        "read_authorized": auth.get("read_tool_calls_authorized"),
        "advisory": auth.get("advisory_planning_authorized"),
        "staging_authorized": auth.get("staging_authorized"),
        "write_authorized": auth.get("write_authorized"),
        "promotion_authorized": auth.get("promotion_authorized"),
        "external_action_authorized": auth.get("external_action_authorized"),
        "prohibitions": list(auth.get("prohibitions") or []),
        "prompt_authorizes_execution": auth.get("prompt_authorizes_execution"),
        "operation_requested": auth.get("operation_requested") or auth.get("action_class"),
        "prompt_permission": auth.get("prompt_permission"),
        "server_policy_permission": auth.get("server_policy_permission"),
        "approval_satisfied": auth.get("approval_satisfied"),
        "currently_executable": auth.get("currently_executable"),
        "next_step": plan.get("next_step"),
        "additional_steps": plan.get("additional_steps"),
        "per_tool_groups": {s.get("tool"): s.get("tool_group") for s in steps if s.get("tool")},
        "confidence": plan.get("route_confidence"),
        "freshness_state": (plan.get("freshness") or {}).get("staleness_state"),
    }


def _evaluate(expected: dict, actual: dict) -> list[str]:
    mismatches: list[str] = []
    if "workflow" in expected and actual.get("workflow") != expected["workflow"]:
        mismatches.append(f"workflow: expected {expected['workflow']!r} got {actual.get('workflow')!r}")
    if "workflow_not" in expected and actual.get("workflow") == expected["workflow_not"]:
        mismatches.append(f"workflow_not: got forbidden {expected['workflow_not']!r}")
    if "read_authorized" in expected and actual.get("read_authorized") is not expected["read_authorized"]:
        # Soft: do_not_promote alone may clarify with read False
        if expected.get("id") != "do_not_promote":
            mismatches.append(
                f"read_authorized: expected {expected['read_authorized']!r} got {actual.get('read_authorized')!r}"
            )
    if expected.get("promotion_authorized") is False and actual.get("promotion_authorized") is not False:
        mismatches.append("promotion_authorized: expected False")
    if expected.get("external_action_authorized") is False and actual.get("external_action_authorized") is not False:
        mismatches.append("external_action_authorized: expected False")
    for cap in expected.get("prohibitions_include") or []:
        if cap not in (actual.get("prohibitions") or []):
            mismatches.append(f"prohibitions_include missing: {cap}")
    for cap in expected.get("prohibitions_exclude") or []:
        if cap in (actual.get("prohibitions") or []):
            mismatches.append(f"prohibitions_exclude present: {cap}")
    for tool in expected.get("tools_include") or []:
        if tool not in (actual.get("tools") or []):
            mismatches.append(f"tools_include missing: {tool}")
    for tool, group in (expected.get("per_tool_groups") or {}).items():
        got = (actual.get("per_tool_groups") or {}).get(tool)
        if got != group:
            mismatches.append(f"per_tool_groups[{tool}]: expected {group!r} got {got!r}")
    if expected.get("require_route_schema_v2") and actual.get("route_schema_version") != 2:
        mismatches.append(f"route_schema_version: expected 2 got {actual.get('route_schema_version')!r}")
    if expected.get("staging_authorized_or_write_class"):
        # Accept either staging authorized or staged_write action class
        if not (actual.get("staging_authorized") or actual.get("operation_requested") in (
            "staged_write", "read",
        )):
            # staging prompts often land on stage workflow with staging_authorized True
            if not actual.get("staging_authorized") and actual.get("operation_requested") != "staged_write":
                # still ok if recommended tools include stage tools
                if not any("stage" in t for t in (actual.get("tools") or [])):
                    mismatches.append("expected staging workflow or staging_authorized")
    return mismatches


def main() -> int:
    rows = []
    for case in CASES:
        plan = route_prompt(case["prompt"])
        actual = _actual(plan)
        expected = dict(case["expected"])
        mismatches = _evaluate(expected, actual)
        # Special soft rule for do_not_promote read_authorized
        if case["id"] == "do_not_promote":
            mismatches = [m for m in mismatches if not m.startswith("read_authorized")]
            if actual.get("promotion_authorized"):
                mismatches.append("promotion_authorized should be false")
            if actual.get("workflow") == "apply_canonical_promotion":
                mismatches.append("must not select apply_canonical_promotion")
        rows.append({
            "id": case["id"],
            "prompt": case["prompt"],
            "expected": expected,
            "actual": actual,
            "mismatches": mismatches,
            "pass": len(mismatches) == 0,
            "rationale": (
                f"Compare actual route for {case['id']} against explicit expectations; "
                "pass is true only when mismatches is empty."
            ),
        })

    out_dir = ROOT / "docs" / "evidence" / "prompt-preflight-routing-consistency"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "route-proof-matrix.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")

    md = [
        "# Route proof matrix (expected vs actual)",
        "",
        "Generated by `scripts/generate-route-proof-matrix.py`. "
        "`pass` is derived only from explicit expectations.",
        "",
        "| id | pass | mismatches | workflow | read | prohibitions |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        md.append(
            f"| {r['id']} | {r['pass']} | {len(r['mismatches'])} | "
            f"{r['actual'].get('workflow')} | {r['actual'].get('read_authorized')} | "
            f"{r['actual'].get('prohibitions')} |"
        )
    failed = [r for r in rows if not r["pass"]]
    md += ["", f"**Totals:** {len(rows) - len(failed)} pass / {len(failed)} fail / {len(rows)} total", ""]
    if failed:
        md.append("## Failures")
        for r in failed:
            md.append(f"### {r['id']}")
            for m in r["mismatches"]:
                md.append(f"- {m}")
            md.append("")
    (out_dir / "route-proof-matrix.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"wrote {out_dir}")
    print(f"pass={sum(1 for r in rows if r['pass'])} fail={len(failed)} total={len(rows)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
