"""`hb-assistant graph` — read-only Microsoft Graph commands (Phase 06).

`graph mail status --json` is the first operational mail command: it reports
delegated-auth + mail-scope readiness, runs an in-process guard self-test against
the endpoint contract (proving every mutation verb/path is refused before HTTP),
and — unless `--no-probe` — issues one bounded read-only probe (`/me/mailFolders`)
through the guarded client. No tokens are ever emitted; the mailbox is never
mutated.
"""

from __future__ import annotations

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
