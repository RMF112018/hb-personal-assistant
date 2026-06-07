"""Auth onboarding services for the optional analytics UI shell."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from hb_assistant.auth.providers import DelegatedAuthProvider
from hb_assistant.config.loader import load_config
from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.procore.auth import check_auth_status

_GRAPH_FLOWS: dict[str, dict[str, Any]] = {}

# Prompt C: in-memory store for Procore OAuth flows (flow_id -> slot with state for CSRF validation,
# timestamps, profile info). Short-lived; popped on completion/expiry/use. Never persisted.
_PROCORE_FLOWS: dict[str, dict[str, Any]] = {}


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

        base = {
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

        if not cache_present:
            return base

        # Prompt B: verify with silent MSAL acquisition (not just file presence).
        # This makes connected status honest and allows readiness to avoid false "valid"
        # when the cached token is expired/revoked. On success we populate safe metadata.
        try:
            prov = self._graph_provider()
            info = prov.status_info()  # performs get_token() -> acquire_token_silent + claims ensure
            if info.get("token_type") == "delegated":
                claims = info.get("id_token_claims") or {}
                return {
                    **base,
                    "token_type": "delegated",
                    "classification": "delegated_verified",
                    "account": info.get("upn") or claims.get("upn") or claims.get("preferred_username"),
                    "tenant": info.get("tenant") or claims.get("tid") or identity.tenant_id,
                    "scopes": info.get("scopes") or _scope_diagnostics(list(identity.delegated_scopes)).get("effective_msal_scopes", []),
                    "expires_in_seconds_if_known": info.get("expires_in"),
                    "next_step": None,
                }
            else:
                # File existed but status_info reports none (silent failed) => stale/reauth
                return {
                    **base,
                    "classification": "stale_reauth_required",
                    "message": "Cached Graph credentials present but silent acquisition failed.",
                }
        except Exception:
            return {
                **base,
                "classification": "stale_reauth_required",
                "message": "Silent verification of cached Graph auth failed; re-auth may be required.",
            }

    def graph_source_status(self) -> dict[str, Any]:
        """Normalized, browser-safe Graph source status for /api/sources/graph/status.

        Reuses ``graph_status()`` (offline; silent-MSAL only, never a Graph data API) and adds a
        normalized ``state`` plus a missing-scope surface. Constructs no Graph data client.
        """
        from hb_assistant.auth.scope_policy import EXPECTED_GRAPH_SCOPES

        base = self.graph_status()
        token_type = base.get("token_type")
        classification = base.get("classification")
        if token_type == "delegated" and classification == "delegated_verified":
            state = "connected_valid"
        elif classification == "stale_reauth_required":
            state = "reauth_required"
        elif classification == "delegated_cache_present":
            state = "cache_present_unverified"
        else:
            state = "not_connected"

        diag = base.get("scope_diagnostics") or {}
        present = {s.lower() for s in (diag.get("configured_scopes") or [])} | {
            s.lower() for s in (base.get("scopes") or [])
        }

        def _satisfied(expected: str) -> bool:
            # A read scope is satisfied by the same scope or a write-capable superset of the
            # same resource (e.g. Calendars.ReadWrite.Shared satisfies Calendars.Read), since
            # ReadWrite grants read. Exact match also satisfies.
            resource = expected.split(".", 1)[0]
            return any(p.startswith(f"{resource}.") and "read" in p for p in present)

        missing = sorted(s for s in EXPECTED_GRAPH_SCOPES if not _satisfied(s))

        return {
            "surface": "analytics.sources.graph.status",
            "system": "microsoft_365_graph",
            "state": state,
            "token_type": token_type,
            "classification": classification,
            "account": base.get("account"),
            "tenant": base.get("tenant"),
            "scopes": base.get("scopes"),
            "expires_in_seconds_if_known": base.get("expires_in_seconds_if_known"),
            "scope_presence": {
                "expected": sorted(EXPECTED_GRAPH_SCOPES),
                "missing": missing,
                "all_present": not missing,
            },
            "scope_diagnostics": diag,
            "next_step": base.get("next_step"),
            "message": base.get("message"),
            "guardrails": base.get("guardrails"),
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

    # Prompt B — new normalized contract methods for the /api/settings/connections/graph/auth/* family.
    # Share the same in-memory _GRAPH_FLOWS slot as the legacy device login methods so that
    # either surface can observe in-flight flows. The new methods return the exact frontend
    # contract shapes (no tokens, no cache paths, safe account hints only). Expiry and pending
    # are handled without blocking.

    def start_graph_device_auth(self) -> dict[str, Any]:
        provider = self._graph_provider()
        app = provider._get_app()  # noqa: SLF001 - existing auth primitive
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
        expires_in = int(flow.get("expires_in") or 900)
        started_at = datetime.now(timezone.utc).isoformat()
        _GRAPH_FLOWS[flow_id] = {
            "flow": flow,
            "provider": provider,
            "raw_scopes": raw_scopes,
            "started_at": started_at,
            "expires_in": expires_in,
        }
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
        return {
            "flow_id": flow_id,
            "verification_uri": flow.get("verification_uri"),
            "verification_uri_complete": flow.get("verification_uri_complete"),
            "user_code": flow.get("user_code"),
            "expires_at": expires_at,
            "interval_seconds": int(flow.get("interval") or 5),
            "message": "Sign in to Microsoft 365 using the displayed code. Connecting does not start sync.",
            "guardrails": _auth_guardrails(),
        }

    def poll_graph_device_auth_status(self, flow_id: str) -> dict[str, Any]:
        slot = _GRAPH_FLOWS.get(flow_id)
        if slot is None:
            return {
                "flow_id": flow_id,
                "status": "failed",
                "message": "No active flow for this id (it may have completed, expired, or been replaced).",
                "guardrails": _auth_guardrails(),
            }

        # Expiry check (best-effort; fallback to flow's expires_in if present)
        expires_in = slot.get("expires_in")
        if expires_in is None and isinstance(slot.get("flow"), dict):
            expires_in = slot["flow"].get("expires_in")
        started_at = slot.get("started_at")
        if started_at and expires_in:
            try:
                start_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - start_dt).total_seconds() > int(expires_in) + 30:
                    _GRAPH_FLOWS.pop(flow_id, None)
                    return {
                        "flow_id": flow_id,
                        "status": "expired",
                        "message": "Device code expired. Please start a new sign-in.",
                        "guardrails": _auth_guardrails(),
                    }
            except Exception:
                pass

        provider: DelegatedAuthProvider = slot["provider"]
        app = provider._get_app()  # noqa: SLF001
        result = app.acquire_token_by_device_flow(slot["flow"])
        if not isinstance(result, dict):
            _GRAPH_FLOWS.pop(flow_id, None)
            return {
                "flow_id": flow_id,
                "status": "failed",
                "message": "Device flow failed.",
                "guardrails": _auth_guardrails(),
            }

        if "access_token" in result:
            provider._cache_mgr.save_cache(app.token_cache, app_only=False)  # noqa: SLF001
            _GRAPH_FLOWS.pop(flow_id, None)
            claims = result.get("id_token_claims") if isinstance(result.get("id_token_claims"), dict) else {}
            account = {
                "display_name": None,
                "account_hint": claims.get("upn") or claims.get("preferred_username"),
                "tenant_hint": claims.get("tid"),
                "scopes": _scope_diagnostics(slot.get("raw_scopes", [])).get("effective_msal_scopes", []),
            }
            return {
                "flow_id": flow_id,
                "status": "complete",
                "account": account,
                "message": "Microsoft 365 is connected.",
                "guardrails": _auth_guardrails(),
            }

        # No token yet — classify the error
        err = str((result or {}).get("error") or "")
        err_desc = str((result or {}).get("error_description") or "").lower()
        if "authorization_pending" in err or "slow_down" in err:
            return {
                "flow_id": flow_id,
                "status": "pending",
                "message": "Waiting for user to complete sign-in in the browser.",
                "guardrails": _auth_guardrails(),
            }

        # Terminal: pop and classify
        _GRAPH_FLOWS.pop(flow_id, None)
        if "expired" in err or "code_expired" in err_desc:
            return {
                "flow_id": flow_id,
                "status": "expired",
                "message": "Device code expired.",
                "guardrails": _auth_guardrails(),
            }
        # Treat user cancel / deny / other as failed (cancelled can be surfaced as message if needed)
        return {
            "flow_id": flow_id,
            "status": "failed",
            "message": "Sign-in failed or was cancelled.",
            "guardrails": _auth_guardrails(),
        }

    def disconnect_graph_local(self) -> dict[str, Any]:
        try:
            provider = self._graph_provider()
            # Clear local delegated cache + remove MSAL account. Discard any returned paths.
            provider.logout()
        except Exception:
            # Best effort; absence of cache on next status is the observable effect.
            pass
        return {
            "ok": True,
            "kind": "graph_disconnected_local",
            "message": "Microsoft 365 local authentication cleared. Sign-in will be required to reconnect.",
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

    # (legacy exchange_procore_oauth_code body removed; single implementation below supports both
    # legacy callers (default normalized_path=False, emits cache_path for root paths) and the
    # normalized contract surfaces (normalized_path=True suppresses cache_path).)

    # Prompt C — normalized contract methods for the /api/settings/connections/procore/auth/* family.
    # These implement the split start + (callback or manual) + poll flow using the existing
    # ProcoreOAuthClient for URL/exchange/refresh and token_provider for cache write/clear/refresh.
    # In-memory flow slots hold state for CSRF; short expiry; never return tokens, codes, state,
    # or cache paths to callers. The callback returns minimal safe HTML only.

    def start_procore_auth_flow(self) -> dict[str, Any]:
        from hb_assistant.procore.config import load_procore_app_profile

        profile = load_procore_app_profile()
        # Acquire client via the test seam ( _procore_oauth_client ) so fakes work for both legacy and new surfaces.
        client = self._procore_oauth_client()
        # Generate opaque flow and CSRF state. Store profile info for validation on callback.
        flow_id = uuid.uuid4().hex
        state = uuid.uuid4().hex
        started_at = datetime.now(timezone.utc).isoformat()
        expires_in = 600  # 10 min window for the OAuth dance
        _PROCORE_FLOWS[flow_id] = {
            "state": state,
            "started_at": started_at,
            "expires_in": expires_in,
            "environment": profile.environment,
            "redirect_uri": profile.redirect_uri,
            "client_id": profile.client_id,
        }
        # Build the URL (client provides base + params; append state for our CSRF).
        base_url = client.build_authorization_url()
        # Ensure state is present (idempotent append if not already in the OOB URL).
        sep = "&" if "?" in base_url else "?"
        auth_url = f"{base_url}{sep}state={state}" if "state=" not in base_url else base_url
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
        # Determine callback posture from the registered redirect (OOB vs localhost).
        callback_mode = "localhost" if profile.redirect_uri.startswith("http://localhost") else "oob"
        return {
            "flow_id": flow_id,
            "authorization_url": auth_url,
            "expires_at": expires_at,
            "callback_mode": callback_mode,
            "manual_code_fallback_available": True,
            "message": "Open Procore to authorize. Connecting does not start sync.",
            "guardrails": _auth_guardrails(),
        }

    def handle_procore_oauth_callback(self, code: str, state: str) -> str:
        """Server-side callback handler. Validates state, exchanges, writes cache (server only),
        returns minimal safe static HTML. Never includes any token material or paths.
        """
        # Find the slot by state (CSRF). Linear scan is fine for small in-mem set.
        flow_id = None
        slot = None
        for fid, s in list(_PROCORE_FLOWS.items()):
            if s.get("state") == state:
                flow_id = fid
                slot = s
                break
        if slot is None:
            # Invalid state or expired flow; still return safe HTML (no leak of why).
            return "<html><body>Procore sign-in could not be completed (invalid or expired). You may close this window and try again.</body></html>"

        # Expiry check
        try:
            started = datetime.fromisoformat(slot.get("started_at", "").replace("Z", "+00:00"))
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - started).total_seconds() > int(slot.get("expires_in", 600)) + 30:
                _PROCORE_FLOWS.pop(flow_id, None)
                return "<html><body>Procore sign-in expired. Please start again from the app.</body></html>"
        except Exception:
            pass

        try:
            from hb_assistant.procore.config import load_procore_app_profile
            from hb_assistant.procore.oauth import ProcoreOAuthError
            from hb_assistant.procore.token_provider import write_token_cache

            # profile only for potential future use / parity; client action goes through seam for fakes
            _ = load_procore_app_profile()
            client = self._procore_oauth_client()
            token_set = client.exchange_authorization_code(code)
            # Write for the rest of the system to use; discard the path so it is never returned.
            write_token_cache(token_set)
        except ProcoreOAuthError:
            _PROCORE_FLOWS.pop(flow_id, None)
            return "<html><body>Procore sign-in failed. You may close this window and retry.</body></html>"
        except Exception:
            _PROCORE_FLOWS.pop(flow_id, None)
            return "<html><body>Procore sign-in could not complete due to a temporary error. Close this window and try again.</body></html>"

        # Success: clean the one-time flow and return safe static HTML.
        _PROCORE_FLOWS.pop(flow_id, None)
        return "<html><body>Procore connected. You may return to the app.</body></html>"

    def poll_procore_auth_status(self, flow_id: str) -> dict[str, Any]:
        slot = _PROCORE_FLOWS.get(flow_id)
        if slot is None:
            # Completed flows are removed; treat missing as terminal (user may have completed via callback).
            # For explicit "not found" we can still say failed to avoid leaking existence, but for UX
            # after a known start we surface a generic terminal; callers that just connected via callback
            # will see status via procore_status() instead.
            return {
                "flow_id": flow_id,
                "status": "failed",
                "message": "No active Procore sign-in for this id (it may have completed via callback, expired, or been replaced).",
                "guardrails": _auth_guardrails(),
            }

        # Expiry
        try:
            started = datetime.fromisoformat(slot.get("started_at", "").replace("Z", "+00:00"))
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - started).total_seconds() > int(slot.get("expires_in", 600)) + 30:
                _PROCORE_FLOWS.pop(flow_id, None)
                return {
                    "flow_id": flow_id,
                    "status": "expired",
                    "message": "Procore sign-in window expired. Start again from the app.",
                    "guardrails": _auth_guardrails(),
                }
        except Exception:
            pass

        # If still present and not expired, it is pending (callback or manual exchange not yet performed).
        return {
            "flow_id": flow_id,
            "status": "pending",
            "message": "Waiting for Procore authorization to complete.",
            "guardrails": _auth_guardrails(),
        }

    def exchange_procore_oauth_code(self, code: str, normalized_path: bool = False) -> dict[str, Any]:
        """Manual fallback exchange. When called from normalized paths (normalized_path=True),
        the response omits any local cache_path for safety under the new contract.
        Legacy callers (root paths) continue to receive prior shape for compatibility.
        """
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
        result = {
            "ok": True,
            "kind": "procore_oauth_exchange",
            "access_cached": True,
            "refresh_cached": bool(getattr(token_set, "refresh_token", None)),
            "expires_in_seconds": token_set.expires_in_seconds(),
            "guardrails": _auth_guardrails(),
        }
        if not normalized_path:
            # Preserve legacy behavior for root paths.
            result["cache_path"] = str(cache_path)
        return result

    def disconnect_procore_local(self) -> dict[str, Any]:
        """Clear local Procore OAuth token cache only. Does not contact Procore."""
        try:
            from hb_assistant.procore.token_provider import clear_token_cache
            clear_token_cache()
        except Exception:
            # Best effort; observable effect is absence of cache on next status.
            pass
        return {
            "ok": True,
            "kind": "procore_disconnected_local",
            "message": "Procore local authentication cleared. Sign-in will be required to reconnect.",
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
        # Prompt B: ensure we attempt silent Graph refresh (via provider) before
        # classifying reauth_required or building required_actions. graph_status
        # already does a verify on cache_present paths; this makes it explicit at
        # the readiness entry point and re-samples so the map sees a possible promotion
        # from stale* to connected_valid.
        try:
            gcache = (graph.get("cache") or {}).get("msal-token-cache.bin") or {}
            if gcache.get("exists") or graph.get("cache_present"):
                p = self._graph_provider()
                p.get_token(force_refresh=False)
                graph = self.graph_status()
        except Exception:
            pass
        procore = self.procore_status()
        # Prompt C: attempt refresh for Procore (via the default provider chain which
        # includes RefreshingOAuthTokenProvider) when a cache is present. This ensures
        # we promote to connected_valid if a refresh succeeds, before deciding reauth_required.
        try:
            pcache = procore.get("cache_present") or (procore.get("access_cached") or procore.get("refresh_cached"))
            if pcache:
                from hb_assistant.procore.token_provider import default_procore_token_provider
                chain = default_procore_token_provider()
                # Force a token acquisition which will refresh via the chain if near expiry.
                # The call is safe (fail-closed inside the provider); it exercises the refresh path.
                for prov in getattr(chain, "providers", ()):
                    if hasattr(prov, "get_access_token"):
                        prov.get_access_token()
                        break
                procore = self.procore_status()
        except Exception:
            pass
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

        # Prompt G: replace the prior stub with unified computation from ConnectionSetupService
        # (approval stages + freshness from saved sources/identities). Falls back to simple
        # has_prior_setup heuristic only if no db_path or service unavailable.
        # The embedded shape stays identical so OnboardingReadinessResponse consumers are unaffected.
        dq_status = "unknown"
        dq_msg = "No approved source data has been collected yet."
        dq_last: str | None = None
        if db_path:
            try:
                from hb_assistant.construction.analytics.connection_setup import ConnectionSetupService  # noqa: I001

                dq = ConnectionSetupService(db_path=db_path).build_data_quality_summary()
                if isinstance(dq, dict):
                    dq_status = dq.get("status") or dq_status
                    dq_msg = dq.get("message") or dq_msg
                    dq_last = dq.get("last_updated_at")
            except Exception:
                # degrade conservatively; do not break readiness
                if has_prior_setup:
                    dq_status = "degraded"
                    dq_msg = "Sources are present; see Admin Data Confidence for details."
        elif has_prior_setup:
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
                "last_updated_at": dq_last,
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
                if before in {"connected_stale_refreshable", "connected_stale_reauth_required"}:
                    # Prompt B: attempt real silent refresh via provider before deciding final state.
                    try:
                        p = self._graph_provider()
                        p.get_token(force_refresh=False)
                        after = "connected_valid"
                    except Exception:
                        after = "connected_stale_reauth_required"
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
                if before in {"connected_stale_refreshable", "connected_stale_reauth_required"}:
                    # Prompt C: perform real refresh attempt via the provider before finalizing state.
                    try:
                        from hb_assistant.procore.token_provider import (
                            default_procore_token_provider,
                        )
                        chain = default_procore_token_provider()
                        for prov in getattr(chain, "providers", ()):
                            if hasattr(prov, "get_access_token"):
                                prov.get_access_token()
                                break
                        after = "connected_valid"
                    except Exception:
                        after = "connected_stale_reauth_required"
                results.append(
                    {
                        "source": "procore",
                        "before": before,
                        "after": after,
                        "reauth_required": after == "connected_stale_reauth_required",
                        "message": "Procore authentication refreshed." if after != before else "Procore authentication status checked.",
                    }
                )
        return {"results": results, "guardrails": _auth_guardrails(), "surface": "analytics.settings.connections.auth.refresh"}

    @staticmethod
    def _map_internal_to_auth_status(raw: dict[str, Any], source: str) -> str:
        """Map the existing internal status dicts to the 7 canonical states.
        Prompt B: uses verified/silent results from graph_status (which calls provider
        status_info/get_token) rather than file existence alone. Supports all 7 states.
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
            cls = str(raw.get("classification") or "").lower()
            if token_type in {"delegated"} and cache_present:
                return "connected_valid"
            if cache_present:
                if "stale_reauth" in cls or "reauth_required" in cls:
                    return "connected_stale_reauth_required"
                if "error" in cls:
                    return "connected_error"
                if token_type in {"cached_unverified"}:
                    # Unverified cache after silent attempt failed => reauth
                    return "connected_stale_reauth_required"
            # explicit disconnect path returns a kind on the action; subsequent status is never_connected
            # (disconnected_by_user can be observed from the action response if needed by callers)
            return "never_connected"
        if source == "procore":
            if raw.get("ready_for_live_calls") or (raw.get("cache_present") and raw.get("access_cached")):
                return "connected_valid"
            if raw.get("cache_present") and not raw.get("access_cached"):
                return "connected_stale_reauth_required"
            return "never_connected"
        return "never_connected"
