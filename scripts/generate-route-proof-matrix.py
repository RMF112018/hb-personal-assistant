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
sys.path.insert(0, str(ROOT / "scripts"))

from hb_assistant.obsidian_mcp.prompt_preflight import route_prompt  # noqa: E402
from route_proof_lib import evaluate_route_expectations, route_actual  # noqa: E402

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
            "currently_executable": True,
            "execution_blocked_reason_in": [None],
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
            "currently_executable": True,
            "execution_blocked_reason_in": [None],
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


def main() -> int:
    rows = []
    for case in CASES:
        plan = route_prompt(case["prompt"])
        actual = route_actual(plan)
        expected = dict(case["expected"])
        mismatches = evaluate_route_expectations(expected, actual)
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