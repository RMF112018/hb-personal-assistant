"""Procore foundation: endpoint contract + dry-run audit.

Read-only by construction. The contract carries ``http_method: Literal["GET"]``
on every endpoint — a writeback endpoint cannot be loaded. No HTTP client
lives in this module; live access is deferred until a future prompt wires
OAuth + a Procore client.

Hard guardrails enforced at type + data level:
- Correspondence endpoint exists but is marked ``status="excluded"``.
- Schedule / Tasks endpoints exist but are marked ``status="deferred"``.
- Financial endpoints (change-events, commitments, prime-contracts, invoices)
  exist and are marked ``status="sensitive_validated"`` + ``sensitivity="high"``.
"""

from .auditor import EndpointAuditor
from .auth import AUTH_TOKEN_FILE_NAME, check_auth_status
from .loader import (
    EndpointContractError,
    ProcoreProjectsError,
    load_endpoint_contract,
    load_procore_projects,
)
from .models import (
    AuthStatusReport,
    EndpointAuditReport,
    EndpointStatus,
    MappingValidationReport,
    ProcoreEndpoint,
    ProcoreEndpointContract,
    ProcoreProjectMapping,
    ProcoreProjectsRegistry,
    Sensitivity,
)

__all__ = [
    "AUTH_TOKEN_FILE_NAME",
    "AuthStatusReport",
    "EndpointAuditReport",
    "EndpointAuditor",
    "EndpointContractError",
    "EndpointStatus",
    "MappingValidationReport",
    "ProcoreEndpoint",
    "ProcoreEndpointContract",
    "ProcoreProjectMapping",
    "ProcoreProjectsError",
    "ProcoreProjectsRegistry",
    "Sensitivity",
    "check_auth_status",
    "load_endpoint_contract",
    "load_procore_projects",
]
