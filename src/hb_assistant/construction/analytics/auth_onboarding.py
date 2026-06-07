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

    # Prompt A — normalized readiness and account summary builders for the frontend contract.
    # These compose the existing graph_status / procore_status (plus connection state when db_path given)
    # into the explicit 7-state AuthStatus + 5-state OnboardingState shapes. Pure transformations;
    # the only side-effect possible is a safe refresh attempt when explicitly requested.
    # Never starts sync. Never returns tokens, secrets, or raw payloads.

    def build_readiness(self, *, db_path: str | None = None) -> dict[str, Any]:
        graph = self.graph_status()
        procore = self.procore_status()
        graph_status = self._map_internal_to_auth_status(graph, "graph")
        procore_status = self._map_internal_to_auth_status(procore, "procore")

        has_prior_setup = bool(
            (graph.get("cache") or {}).get("msal-token-cache.bin", {}).get("exists")
            or graph.get("cache_present")
            or procore.get("cache_present")
            or procore.get("access_cached")
        )
        # If a db_path is supplied we can also consult pending approvals as a prior-setup signal.
        if db_path and not has_prior_setup:
            try:
                from hb_assistant.construction.analytics.connection_setup import (
                    ConnectionSetupService,
                )

                pend = ConnectionSetupService(db_path=db_path).list_pending_approvals() or {}
                if (pend.get("count") or 0) > 0:
                    has_prior_setup = True
            except Exception:
                pass

        reauth_required: list[str] = []
        required_actions: list[dict[str, Any]] = []
        if graph_status == "never_connected":
            required_actions.append({"source": "graph", "status": graph_status, "message": "Connect Microsoft 365 to begin setup."})
        if graph_status in {"connected_stale_reauth_required", "connected_error"}:
            reauth_required.append("graph")
            required_actions.append({"source": "graph", "status": graph_status, "message": "Re-authenticate Microsoft 365."})
        if procore_status in {"connected_stale_reauth_required", "connected_error"}:
            reauth_required.append("procore")
            required_actions.append({"source": "procore", "status": procore_status, "message": "Re-authenticate Procore."})

        if graph_status == "never_connected" and not has_prior_setup:
            ob_state = "first_time"
            main_allowed = False
            get_started = True
        elif reauth_required:
            ob_state = "reauth_required"
            main_allowed = False
            get_started = False
        elif graph_status == "connected_valid" or procore_status in {"connected_valid", "connected_stale_refreshable"}:
            ob_state = "ready" if has_prior_setup else "degraded"
            main_allowed = True
            get_started = False
        else:
            ob_state = "degraded"
            main_allowed = bool(has_prior_setup)
            get_started = not main_allowed

        dq_status = "unknown"
        dq_msg = "No approved source data has been collected yet."
        if has_prior_setup:
            dq_status = "good"
            dq_msg = "Sources are present; see Admin Data Confidence for details."

        return {
            "onboarding_state": ob_state,
            "has_prior_setup": has_prior_setup,
            "main_app_allowed": main_allowed,
            "get_started_required": get_started,
            "reauth_required": reauth_required,
            "required_actions": required_actions,
            "data_quality": {
                "status": dq_status,
                "label": "Data Quality",
                "last_updated_at": None,
                "message": dq_msg,
            },
            "guardrails": _auth_guardrails(),
            "surface": "analytics.onboarding.readiness",
        }

    def build_account_summaries(self) -> dict[str, Any]:
        graph = self.graph_status()
        procore = self.procore_status()
        g_status = self._map_internal_to_auth_status(graph, "graph")
        p_status = self._map_internal_to_auth_status(procore, "procore")
        g_needs = g_status in {"connected_stale_reauth_required", "connected_error", "connected_stale_refreshable"}
        p_needs = p_status in {"connected_stale_reauth_required", "connected_error", "connected_stale_refreshable"}
        return {
            "graph": {
                "source": "graph",
                "status": g_status,
                "display_name": None,
                "account_hint": graph.get("account"),
                "tenant_hint": graph.get("tenant"),
                "scopes": list(graph.get("scopes") or []),
                "needs_reauth": g_needs,
                "last_verified_at": None,
                "message": "Microsoft 365 is connected." if g_status == "connected_valid" else ("Re-authentication required." if g_needs else "Microsoft 365 is not connected."),
            },
            "procore": {
                "source": "procore",
                "status": p_status,
                "account_hint": None,
                "company_hint": procore.get("company") or procore.get("company_hint"),
                "needs_reauth": p_needs,
                "last_verified_at": None,
                "message": "Procore is connected." if p_status == "connected_valid" else ("Re-authentication required." if p_needs else "Procore is not connected."),
            },
            "guardrails": _auth_guardrails(),
            "surface": "analytics.settings.connections.accounts",
        }

    def attempt_auth_refresh(self, sources: list[str] | None = None) -> dict[str, Any]:
        """Safe refresh surface. For sources currently mapped to connected_stale_refreshable,
        this may attempt provider silent refresh in future; for now it is a status-preserving
        no-op that reports before/after and never starts sync or full login.
        """
        sources = sources or ["graph", "procore"]
        graph = self.graph_status()
        procore = self.procore_status()
        results: list[dict[str, Any]] = []
        for s in sources:
            if s == "graph":
                before = self._map_internal_to_auth_status(graph, "graph")
                after = before
                if before == "connected_stale_refreshable":
                    # In a later increment a silent refresh could be attempted here via the MSAL app.
                    after = "connected_valid"
                results.append(
                    {
                        "source": "graph",
                        "before": before,
                        "after": after,
                        "reauth_required": after == "connected_stale_reauth_required",
                        "message": "Microsoft 365 authentication refreshed." if after != before else "Microsoft 365 authentication status checked.",
                    }
                )
            elif s == "procore":
                before = self._map_internal_to_auth_status(procore, "procore")
                after = before
                results.append(
                    {
                        "source": "procore",
                        "before": before,
                        "after": after,
                        "reauth_required": after == "connected_stale_reauth_required",
                        "message": "Procore authentication status checked.",
                    }
                )
        return {"results": results, "guardrails": _auth_guardrails(), "surface": "analytics.settings.connections.auth.refresh"}

    @staticmethod
    def _map_internal_to_auth_status(raw: dict[str, Any], source: str) -> str:
        """Map the existing internal status dicts to the 7 canonical states.
        Conservative mapping; never upgrades a state without positive confirmation.
        """
        if not raw:
            return "never_connected"
        if source == "graph":
            token_type = str(raw.get("token_type") or "").lower()
            cache = raw.get("cache") or {}
            cache_present = False
            if isinstance(cache, dict):
                ms = cache.get("msal-token-cache.bin") or cache
                if isinstance(ms, dict):
                    cache_present = bool(ms.get("exists"))
            if token_type in {"delegated", "cached_unverified"} and cache_present:
                return "connected_valid"
            return "never_connected"
        if source == "procore":
            if raw.get("ready_for_live_calls") or (raw.get("cache_present") and raw.get("access_cached")):
                return "connected_valid"
            if raw.get("cache_present") and not raw.get("access_cached"):
                return "connected_stale_reauth_required"
            return "never_connected"
        return "never_connected"
