#!/usr/bin/env python3
"""Generate expected-vs-actual route proof matrix (JSON + Markdown).

``pass`` is computed only from explicit expectations. Unknown expectation keys fail closed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hb_assistant.obsidian_mcp.prompt_preflight import route_prompt  # noqa: E402

# Supported expectation keys only — anything else is a matrix generator bug.
_SUPPORTED_KEYS = frozenset({
    "workflow", "workflow_not", "workflow_in",
    "read_authorized", "staging_authorized", "staging_authorized_or_write_class",
    "write_authorized", "promotion_authorized", "external_action_authorized",
    "prohibitions_include", "prohibitions_exclude",
    "tools_include", "tools_empty",
    "per_tool_groups", "per_tool_families",
    "require_route_schema_v2",
    "currently_executable", "execution_blocked_reason_in",
    "operation_requested",
    "confidence_in",
})

CASES: list[dict] = [
    {
        "id": "project_notes",
        "prompt": "Find my project notes.",
        "expected": {
            "workflow": "vault_note_search",
            "read_authorized": True,
            "prohibitions_exclude": ["execute"],
            "tools_include": ["assistant_search_sources"],
            "require_route_schema_v2": True,
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
            "tools_include": ["assistant_source_roots_list", "assistant_source_root_map"],
            "per_tool_groups": {
                "assistant_source_roots_list": "source_connector",
                "assistant_source_root_map": "source_structure",
            },
            "currently_executable": False,
        },
    },
    {
        "id": "nas_file_search_explain",
        "prompt": "Explain which read-only Personal Assistant tool searches indexed NAS files.",
        "expected": {
            "workflow": "source_file_search",
            "read_authorized": True,
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
            "prohibitions_exclude": ["execute", "write"],
            "execution_blocked_reason_in": [None, "missing_arguments"],
        },
    },
    {
        "id": "do_not_promote",
        "prompt": "Do not promote anything.",
        "expected": {
            "workflow_not": "apply_canonical_promotion",
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
            "tools_include": ["assistant_list_decisions", "assistant_get_decision"],
            "per_tool_groups": {"assistant_list_decisions": "decision_memory"},
            "per_tool_families": {"assistant_list_decisions": "assistant_decision_memory"},
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
            "currently_executable": False,
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
            "prohibitions_include": ["write", "stage", "promote", "execute_non_read"],
            "prohibitions_exclude": ["execute"],
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
            "workflow": "context_preflight",
            "tools_empty": True,
            "promotion_authorized": False,
            "workflow_not": "inspect_promotion_receipt",
        },
    },
    {
        "id": "preference_retrieval",
        "prompt": "What preferences do I have for X?",
        "expected": {
            "workflow": "canonical_preference_retrieval",
            "read_authorized": True,
            "tools_include": ["assistant_list_preferences", "assistant_get_preference"],
            "per_tool_groups": {"assistant_list_preferences": "decision_memory"},
            "per_tool_families": {"assistant_list_preferences": "assistant_decision_memory"},
        },
    },
    {
        "id": "open_loops",
        "prompt": "What open loops remain?",
        "expected": {
            "workflow": "canonical_open_loop_retrieval",
            "read_authorized": True,
            "tools_include": ["assistant_list_open_loops"],
            "per_tool_groups": {"assistant_list_open_loops": "decision_memory"},
            "per_tool_families": {"assistant_list_open_loops": "assistant_decision_memory"},
        },
    },
    {
        "id": "stage_for_review",
        "prompt": "Stage this for review.",
        "expected": {
            "workflow": "stage_artifact_proposals",
            "operation_requested": "staged_write",
            "staging_authorized": True,
            "staging_authorized_or_write_class": True,
            "promotion_authorized": False,
            "currently_executable": False,
            "execution_blocked_reason_in": ["missing_arguments"],
        },
    },
    {
        "id": "promote_approved",
        "prompt": "Promote the approved artifact.",
        "expected": {
            "workflow": "apply_canonical_promotion",
            "promotion_authorized": False,
            "currently_executable": False,
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
        "execution_blocked_reason": auth.get("execution_blocked_reason"),
        "next_step": plan.get("next_step"),
        "additional_steps": plan.get("additional_steps"),
        "per_tool_groups": {s.get("tool"): s.get("tool_group") for s in steps if s.get("tool")},
        "per_tool_families": {s.get("tool"): s.get("family") for s in steps if s.get("tool")},
        "confidence": plan.get("route_confidence"),
        "freshness_state": (plan.get("freshness") or {}).get("staleness_state"),
    }


def _evaluate(expected: dict, actual: dict) -> list[str]:
    mismatches: list[str] = []
    unknown = sorted(set(expected) - _SUPPORTED_KEYS)
    if unknown:
        mismatches.append(f"unsupported_expectation_keys:{unknown}")
        return mismatches  # fail closed

    if "workflow" in expected and actual.get("workflow") != expected["workflow"]:
        mismatches.append(f"workflow: expected {expected['workflow']!r} got {actual.get('workflow')!r}")
    if "workflow_not" in expected and actual.get("workflow") == expected["workflow_not"]:
        mismatches.append(f"workflow_not: got forbidden {expected['workflow_not']!r}")
    if "workflow_in" in expected and actual.get("workflow") not in expected["workflow_in"]:
        mismatches.append(f"workflow_in: got {actual.get('workflow')!r} not in {expected['workflow_in']!r}")
    if "operation_requested" in expected and actual.get("operation_requested") != expected["operation_requested"]:
        mismatches.append(
            f"operation_requested: expected {expected['operation_requested']!r} "
            f"got {actual.get('operation_requested')!r}"
        )
    if "read_authorized" in expected and actual.get("read_authorized") is not expected["read_authorized"]:
        mismatches.append(
            f"read_authorized: expected {expected['read_authorized']!r} got {actual.get('read_authorized')!r}"
        )
    if "staging_authorized" in expected and actual.get("staging_authorized") is not expected["staging_authorized"]:
        mismatches.append(
            f"staging_authorized: expected {expected['staging_authorized']!r} "
            f"got {actual.get('staging_authorized')!r}"
        )
    if expected.get("staging_authorized_or_write_class") is True:
        ok = (
            actual.get("staging_authorized") is True
            or actual.get("operation_requested") == "staged_write"
            or any("stage" in str(t) for t in (actual.get("tools") or []))
        )
        if not ok:
            mismatches.append(
                "staging_authorized_or_write_class: expected staging_authorized "
                f"or staged_write (got op={actual.get('operation_requested')!r} "
                f"stage={actual.get('staging_authorized')!r} tools={actual.get('tools')!r})"
            )
    if "write_authorized" in expected and actual.get("write_authorized") is not expected["write_authorized"]:
        mismatches.append(
            f"write_authorized: expected {expected['write_authorized']!r} got {actual.get('write_authorized')!r}"
        )
    if expected.get("promotion_authorized") is False and actual.get("promotion_authorized") is not False:
        mismatches.append("promotion_authorized: expected False")
    if expected.get("external_action_authorized") is False and actual.get("external_action_authorized") is not False:
        mismatches.append("external_action_authorized: expected False")
    if "currently_executable" in expected and actual.get("currently_executable") is not expected["currently_executable"]:
        mismatches.append(
            f"currently_executable: expected {expected['currently_executable']!r} "
            f"got {actual.get('currently_executable')!r} "
            f"(blocked={actual.get('execution_blocked_reason')!r})"
        )
    if "execution_blocked_reason_in" in expected:
        allowed = expected["execution_blocked_reason_in"]
        got = actual.get("execution_blocked_reason")
        if got not in allowed:
            mismatches.append(f"execution_blocked_reason: got {got!r} not in {allowed!r}")
    for cap in expected.get("prohibitions_include") or []:
        if cap not in (actual.get("prohibitions") or []):
            mismatches.append(f"prohibitions_include missing: {cap}")
    for cap in expected.get("prohibitions_exclude") or []:
        if cap in (actual.get("prohibitions") or []):
            mismatches.append(f"prohibitions_exclude present: {cap}")
    for tool in expected.get("tools_include") or []:
        if tool not in (actual.get("tools") or []):
            mismatches.append(f"tools_include missing: {tool}")
    if expected.get("tools_empty") is True and (actual.get("tools") or []):
        mismatches.append(f"tools_empty: expected [] got {actual.get('tools')!r}")
    for tool, group in (expected.get("per_tool_groups") or {}).items():
        got = (actual.get("per_tool_groups") or {}).get(tool)
        if got != group:
            mismatches.append(f"per_tool_groups[{tool}]: expected {group!r} got {got!r}")
    for tool, fam in (expected.get("per_tool_families") or {}).items():
        got = (actual.get("per_tool_families") or {}).get(tool)
        if got != fam:
            mismatches.append(f"per_tool_families[{tool}]: expected {fam!r} got {got!r}")
    if expected.get("require_route_schema_v2") and actual.get("route_schema_version") != 2:
        mismatches.append(f"route_schema_version: expected 2 got {actual.get('route_schema_version')!r}")
    if "confidence_in" in expected and actual.get("confidence") not in expected["confidence_in"]:
        mismatches.append(f"confidence: got {actual.get('confidence')!r}")
    return mismatches


def main() -> int:
    rows = []
    for case in CASES:
        plan = route_prompt(case["prompt"])
        actual = _actual(plan)
        expected = dict(case["expected"])
        mismatches = _evaluate(expected, actual)
        rows.append({
            "id": case["id"],
            "prompt": case["prompt"],
            "expected": expected,
            "actual": actual,
            "mismatches": mismatches,
            "pass": len(mismatches) == 0,
            "rationale": (
                f"Compare actual route for {case['id']} against explicit expectations; "
                "pass is true only when mismatches is empty. Unknown expectation keys fail closed."
            ),
        })

    out_dir = ROOT / "docs" / "evidence" / "prompt-preflight-routing-consistency"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "route-proof-matrix.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")

    md = [
        "# Route proof matrix (expected vs actual)",
        "",
        "Generated by `scripts/generate-route-proof-matrix.py`.",
        "`pass` is derived only from explicit expectations; unknown keys fail closed.",
        "",
        "| id | pass | mismatches | workflow | read | stage | currently_executable | prohibitions |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        md.append(
            f"| {r['id']} | {r['pass']} | {len(r['mismatches'])} | "
            f"{r['actual'].get('workflow')} | {r['actual'].get('read_authorized')} | "
            f"{r['actual'].get('staging_authorized')} | {r['actual'].get('currently_executable')} | "
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
    for r in failed:
        print("FAIL", r["id"], r["mismatches"])
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
