"""`hb-assistant graph` — read-only Microsoft Graph commands (Phase 06).

`graph mail status --json` is the first operational mail command: it reports
delegated-auth + mail-scope readiness, runs an in-process guard self-test against
the endpoint contract (proving every mutation verb/path is refused before HTTP),
and — unless `--no-probe` — issues one bounded read-only probe (`/me/mailFolders`)
through the guarded client. No tokens are ever emitted; the mailbox is never
mutated.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

import typer

from hb_assistant.auth.providers import DelegatedAuthProvider
from hb_assistant.config.loader import load_config
from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.email import (
    EmailFolderDiscovery,
    EmailMessageIndexer,
    ProjectEmailDiscovery,
    RelationshipCandidateBuilder,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.http_client import GraphHttpClient, GraphHttpError
from hb_assistant.graph.mail_endpoint_guard import (
    MailboxMutationBlockedError,
    MailEndpointContract,
    assert_mail_request_allowed,
    load_mail_endpoint_contract,
)
from hb_assistant.graph.mail_readonly_client import ReadOnlyMailClient

app = typer.Typer(help="Microsoft Graph read-only commands.")
mail_app = typer.Typer(help="Read-only Outlook/Exchange mail intelligence (Phase 06).")
app.add_typer(mail_app, name="mail")
body_app = typer.Typer(help="Controlled decrypt read for encrypted email bodies (local-only).")
mail_app.add_typer(body_app, name="body")

# Mail write scopes that must never be requested at runtime (mirrors the
# mutation-lockout regression set). Read-only Phase 06 requests Mail.Read only.
_FORBIDDEN_MAIL_SCOPES = (
    "Mail.ReadWrite.All",
    "Mail.ReadWrite",
    "Mail.ReadWrite.Shared",
    "Mail.Send",
    "Mail.Send.Shared",
)


def _sample_path(template: str) -> str:
    """Fill ``{placeholder}`` segments with a sample id for guard self-testing."""
    return "/".join(
        "SAMPLEID" if seg.startswith("{") and seg.endswith("}") else seg
        for seg in template.split("/")
    )


def _guard_self_test(contract: MailEndpointContract) -> Dict[str, Any]:
    """Prove, in-process and without network, that the guard allows every
    allowlisted GET and blocks every forbidden verb/path."""
    anomalies: List[str] = []
    read_allowed = 0
    mutation_blocked = 0

    for tmpl in contract.allowed_paths:
        try:
            assert_mail_request_allowed("GET", _sample_path(tmpl), contract=contract)
            read_allowed += 1
        except MailboxMutationBlockedError as e:
            anomalies.append(f"GET {tmpl} unexpectedly blocked: {e.reason}")

    for tmpl in contract.forbidden_paths:
        try:
            assert_mail_request_allowed("POST", _sample_path(tmpl), contract=contract)
            anomalies.append(f"POST {tmpl} unexpectedly allowed")
        except MailboxMutationBlockedError:
            mutation_blocked += 1

    for verb in sorted(contract.forbidden_methods):
        try:
            assert_mail_request_allowed(verb, "/me/messages/SAMPLEID", contract=contract)
            anomalies.append(f"{verb} on an allowlisted path unexpectedly allowed")
        except MailboxMutationBlockedError:
            mutation_blocked += 1

    return {
        "passed": not anomalies,
        "read_paths_allowed": read_allowed,
        "mutation_attempts_blocked": mutation_blocked,
        "anomalies": anomalies,
    }


def _mail_probe(provider: DelegatedAuthProvider, contract: MailEndpointContract) -> Dict[str, Any]:
    """One bounded, read-only probe (`/me/mailFolders`) through the guarded client."""
    def token_getter(scopes: Optional[List[str]] = None) -> Dict[str, Any]:
        return provider.get_token(scopes or ["Mail.Read"])

    client: Optional[GraphHttpClient] = None
    try:
        client = GraphHttpClient(token_getter)
        reader = ReadOnlyMailClient(client, contract=contract)
        folders = reader.list_mail_folders(top=1, max_items=1)
        return {
            "attempted": True,
            "path": "/me/mailFolders",
            "status": 200,
            "folder_sample_count": len(folders),
        }
    except GraphHttpError as e:
        return {"attempted": True, "path": "/me/mailFolders", "status": e.status, "error": e.message[:150]}
    except MailboxMutationBlockedError as e:  # pragma: no cover - read path is allowlisted
        return {"attempted": True, "path": e.path, "status": "blocked", "error": e.reason}
    except Exception as e:
        return {"attempted": True, "path": "/me/mailFolders", "error": str(e)[:150]}
    finally:
        if client is not None:
            client.close()


@mail_app.command("status")
def status_cmd(
    json_out: bool = typer.Option(False, "--json", help="Output JSON"),
    probe: bool = typer.Option(True, "--probe/--no-probe", help="Issue one bounded read-only Graph probe"),
) -> None:
    """Report mail read-only readiness: auth, scopes, endpoint-guard, and a bounded probe."""
    try:
        cfg = load_config()
        pp = PathPolicy(cfg)
        configured = list(cfg.identity.delegated_scopes)
        provider = DelegatedAuthProvider(
            cfg.identity.tenant_id, cfg.identity.client_id, configured, path_policy=pp
        )
        contract = load_mail_endpoint_contract()

        mail_read_present = any(s.lower() == "mail.read" for s in configured)
        forbidden_present = [
            s for s in configured if s.lower() in {x.lower() for x in _FORBIDDEN_MAIL_SCOPES}
        ]

        auth_info = provider.status_info()  # safe: no tokens, redacted claims
        guard = _guard_self_test(contract)
        mail_probe = _mail_probe(provider, contract) if probe else {"attempted": False}

        guardrails = {
            "mailbox_read_only": True,
            "mutation_endpoints_blocked": guard["passed"],
            "no_mail_write_scopes_requested": not forbidden_present,
            "metadata_only_select": "body" not in contract.message_metadata_select,
            "attachment_content_excluded": "contentBytes" not in contract.attachment_metadata_select,
        }
        ok = bool(mail_read_present and guardrails["no_mail_write_scopes_requested"] and guard["passed"])

        payload: Dict[str, Any] = {
            "command": "graph mail status",
            "ok": ok,
            "mail_read_scope_present": mail_read_present,
            "forbidden_mail_scopes_requested": forbidden_present,
            "auth": auth_info,
            "guard_self_test": guard,
            "mail_probe": mail_probe,
            "guardrails": guardrails,
            "contract": {
                "allowed_methods": sorted(contract.allowed_methods),
                "allowed_paths_count": len(contract.allowed_paths),
                "forbidden_methods": sorted(contract.forbidden_methods),
                "forbidden_paths_count": len(contract.forbidden_paths),
            },
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0 if ok else 1)
    except typer.Exit:
        raise
    except Exception as e:  # pragma: no cover - defensive envelope
        payload = {"command": "graph mail status", "ok": False, "status": "status_error", "error": str(e)[:200]}
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1) from None


@mail_app.command("folders")
def folders_cmd(
    json_out: bool = typer.Option(False, "--json", help="Output JSON"),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="Preview without persisting (default); --no-dry-run writes source/sync rows",
    ),
) -> None:
    """Discover Inbox / Sent Items / Archive (excluding Deleted Items / Junk Email / Drafts).

    Resolves the policy folder registry against the live mailbox (read-only) and,
    unless --dry-run, persists email_source_locations + email_sync_state.
    """
    client: Optional[GraphHttpClient] = None
    try:
        cfg = load_config()
        pp = PathPolicy(cfg)
        provider = DelegatedAuthProvider(
            cfg.identity.tenant_id,
            cfg.identity.client_id,
            list(cfg.identity.delegated_scopes),
            path_policy=pp,
        )
        contract = load_mail_endpoint_contract()

        def token_getter(scopes: Optional[List[str]] = None) -> Dict[str, Any]:
            return provider.get_token(scopes or ["Mail.Read"])

        client = GraphHttpClient(token_getter)
        reader = ReadOnlyMailClient(client, contract=contract)
        discovery = EmailFolderDiscovery(reader, ConstructionStore())
        result = discovery.discover(dry_run=dry_run)

        payload: Dict[str, Any] = {"command": "graph mail folders", "ok": True, **result.model_dump()}
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0)
    except typer.Exit:
        raise
    except Exception as e:
        payload = {
            "command": "graph mail folders",
            "ok": False,
            "dry_run": dry_run,
            "status": "folders_error",
            "error": str(e)[:200],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1) from None
    finally:
        if client is not None:
            client.close()


@mail_app.command("index")
def index_cmd(
    project: Optional[str] = typer.Option(None, "--project", help="Project key label for this crawl run"),
    lookback_days: int = typer.Option(30, "--lookback-days", help="Bounded lookback window in days (1-366)"),
    max_messages: int = typer.Option(200, "--max-messages", help="Max messages indexed per folder (bounded)"),
    include_encrypted_body: bool = typer.Option(
        False,
        "--include-encrypted-body",
        help="Also capture full bodies ENCRYPTED at rest (policy-gated; no plaintext persisted)",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run/--no-dry-run", help="Preview without writing message rows (default: persist)"
    ),
    json_out: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Index bounded message metadata (no full body) into local SQLite, read-only.

    Discovers messages in the included folders within the lookback window, normalizes
    redacted metadata, and persists email_messages + recipients + attachment metadata
    + crawl runs + receipts. Idempotent: re-running upserts in place.
    """
    client: Optional[GraphHttpClient] = None
    try:
        cfg = load_config()
        pp = PathPolicy(cfg)
        provider = DelegatedAuthProvider(
            cfg.identity.tenant_id,
            cfg.identity.client_id,
            list(cfg.identity.delegated_scopes),
            path_policy=pp,
        )
        contract = load_mail_endpoint_contract()

        def token_getter(scopes: Optional[List[str]] = None) -> Dict[str, Any]:
            return provider.get_token(scopes or ["Mail.Read"])

        client = GraphHttpClient(token_getter)
        reader = ReadOnlyMailClient(client, contract=contract)
        indexer = EmailMessageIndexer(reader, ConstructionStore())
        result = indexer.index(
            project_key=project,
            lookback_days=lookback_days,
            dry_run=dry_run,
            max_messages_per_folder=max_messages,
            include_encrypted_body=include_encrypted_body,
        )

        payload: Dict[str, Any] = {"command": "graph mail index", "ok": True, **result.model_dump()}
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0)
    except typer.Exit:
        raise
    except Exception as e:
        payload = {
            "command": "graph mail index",
            "ok": False,
            "dry_run": dry_run,
            "status": "index_error",
            "error": str(e)[:200],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1) from None
    finally:
        if client is not None:
            client.close()


