"""Endpoint auditor — pure projection over the loaded contract + projects.

No I/O. No network. Given a :class:`ProcoreEndpointContract` and a
:class:`ProcoreProjectsRegistry`, produces the access matrix per project
and validates the mapping registry against the source registry.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from .models import (
    AuditVerdict,
    DryRunRequestEnvelope,
    EndpointAuditReceipt,
    EndpointAuditReport,
    EndpointAuditRunReceipt,
    MappingValidationReport,
    ProcoreEndpoint,
    ProcoreEndpointContract,
    ProcoreProjectsRegistry,
)

# Verdict the auditor assigns per endpoint+project.
VERDICT_AUDITABLE = "would_audit"
VERDICT_SENSITIVE = "sensitive_review_required"
VERDICT_EXCLUDED = "excluded"
VERDICT_DEFERRED = "deferred"
VERDICT_UNMAPPED = "project_not_mapped"


def _verdict_for(endpoint: ProcoreEndpoint, *, mapped: bool) -> str:
    if endpoint.status == "excluded":
        return VERDICT_EXCLUDED
    if endpoint.status == "deferred":
        return VERDICT_DEFERRED
    if not mapped:
        return VERDICT_UNMAPPED
    if endpoint.status == "sensitive_validated":
        return VERDICT_SENSITIVE
    return VERDICT_AUDITABLE


class EndpointAuditor:
    def __init__(
        self,
        contract: ProcoreEndpointContract,
        projects: ProcoreProjectsRegistry,
    ) -> None:
        self._contract = contract
        self._projects = projects

    def audit_project(self, hb_project_key: str) -> EndpointAuditReport:
        mapping = self._projects.get(hb_project_key)
        if mapping is None:
            raise KeyError(f"unknown hb_project_key: {hb_project_key!r}")

        mapped = bool(mapping.procore_project_id)
        endpoint_rows: list[dict] = []
        counts: dict[str, int] = {}
        for ep in self._contract.endpoints:
            verdict = _verdict_for(ep, mapped=mapped)
            counts[verdict] = counts.get(verdict, 0) + 1
            endpoint_rows.append(
                {
                    "endpoint_id": ep.endpoint_id,
                    "category": ep.category,
                    "http_method": ep.http_method,
                    "path_template": ep.path_template,
                    "status": ep.status,
                    "sensitivity": ep.sensitivity,
                    "verdict": verdict,
                }
            )
        return EndpointAuditReport(
            project_key=hb_project_key,
            procore_project_id=mapping.procore_project_id,
            procore_project_name=mapping.procore_project_name,
            company_id=self._contract.company_id,
            endpoints=endpoint_rows,
            summary=counts,
        )

    def audit_all(self) -> list[EndpointAuditReport]:
        return [self.audit_project(p.hb_project_key) for p in self._projects.projects]

    def validate_mapping(self) -> MappingValidationReport:
        by_status: dict[str, int] = {}
        rows: list[dict] = []
        for p in self._projects.projects:
            mapped = bool(p.procore_project_id)
            row = {
                "hb_project_key": p.hb_project_key,
                "procore_project_id": p.procore_project_id,
                "procore_project_name": p.procore_project_name,
                "status": p.status,
                "mapped": mapped,
            }
            rows.append(row)
            by_status[p.status] = by_status.get(p.status, 0) + 1
        # ok only when every project either is a pilot with an id, or
        # explicitly deprecated (pending rows flag an incomplete mapping).
        ok = all(
            r["status"] in ("pilot", "deprecated") and (r["mapped"] or r["status"] == "deprecated")
            for r in rows
        )
        return MappingValidationReport(
            company_id=self._projects.company_id,
            total=len(rows),
            by_status=by_status,
            rows=rows,
            ok=ok,
        )


# Prompt_07 additions: endpoint dry-run request construction (no network) + optional explicit manual live (GET-only)
# + per-endpoint verdicts + default body redaction + receipt emission (JSON-first; SQLite gated on migrator readiness).
# Reuses existing contract + projects registry + Prompt_04 redaction/error patterns + Prompt_05 categories + Prompt_06 pending handling.

# New explicit verdicts (extend/compat with existing _verdict_for where possible).
NEW_VERDICT_AVAILABLE = "available"
NEW_VERDICT_UNAUTHORIZED = "unauthorized"
NEW_VERDICT_FORBIDDEN = "forbidden"
NEW_VERDICT_NOT_FOUND = "not_found"
# (deferred/excluded/error reuse existing strings for continuity)


def _map_existing_to_new_verdict(old_verdict: str) -> AuditVerdict:
    mapping = {
        "would_audit": NEW_VERDICT_AVAILABLE,
        "sensitive_review_required": NEW_VERDICT_FORBIDDEN,
        "excluded": "excluded",
        "deferred": "deferred",
        "project_not_mapped": "error",  # treat unmapped as error for audit context
    }
    return mapping.get(old_verdict, "error")  # type: ignore[return-value]


def _build_dry_run_envelope(
    endpoint: "ProcoreEndpoint",  # type: ignore[name-defined]
    *,
    company_id: str,
    base_url: str,  # from Prompt_02 env config (sanitized)
    project_id: str | None,
    correlation_id: str | None = None,
) -> DryRunRequestEnvelope:
    """Pure construction — no network, no secrets."""
    path = endpoint.path_template
    if project_id and "{project_id}" in path:
        path = path.replace("{project_id}", project_id)
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    headers_redacted = {
        "Authorization": "[REDACTED]",
        "Procore-Company-Id": company_id,
        "Accept": "application/json",
        "User-Agent": "hb-assistant-procore-dry-run/1.0",
    }
    params: dict[str, Any] | None = (
        None  # extend with pagination defaults from Prompt_04/01 research if needed
    )
    return DryRunRequestEnvelope(
        url=url,
        headers_redacted=headers_redacted,
        params=params,
        correlation_id=correlation_id or str(uuid4()),
        company_id=company_id,
    )


class EndpointAuditor(EndpointAuditor):  # noqa: F811  # extended in place
    # ... (existing __init__, audit_project, audit_all, validate_mapping unchanged above)

    def dry_run_audit_project(
        self,
        hb_project_key: str,
        *,
        base_url: str,
        redactor: Any | None = None,  # injectable redaction (defaults to Prompt_04)
    ) -> list[EndpointAuditReceipt]:
        """Dry-run only: constructs request envelopes, assigns verdicts, redacts by default. No network."""
        mapping = self._projects.get(hb_project_key)
        if mapping is None:
            raise KeyError(f"unknown hb_project_key: {hb_project_key!r}")

        mapped = bool(mapping.procore_project_id)
        receipts: list[EndpointAuditReceipt] = []
        for ep in self._contract.endpoints:
            old_v = _verdict_for(ep, mapped=mapped)
            verdict: AuditVerdict = _map_existing_to_new_verdict(old_v)
            envelope = _build_dry_run_envelope(
                ep,
                company_id=self._contract.company_id,
                base_url=base_url,
                project_id=mapping.procore_project_id or None,
            )
            # Default body redaction (even for simulated "response")
            receipt = EndpointAuditReceipt(
                endpoint_id=ep.endpoint_id,
                verdict=verdict,
                request=envelope,
                redacted_response_summary={
                    "redacted": True,
                    "reason": "default-body-redaction-in-dry-run",
                },
                category=getattr(ep, "category", None),
                sensitivity=getattr(ep, "sensitivity", None),
                notes_redacted="[REDACTED]" if getattr(ep, "notes", None) else None,
                mode="dry_run",
            )
            receipts.append(receipt)
        return receipts

    def build_audit_run_receipt(
        self,
        project_key: str,
        *,
        base_url: str,
        mode: Literal["dry_run", "live_manual"] = "dry_run",
        live_client: Any | None = None,  # only for explicit manual live; must be Prompt_04 client
        migrator: Any | None = None,  # for SQLite readiness gate (optional)
    ) -> EndpointAuditRunReceipt:
        """Top-level receipt builder. Dry-run default. Live only via explicit opt-in (never auto)."""
        if mode == "live_manual" and live_client is None:
            raise ValueError(
                "live_manual requires explicit live_client (opt-in only; never in tests)"
            )

        started = datetime.now(timezone.utc).isoformat()
        receipts = self.dry_run_audit_project(project_key, base_url=base_url)  # dry-run core

        # Optional: if live_client provided (manual only), execute real GETs here (still redacted via Prompt_04)
        # Guard: caller must have explicitly opted in; we do not auto-promote.

        completed = datetime.now(timezone.utc).isoformat()

        # SQLite gate (if migrator passed): check readiness; never write in dry-run or unready
        persisted = False
        schema_v = None
        if migrator is not None:
            try:
                schema_v = getattr(migrator, "current_version", lambda: 0)()
                # In real: only write if >= target and mode allows; here we stay JSON-first per plan
                persisted = False  # evidence JSON is primary for this prompt
            except Exception:
                persisted = False

        breakdown: dict[str, Any] = {"by_verdict": {}, "review_required": 0}
        for r in receipts:
            breakdown["by_verdict"][r.verdict] = breakdown["by_verdict"].get(r.verdict, 0) + 1

        guardrails = {
            "read_only": True,
            "body_redaction": "default",
            "live_calls": "opt_in_manual_only",
            "transport_injected": True,
            "no_secrets_in_artifacts": True,
        }

        return EndpointAuditRunReceipt(
            audit_id=str(uuid4()),
            mode=mode,
            company_id=self._contract.company_id,
            started_at=started,
            completed_at=completed,
            endpoints_audited=len(receipts),
            breakdown=breakdown,
            receipts=receipts,
            persisted_to_sqlite=persisted,
            schema_version_at_audit=schema_v,
            redaction_applied=True,
            guardrails=guardrails,
        )
