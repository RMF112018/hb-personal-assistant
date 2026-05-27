"""Pydantic models for Ollama-backed construction classification.

Every model is recommendation-only. Status ``accepted`` is awarded only when:
1. The proposed label is not in PROTECTED_CATEGORIES (no model decisioning for
   contract / financial / legal / incident / injury / personnel material), AND
2. The model confidence meets the configured threshold, AND
3. The deterministic controller policy did not also flag the item.

Otherwise the decision routes to ``review`` for controller validation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ProposedLabel = Literal[
    "contract",
    "financial",
    "legal",
    "incident",
    "injury",
    "personnel",
    "operational",
    "other",
]

ModelTask = Literal["classification", "review_reason"]
DecisionStatus = Literal["accepted", "review"]

PROTECTED_CATEGORIES: tuple[str, ...] = (
    "contract",
    "financial",
    "legal",
    "incident",
    "injury",
    "personnel",
)


class ModelClassification(BaseModel):
    """The validated JSON payload the model is expected to produce."""

    item_id: str
    proposed_label: ProposedLabel
    confidence: float
    rationale: str
    risk_terms: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}

    @field_validator("confidence")
    @classmethod
    def _confidence_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0]; got {v}")
        return v

    @field_validator("rationale")
    @classmethod
    def _rationale_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("rationale must be a non-empty string")
        return v


class ModelTaskRouting(BaseModel):
    """Per-task model + system-prompt routing."""

    task: ModelTask
    model: str
    system_prompt: str

    model_config = {"extra": "forbid"}

    @field_validator("model")
    @classmethod
    def _model_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("model must be a non-empty string")
        return v

    @field_validator("system_prompt")
    @classmethod
    def _system_prompt_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("system_prompt must be a non-empty string")
        return v


DEFAULT_OLLAMA_ENDPOINT = "http://localhost:11434"


class ModelRoutingConfig(BaseModel):
    """Top-level Ollama routing config (loaded from YAML)."""

    version: int = 1
    default_model: str
    low_confidence_threshold: float = 0.7
    protected_categories: list[str] = Field(
        default_factory=lambda: list(PROTECTED_CATEGORIES),
    )
    timeout_seconds: float = 15.0
    max_output_chars: int = 4000
    endpoint_url: str = DEFAULT_OLLAMA_ENDPOINT
    expected_models: list[str] = Field(default_factory=list)
    tasks: list[ModelTaskRouting] = Field(default_factory=list)

    model_config = {"extra": "forbid"}

    @field_validator("endpoint_url")
    @classmethod
    def _endpoint_url_shape(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError(
                f"endpoint_url must start with 'http://' or 'https://'; got {v!r}"
            )
        if v.endswith("/"):
            raise ValueError(
                f"endpoint_url must not end with a trailing slash; got {v!r}"
            )
        return v

    @field_validator("low_confidence_threshold")
    @classmethod
    def _threshold_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"low_confidence_threshold must be in [0.0, 1.0]; got {v}")
        return v

    @field_validator("timeout_seconds")
    @classmethod
    def _timeout_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"timeout_seconds must be > 0; got {v}")
        return v

    @field_validator("max_output_chars")
    @classmethod
    def _max_output_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"max_output_chars must be > 0; got {v}")
        return v

    @model_validator(mode="after")
    def _check_consistency(self) -> "ModelRoutingConfig":
        # Every protected category from the canonical default must be present.
        for cat in PROTECTED_CATEGORIES:
            if cat not in self.protected_categories:
                raise ValueError(
                    f"protected_categories must include every canonical category; "
                    f"missing: {cat!r}"
                )
        # Task entries must be unique by `task`.
        task_keys = [t.task for t in self.tasks]
        if len(task_keys) != len(set(task_keys)):
            dupes = sorted({k for k in task_keys if task_keys.count(k) > 1})
            raise ValueError(f"duplicate task entries: {dupes}")

        # If expected_models is explicit, it must be unique and cover
        # default_model + every per-task model so an operator cannot ship a
        # readiness expectation that disagrees with the routing config itself.
        if self.expected_models:
            if len(self.expected_models) != len(set(self.expected_models)):
                dupes = sorted(
                    {m for m in self.expected_models if self.expected_models.count(m) > 1}
                )
                raise ValueError(f"duplicate expected_models entries: {dupes}")
            if self.default_model not in self.expected_models:
                raise ValueError(
                    f"expected_models must include default_model "
                    f"{self.default_model!r}; got {self.expected_models}"
                )
            for t in self.tasks:
                if t.model not in self.expected_models:
                    raise ValueError(
                        f"expected_models must include every task model; missing "
                        f"{t.model!r} for task {t.task!r}"
                    )
        return self

    def task_for(self, task: ModelTask) -> ModelTaskRouting:
        for t in self.tasks:
            if t.task == task:
                return t
        raise KeyError(f"no routing entry for task {task!r}")

    def resolved_expected_models(self) -> list[str]:
        """Return the effective list of models the Ollama daemon must serve.

        When ``expected_models`` is explicit, return it as-is (already
        validated to include default_model + every task model). When omitted,
        derive from ``default_model`` plus every per-task model, deduped and
        order-preserved.
        """
        if self.expected_models:
            return list(self.expected_models)
        seen: dict[str, None] = {}
        seen[self.default_model] = None
        for t in self.tasks:
            seen.setdefault(t.model, None)
        return list(seen.keys())


class ClassificationDecision(BaseModel):
    """The persisted record of one model recommendation + router verdict."""

    source_key: str
    item_id: str
    project_key: str | None = None
    model_name: str
    model_task: ModelTask
    proposed_label: ProposedLabel
    confidence: float
    rationale_truncated: str
    raw_output_truncated: str
    status: DecisionStatus
    routing_reason: str
    routed_at: str

    model_config = {"extra": "forbid"}

    @field_validator("confidence")
    @classmethod
    def _confidence_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0]; got {v}")
        return v
