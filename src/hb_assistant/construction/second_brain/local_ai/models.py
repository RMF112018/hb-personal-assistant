"""Phase 10 Prompt 01 — local-AI contract enforcement models (Pydantic).

Declarative-only. These models validate the Phase 10 seed policies and the action-candidate
output shape **before** any future database write. There is no runtime here: no Ollama call,
no job execution, no DB access, no writeback. The repo has no ``jsonschema`` dependency, so the
published JSON Schema (``phase_10_action_candidate_output_schema.json``) is enforced in code via
the :class:`ActionCandidate` model below.

Every model uses ``extra="forbid"`` so unknown / forbidden raw fields (``raw_email_body``,
``raw_response``, ``token``, ``signed_url`` …) are rejected at parse time. Enums are closed
``Literal`` types so unsupported values fail fast. Cross-field guardrails (high-stakes items are
review signals never determinations; candidates always carry >=1 source ref; heavy model profiles
require explicit enable) are enforced with model validators.
"""

from __future__ import annotations

from typing import Literal, get_args

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Shared closed enums (mirror the JSON contracts verbatim).
# ---------------------------------------------------------------------------
Provider = Literal["ollama", "mock", "mlx", "llama_cpp"]

CandidateType = Literal[
    "task", "commitment", "decision", "question", "meeting_prep", "risk_signal", "relationship"
]
Assignee = Literal["user", "other", "unknown"]
Urgency = Literal["low", "normal", "high", "critical"]
WaitingState = Literal["waiting_on_me", "waiting_on_others", "unknown", "not_applicable"]
ReviewStatus = Literal["pending", "accepted", "rejected", "snoozed", "suppressed"]
SafetyCategory = Literal[
    "normal",
    "contract",
    "legal",
    "financial",
    "payment",
    "claim",
    "entitlement",
    "schedule",
    "safety",
]
RecommendedNextAction = Literal[
    "review", "accept", "snooze", "ignore", "draft_followup", "prepare_meeting", "prepare_packet"
]

#: High-stakes safety categories: signals requiring human review, never model determinations.
HIGH_STAKES_CATEGORIES: frozenset[str] = frozenset(get_args(SafetyCategory)) - {"normal"}


# ---------------------------------------------------------------------------
# Local model profile seed model.
# ---------------------------------------------------------------------------
class LocalModelProfile(BaseModel):
    """A single tiered local model profile (advisory; no runtime here)."""

    profile_id: str
    provider: Provider
    model_name: str
    enabled: bool
    role: str
    max_context_tokens: int = Field(gt=0)
    timeout_seconds: int = Field(gt=0)
    concurrency_limit: int = Field(ge=1)
    heavy_profile: bool
    requires_explicit_enable: bool

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _heavy_profile_invariants(self) -> "LocalModelProfile":
        if self.heavy_profile:
            if not self.requires_explicit_enable:
                raise ValueError(f"heavy profile {self.profile_id!r} must require explicit enable")
            if self.concurrency_limit != 1:
                raise ValueError(f"heavy profile {self.profile_id!r} must be single-concurrency")
        return self


class LocalModelProfiles(BaseModel):
    """The ``phase_10_local_model_profiles`` seed policy."""

    version: str
    provider_default: Provider
    profiles: list[LocalModelProfile] = Field(min_length=1)
    fallbacks: dict[str, str] = Field(default_factory=dict)
    guardrails: dict[str, bool] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _registry_invariants(self) -> "LocalModelProfiles":
        ids = [p.profile_id for p in self.profiles]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate profile_id entries")
        if "default_extract" not in ids:
            raise ValueError("required profile 'default_extract' is missing")
        by_id = {p.profile_id: p for p in self.profiles}
        if not by_id["default_extract"].enabled:
            raise ValueError("'default_extract' must be enabled by default")
        for src, dst in self.fallbacks.items():
            if src not in by_id:
                raise ValueError(f"fallback source {src!r} is not a registered profile")
            if dst not in by_id:
                raise ValueError(f"fallback target {dst!r} is not a registered profile")
        # Guardrails are local-first: never persist raw prompt/response, never writeback.
        for key in ("raw_prompt_persisted", "raw_response_persisted", "external_writeback"):
            if self.guardrails.get(key, False):
                raise ValueError(f"guardrail {key!r} must be false")
        if self.guardrails.get("scheduled_heavy_profile_default", False):
            raise ValueError("heavy profiles must not be scheduled by default")
        return self


# ---------------------------------------------------------------------------
# AI job policy seed model.
# ---------------------------------------------------------------------------
class AiJobDefaults(BaseModel):
    dry_run_default: bool
    max_concurrent_jobs: int = Field(ge=1)
    max_items_per_run: int = Field(ge=1)
    max_retries: int = Field(ge=0)
    retry_backoff_seconds: int = Field(ge=0)
    timeout_seconds: int = Field(gt=0)
    run_after_source_refresh: Literal["enqueue_only", "disabled"]

    model_config = {"extra": "forbid"}


