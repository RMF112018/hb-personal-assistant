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

import re
from datetime import datetime

# Prompt_05 addition: Explicit Category enum
from enum import Enum as _Enum  # avoid collision if Enum already imported
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator


class Category(str, _Enum):
    """Prompt_05 categories per Decision Register."""

    FOUNDATION = "foundation"
    PROJECT_CONTROLS = "project_controls"
    FINANCIALS = "financials"


HttpMethod = Literal["GET"]  # read-only by construction
EndpointStatus = Literal["validated", "sensitive_validated", "excluded", "deferred"]
Sensitivity = Literal["low", "medium", "high", "critical"]
ProjectMappingStatus = Literal["pilot", "active", "pending", "deprecated"]
LIVE_REFRESH_ELIGIBLE_PROJECT_STATUSES: tuple[str, ...] = ("pilot", "active")
AuthStatus = Literal["env_present", "env_partial", "env_absent"]
VerificationStatus = Literal[
    "official_docs_verified",
    "candidate",
    "unverified",
    "excluded_by_guardrail",
    "deferred_by_guardrail",
]

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
    # --- Phase 04 Prompt 03: structured verification metadata --------------
    verification_status: VerificationStatus = "candidate"
    official_reference_url: str | None = None
    verified_at_utc: str | None = None
    verified_by: str | None = None
    live_dry_run_receipt_id: str | None = None
    verification_reason: str | None = None

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

    @field_validator("official_reference_url")
    @classmethod
    def _official_url_https(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v.startswith("https://"):
            raise ValueError(f"official_reference_url must start with 'https://'; got {v!r}")
        return v

    @field_validator("verified_at_utc")
    @classmethod
    def _verified_at_iso8601(cls, v: str | None) -> str | None:
        if v is None:
            return v
        normalized = v.replace("Z", "+00:00")
        try:
            datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(f"verified_at_utc must be ISO 8601; got {v!r}") from exc
        return v

    @model_validator(mode="after")
    def _check_verification_consistency(self) -> "ProcoreEndpoint":
        if self.status == "excluded" and self.verification_status != "excluded_by_guardrail":
            raise ValueError(
                f"status='excluded' requires verification_status='excluded_by_guardrail' "
                f"(got {self.verification_status!r} on {self.endpoint_id!r})"
            )
        if self.status == "deferred" and self.verification_status != "deferred_by_guardrail":
            raise ValueError(
                f"status='deferred' requires verification_status='deferred_by_guardrail' "
                f"(got {self.verification_status!r} on {self.endpoint_id!r})"
            )
        if self.verification_status == "excluded_by_guardrail" and self.status != "excluded":
            raise ValueError(
                f"verification_status='excluded_by_guardrail' requires status='excluded' "
                f"(got status={self.status!r} on {self.endpoint_id!r})"
            )
        if self.verification_status == "deferred_by_guardrail" and self.status != "deferred":
            raise ValueError(
                f"verification_status='deferred_by_guardrail' requires status='deferred' "
                f"(got status={self.status!r} on {self.endpoint_id!r})"
            )
        if self.status in ("validated", "sensitive_validated") and self.included_in_phase_01:
            if self.verification_status not in ("official_docs_verified", "candidate"):
                raise ValueError(
                    f"included Phase-01 endpoints must declare verification_status "
                    f"as 'official_docs_verified' or 'candidate' "
                    f"(got {self.verification_status!r} on {self.endpoint_id!r})"
                )
            has_url = bool(self.official_reference_url and self.official_reference_url.strip())
            has_reason = bool(self.verification_reason and self.verification_reason.strip())
            if not (has_url or has_reason):
                raise ValueError(
                    f"included Phase-01 endpoint {self.endpoint_id!r} must provide either "
                    "official_reference_url or verification_reason (got neither)"
                )
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_live_eligible(self) -> bool:
        """True only when this endpoint may be invoked against live Procore."""
        return (
            self.status not in ("excluded", "deferred")
            and self.included_in_phase_01
            and self.verification_status == "official_docs_verified"
        )


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
                f"endpoint contract must cover every required category (missing: {missing})"
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

    def get_endpoint(self, endpoint_id: str) -> ProcoreEndpoint | None:
        """Return the endpoint with the given id, or ``None`` if absent."""
        return next(
            (e for e in self.endpoints if e.endpoint_id == endpoint_id),
            None,
        )


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
        # status in ("pilot", "active", "deprecated") — must carry a valid numeric Procore ID.
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
    # Phase 04: also reflect whether the canonical macOS Keychain entry
    # exists. Defaults to False so existing test fixtures don't need updating.
    keychain_secret_present: bool = False

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


# Prompt_07: Endpoint audit dry-run + optional manual live (GET-only, redacted by default)
# Verdicts for per-endpoint audit outcomes (dry-run construction or explicit live).
AuditVerdict = Literal[
    "available",  # 2xx + valid shape, ready
    "unauthorized",  # 401
    "forbidden",  # 403 (incl. sensitive_review_required cases)
    "not_found",  # 404
    "deferred",  # per Prompt_05 contract (schedule/tasks etc.)
    "excluded",  # per Prompt_05 contract (correspondence)
    "error",  # network/parse/redaction/other
]


class DryRunRequestEnvelope(BaseModel):
    """Dry-run (no network) constructed GET request. Auth redacted by default."""

    method: Literal["GET"] = "GET"
    url: str
    headers_redacted: dict[str, str] = Field(default_factory=dict)  # e.g. Authorization: [REDACTED]
    params: dict[str, Any] | None = None
    correlation_id: str
    company_id: str | None = None

    model_config = {"extra": "forbid"}


class EndpointAuditReceipt(BaseModel):
    """Structured receipt for one endpoint audit (dry-run or manual live). Bodies redacted by default."""

    endpoint_id: str
    verdict: AuditVerdict
    request: DryRunRequestEnvelope
    redacted_response_summary: dict[str, Any] | None = (
        None  # structural only (keys/counts/hash); never full body
    )
    http_status: int | None = None
    category: str | None = None
    sensitivity: str | None = None
    notes_redacted: str | None = None
    redaction_applied: bool = True
    mode: Literal["dry_run", "live_manual"] = "dry_run"

    model_config = {"extra": "forbid"}


class EndpointAuditRunReceipt(BaseModel):
    """Top-level receipt for a full audit run (the 06- evidence JSON shape)."""

    receipt_type: str = "procore_endpoint_audit"
    audit_id: str
    mode: Literal["dry_run", "live_manual"]
    contract_version: str | None = None
    company_id: str
    started_at: str
    completed_at: str
    status: Literal["completed", "partial", "blocked_schema_not_ready"] = "completed"
    endpoints_audited: int
    breakdown: dict[str, Any] = Field(
        default_factory=dict
    )  # by_status, by_sensitivity, review_required etc.
    receipts: list[EndpointAuditReceipt] = Field(default_factory=list)
    persisted_to_sqlite: bool = False
    schema_version_at_audit: int | None = None
    redaction_applied: bool = True
    guardrails: dict[str, Any] = Field(default_factory=dict)
    error_redacted: dict[str, Any] | None = None

    model_config = {"extra": "forbid"}
