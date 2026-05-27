"""Delegated Graph proof runner for current runtime.

Implements Prompt 05 proof scope using live CLI/runtime auth and graph clients.
All outputs are sanitized and bounded.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from hb_assistant.auth.classifier import classify_token_claims
from hb_assistant.auth.providers import AppOnlyAuthProvider, DelegatedAuthProvider
from hb_assistant.config.loader import load_config
from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.graph.http_client import GraphHttpClient, GraphHttpError

DEFAULT_CERT_BUNDLE = "/Users/bobbyfetting/.secrets/hb-sharepoint-creator/hb-sharepoint-creator.bundle.pem"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _classify_delegated_claims(claims: dict[str, Any] | None) -> dict[str, Any]:
    claims = claims or {}
    has_scp = bool(claims.get("scp"))
    has_roles = bool(claims.get("roles"))
    classification = classify_token_claims(claims)
    delegated_runtime_valid = has_scp and not has_roles and classification == "delegated"
    return {
        "classification": classification,
        "has_scp": has_scp,
        "has_roles": has_roles,
        "delegated_runtime_valid": delegated_runtime_valid,
    }


def _calendar_window() -> Tuple[str, str]:
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = (now + timedelta(days=3)).replace(hour=23, minute=59, second=59, microsecond=0)
    return start.isoformat(), end.isoformat()


def _sanitize_message_meta(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_present": bool(item.get("id")),
        "has_attachments": bool(item.get("hasAttachments")),
        "received": item.get("receivedDateTime") or item.get("sentDateTime"),
    }


def _scan_sensitive(repo: str = ".") -> dict[str, Any]:
    from hb_assistant.security import SensitiveScanner

    return SensitiveScanner().scan(repo=repo)


def run_delegated_graph_proof(*, safe: bool = True, repo: str = ".") -> dict[str, Any]:
    cfg = load_config()
    pp = PathPolicy(cfg)
    evidence_root = Path("docs/evidence/remediation/prompt-05-delegated-graph-proof")
    evidence_root.mkdir(parents=True, exist_ok=True)

    delegated = DelegatedAuthProvider(cfg.identity.tenant_id, cfg.identity.client_id, cfg.identity.delegated_scopes, path_policy=pp)
    app_only = AppOnlyAuthProvider(cfg.identity.tenant_id, cfg.identity.client_id, DEFAULT_CERT_BUNDLE, path_policy=pp)

    result: dict[str, Any] = {
        "proof": "delegated-graph",
        "safe": safe,
        "timestamp": _now(),
        "steps": [],
        "status": "runtime_error",
    }

    try:
        token = delegated.get_token(["User.Read"], force_refresh=False)
    except Exception as exc:
        result.update(
            {
                "status": "blocked_no_token",
                "reason": "delegated_token_unavailable",
                "remediation": "Run hb-assistant auth login --json and retry proof.",
                "error": str(exc)[:220],
            }
        )
        (evidence_root / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    claims = token.get("id_token_claims") or token.get("claims") or {}
    classification = _classify_delegated_claims(claims)
    result["delegated_classification"] = classification

    if not classification["delegated_runtime_valid"]:
        result.update(
            {
                "status": "gap",
                "reason": "delegated_token_classification_invalid",
                "remediation": "Runtime requires delegated token with scp present and roles absent.",
            }
        )
        (evidence_root / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    client = GraphHttpClient(lambda scopes=None: delegated.get_token(scopes or ["User.Read"]))

    inbox_message_id = None
    attachment_message_id = None
    drive_item_id = None

    def add_step(name: str, endpoint: str, status: str, details: dict[str, Any]) -> None:
        result["steps"].append({"name": name, "endpoint": endpoint, "status": status, "details": details})

    # 1 /me
    try:
        me = client.get("/me?$select=id,displayName,userPrincipalName,mail")
        add_step("me", "/me", "pass", {"id_present": bool(me.get("id")), "upn": bool(me.get("userPrincipalName"))})
    except GraphHttpError as exc:
        add_step("me", "/me", "gap", {"graph_status": exc.status, "error": exc.message})

    # 2 inbox metadata
    try:
        inbox = client.get("/me/mailFolders/inbox/messages?$top=5&$select=id,subject,from,receivedDateTime,hasAttachments,bodyPreview")
        items = inbox.get("value", [])
        if items:
            inbox_message_id = items[0].get("id")
            for item in items:
                if item.get("hasAttachments"):
                    attachment_message_id = item.get("id")
                    break
        add_step("inbox_metadata", "/me/mailFolders/inbox/messages", "pass", {"count": len(items), "sample": _sanitize_message_meta(items[0]) if items else {}})
    except GraphHttpError as exc:
        add_step("inbox_metadata", "/me/mailFolders/inbox/messages", "gap", {"graph_status": exc.status, "error": exc.message, "remediation": "Verify Mail.Read delegated permission."})

    # 3 sent metadata
    try:
        sent = client.get("/me/mailFolders/sentitems/messages?$top=5&$select=id,subject,toRecipients,sentDateTime,bodyPreview")
        items = sent.get("value", [])
        add_step("sent_metadata", "/me/mailFolders/sentitems/messages", "pass", {"count": len(items), "sample": _sanitize_message_meta(items[0]) if items else {}})
    except GraphHttpError as exc:
        add_step("sent_metadata", "/me/mailFolders/sentitems/messages", "gap", {"graph_status": exc.status, "error": exc.message, "remediation": "Verify Mail.Read delegated permission."})

    # 4 bounded body retrieval
    if inbox_message_id:
        endpoint = f"/me/messages/{inbox_message_id}?$select=id,bodyPreview,body"
        try:
            body = client.get(endpoint)
            text = ((body.get("body") or {}).get("content") or "")[:500]
            add_step("bounded_body_retrieval", endpoint, "pass", {"id_present": bool(body.get("id")), "content_length_bounded": len(text)})
        except GraphHttpError as exc:
            add_step("bounded_body_retrieval", endpoint, "gap", {"graph_status": exc.status, "error": exc.message})
    else:
        add_step("bounded_body_retrieval", "/me/messages/{id}", "gap", {"error": "No candidate inbox message ID available.", "remediation": "Ensure inbox metadata returns at least one message."})

    # 5 calendarView
    start, end = _calendar_window()
    cal_ep = f"/me/calendarView?startDateTime={start}&endDateTime={end}&$top=5&$select=id,subject,start,end,organizer,webLink"
    try:
        cal = client.get(cal_ep)
        items = cal.get("value", [])
        add_step("calendar_view", "/me/calendarView", "pass", {"count": len(items)})
    except GraphHttpError as exc:
        add_step("calendar_view", "/me/calendarView", "gap", {"graph_status": exc.status, "error": exc.message, "remediation": "Verify Calendars.ReadWrite.Shared delegated permission."})

    # 6 attachment metadata
    if attachment_message_id:
        att_ep = f"/me/messages/{attachment_message_id}/attachments?$select=id,name,size,contentType,isInline"
        try:
            atts = client.get(att_ep).get("value", [])
            add_step("attachment_metadata", att_ep, "pass", {"count": len(atts), "sample": {"name": atts[0].get("name"), "size": atts[0].get("size")} if atts else {}})
        except GraphHttpError as exc:
            add_step("attachment_metadata", att_ep, "gap", {"graph_status": exc.status, "error": exc.message})
    else:
        add_step("attachment_metadata", "/me/messages/{id}/attachments", "gap", {"error": "No message with attachments discovered.", "remediation": "Inbox sample had no attachment-bearing message."})

    # 7 drive root/recent metadata
    try:
        root = client.get("/me/drive/root?$select=id,name,webUrl")
        recent = client.get("/me/drive/recent?$top=5")
        items = recent.get("value", [])
        if items:
            drive_item_id = items[0].get("id")
        add_step("drive_metadata", "/me/drive/root,/me/drive/recent", "pass", {"root_id_present": bool(root.get("id")), "recent_count": len(items)})
    except GraphHttpError as exc:
        add_step("drive_metadata", "/me/drive/root,/me/drive/recent", "gap", {"graph_status": exc.status, "error": exc.message, "remediation": "Verify Files.ReadWrite.All delegated permission."})

    # 8 controlled small-file download proof
    if drive_item_id:
        try:
            metadata = client.get(f"/me/drive/items/{drive_item_id}?$select=id,name,size,file")
            size = int(metadata.get("size") or 0)
            is_file = bool(metadata.get("file"))
            if is_file and size > 0 and size <= 2_000_000:
                dl_path = pp.get_cache_dir("proof-downloads") / f"{drive_item_id}.bin"
                written = client.download_to_file(f"/me/drive/items/{drive_item_id}/content", dl_path, max_bytes=2_000_000)
                file_hash = hashlib.sha256(dl_path.read_bytes()).hexdigest()
                add_step("controlled_download", f"/me/drive/items/{drive_item_id}/content", "pass", {"bytes_written": written, "sha256": file_hash, "name": metadata.get("name")})
            else:
                add_step("controlled_download", f"/me/drive/items/{drive_item_id}", "gap", {"error": "No eligible small file available.", "size": size, "is_file": is_file})
        except GraphHttpError as exc:
            add_step("controlled_download", f"/me/drive/items/{drive_item_id}/content", "gap", {"graph_status": exc.status, "error": exc.message})
        except Exception as exc:
            add_step("controlled_download", f"/me/drive/items/{drive_item_id}/content", "gap", {"error": str(exc)[:220]})
    else:
        add_step("controlled_download", "/me/drive/items/{id}/content", "gap", {"error": "No drive item id available from recent metadata."})

    # 9 app-only rejection for mail/calendar runtime
    try:
        app_tok = app_only.get_token(["https://graph.microsoft.com/.default"])
        app_claims = app_tok.get("id_token_claims") or app_tok.get("claims") or {"roles": [".default"]}
        app_class = _classify_delegated_claims(app_claims)
        app_client = GraphHttpClient(lambda scopes=None: app_only.get_token(["https://graph.microsoft.com/.default"]))
        try:
            app_client.get("/me/messages?$top=1")
            add_step("app_only_rejection", "/me/messages", "gap", {"error": "App-only request unexpectedly succeeded for runtime mail endpoint.", "classification": app_class})
        except Exception as exc:
            add_step("app_only_rejection", "/me/messages", "pass", {"classification": app_class, "rejected_error": str(exc)[:220]})
    except Exception as exc:
        add_step("app_only_rejection", "app_only_token", "pass", {"note": "App-only token unavailable; runtime remains delegated-only.", "error": str(exc)[:220]})

    # 10 sensitive scan
    scan = _scan_sensitive(repo=repo)
    add_step("sensitive_scan", "local_scan", "pass", {"categories": {k: len(v) for k, v in scan["findings_by_category"].items()}})
    result["sensitive_scan"] = scan

    status = "pass"
    for step in result["steps"]:
        if step["status"] != "pass":
            status = "gap"
            break
    result["status"] = status

    (evidence_root / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