class AiJobTypePolicy(BaseModel):
    profile_id: str | None = None
    fallback_profile_id: str | None = None
    max_items_per_run: int | None = Field(default=None, ge=1)
    source_families: list[str] = Field(default_factory=list)
    deterministic_only: bool = False

    model_config = {"extra": "forbid"}


class AiJobPolicy(BaseModel):
    """The ``phase_10_ai_job_policy`` seed policy."""

    version: str
    defaults: AiJobDefaults
    job_types: dict[str, AiJobTypePolicy] = Field(default_factory=dict)
    guardrails: dict[str, bool] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _policy_invariants(self) -> "AiJobPolicy":
        # Dry-run is the safe default for anything that can create local records/files.
        if not self.defaults.dry_run_default:
            raise ValueError("defaults.dry_run_default must be true (safe by default)")
        for key in (
            "no_external_writeback",
            "no_raw_content_persistence",
            "schema_validation_required",
        ):
            if not self.guardrails.get(key, False):
                raise ValueError(f"guardrail {key!r} must be true")
        return self


# ---------------------------------------------------------------------------
# Obsidian vault policy seed model.
# ---------------------------------------------------------------------------
class ObsidianManagedMarkers(BaseModel):
    start_prefix: str
    end_prefix: str

    model_config = {"extra": "forbid"}


class ObsidianVaultPolicy(BaseModel):
    """The ``phase_10_obsidian_vault_policy`` seed policy."""

    version: str
    vault_profile: str
    target_daily_brief_folder: str
    allowlisted_folders: list[str] = Field(min_length=1)
    managed_markers: ObsidianManagedMarkers
    frontmatter_allowlist: list[str] = Field(default_factory=list)
    default_tags: dict[str, list[str]] = Field(default_factory=dict)
    guardrails: dict[str, bool] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _vault_invariants(self) -> "ObsidianVaultPolicy":
        if self.target_daily_brief_folder not in self.allowlisted_folders:
            raise ValueError("target_daily_brief_folder must be allowlisted")
        if not self.guardrails.get("marker_bounded_writes_only", False):
            raise ValueError("guardrail 'marker_bounded_writes_only' must be true")
        if not self.guardrails.get("preserve_user_body", False):
            raise ValueError("guardrail 'preserve_user_body' must be true")
        if self.guardrails.get("source_file_copied_to_vault", False):
            raise ValueError("guardrail 'source_file_copied_to_vault' must be false")
        return self


# ---------------------------------------------------------------------------
# MCP packet policy seed model.
# ---------------------------------------------------------------------------
class McpPacketPolicy(BaseModel):
    """The ``phase_10_mcp_packet_policy`` seed policy."""

    version: str
    resources: list[str] = Field(min_length=1)
    tools: list[str] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)
    guardrails: dict[str, bool] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _mcp_invariants(self) -> "McpPacketPolicy":
        for key in ("read_only", "metadata_only", "source_refs_required"):
            if not self.guardrails.get(key, False):
                raise ValueError(f"guardrail {key!r} must be true")
        required_forbidden = {
            "arbitrary_sql",
            "graph_writeback",
            "procore_writeback",
            "email_send",
            "calendar_mutation",
            "raw_content_access",
        }
        missing = required_forbidden - set(self.forbidden)
        if missing:
            raise ValueError(f"mcp policy must forbid: {sorted(missing)}")
        return self


# ---------------------------------------------------------------------------
# Action candidate output model — enforces the published JSON Schema in code.
# ---------------------------------------------------------------------------
class ActionCandidate(BaseModel):
    """A single advisory action candidate (model output before human review).

    Mirrors ``phase_10_action_candidate_output_schema.json``. ``extra="forbid"`` rejects any
    forbidden raw field. A candidate can never exist without at least one source reference, and
    every candidate carries advisory provenance (model profile, prompt template, input window).
    """

    candidate_type: CandidateType
    title: str = Field(min_length=1, max_length=240)
    project_key: str | None = None
    assignee: Assignee = "unknown"
    due_at: str | None = None
    urgency: Urgency = "normal"
    waiting_state: WaitingState = "unknown"
    source_refs: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(max_length=1000)
    model_name: str | None = None
    model_profile_id: str | None = None
    prompt_template_version: str | None = None
    input_window_hash: str | None = None
    review_status: ReviewStatus = "pending"
    safety_category: SafetyCategory
    recommended_next_action: RecommendedNextAction
    external_action_requires_approval: Literal[True] = True

    model_config = {"extra": "forbid"}

    @field_validator("source_refs")
    @classmethod
    def _source_refs_nonempty(cls, value: list[str]) -> list[str]:
        if any(not isinstance(ref, str) or not ref.strip() for ref in value):
            raise ValueError("every source_ref must be a non-empty string")
        return value

    @model_validator(mode="after")
    def _high_stakes_routing(self) -> "ActionCandidate":
        # High-stakes items are review signals, never determinations: they must route to review
        # and may not be pre-accepted by the model.
        if self.safety_category in HIGH_STAKES_CATEGORIES:
            if self.recommended_next_action != "review":
                raise ValueError(
                    f"high-stakes safety_category {self.safety_category!r} must recommend review"
                )
            if self.review_status == "accepted":
                raise ValueError(
                    f"high-stakes safety_category {self.safety_category!r} cannot be model-accepted"
                )
        return self


