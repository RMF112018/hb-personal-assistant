"""Procore foundation: GET-only HTTP client, dry-run audit, and dry-run sync.

Read-only by construction. The endpoint contract carries ``http_method:
Literal["GET"]`` on every endpoint — a writeback endpoint cannot be loaded.
The HTTP client (:class:`hb_assistant.procore.http_client.ProcoreHTTPClient`)
requires an OAuth access token via an injectable provider and fails closed
with :class:`ProcoreAuthRequired` if none is available. The client never
consumes ``PROCORE_CLIENT_SECRET`` as a bearer credential.

OAuth token-exchange itself is not implemented in this module; until it is,
operators populate ``PROCORE_ACCESS_TOKEN`` (env) or the macOS Keychain
account ``access-token`` under service ``hb-assistant-procore``.

The sync coordinator (:class:`ProcoreSyncCoordinator`) supports a redacted
dry-run plan (default) and an explicit ``apply`` mode that writes only to
local SQLite. Pending project mappings are rejected unless the caller passes
``allow_pending=True``; the prior stub-projects fallback has been removed.

Hard guardrails enforced at type + data level:
- Correspondence endpoint exists but is marked ``status="excluded"``.
- Schedule / Tasks endpoints exist but are marked ``status="deferred"``.
- Financial endpoints (change-events, commitments, prime-contracts, invoices)
  exist and are marked ``status="sensitive_validated"`` + ``sensitivity="high"``.
"""

from .auditor import EndpointAuditor
from .auth import AUTH_TOKEN_FILE_NAME, check_auth_status
from .errors import (
    ProcoreAPIError,
    ProcoreAuthRequired,
    ProcoreMappingUnavailable,
    ProcorePendingProjectRejected,
    ProcoreRateLimitError,
)
from .http_client import ProcoreHTTPClient
from .live_gate import (
    LIVE_ENV_ENABLER,
    LIVE_ENV_VAR,
    LiveEnvNotSet,
    assert_live_mapping_strict,
    live_env_active,
    require_live_env,
)
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
from .oauth import (
    ProcoreOAuthClient,
    ProcoreOAuthError,
    TokenSet,
)
from .obsidian import (
    PROCORE_GUARDRAILS,
    ProcoreObsidianRenderer,
    procore_obsidian_preview,
    reset_procore_obsidian_caches,
)
from .sync import (
    ProcoreSyncCoordinator,
    SyncReceipt,
    run_sync,
)
from .token_provider import (
    EnvOrKeychainTokenProvider,
    LocalOAuthCacheTokenProvider,
    MissingTokenProvider,
    ProcoreTokenProvider,
    RefreshingOAuthTokenProvider,
    clear_token_cache,
    default_procore_token_provider,
    write_token_cache,
)

__all__ = [
    "AUTH_TOKEN_FILE_NAME",
    "AuthStatusReport",
    "EndpointAuditReport",
    "EndpointAuditor",
    "EndpointContractError",
    "EndpointStatus",
    "EnvOrKeychainTokenProvider",
    "LIVE_ENV_ENABLER",
    "LIVE_ENV_VAR",
    "LiveEnvNotSet",
    "LocalOAuthCacheTokenProvider",
    "MappingValidationReport",
    "MissingTokenProvider",
    "PROCORE_GUARDRAILS",
    "ProcoreAPIError",
    "ProcoreAuthRequired",
    "ProcoreEndpoint",
    "ProcoreEndpointContract",
    "ProcoreHTTPClient",
    "ProcoreMappingUnavailable",
    "ProcoreOAuthClient",
    "ProcoreOAuthError",
    "ProcoreObsidianRenderer",
    "ProcorePendingProjectRejected",
    "ProcoreProjectMapping",
    "ProcoreProjectsError",
    "ProcoreProjectsRegistry",
    "ProcoreRateLimitError",
    "ProcoreSyncCoordinator",
    "ProcoreTokenProvider",
    "RefreshingOAuthTokenProvider",
    "Sensitivity",
    "SyncReceipt",
    "TokenSet",
    "assert_live_mapping_strict",
    "check_auth_status",
    "clear_token_cache",
    "default_procore_token_provider",
    "live_env_active",
    "load_endpoint_contract",
    "load_procore_projects",
    "procore_obsidian_preview",
    "require_live_env",
    "reset_procore_obsidian_caches",
    "run_sync",
    "write_token_cache",
]
