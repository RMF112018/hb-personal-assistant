"""OAuth 2.1 route layer for the NAS MCP surface.

Reuses the proven authorization-server logic in ``obsidian_mcp.oauth_store`` (PKCE S256,
Dynamic Client Registration, code/token lifecycle, resource binding, discovery generators)
but owns a NAS-branded scope vocabulary and an ISOLATED token/code/client store under the
NAS audit dir. The obsidian ``:8000`` surface is untouched — coupling is via two
process-level env vars set by :func:`configure_process_oauth` before ``oauth_store`` is used.

Endpoints (mounted by ``server.py`` BEFORE the catch-all MCP ``Mount('/')``):
  GET  /.well-known/oauth-authorization-server   AS metadata (RFC 8414)
  GET  /.well-known/openid-configuration          AS metadata alias
  GET  /.well-known/oauth-protected-resource      Protected Resource Metadata (RFC 9728)
  GET  /.well-known/oauth-protected-resource/mcp  PRM (path-suffixed client probe)
  POST /oauth/register                            Dynamic Client Registration (RFC 7591)
  GET  /oauth/authorize                           consent page
  POST /oauth/authorize                           approve/deny -> authorization code
  POST /oauth/token                               PKCE code exchange -> access token

These endpoints run PRE-token and are origin-auth-exempt (server.py bypasses them in the
middleware). Resource-owner authentication for ``/oauth/authorize`` is supplied at the EDGE
by Cloudflare Access SSO (Bobby only) — the consent page itself has no login by design.
"""

from __future__ import annotations

import html as _html
import json
from typing import Any
from urllib.parse import urlsplit

from hb_assistant.obsidian_mcp import oauth_store

# NAS-branded scope vocabulary (advertised in discovery + accepted at DCR/authorize).
NAS_SUPPORTED_SCOPES = ("nas.read", "nas.write")
NAS_DEFAULT_SCOPE = "nas.read"
# Single-user policy: every registered client + every approved grant receives the FULL scope
# set (read AND write). The operator (Bobby) owns all clients and still approves each grant at
# the consent page; the one write tool stays folder-locked + rate-limited + receipted. A token
# lacking nas.write is still handled correctly downstream (denied the write tool) — this only
# governs what the NAS routes issue.
NAS_GRANTED_SCOPE = " ".join(NAS_SUPPORTED_SCOPES)


def configure_process_oauth(config: Any) -> None:
    """Point ``oauth_store`` at the NAS store dir + scope vocabulary for THIS process.

    Idempotent; call once at app build. Sets the two env vars ``oauth_store`` reads. The
    store lands under the NAS audit RW mount (``<audit_dir>/oauth``), isolated from the
    obsidian store and writable by the container runtime user.
    """
    import os  # noqa: PLC0415

    os.environ["HB_OAUTH_SUPPORTED_SCOPES"] = ",".join(NAS_SUPPORTED_SCOPES)
    os.environ.setdefault("HB_OAUTH_STORE_DIR", str(config.audit_dir / "oauth"))


def _error_html(error: str, description: str | None = None) -> str:
    detail = _html.escape(description or error)
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>HB NAS MCP — authorization error</title></head>"
        "<body style='font-family:system-ui;max-width:32rem;margin:3rem auto;padding:0 1rem'>"
        f"<h1 style='font-size:1.1rem'>Authorization error: {_html.escape(error)}</h1>"
        f"<p>{detail}</p></body></html>"
    )


def _consent_html(*, scopes: list[str], params: dict[str, str], base_url: str) -> str:
    hidden = "".join(
        f"<input type='hidden' name='{_html.escape(k)}' value='{_html.escape(v)}'>"
        for k, v in params.items()
        if k != "client_name"
    )
    scope_items = "".join(f"<li><code>{_html.escape(s)}</code></li>" for s in scopes)
    write_warning = (
        "<p style='border:1px solid #f59e0b;padding:.75rem'>This connection requests "
        "<code>nas.write</code>. The only write available on this surface is the "
        "folder-locked <em>AI Outputs</em> card writer; all other mutations stay blocked.</p>"
        if "nas.write" in scopes
        else ""
    )
    client_name = params.get("client_name") or params.get("client_id") or "MCP client"
    redirect_host = urlsplit(params.get("redirect_uri") or "").hostname or "unknown"
    resource = params.get("resource") or "not provided"
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>HB NAS MCP — authorize client</title></head>"
        "<body style='font-family:system-ui;max-width:34rem;margin:3rem auto;padding:0 1rem'>"
        f"<h1 style='font-size:1.15rem'>{_html.escape(client_name)} is requesting access to HB NAS MCP</h1>"
        "<p>Approve to let this remote MCP connector call the read-mostly NAS tools.</p>"
        "<p><strong>Requested scopes</strong></p>"
        f"<ul>{scope_items}</ul>{write_warning}"
        f"<p><strong>Redirect host:</strong> <code>{_html.escape(redirect_host)}</code></p>"
        f"<p><strong>MCP resource:</strong> <code>{_html.escape(resource)}</code></p>"
        f"<p><strong>Server:</strong> <code>{_html.escape(base_url)}</code></p>"
        "<form method='post' action='/oauth/authorize'>"
        f"{hidden}"
        "<button type='submit' name='decision' value='approve' "
        "style='padding:.5rem 1rem;font-size:1rem;margin-right:.5rem'>Approve</button>"
        "<button type='submit' name='decision' value='deny' "
        "style='padding:.5rem 1rem;font-size:1rem'>Deny</button>"
        "</form></body></html>"
    )