@mail_app.command("discover")
def discover_cmd(
    project: Optional[str] = typer.Option(None, "--project", help="Pilot project key (omit to match all pilot projects)"),
    lookback_days: int = typer.Option(30, "--lookback-days", help="Bounded lookback window in days (1-366)"),
    max_messages: int = typer.Option(200, "--max-messages", help="Max messages scanned per folder (bounded)"),
    dry_run: bool = typer.Option(
        True, "--dry-run/--no-dry-run", help="Preview matches without persisting (default); --no-dry-run writes matches"
    ),
    json_out: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Project-aware discovery: match the bounded message window to pilot projects, read-only.

    Subject/bodyPreview are matched in-memory (never persisted raw). --dry-run previews;
    --no-dry-run persists email_project_matches + the message project verdict.
    """
    client: Optional[GraphHttpClient] = None
    try:
        cfg = load_config()
        pp = PathPolicy(cfg)
        provider = DelegatedAuthProvider(
            cfg.identity.tenant_id,
            cfg.identity.client_id,
            list(cfg.identity.delegated_scopes),
            path_policy=pp,
        )
        contract = load_mail_endpoint_contract()

        def token_getter(scopes: Optional[List[str]] = None) -> Dict[str, Any]:
            return provider.get_token(scopes or ["Mail.Read"])

        client = GraphHttpClient(token_getter)
        reader = ReadOnlyMailClient(client, contract=contract)
        discovery = ProjectEmailDiscovery(reader, ConstructionStore())
        report = discovery.discover(
            project_key=project,
            lookback_days=lookback_days,
            dry_run=dry_run,
            max_messages_per_folder=max_messages,
        )

        payload: Dict[str, Any] = {"command": "graph mail discover", "ok": True, **report.model_dump()}
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0)
    except typer.Exit:
        raise
    except Exception as e:
        payload = {
            "command": "graph mail discover",
            "ok": False,
            "dry_run": dry_run,
            "status": "discover_error",
            "error": str(e)[:200],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1) from None
    finally:
        if client is not None:
            client.close()


@mail_app.command("relationships")
def relationships_cmd(
    project: Optional[str] = typer.Option(None, "--project", help="Pilot project key"),
    lookback_days: int = typer.Option(30, "--lookback-days", help="Bounded lookback window in days (1-366)"),
    dry_run: bool = typer.Option(
        False, "--dry-run/--no-dry-run", help="Preview without persisting (default: persist candidates)"
    ),
    json_out: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Generate email relationship candidates (project, Procore, files, meetings), local-only.

    Reads stored email intelligence + the repo's Procore/calendar/drive data — NO Graph
    call, NO mailbox access. Candidates are NOT determinations: each carries confidence,
    review-required, and redacted evidence. The only writes are local SQLite candidate rows.
    """
    try:
        builder = RelationshipCandidateBuilder(ConstructionStore())
        report = builder.build(project_key=project, lookback_days=lookback_days, dry_run=dry_run)
        payload: Dict[str, Any] = {"command": "graph mail relationships", "ok": True, **report.model_dump()}
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0)
    except typer.Exit:
        raise
    except Exception as e:
        payload = {
            "command": "graph mail relationships",
            "ok": False,
            "dry_run": dry_run,
            "status": "relationships_error",
            "error": str(e)[:200],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1) from None


