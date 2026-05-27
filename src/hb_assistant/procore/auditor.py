"""Endpoint auditor — pure projection over the loaded contract + projects.

No I/O. No network. Given a :class:`ProcoreEndpointContract` and a
:class:`ProcoreProjectsRegistry`, produces the access matrix per project
and validates the mapping registry against the source registry.
"""

from __future__ import annotations

from .models import (
    EndpointAuditReport,
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
            endpoint_rows.append({
                "endpoint_id": ep.endpoint_id,
                "category": ep.category,
                "http_method": ep.http_method,
                "path_template": ep.path_template,
                "status": ep.status,
                "sensitivity": ep.sensitivity,
                "verdict": verdict,
            })
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