# ---------------------------------------------------------------------------
# Raw content policy seed model (Phase 10A Prompt 01 addendum).
# ---------------------------------------------------------------------------

RawContentMode = Literal[
    "disabled", "email_calendar", "all_supported", "all_supported_plus_downstream"
]


class DownstreamToggles(BaseModel):
    """Downstream consumption toggles (MCP, Obsidian). Prompt 01 keeps both false."""

    mcp_allow_raw_content: bool = False
    obsidian_allow_raw_content: bool = False

    model_config = {"extra": "forbid"}


class ModelContextConfig(BaseModel):
    """Model context inclusion controls for raw content (email/calendar bodies)."""

    include_raw_content: bool = True
    max_threads_per_run: int = Field(ge=0)
    max_messages_per_thread: int = Field(ge=0)
    max_body_chars_per_message: int = Field(ge=0)
    max_events_per_run: int = Field(ge=0)
    max_calendar_body_chars_per_event: int = Field(ge=0)

    model_config = {"extra": "forbid"}


class PersistenceConfig(BaseModel):
    """Per-field persistence decisions for raw content tables (subject/body etc.)."""

    persist_email_subject: bool = True
    persist_email_body_preview: bool = True
    persist_email_body_text: bool = True
    persist_email_body_html: bool = True
    persist_calendar_subject: bool = True
    persist_calendar_body_text: bool = True
    persist_calendar_body_html: bool = True
    persist_calendar_location: bool = True
    persist_calendar_attendees: bool = True
    persist_calendar_join_url: bool = True

    model_config = {"extra": "forbid"}


class EndpointsConfig(BaseModel):
    """API endpoint behavior for raw content (include/exclude param)."""

    allow_include_raw_param: bool = True
    default_raw_mode: Literal["include", "exclude"] = "include"

    model_config = {"extra": "forbid"}


class ProhibitedWithoutApproval(BaseModel):
    """Explicit prohibitions that require future approval to relax (writeback etc.)."""

    external_writeback: bool = True
    automatic_email_send: bool = True
    automatic_calendar_mutation: bool = True
    cloud_llm_submission: bool = True

    model_config = {"extra": "forbid"}


class StartingSources(BaseModel):
    """Initial sources enabled for raw content ingestion (email + calendar for Prompt 01)."""

    email: bool = True
    calendar: bool = True

    model_config = {"extra": "forbid"}


class RawContentSettings(BaseModel):
    """The nested raw_content block in the policy seed."""

    enabled: bool = True
    mode: RawContentMode = "email_calendar"
    default_endpoint_behavior: Literal["include_raw", "metadata_only"] = "include_raw"
    starting_sources: StartingSources = Field(default_factory=StartingSources)
    downstream: DownstreamToggles = Field(default_factory=DownstreamToggles)
    model_context: ModelContextConfig
    persistence: PersistenceConfig
    endpoints: EndpointsConfig = Field(default_factory=EndpointsConfig)
    prohibited_without_future_approval: ProhibitedWithoutApproval = Field(
        default_factory=ProhibitedWithoutApproval
    )

    model_config = {"extra": "forbid"}


class RawContentPolicy(BaseModel):
    """The ``phase_10a_raw_content_policy`` seed policy.

    Phase 10A addendum Prompt 01: explicit raw-content policy config.
    Supports ``email_calendar`` mode first. Enforces that external writeback,
    automatic mutations, and cloud LLM submission remain prohibited.
    """

    version: str
    raw_content: RawContentSettings

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _raw_content_invariants(self) -> "RawContentPolicy":
        allowed_modes: tuple[str, ...] = (
            "disabled",
            "email_calendar",
            "all_supported",
            "all_supported_plus_downstream",
        )
        if self.raw_content.mode not in allowed_modes:
            raise ValueError(f"raw_content.mode must be one of {allowed_modes}")

        # email_calendar mode requires the starting email+calendar sources.
        if self.raw_content.mode == "email_calendar":
            ss = self.raw_content.starting_sources
            if not (ss.email and ss.calendar):
                raise ValueError(
                    "email_calendar mode requires email and calendar starting_sources true"
                )

        # Non-negotiable: writeback and automatic actions stay disabled.
        p = self.raw_content.prohibited_without_future_approval
        for flag, label in [
            (p.external_writeback, "external_writeback"),
            (p.automatic_email_send, "automatic_email_send"),
            (p.automatic_calendar_mutation, "automatic_calendar_mutation"),
            (p.cloud_llm_submission, "cloud_llm_submission"),
        ]:
            if not flag:
                raise ValueError(f"prohibited_without_future_approval.{label} must be true")

        # Prompt 01 scope: downstream allowances off when using email_calendar (conservative start).
        d = self.raw_content.downstream
        if self.raw_content.mode in ("email_calendar", "disabled") and (
            d.mcp_allow_raw_content or d.obsidian_allow_raw_content
        ):
            raise ValueError(
                "downstream raw allowances must be false for email_calendar in Prompt 01"
            )

        return self
