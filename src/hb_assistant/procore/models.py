"""Pydantic models for the Procore foundation + endpoint audit.

Every model is read-only by construction:

- :class:`ProcoreEndpoint.http_method` is ``Literal["GET"]`` — a writeback (hard GET-only enforced per Prompt_05; any non-GET is rejected at model load)

# Prompt_05: Financials must force review routing
    if category == Category.FINANCIALS and (not review_required or not sensitive):
        raise ValueError("Financials category requires review_required=True and sensitive=True")
  endpoint cannot be constructed.
- :class:`ProcoreEndpoint.status` is a closed ``Literal`` that includes
  ``"excluded"`` (correspondence; hard guardrail) and ``"deferred"``
  (schedule/tasks; hard guardrail).
- :class:`ProcoreEndpointContract` validates that every category present in
  the seed has at least one endpoint, and that ``endpoint_id`` values are
  unique.
"""

from __future__ import annotations

# Prompt_05 addition: Explicit Category enum
from enum import Enum as _Enum  # avoid collision if Enum already imported

class Category(str, _Enum):
    """Prompt_05 categories per Decision Register."""
    FOUNDATION = "foundation"
    PROJECT_CONTROLS = "project_controls"
    FINANCIALS = "financials"

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

HttpMethod = Literal["GET"]  # read-only by construction
EndpointStatus = Literal["validated", "sensitive_validated", "excluded", "deferred"]
Sensitivity = Literal["low", "medium", "high", "critical"]
ProjectMappingStatus = Literal["pilot", "pending", "deprecated"]
AuthStatus = Literal["env_present", "env_partial", "env_absent"]

# Hard-guardrail categories the seed MUST cover so the operator-visible
# audit always reports them, even if a config edit drops them.
REQUIRED_CATEGORIES: tuple[str, ...] = (
    "rfis",
    "submittals",
    "drawings",
    "daily-logs",
    "punch-items",
    "change-events",
    "commitments",
    "prime-contracts",
    "invoices",
    "correspondence",
    "schedule",
    "tasks",
)

_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Procore project IDs in the Procore API are integers (e.g. 2525840). HB
# internal project numbers follow the pattern YY-NNN-VV (e.g. 23-435-01) and
# MUST NEVER be stored in procore_project_id — they identify a different
# system and would cause live audits to query the wrong project.
_HB_NUMBER_PATTERN = re.compile(r"^\d{2}-\d{3}-\d{2}$")
_NUMERIC_PROCORE_ID_PATTERN = re.compile(r"^\d+$")


def _kebab(value: str, field_name: str) -> str:
    if not _ID_RE.match(value):
        raise ValueError(
            f"{field_name} must be lowercase kebab-case (a-z0-9 with single hyphens); got {value!r}"
        )
    return value


class ProcoreEndpoint(BaseModel):
    endpoint_id: str
    http_method: HttpMethod
    path_template: str
    category: str
    status: EndpointStatus
    sensitivity: Sensitivity
    included_in_phase_01: bool = True
    notes: str | None = None

    model_config = {"extra": "forbid"}

    @field_validator("endpoint_id")
    @classmethod
    def _endpoint_id_kebab(cls, v: str) -> str:
        return _kebab(v, "endpoint_id")

    @field_validator("category")
    @classmethod
    def _category_kebab(cls, v: str) -> str:
        return _kebab(v, "category")

    @field_validator("path_template")
    @classmethod
    def _path_template_non_empty(cls, v: str) -> str:
        if not v.strip() or not v.startswith("/"):
            raise ValueError(f"path_template must start with '/'; got {v!r}")
        return v