@body_app.command("show")
def body_show_cmd(
    message_id: str = typer.Option(..., "--message-id", help="Indexed message id whose encrypted body to read"),
    reason: str = typer.Option(..., "--reason", help="Operator reason for the decrypt (audited locally)"),
    show_plaintext: bool = typer.Option(
        False, "--show-plaintext", help="Print the decrypted body to THIS terminal only (never to disk/log/evidence)"
    ),
    json_out: bool = typer.Option(False, "--json", help="Output JSON (redacted summary; never plaintext)"),
) -> None:
    """Controlled, local-only read of an encrypted email body (no Graph call).

    Default output is a redacted summary (length, hash prefix, content type,
    sensitivity, review flag) — never plaintext. --show-plaintext decrypts to this
    terminal only. Every invocation records a local audit receipt (no plaintext).
    """
    from hb_assistant.security.text_vault import decrypt_text

    try:
        store = ConstructionStore()
        record = store.get_email_body_vault_ref(message_id)
        if record is None:
            payload = {"command": "graph mail body show", "ok": True, "found": False, "message_id": message_id}
            typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
            raise typer.Exit(0)

        ref = record["encrypted_full_body_ref"]
        plaintext_emitted = False
        plaintext: Optional[str] = None
        if show_plaintext:
            plaintext = decrypt_text(ref)
            plaintext_emitted = plaintext is not None

        # Local audit receipt — reason + length only, never plaintext.
        store.insert_email_processing_receipt(
            receipt_id=f"{message_id}:body_decrypt_read:{hashlib.sha256(reason.encode('utf-8')).hexdigest()[:12]}",
            operation="body_decrypt_read",
            status="ok",
            message_id=message_id,
            detail={
                "reason": reason,
                "body_length": record["body_length"],
                "plaintext_emitted": plaintext_emitted,
            },
        )

        summary: Dict[str, Any] = {
            "command": "graph mail body show",
            "ok": True,
            "found": True,
            "message_id": message_id,
            "reason": reason,
            "encrypted_full_body_ref_present": bool(ref),
            "body_hash_prefix": (record["body_hash"] or "")[:12],
            "body_length": record["body_length"],
            "body_content_type": record["body_content_type"],
            "sensitivity_classification": record["sensitivity_classification"],
            "review_required": record["review_required"],
            "plaintext_persisted": False,
            "encryption_method": record["encryption_method"],
        }
        typer.echo(json.dumps(summary, indent=2) if json_out else str(summary))
        if show_plaintext and plaintext is not None:
            # Plaintext to THIS terminal only; never captured in JSON/evidence/logs.
            typer.echo("\n----- decrypted body (terminal only; not persisted) -----")
            typer.echo(plaintext)
        raise typer.Exit(0)
    except typer.Exit:
        raise
    except Exception as e:
        payload = {"command": "graph mail body show", "ok": False, "status": "body_show_error", "error": str(e)[:200]}
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1) from None
