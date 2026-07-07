"""N8C-21 — consolidated final validation of the remote NAS MCP surface across ALL 13 read-only assistant tool
groups (nav … quality).

Asserts, in one place: every group is registered BY NAME (78 assistant tools); every group is independently
gated by its default-ON kill-switch (toggling one env var flips only that group's `gate_status`); the finality
guard passes across EVERY assistant tool; `DENIED_TOOL_NAMES` blocks raw_sql/sql/shell/exec/
read_file_absolute/hb_output_delete; `ai_outputs_card_upsert` is the ONLY registered write tool; and
`hb_mcp_status` advertises every group's `*_enabled` + `*_tools`. Non-destructive: temp DB + a fake MCP only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.nas_mcp.broker import (
    ASSISTANT_ACTION_STAGE_TOOLS,
    ASSISTANT_ANSWER_DRAFT_TOOLS,
    ASSISTANT_CONTEXT_PACK_TOOLS,
    ASSISTANT_DECISION_MEMORY_TOOLS,
    ASSISTANT_FEEDBACK_TOOLS,
    ASSISTANT_INTELLIGENCE_TOOLS,
    ASSISTANT_MEMORY_TOOLS,
    ASSISTANT_NAV_TOOLS,
    ASSISTANT_QUALITY_TOOLS,
    ASSISTANT_RESEARCH_PACKET_TOOLS,
    ASSISTANT_REVIEW_TOOLS,
    ASSISTANT_SOURCE_CONNECTOR_TOOLS,
    ASSISTANT_WORKFLOW_TOOLS,
    DENIED_TOOL_NAMES,
    NasMcpBroker,
)
from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec
from hb_assistant.nas_mcp.profile import AI_OUTPUTS_WRITE_TOOL, gate_status
from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools
from hb_assistant.store.migrator import SQLiteMigrator

# The 13 read-only assistant groups: (label, tools tuple, gate_status key, kill-switch env var).
GROUPS = [
    ("nav", ASSISTANT_NAV_TOOLS, "assistant_nav_enabled", "HB_MCP_ASSISTANT_NAV"),
    ("context_packs", ASSISTANT_CONTEXT_PACK_TOOLS, "assistant_context_packs_enabled",
     "HB_MCP_ASSISTANT_CONTEXT_PACKS"),
    ("memory", ASSISTANT_MEMORY_TOOLS, "assistant_memory_enabled", "HB_MCP_ASSISTANT_MEMORY"),
    ("decision_memory", ASSISTANT_DECISION_MEMORY_TOOLS, "assistant_decision_memory_enabled",
     "HB_MCP_ASSISTANT_DECISION_MEMORY"),
    ("review", ASSISTANT_REVIEW_TOOLS, "assistant_review_enabled", "HB_MCP_ASSISTANT_REVIEW"),
    ("intelligence", ASSISTANT_INTELLIGENCE_TOOLS, "assistant_intelligence_enabled",
     "HB_MCP_ASSISTANT_INTELLIGENCE"),
    ("research_packets", ASSISTANT_RESEARCH_PACKET_TOOLS, "assistant_research_packets_enabled",
     "HB_MCP_ASSISTANT_RESEARCH_PACKETS"),
    ("source_connector", ASSISTANT_SOURCE_CONNECTOR_TOOLS, "assistant_source_connector_enabled",
     "HB_MCP_ASSISTANT_SOURCE_CONNECTOR"),
    ("answer_drafts", ASSISTANT_ANSWER_DRAFT_TOOLS, "assistant_answer_drafts_enabled",
     "HB_MCP_ASSISTANT_ANSWER_DRAFTS"),
    ("workflows", ASSISTANT_WORKFLOW_TOOLS, "assistant_workflows_enabled", "HB_MCP_ASSISTANT_WORKFLOWS"),
    ("feedback", ASSISTANT_FEEDBACK_TOOLS, "assistant_feedback_enabled", "HB_MCP_ASSISTANT_FEEDBACK"),
    ("action_stages", ASSISTANT_ACTION_STAGE_TOOLS, "assistant_action_stages_enabled",
     "HB_MCP_ASSISTANT_ACTION_STAGES"),
    ("quality", ASSISTANT_QUALITY_TOOLS, "assistant_quality_enabled", "HB_MCP_ASSISTANT_QUALITY"),
]

# The 23-substring finality guard, plus the N8C-20 additions.
FINALITY_SUBSTRINGS = (
    "execute", "apply", "write", "create", "delete", "persist", "upsert", "close", "reopen", "accept",
    "reject", "defer", "dispose", "build", "send", "remind", "answer", "generate", "scan", "reindex",
    "rebuild", "dispatch", "schedule", "repair", "evaluate",
)


class _FakeMcp:
    def __init__(self) -> None:
        self.names: list[str] = []

    def tool(self, name: str | None = None):
        def deco(fn):
            self.names.append(name or fn.__name__)
            return fn
        return deco


@pytest.fixture()
def env(tmp_path: Path):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    audit = tmp_path / "audit"
    cfg = NasMcpConfig(
        db_path=Path(db), audit_dir=audit,
        roots={"vault": RootSpec("vault", vault, "read_write")},
        obsidian=NasObsidianConfig(vault_root=vault, backup_dir=audit / "bk", support_dir=audit / "support"),
    )
    mcp = _FakeMcp()
    broker = NasMcpBroker(cfg)
    register_nas_mcp_tools(mcp, broker)
    return {"mcp": mcp, "broker": broker}


def test_thirteen_groups() -> None:
    assert len(GROUPS) == 13


def test_every_group_registered_by_name(env) -> None:
    registered = set(env["mcp"].names)
    for label, tools, _key, _var in GROUPS:
        assert set(tools) <= registered, f"{label} tools missing: {set(tools) - registered}"


def test_assistant_tool_count_is_78(env) -> None:
    assistant = [n for n in env["mcp"].names if n.startswith("assistant_")]
    union = set().union(*(set(t) for _l, t, _k, _v in GROUPS))
    assert set(assistant) == union
    assert len(assistant) == 78


def test_finality_guard_across_every_assistant_tool(env) -> None:
    offenders = [n for n in env["mcp"].names if n.startswith("assistant_")
                 and any(s in n for s in FINALITY_SUBSTRINGS)]
    assert offenders == []


def test_each_group_gated_independently(monkeypatch: pytest.MonkeyPatch) -> None:
    # All 13 default-ON; toggling one env var to "0" disables ONLY that group's gate.
    base = gate_status()
    for _label, _tools, key, _var in GROUPS:
        assert base[key] is True
    for label, _tools, key, var in GROUPS:
        monkeypatch.setenv(var, "0")
        gs = gate_status()
        assert gs[key] is False, f"{label} did not disable"
        for other_label, _t, other_key, _v in GROUPS:
            if other_key != key:
                assert gs[other_key] is True, f"{other_label} wrongly disabled by {label}"
        monkeypatch.delenv(var)


def test_denied_tool_names_blocked(env) -> None:
    for name in ("raw_sql", "sql", "shell", "exec", "read_file_absolute", "hb_output_delete"):
        assert name in DENIED_TOOL_NAMES
        r = env["broker"].dispatch(name, {})
        assert r["ok"] is False


def test_ai_outputs_is_the_only_write_tool(env) -> None:
    # `ai_outputs_card_upsert` is the only registered tool that actually mutates state. Every other tool whose
    # NAME contains a write verb is a read-only `*_plan` generator (its build/apply path is CLI-only and never
    # exposed remotely — see the tool_registration comments) — so it never writes.
    assert AI_OUTPUTS_WRITE_TOOL == "ai_outputs_card_upsert"
    assert AI_OUTPUTS_WRITE_TOOL in env["mcp"].names
    writeish = [n for n in env["mcp"].names
                if any(v in n for v in ("write", "upsert", "delete", "create", "persist"))
                and n != AI_OUTPUTS_WRITE_TOOL]
    non_plan = [n for n in writeish if not n.endswith("_plan")]
    # local-scratch/legacy actual writers are gated OFF in the default (remote) profile, so the only remaining
    # non-plan write-verb tool is the sanctioned ai_outputs write itself.
    assert non_plan == [], non_plan
    # and no ASSISTANT (N8C) tool is write-ish at all.
    assert [n for n in writeish if n.startswith("assistant_")] == []


def test_status_advertises_every_group(env) -> None:
    res = env["broker"].dispatch("hb_mcp_status", {})["result"]
    for label, tools, key, _var in GROUPS:
        assert res.get(key) is True, f"{label} enabled flag missing"
        tools_key = {
            "action_stages": "assistant_action_stage_tools",
            "context_packs": "assistant_context_pack_tools",
            "research_packets": "assistant_research_packet_tools",
            "answer_drafts": "assistant_answer_draft_tools",
            "workflows": "assistant_workflow_tools",
        }.get(label, f"assistant_{label}_tools")
        assert set(res.get(tools_key, [])) == set(tools), f"{label} tools list mismatch ({tools_key})"