def build_oauth_routes(base_url: str) -> list[Any]:
    """Return the Starlette Routes for the OAuth surface, bound to ``base_url`` (the fixed
    public HTTPS origin — NOT derived from the request Host, to avoid Host-header spoofing)."""
    from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse  # noqa: PLC0415
    from starlette.routing import Route  # noqa: PLC0415

    resource = oauth_store.mcp_resource(base_url)

    async def as_metadata(_request: Any) -> Any:
        return JSONResponse(oauth_store.authorization_server_metadata(base_url))

    async def prm(_request: Any) -> Any:
        return JSONResponse(oauth_store.protected_resource_metadata(base_url))

    async def register(request: Any) -> Any:
        try:
            payload = json.loads((await request.body()) or b"{}")
        except (json.JSONDecodeError, ValueError):
            return JSONResponse(
                {"error": "invalid_client_metadata", "error_description": "JSON object required"}, status_code=400
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                {"error": "invalid_client_metadata", "error_description": "JSON object required"}, status_code=400
            )
        # Register every client for the full NAS scope set (single-user policy) so an approved
        # grant can request read + write regardless of what the client asked for at DCR.
        payload = {**payload, "scope": NAS_GRANTED_SCOPE}
        try:
            return JSONResponse(oauth_store.register_client(payload, default_scope=NAS_DEFAULT_SCOPE), status_code=201)
        except oauth_store.OAuthError as exc:
            return JSONResponse({"error": exc.error, "error_description": exc.description}, status_code=400)

    def _validated_scopes(source: Any) -> list[str]:
        return oauth_store.validate_authorize_request(
            response_type=source.get("response_type", ""),
            client_id=source.get("client_id", ""),
            redirect_uri=source.get("redirect_uri", ""),
            scope=source.get("scope", ""),
            code_challenge=source.get("code_challenge", ""),
            code_challenge_method=source.get("code_challenge_method", ""),
            resource=source.get("resource") or resource,
            base_url=base_url,
        )

    async def authorize(request: Any) -> Any:
        if request.method == "POST":
            form = await request.form()
            p = {k: str(v) for k, v in form.items()}
            p["scope"] = NAS_GRANTED_SCOPE  # grant the full NAS scope set (single-user policy)
            redirect_uri = p.get("redirect_uri", "")
            state = p.get("state", "")
            try:
                _validated_scopes(p)
            except oauth_store.OAuthError as exc:
                return HTMLResponse(_error_html(exc.error, exc.description), status_code=400)
            if p.get("decision", "approve") != "approve":
                return RedirectResponse(
                    oauth_store.redirect_with(redirect_uri, {"error": "access_denied", "state": state}),
                    status_code=302,
                )
            code = oauth_store.create_authorization_code(
                client_id=p.get("client_id", ""),
                redirect_uri=redirect_uri,
                scope=p.get("scope", ""),
                code_challenge=p.get("code_challenge", ""),
                code_challenge_method=p.get("code_challenge_method", ""),
                resource=p.get("resource") or resource,
                base_url=base_url,
            )
            return RedirectResponse(
                oauth_store.redirect_with(redirect_uri, {"code": code, "state": state}), status_code=302
            )
        # GET → consent page
        q = dict(request.query_params)
        q["scope"] = NAS_GRANTED_SCOPE  # consent shows + grants the full NAS scope set
        try:
            scopes = _validated_scopes(q)
        except oauth_store.OAuthError as exc:
            return HTMLResponse(_error_html(exc.error, exc.description), status_code=400)
        client = oauth_store.get_client(q.get("client_id", ""))
        params = {
            "response_type": q.get("response_type", ""),
            "client_id": q.get("client_id", ""),
            "client_name": (client.client_name if client else q.get("client_id", "")),
            "redirect_uri": q.get("redirect_uri", ""),
            "scope": q.get("scope", ""),
            "state": q.get("state", ""),
            "code_challenge": q.get("code_challenge", ""),
            "code_challenge_method": q.get("code_challenge_method", ""),
            "resource": q.get("resource") or resource,
        }
        return HTMLResponse(_consent_html(scopes=scopes, params=params, base_url=base_url))

    async def token(request: Any) -> Any:
        form = await request.form()
        p = {k: str(v) for k, v in form.items()}
        if p.get("grant_type", "") != "authorization_code":
            return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)
        try:
            scopes, client_id, tok_resource = oauth_store.consume_authorization_code(
                raw_code=p.get("code", ""),
                client_id=p.get("client_id", ""),
                redirect_uri=p.get("redirect_uri", ""),
                code_verifier=p.get("code_verifier", ""),
                resource=p.get("resource") or None,
                base_url=base_url,
            )
            issued = oauth_store.issue_access_token(scopes=scopes, client_id=client_id, resource=tok_resource)
        except oauth_store.OAuthError as exc:
            return JSONResponse({"error": exc.error, "error_description": exc.description}, status_code=400)
        return JSONResponse(issued)

    return [
        Route("/.well-known/oauth-authorization-server", as_metadata, methods=["GET"]),
        Route("/.well-known/openid-configuration", as_metadata, methods=["GET"]),
        Route("/.well-known/oauth-protected-resource", prm, methods=["GET"]),
        Route("/.well-known/oauth-protected-resource/mcp", prm, methods=["GET"]),
        Route("/oauth/register", register, methods=["POST"]),
        Route("/oauth/authorize", authorize, methods=["GET", "POST"]),
        Route("/oauth/token", token, methods=["POST"]),
    ]
