"""Auth onboarding services for the optional analytics UI shell."""

from __future__ import annotations

import uuid
from typing import Any

from hb_assistant.auth.providers import DelegatedAuthProvider
from hb_assistant.config.loader import load_config
from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.procore.auth import check_auth_status

_GRAPH_FLOWS: dict[str, dict[str, Any]] = {}


def _auth_guardrails() -> dict[str, Any]:
    return {
        "local_cache_only": True,
        "tokens_returned": False,
        "secrets_returned": False,
        "graph_data_api_called": False,
        "procore_data_api_called": False,
        "cli_shellout": False,
    }


def _scope_diagnostics(scopes: list[str]) -> dict[str, Any]:
    from hb_assistant.auth.scope_policy import get_scope_diagnostics

    return get_scope_diagnostics(scopes)


class AuthOnboardingService:
    """First-run Graph and Procore auth onboarding service.

    The service may write local auth caches only when an explicit completion or
    OAuth-code exchange method is called. It never returns bearer-token values.
    """

    def __init__(self, *, path_policy: PathPolicy | None = None) -> None:
        self._config = load_config()
        self._path_policy = path_policy or PathPolicy(self._config)

    def build_combined_status(self) -> dict[str, Any]:
        graph = self.graph_status()
        procore = self.procore_status()
        return {
            "surface": "analytics.auth_onboarding.status",
            "graph": graph,
            "procore": procore,
            "ready": {
                "graph_delegated": graph.get("token_type") == "delegated",
                "procore_oauth": bool(procore.get("ready_for_live_calls")),
            },
            "guardrails": _auth_guardrails(),
        }

    def graph_status(self) -> dict[str, Any]:
        from hb_assistant.auth.token_cache_manager import TokenCacheManager

        identity = self._config.identity
        cache = TokenCacheManager(self._path_policy).check_permissions()
        delegated_cache = cache.get("msal-token-cache.bin")
        cache_present = bool(
            isinstance(delegated_cache, dict) and delegated_cache.get("exists")
        )
        return {
            "surface": "analytics.auth_onboarding.graph_status",
            "token_type": "cached_unverified" if cache_present else "none",
            "classification": "delegated_cache_present" if cache_present else None,
            "account": None,
            "tenant": identity.tenant_id,
            "scopes": [],
            "expires_in_seconds_if_known": None,
            "cache": self._cache_presence(cache),
            "scope_diagnostics": _scope_diagnostics(list(identity.delegated_scopes)),
            "next_step": "verify_graph_status" if cache_present else "start_graph_device_login",
            "guardrails": _auth_guardrails(),
        }

    def start_graph_device_login(self) -> dict[str, Any]:
        provider = self._graph_provider()
        app = provider._get_app()  # noqa: SLF001 - existing auth primitive, no CLI shell-out.
        raw_scopes = list(provider._configured_scopes)  # noqa: SLF001
        scopes = provider.default_scopes
        flow = app.initiate_device_flow(scopes=scopes)
        if not isinstance(flow, dict) or "user_code" not in flow:
            return {
                "ok": False,
                "kind": "graph_device_flow_start_failed",
                "guardrails": _auth_guardrails(),
            }
        flow_id = uuid.uuid4().hex
        _GRAPH_FLOWS[flow_id] = {"flow": flow, "provider": provider, "raw_scopes": raw_scopes}
        return {
            "ok": True,
            "kind": "graph_device_flow_started",
            "flow_id": flow_id,
            "verification_uri": flow.get("verification_uri"),
            "verification_uri_complete": flow.get("verification_uri_complete"),
            "user_code": flow.get("user_code"),
            "expires_in": flow.get("expires_in"),
            "interval": flow.get("interval"),
            "message": flow.get("message"),
            "scope_diagnostics": _scope_diagnostics(raw_scopes),
            "guardrails": _auth_guardrails(),
        }

    def complete_graph_device_login(self, flow_id: str) -> dict[str, Any]:
        slot = _GRAPH_FLOWS.pop(flow_id, None)
        if slot is None:
            return {
                "ok": False,
                "kind": "graph_device_flow_not_found",
                "guardrails": _auth_guardrails(),
            }
        provider: DelegatedAuthProvider = slot["provider"]
        app = provider._get_app()  # noqa: SLF001 - uses same MSAL app/cache as start.
        result = app.acquire_token_by_device_flow(slot["flow"])
        if not isinstance(result, dict) or "access_token" not in result:
            return {
                "ok": False,
                "kind": "graph_device_flow_login_failed",
                "error": str(result.get("error") or "token_unavailable")[:80]
                if isinstance(result, dict)
                else "token_unavailable",
                "guardrails": _auth_guardrails(),
            }
        provider._cache_mgr.save_cache(app.token_cache, app_only=False)  # noqa: SLF001
        claims = result.get("id_token_claims") if isinstance(result.get("id_token_claims"), dict) else {}
        return {
            "ok": True,
            "kind": "graph_device_flow_login",
            "account": claims.get("upn") or claims.get("preferred_username"),
            "tenant": claims.get("tid"),
            "expires_in_seconds_if_known": result.get("expires_in"),
            "scope_diagnostics": _scope_diagnostics(slot["raw_scopes"]),
            "guardrails": _auth_guardrails(),
        }

    def procore_status(self) -> dict[str, Any]:
        from hb_assistant.procore.token_provider import (
            default_procore_token_provider,
            read_token_cache_payload,
        )

        report = check_auth_status().model_dump()
        cache_payload = read_token_cache_payload()
        chain = default_procore_token_provider()
        return {
            "surface": "analytics.auth_onboarding.procore_status",
            **report,
            "cache_present": cache_payload is not None,
            "access_cached": bool(
                cache_payload
                and isinstance(cache_payload.get("access_token"), str)
                and cache_payload["access_token"]
            ),
            "refresh_cached": bool(
                cache_payload
                and isinstance(cache_payload.get("refresh_token"), str)
                and cache_payload["refresh_token"]
            ),
            "expires_in_seconds_if_known": self._procore_cache_expiry(cache_payload),
            "chain_order": [getattr(p, "kind", type(p).__name__) for p in getattr(chain, "providers", ())],
            "guardrails": _auth_guardrails(),
        }

    def start_procore_oauth(self) -> dict[str, Any]:
        client = self._procore_oauth_client()
        return {
            "ok": True,
            "kind": "procore_oauth_started",
            "authorization_url": client.build_authorization_url(),
            "environment": client.environment,
            "redirect_uri": client.redirect_uri,
            "guardrails": _auth_guardrails(),
        }

    def exchange_procore_oauth_code(self, code: str) -> dict[str, Any]:
        from hb_assistant.procore.config import SecretNotAvailableError
        from hb_assistant.procore.oauth import ProcoreOAuthError
        from hb_assistant.procore.token_provider import write_token_cache

        try:
            token_set = self._procore_oauth_client().exchange_authorization_code(code)
            cache_path = write_token_cache(token_set)
        except SecretNotAvailableError:
            return {
                "ok": False,
                "kind": "secret_not_configured",
                "reason": "no_client_secret_in_keychain_env_or_protected_file",
                "guardrails": _auth_guardrails(),
            }
        except ProcoreOAuthError as exc:
            return {
                "ok": False,
                "kind": "oauth_login_failed",
                "status": int(exc.status),
                "correlation_id": exc.correlation_id,
                "guardrails": _auth_guardrails(),
            }
        return {
            "ok": True,
            "kind": "procore_oauth_exchange",
            "access_cached": True,
            "refresh_cached": bool(getattr(token_set, "refresh_token", None)),
            "expires_in_seconds": token_set.expires_in_seconds(),
            "cache_path": str(cache_path),
            "guardrails": _auth_guardrails(),
        }

    def _graph_provider(self) -> DelegatedAuthProvider:
        identity = self._config.identity
        return DelegatedAuthProvider(
            identity.tenant_id,
            identity.client_id,
            list(identity.delegated_scopes),
            path_policy=self._path_policy,
        )

    @staticmethod
    def _procore_oauth_client() -> Any:
        from hb_assistant.procore.config import load_procore_app_profile
        from hb_assistant.procore.oauth import ProcoreOAuthClient

        profile = load_procore_app_profile()
        return ProcoreOAuthClient(environment=profile.environment)

    @staticmethod
    def _cache_presence(cache: dict[str, Any]) -> dict[str, Any]:
        safe: dict[str, Any] = {}
        for key, value in cache.items():
            if key == "path_status" and isinstance(value, dict):
                safe[key] = {
                    "path_error": value.get("path_error"),
                    "has_ensure_report": bool(value.get("ensure_report")),
                }
            elif isinstance(value, dict):
                safe[key] = {
                    "exists": value.get("exists"),
                    "mode": value.get("mode"),
                    "perms_ok": value.get("perms_ok"),
                }
        return safe

    @staticmethod
    def _procore_cache_expiry(cache_payload: dict[str, Any] | None) -> int | None:
        if not cache_payload or not isinstance(cache_payload.get("expires_at"), str):
            return None
        from datetime import datetime, timezone

        try:
            deadline = datetime.fromisoformat(cache_payload["expires_at"].replace("Z", "+00:00"))
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            return int((deadline - datetime.now(timezone.utc)).total_seconds())
        except ValueError:
            return None
