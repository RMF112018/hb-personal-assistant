"""Auth providers (delegated primary + app-only proof) using MSAL.

Phase 2: login/status/logout/clear-cache. No mutation of M365.
All status output is safe (no tokens, keys, or full bodies).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import msal  # type: ignore

from hb_assistant.config.path_policy import PathPolicy

from .classifier import classify_token_claims, require_delegated, safe_redact_claims
from .exceptions import AuthError, CertificateError, NoTokenError
from .scope_policy import get_scope_diagnostics, sanitize_delegated_scopes
from .token_cache_manager import TokenCacheManager


def _decode_jwt_payload_unverified(token: str) -> Dict[str, Any]:
    """Decode a JWT's payload segment without verifying the signature.

    Used solely to backfill claim fields (scp, upn, tid, oid) that MSAL's
    ``acquire_token_silent`` strips. The token's authenticity has already
    been established by MSAL acquiring it from the IdP; this helper does
    not re-validate it, it only inspects it. Returns an empty dict on any
    parse failure (fail-closed downstream when the classifier sees no
    ``scp``/``roles``).
    """
    import base64
    import json

    try:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        payload_b64 = parts[1]
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        claims = json.loads(decoded)
        return claims if isinstance(claims, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _ensure_delegated_id_token_claims(result: Dict[str, Any], account: Dict[str, Any]) -> Dict[str, Any]:
    """Backfill `id_token_claims` on a silent-acquisition result.

    MSAL's ``acquire_token_silent`` returns the cached access token but only
    re-issues ``id_token_claims`` on the original login flow. Downstream
    code (`require_delegated`, `classify_token_claims`) relies on the
    presence of ``scp`` in the claims dict to confirm the token is
    delegated; without it, the request path raises ClassificationError
    even though the access token itself is valid.

    Strategy: decode the access-token JWT payload (delegated Graph tokens
    are JWTs and carry their own ``scp``/``upn``/``tid``/``oid``). Fall
    back to the cached account record's ``username`` and the tenant id
    extracted from ``home_account_id`` only for the few fields the JWT
    might omit. This preserves the fail-closed posture: if neither the
    JWT nor the account yield ``scp``/``roles``, the classifier still
    rejects as ``invalid``.
    """
    existing = result.get("id_token_claims") or {}
    if existing.get("scp") or existing.get("roles"):
        return result

    synthesized: Dict[str, Any] = dict(existing)

    access_token = result.get("access_token")
    if isinstance(access_token, str):
        jwt_claims = _decode_jwt_payload_unverified(access_token)
        for key in ("scp", "roles", "upn", "preferred_username", "tid", "oid", "appid", "azp", "aud", "iss", "exp", "iat", "name"):
            if key in jwt_claims and key not in synthesized:
                synthesized[key] = jwt_claims[key]

    username = account.get("username") if account else None
    if username and "upn" not in synthesized:
        synthesized["upn"] = username
        synthesized.setdefault("preferred_username", username)

    home_account_id = account.get("home_account_id") if account else None
    if isinstance(home_account_id, str) and "." in home_account_id and "tid" not in synthesized:
        synthesized["tid"] = home_account_id.split(".", 1)[1]

    if synthesized:
        result = {**result, "id_token_claims": synthesized}
    return result


class _BaseProvider:
    def __init__(self, path_policy: Optional[PathPolicy] = None) -> None:
        self._pp = path_policy or PathPolicy()
        self._cache_mgr = TokenCacheManager(self._pp)

    def _get_auth_dir(self) -> Path:
        return self._pp.get_auth_dir()


class DelegatedAuthProvider(_BaseProvider):
    """Delegated (user) auth using MSAL PublicClientApplication + device/interactive."""

    def __init__(self, tenant_id: str, client_id: str, scopes: List[str], path_policy: Optional[PathPolicy] = None) -> None:
        super().__init__(path_policy)
        self.tenant_id = tenant_id
        self.client_id = client_id
        raw = scopes or ["User.Read", "offline_access"]
        self._configured_scopes: List[str] = list(raw)
        self.default_scopes: List[str] = sanitize_delegated_scopes(raw)
        self._app: Optional[msal.PublicClientApplication] = None

    def _get_app(self) -> msal.PublicClientApplication:
        if self._app is None:
            authority = f"https://login.microsoftonline.com/{self.tenant_id}"
            cache = self._cache_mgr.load_cache(app_only=False)
            self._app = msal.PublicClientApplication(
                client_id=self.client_id,
                authority=authority,
                token_cache=cache,
            )
        return self._app

    def login(self, scopes: Optional[List[str]] = None, use_device_code: bool = True) -> Dict[str, Any]:
        """Interactive or device_code login. Persists to delegated cache."""
        app = self._get_app()
        raw_scopes = scopes or self._configured_scopes
        scopes = sanitize_delegated_scopes(raw_scopes)

        # Try silent first (existing account)
        accounts = app.get_accounts()
        if accounts:
            result = app.acquire_token_silent(scopes, account=accounts[0])
            if result and "access_token" in result:
                self._cache_mgr.save_cache(app.token_cache, app_only=False)
                return {"status": "silent", "account": accounts[0].get("username"), **get_scope_diagnostics(raw_scopes)}

        # Fresh login
        if use_device_code:
            flow = app.initiate_device_flow(scopes=scopes)
            if "user_code" not in flow:
                raise AuthError("Device flow initiation failed")
            print(f"\n[auth] Go to {flow['verification_uri']} and enter code: {flow['user_code']}\n")
            result = app.acquire_token_by_device_flow(flow)
        else:
            # Fallback (may open browser)
            result = app.acquire_token_interactive(scopes=scopes)

        if not result or "access_token" not in result:
            raise AuthError(f"Login failed: {result.get('error_description', result) if result else 'no result'}")

        self._cache_mgr.save_cache(app.token_cache, app_only=False)
        return {"status": "success", "account": result.get("id_token_claims", {}).get("upn") or result.get("id_token_claims", {}).get("preferred_username"), **get_scope_diagnostics(raw_scopes)}

    def get_token(self, scopes: Optional[List[str]] = None, force_refresh: bool = False) -> Dict[str, Any]:
        app = self._get_app()
        raw_scopes = scopes or self._configured_scopes
        scopes = sanitize_delegated_scopes(raw_scopes)
        accounts = app.get_accounts()
        if not accounts:
            raise NoTokenError("No delegated account in cache. Run `hb-assistant auth login` first.")

        result = app.acquire_token_silent(scopes, account=accounts[0], force_refresh=force_refresh)
        if not result or "access_token" not in result:
            raise NoTokenError("Failed to acquire delegated token (expired or revoked). Re-login required.")

        result = _ensure_delegated_id_token_claims(result, accounts[0])
        self._cache_mgr.save_cache(app.token_cache, app_only=False)
        return {**result, **get_scope_diagnostics(raw_scopes)}

    def logout(self) -> List[str]:
        app = self._get_app()
        deleted = self._cache_mgr.clear_cache(app_only=False)
        for acct in app.get_accounts():
            app.remove_account(acct)
        return deleted

    def status_info(self) -> Dict[str, Any]:
        cache_info = self._cache_mgr.check_permissions()
        diag = get_scope_diagnostics(self._configured_scopes)
        try:
            result = self.get_token(["User.Read"], force_refresh=False)
            claims = result.get("id_token_claims") or result.get("claims") or {}
            ttype = classify_token_claims(claims)
            return {
                "token_type": ttype,
                "classification": "delegated" if ttype == "delegated" else "unexpected",
                "upn": claims.get("upn") or claims.get("preferred_username"),
                "tenant": claims.get("tid"),
                "scopes": result.get("scope", "").split() if result.get("scope") else [],
                "expires_in": result.get("expires_in"),
                "cache": cache_info,
                "safe_claims": safe_redact_claims(claims),
                **diag,  # configured_scopes, effective_msal_scopes, removed_reserved_scopes
            }
        except NoTokenError:
            return {"token_type": "none", "message": "No delegated token. Run login.", "cache": cache_info, **diag}


class AppOnlyAuthProvider(_BaseProvider):
    """App-only (certificate) auth for proof/admin only. Never used for mail/calendar runtime."""

    def __init__(self, tenant_id: str, client_id: str, cert_path: Optional[str], path_policy: Optional[PathPolicy] = None) -> None:
        super().__init__(path_policy)
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.cert_path = Path(cert_path).expanduser() if cert_path else None
        self._app: Optional[msal.ConfidentialClientApplication] = None

    def _get_app(self) -> msal.ConfidentialClientApplication:
        if self._app is None:
            if not self.cert_path or not self.cert_path.exists():
                raise CertificateError(f"Certificate bundle not found at {self.cert_path}")
            authority = f"https://login.microsoftonline.com/{self.tenant_id}"
            cache = self._cache_mgr.load_cache(app_only=True)
            self._app = msal.ConfidentialClientApplication(
                client_id=self.client_id,
                authority=authority,
                client_credential={
                    "private_key": self.cert_path.read_text(encoding="utf-8"),
                    # thumbprint and public cert optional for bundle; MSAL accepts full PEM for private_key in many cases
                },
                token_cache=cache,
            )
        return self._app

    def login(self, scopes: Optional[List[str]] = None) -> Dict[str, Any]:
        """Acquire app-only token via certificate (for proof flows only)."""
        app = self._get_app()
        scopes = scopes or [".default"]
        result = app.acquire_token_for_client(scopes=scopes)
        if not result or "access_token" not in result:
            raise AuthError(f"App-only login failed: {result}")
        self._cache_mgr.save_cache(app.token_cache, app_only=True)
        return {"status": "success", "token_type": "app_only"}

    def get_token(self, scopes: Optional[List[str]] = None, force_refresh: bool = False) -> Dict[str, Any]:
        app = self._get_app()
        scopes = scopes or [".default"]
        result = app.acquire_token_for_client(scopes=scopes)
        if not result or "access_token" not in result:
            raise NoTokenError("Failed to acquire app-only token via certificate.")
        self._cache_mgr.save_cache(app.token_cache, app_only=True)
        return result

    def logout(self) -> List[str]:
        return self._cache_mgr.clear_cache(app_only=True)

    def status_info(self) -> Dict[str, Any]:
        cache_info = self._cache_mgr.check_permissions()
        try:
            result = self.get_token(["https://graph.microsoft.com/.default"])
            claims = {}  # app-only tokens rarely have rich id claims in the result; we can decode if needed later
            return {
                "token_type": "app_only",
                "classification": "app_only",
                "tenant": self.tenant_id,
                "client_id": self.client_id,
                "scopes": result.get("scope", "").split() if result.get("scope") else [],
                "expires_in": result.get("expires_in"),
                "cache": cache_info,
                "note": "App-only token present (proof/admin only — not for mail/calendar runtime).",
            }
        except (NoTokenError, CertificateError) as e:
            return {"token_type": "none", "message": str(e), "cache": cache_info}
