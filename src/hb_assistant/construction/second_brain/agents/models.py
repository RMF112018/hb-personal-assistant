"""Phase 08A agent runtime foundation — Pydantic structures (Prompt 02 Addendum).

Defines the agent registry models and the internal `AgentResult` /
`AgentRunReceipt` structures used by the (future) agent runtime. These structures
are **in-memory only** this prompt — no agent executes and nothing is persisted.
The V27 agent persistence tables land in the later agent-runtime prompt.

Agents are deterministic or model-assisted service modules behind controller
policy, not autonomous actors. No external API access, no writeback, no raw
content.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class AgentDefinition(BaseModel):
    """One registered Phase 08A internal service agent (A01-A09)."""

    agent_id: str
    phase_owner: str
    enabled: bool
    purpose: str
    allowed_tool_groups: list[str]
    denied_tool_groups: list[str]
    default_model_profile: str
    review_policy: str
    output_contract: str
    receipt_required: bool

    model_config = {"extra": "forbid"}


class AgentRegistry(BaseModel):
    """Effective local registry of Phase 08A agents (loaded from the seed)."""

    version: str
    agents: list[AgentDefinition] = Field(default_factory=list)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _no_duplicate_ids(self) -> "AgentRegistry":
        seen: set[str] = set()
        for agent in self.agents:
            if agent.agent_id in seen:
                raise ValueError(f"duplicate agent_id in registry: {agent.agent_id!r}")
            seen.add(agent.agent_id)
        return self

    def by_id(self, agent_id: str) -> AgentDefinition | None:
        for agent in self.agents:
            if agent.agent_id == agent_id:
                return agent
        return None


class AgentResult(BaseModel):
    """Internal structured result returned by an agent invocation (in-memory).

    Carries source references and a review-tier summary; never raw prompts, raw
    model responses, signed/download URLs, secrets, or raw source bodies.
    """

    ok: bool
    status: str
    agent_id: str
    receipt_id: str
    source_refs: list[dict[str, str]] = Field(default_factory=list)
    review_tier_summary: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class AgentRunReceipt(BaseModel):
    """Internal audit receipt for one agent run (metadata only; in-memory).

    Mirrors the future `second_brain_agent_run_receipts` row shape. Persisted in
    a later prompt (V27) — this prompt only defines the structure. Model-call
    metadata only: no raw prompt/response is ever carried here.
    """

    agent_run_id: str
    agent_id: str
    origin_id: str | None = None
    request_kind: str
    mode: str
    status: str
    review_tier_summary: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    source_refs: list[dict[str, str]] = Field(default_factory=list)
    evaluation_result_id: str | None = None
    created_utc: str

    model_config = {"extra": "forbid"}