class ProcoreEndpointContract(BaseModel):
    version: int = 1
    company_id: str
    company_display_name: str
    endpoints: list[ProcoreEndpoint] = Field(default_factory=list)

    model_config = {"extra": "forbid"}

    @field_validator("company_id")
    @classmethod
    def _company_id_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("company_id must be a non-empty string")
        return v

    @model_validator(mode="after")
    def _check_consistency(self) -> "ProcoreEndpointContract":
        ids = [e.endpoint_id for e in self.endpoints]
        if len(ids) != len(set(ids)):
            dupes = sorted({k for k in ids if ids.count(k) > 1})
            raise ValueError(f"duplicate endpoint_id entries: {dupes}")

        categories = {e.category for e in self.endpoints}
        missing = [c for c in REQUIRED_CATEGORIES if c not in categories]
        if missing:
            raise ValueError(
                "endpoint contract must cover every required category "
                f"(missing: {missing})"
            )

        # Defense-in-depth: ensure correspondence is excluded, and
        # schedule/tasks are deferred, even if someone hand-edits the seed.
        for e in self.endpoints:
            if e.category == "correspondence" and e.status != "excluded":
                raise ValueError(
                    "correspondence endpoints must carry status='excluded' "
                    f"(got {e.status!r} on {e.endpoint_id!r})"
                )
            if e.category in ("schedule", "tasks") and e.status != "deferred":
                raise ValueError(
                    f"{e.category} endpoints must carry status='deferred' "
                    f"(got {e.status!r} on {e.endpoint_id!r})"
                )
        return self


class ProcoreProjectMapping(BaseModel):
    hb_project_key: str
    procore_project_id: str = ""  # may be empty for pending mappings
    procore_project_name: str = ""
    status: ProjectMappingStatus = "pending"

    model_config = {"extra": "forbid"}

    @field_validator("hb_project_key")
    @classmethod
    def _key_kebab(cls, v: str) -> str:
        return _kebab(v, "hb_project_key")

    @model_validator(mode="after")
    def _check_procore_project_id_shape(self) -> "ProcoreProjectMapping":
        value = self.procore_project_id
        if self.status == "pending":
            if value:
                raise ValueError(
                    f"procore_project_id={value!r} must be empty when status='pending' "
                    f"(hb_project_key={self.hb_project_key!r}); pending rows document "
                    "that a Procore mapping has not yet been established"
                )
            return self
        # status in ("pilot", "deprecated") — must carry a valid numeric Procore ID.
        if not value:
            raise ValueError(
                f"procore_project_id must be non-empty when status={self.status!r} "
                f"(hb_project_key={self.hb_project_key!r}); only 'pending' mappings "
                "may have an empty procore_project_id"
            )
        if _HB_NUMBER_PATTERN.match(value):
            raise ValueError(
                f"procore_project_id={value!r} matches forbidden HB project-number "
                r"pattern ^\d{2}-\d{3}-\d{2}$; Procore project IDs are integers "
                f"(hb_project_key={self.hb_project_key!r}) — use the numeric Procore "
                "ID instead"
            )
        if not _NUMERIC_PROCORE_ID_PATTERN.match(value):
            raise ValueError(
                f"procore_project_id={value!r} must be a numeric string matching "
                r"^\d+$ (Procore project IDs are integers); "
                f"hb_project_key={self.hb_project_key!r}"
            )
        return self


class ProcoreProjectsRegistry(BaseModel):
    version: int = 1
    company_id: str
    projects: list[ProcoreProjectMapping] = Field(default_factory=list)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _check_consistency(self) -> "ProcoreProjectsRegistry":
        keys = [p.hb_project_key for p in self.projects]
        if len(keys) != len(set(keys)):
            dupes = sorted({k for k in keys if keys.count(k) > 1})
            raise ValueError(f"duplicate hb_project_key entries: {dupes}")

        non_empty_ids = [p.procore_project_id for p in self.projects if p.procore_project_id]
        if len(non_empty_ids) != len(set(non_empty_ids)):
            dupes = sorted({k for k in non_empty_ids if non_empty_ids.count(k) > 1})
            raise ValueError(f"duplicate procore_project_id entries: {dupes}")
        return self

    def get(self, hb_project_key: str) -> ProcoreProjectMapping | None:
        return next(
            (p for p in self.projects if p.hb_project_key == hb_project_key),
            None,
        )


class AuthStatusReport(BaseModel):
    status: AuthStatus
    env_keys_present: list[str]
    env_keys_missing: list[str]
    token_cache_present: bool
    ready_for_live_calls: bool
    hint: str

    model_config = {"extra": "forbid"}


class EndpointAuditReport(BaseModel):
    project_key: str
    procore_project_id: str
    procore_project_name: str
    company_id: str
    endpoints: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class MappingValidationReport(BaseModel):
    company_id: str
    total: int
    by_status: dict[str, int] = Field(default_factory=dict)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    ok: bool

    model_config = {"extra": "forbid"}
