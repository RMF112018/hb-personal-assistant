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
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
from pydantic import ValidationError

from hb_assistant.auth.providers import DelegatedAuthProvider
from hb_assistant.config.loader import load_config
from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.classification.client import OllamaChatClient
from hb_assistant.construction.config import load_source_registry
from hb_assistant.construction.config.loader import SourceRegistryError
from hb_assistant.construction.email import (
    EmailFolderDiscovery,
    EmailIntelligenceClassifier,
    EmailMessageIndexer,
    EmailObsidianProjector,
    ProjectEmailDiscovery,
    RelationshipCandidateBuilder,
    ReviewRouter,
    run_operational_validation,
)
from hb_assistant.construction.email.email_classifier import DEFAULT_MODEL_NAME
from hb_assistant.construction.graph.baseline_crawler import BaselineCrawler
from hb_assistant.construction.graph.controlled_extraction import ControlledExtractor
from hb_assistant.construction.graph.delta_sync import DeltaSync
from hb_assistant.construction.graph.drive_item_indexer import DriveItemIndexer
from hb_assistant.construction.graph.file_obsidian_projection import FileObsidianProjector
from hb_assistant.construction.graph.file_project_matcher import FileProjectMatcher
from hb_assistant.construction.graph.file_retrieval import FileRetriever
from hb_assistant.construction.graph.file_review_router import FileReviewRouter
from hb_assistant.construction.graph.ingestion_eligibility import IngestionEligibilityEvaluator
from hb_assistant.construction.graph.link_resolver import LinkResolver
from hb_assistant.construction.graph.resolver import GRAPH_SCOPES as _FILES_GRAPH_SCOPES
from hb_assistant.construction.graph.site_drive_discovery import SiteDriveDiscovery
from hb_assistant.construction.policy import (
    ReviewPolicyEvaluator,
    ReviewRulesError,
    load_review_rules,
)
from hb_assistant.construction.policy.email_active import (
    load_email_intelligence_active_policy,
)
from hb_assistant.construction.source_projection import (
    project_registry_to_v5_source_locations,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.calendar_endpoint_guard import (
    CalendarEndpointContract,
    CalendarMutationBlockedError,
    load_calendar_endpoint_contract,
    run_calendar_no_writeback_self_test,
)
from hb_assistant.graph.calendar_readonly_client import ReadOnlyCalendarClient
from hb_assistant.graph.files_endpoint_guard import (
    load_files_endpoint_contract,
    run_files_no_writeback_self_test,
)
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
files_app = typer.Typer(
    help=(
        "Read-only SharePoint/OneDrive file intelligence (Phase 06A). "
        "DRY-RUN IS THE DEFAULT for every command that could write SQLite, a cache file, or an "
        "Obsidian note. Side effects require explicit opt-in flags: --apply (persist discovery "
        "receipts / driveItem index / sync state / ingestion decisions / review-queue rows / "
        "Obsidian notes), --download (controlled content fetch to a cache outside the repo+vault, "
        "deleted after parse), and --extract (bounded redacted parse; requires --download). "
        "Read-only against Microsoft 365: no upload, create, update, delete, relocate, duplicate, "
        "share, label, check-in/out, or permission change; no full document text, signed URLs, "
        "download URLs, or raw delta links are ever persisted. Broad Graph file permission tightening is deferred "
        "(documented risk). Start with `status`; end with `no-writeback-proof`."
    )
)
app.add_typer(files_app, name="files")
files_site_app = typer.Typer(help="SharePoint site resolution (read-only, metadata-only).")
files_app.add_typer(files_site_app, name="site")
files_link_app = typer.Typer(
    help="Resolve a user-provided OneDrive/SharePoint link to canonical IDs."
)
files_app.add_typer(files_link_app, name="link")
calendar_app = typer.Typer(
    help=(
        "Read-only Outlook/Exchange calendar intelligence (Phase 07B). "
        "Read-only against Microsoft 365: no event create/update/delete, attendee "
        "accept/decline/tentative response, organizer cancel, forward, or reminder "
        "change; no event body/description or online-meeting join URL is requested "
        "or persisted. The write-capable Calendars.ReadWrite.Shared scope is "
        "consented at the tenant; scope tightening is DEFERRED (documented residual "
        "risk) — the calendar endpoint guard enforces read-only regardless. Start "
        "with `status`."
    )
)
app.add_typer(calendar_app, name="calendar")

# Write-capable Graph file/site scopes whose presence is the known DEFERRED
# over-broad posture (documented, not tightened in this phase).
_BROAD_FILE_WRITE_SCOPES = (
    "Files.ReadWrite.All",
    "Files.ReadWrite",
    "Sites.ReadWrite.All",
    "Sites.Manage.All",
    "Sites.FullControl.All",
    "AllSites.FullControl",
)

# Source trees that issue (or will issue) Graph SharePoint/OneDrive reads. The
# no-writeback static scan asserts none contain a mutating HTTP verb call.
_FILE_SERVICE_DIRS = (
    "src/hb_assistant/graph",
    "src/hb_assistant/construction/graph",
    "src/hb_assistant/files",
)
_WRITE_VERB_CALL_RE = re.compile(r"\.(post|put|patch|delete)\s*\(")

# Mail write scopes that must never be requested at runtime (mirrors the
# mutation-lockout regression set). Read-only Phase 06 requests Mail.Read only.
_FORBIDDEN_MAIL_SCOPES = (
    "Mail.ReadWrite.All",
    "Mail.ReadWrite",
    "Mail.ReadWrite.Shared",
    "Mail.Send",
    "Mail.Send.Shared",
)

# Calendar scopes. Read-only Phase 07B needs read capability — Calendars.Read or
# the broader Calendars.ReadWrite.Shared (which also grants read). The write-
# capable scopes below are reported as a DEFERRED tightening posture (documented
# residual risk); the calendar endpoint guard enforces read-only regardless.
_WRITE_CAPABLE_CALENDAR_SCOPES = (
    "Calendars.ReadWrite",
    "Calendars.ReadWrite.Shared",
    "Calendars.ReadWrite.All",
)
_READ_CALENDAR_SCOPES = (
    "Calendars.Read",
    "Calendars.Read.Shared",
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
        return {
            "attempted": True,
            "path": "/me/mailFolders",
            "status": e.status,
            "error": e.message[:150],
        }
    except MailboxMutationBlockedError as e:  # pragma: no cover - read path is allowlisted
        return {"attempted": True, "path": e.path, "status": "blocked", "error": e.reason}
    except Exception as e:
        return {"attempted": True, "path": "/me/mailFolders", "error": str(e)[:150]}
    finally:
        if client is not None:
            client.close()


def _files_static_scan(repo_root: Path) -> Dict[str, Any]:
    """Scan the Graph file-service source trees for any mutating HTTP verb call.
    Expect zero — file access is read-only (GET/stream) by construction."""
    files_scanned = 0
    violations: List[str] = []
    for rel in _FILE_SERVICE_DIRS:
        base = repo_root / rel
        if not base.exists():
            continue
        for py in sorted(base.rglob("*.py")):
            files_scanned += 1
            for n, line in enumerate(py.read_text(encoding="utf-8").splitlines(), start=1):
                if _WRITE_VERB_CALL_RE.search(line):
                    violations.append(f"{py.relative_to(repo_root)}:{n}")
    return {
        "dirs_scanned": list(_FILE_SERVICE_DIRS),
        "files_scanned": files_scanned,
        "mutation_method_calls_found": len(violations),
        "violations": violations,
    }


def _calendar_probe(
    provider: DelegatedAuthProvider, contract: CalendarEndpointContract
) -> Dict[str, Any]:
    """One bounded, read-only probe (`/me/calendarView`) through the guarded client.

    Surfaces only an event *count* — never any subject, organizer, attendee,
    location, body, or join URL. Any failure (including no cached token) is
    non-fatal and reported as a readiness status.
    """

    def token_getter(scopes: Optional[List[str]] = None) -> Dict[str, Any]:
        return provider.get_token(scopes or ["Calendars.Read"])

    # Bounded, fixed window (no Date.now in evidence); read-only by construction.
    window_start = "2026-01-01T00:00:00Z"
    window_end = "2026-12-31T23:59:59Z"
    client: Optional[GraphHttpClient] = None
    try:
        client = GraphHttpClient(token_getter)
        reader = ReadOnlyCalendarClient(client, contract=contract)
        events = reader.list_calendar_view(
            start=window_start, end=window_end, top=1, max_items=1
        )
        return {
            "attempted": True,
            "path": "/me/calendarView",
            "status": 200,
            "event_sample_count": len(events),
        }
    except GraphHttpError as e:
        return {
            "attempted": True,
            "path": "/me/calendarView",
            "status": e.status,
            "error": e.message[:150],
        }
    except CalendarMutationBlockedError as e:  # pragma: no cover - read path is allowlisted
        return {"attempted": True, "path": e.path, "status": "blocked", "error": e.reason}
    except Exception as e:
        return {"attempted": True, "path": "/me/calendarView", "error": str(e)[:150]}
    finally:
        if client is not None:
            client.close()


def _files_auth_posture() -> Dict[str, Any]:
    """Best-effort, redacted permission posture (scope NAMES only, no tokens).
    Tolerant of an absent token cache so the proof stays deterministic/offline."""
    try:
        cfg = load_config()
        pp = PathPolicy(cfg)
        configured = list(cfg.identity.delegated_scopes)
        provider = DelegatedAuthProvider(
            cfg.identity.tenant_id, cfg.identity.client_id, configured, path_policy=pp
        )
        info = provider.status_info()  # safe: no tokens, redacted claims
        cached_scopes = info.get("scopes") or []
        broad = {b.lower() for b in _BROAD_FILE_WRITE_SCOPES}
        present = sorted({s for s in list(configured) + list(cached_scopes) if s.lower() in broad})
        return {
            "available": True,
            "token_type": info.get("token_type"),
            "classification": info.get("classification"),
            "configured_delegated_scopes": configured,
            "broad_file_write_scopes_present": present,
            "permission_tightening": "deferred",
        }
    except Exception as e:  # pragma: no cover - defensive; proof must not depend on auth
        return {"available": False, "error": str(e)[:150], "permission_tightening": "deferred"}


@files_app.command("no-writeback-proof")
def files_no_writeback_proof_cmd(
    json_out: bool = typer.Option(True, "--json", help="Output JSON (default)"),
) -> None:
    """Prove behavior-level no-writeback for SharePoint/OneDrive file access.

    Combines an in-process endpoint-guard self-test (every allowlisted GET
    permitted; every mutation verb/path refused before HTTP), a source static
    scan of the Graph file-service trees (zero mutating verb calls), and a
    contract summary. Offline and deterministic. Permission tightening remains
    deferred; no scopes are changed or inspected for write capability removal.
    """
    try:
        contract = load_files_endpoint_contract()
        guard = run_files_no_writeback_self_test(contract)
        repo_root = PathPolicy().resolve_repo_root()
        scan = _files_static_scan(repo_root)
        auth = _files_auth_posture()

        metadata_select_lower = {f.lower() for f in contract.drive_item_metadata_select}
        guardrails = {
            "microsoft_365_writeback": "none",
            "file_mutation_endpoints_blocked": guard["passed"],
            "no_mutation_method_calls_in_file_services": scan["mutation_method_calls_found"] == 0,
            "metadata_only_select": "content" not in metadata_select_lower,
            "download_url_never_persisted": any(
                "downloadurl" in n.lower() for n in contract.never_persist
            ),
            "permission_tightening": "deferred",
        }
        ok = bool(
            guard["passed"]
            and scan["mutation_method_calls_found"] == 0
            and guardrails["download_url_never_persisted"]
        )

        payload: Dict[str, Any] = {
            "command": "graph files no-writeback-proof",
            "ok": ok,
            "permission_tightening": "deferred",
            "auth": auth,
            "guard_self_test": guard,
            "static_scan": scan,
            "contract": {
                "allowed_methods": sorted(contract.allowed_methods),
                "allowed_paths_count": len(contract.allowed_paths),
                "forbidden_methods": sorted(contract.forbidden_methods),
                "forbidden_paths_count": len(contract.forbidden_paths),
                "forbidden_keywords_count": len(contract.forbidden_operation_keywords),
                "never_persist_count": len(contract.never_persist),
            },
            "guardrails": guardrails,
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0 if ok else 1)
    except typer.Exit:
        raise
    except Exception as e:  # pragma: no cover - defensive envelope
        payload = {
            "command": "graph files no-writeback-proof",
            "ok": False,
            "status": "proof_error",
            "error": str(e)[:200],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1) from None


@files_app.command("status")
def files_status_cmd(
    json_out: bool = typer.Option(True, "--json", help="Emit machine-readable JSON (default)."),
) -> None:
    """Operator status dashboard for the SharePoint/OneDrive file surface.

    Offline and read-only: reports the delegated-auth posture (scope NAMES only, no tokens; no
    interactive login — a live token is acquired only by --apply/--download workflows), source
    registry counts (by system, by resolution status, enabled), the V5 projection count, the open
    review-queue size, and the standing no-writeback / deferred-permission guardrails. Constructs no
    Graph client and writes nothing.
    """
    try:
        registry = load_source_registry()
    except (SourceRegistryError, ValidationError) as e:
        _echo_files_error("graph files status", e, json_out)
        return

    by_system: Dict[str, int] = {}
    by_resolution: Dict[str, int] = {}
    enabled = 0
    for src in registry.sources:
        system = "sharepoint" if str(src.kind).startswith("sharepoint") else "onedrive"
        by_system[system] = by_system.get(system, 0) + 1
        by_resolution[src.resolution_status] = by_resolution.get(src.resolution_status, 0) + 1
        if src.enabled:
            enabled += 1
    resolved = sum(
        n for s, n in by_resolution.items() if s in {"resolved", "graph_delta_ready"}
    )

    # Lightweight store reads only (no heavy V5 table scans); resilient to an empty store.
    projected_v5 = 0
    review_queue_open = 0
    try:
        store = ConstructionStore()
        projected_v5 = len(store.list_source_locations(limit=100000))
        review_queue_open = store.count_review_queue(status="open")
    except Exception as e:  # pragma: no cover - defensive; status must stay offline-safe
        store_error = str(e)[:150]
    else:
        store_error = None

    payload: Dict[str, Any] = {
        "command": "graph files status",
        "ok": True,
        "delegated_auth": {
            "mode": "delegated",
            "token_acquisition": "on_demand",
            "note": "Offline status; a live token is acquired only by --apply/--download workflows.",
            **_files_auth_posture(),
        },
        "sources": {
            "registry_total": len(registry.sources),
            "by_system": by_system,
            "enabled": enabled,
            "by_resolution_status": by_resolution,
            "resolved": resolved,
            "pending": len(registry.sources) - resolved,
            "projected_v5": projected_v5,
        },
        "operational": {
            "review_queue_open": review_queue_open,
            "store_error": store_error,
        },
        "guardrails": {
            "external_systems": "read_only",
            "writeback": "none",
            "graph_calls": "none",
            "microsoft_365_writeback_enabled": False,
            "dry_run_default": True,
            "permission_tightening": "deferred",
            "broad_consent_note": (
                "Files.ReadWrite.All consent retained at tenant; runtime read-only; "
                "tightening deferred (documented risk)."
            ),
        },
    }
    typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
    raise typer.Exit(0)


_DISCOVERY_GUARDRAILS = {
    "external_systems": "read_only",
    "writeback": "none",
    "metadata_only": True,
    "content_crawl": "none",
    "permission_tightening": "deferred",
}
_SHAREPOINT_SOURCE_KINDS = {
    "sharepoint_site",
    "sharepoint_library",
    "sharepoint_project_drive_folder",
    "sharepoint_site_page",
}


def _files_graph_client_or_auth(
    scopes: List[str],
) -> tuple[Optional[GraphHttpClient], Optional[Dict[str, Any]]]:
    """Build a delegated GraphHttpClient, or return a structured ``auth_required``
    payload when no cached token exists. Never triggers an interactive login."""
    try:
        cfg = load_config()
        pp = PathPolicy(cfg)
        provider = DelegatedAuthProvider(
            cfg.identity.tenant_id,
            cfg.identity.client_id,
            list(cfg.identity.delegated_scopes),
            path_policy=pp,
        )
        token = provider.get_token(scopes)
    except Exception as e:  # noqa: BLE001 — surface as structured payload
        return None, {
            "status": "auth_required",
            "scopes": scopes,
            "detail": str(e)[:200],
            "hint": "Run `hb-assistant auth login --json` interactively to obtain a delegated token.",
        }
    if "access_token" not in token:
        return None, {
            "status": "auth_required",
            "scopes": scopes,
            "detail": token.get("error_description")
            or token.get("error")
            or "no_access_token_in_cache",
            "hint": "Run `hb-assistant auth login --json` interactively to obtain a delegated token.",
        }

    def token_getter(s: Optional[List[str]] = None) -> Dict[str, Any]:
        return provider.get_token(s or scopes)

    return GraphHttpClient(token_getter), None


@files_app.command("sites")
def files_sites_cmd(
    source: Optional[str] = typer.Option(None, "--source", help="Resolve only this source key."),
    dry_run: bool = typer.Option(
        True, "--dry-run/--apply", help="Default dry-run; --apply persists discovery receipts."
    ),
    json_out: bool = typer.Option(True, "--json", help="Output JSON (default)."),
) -> None:
    """Resolve approved SharePoint sites (by URL or pre-seeded ID). Read-only,
    metadata-only; no content crawl. Dry-run by default."""
    try:
        registry = load_source_registry()
    except (SourceRegistryError, ValidationError) as e:
        _echo_files_error("graph files sites", e, json_out)
        return

    targets = [
        s
        for s in registry.sources
        if s.kind in _SHAREPOINT_SOURCE_KINDS and (source is None or s.source_key == source)
    ]
    if not targets:
        payload = {
            "command": "graph files sites",
            "status": "not_found",
            "requested": source,
            "available": [
                s.source_key for s in registry.sources if s.kind in _SHAREPOINT_SOURCE_KINDS
            ],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    client, auth_payload = _files_graph_client_or_auth(_FILES_GRAPH_SCOPES)
    if client is None:
        payload = {
            "command": "graph files sites",
            "mode": "dry_run" if dry_run else "apply",
            **auth_payload,
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0)

    try:
        store = ConstructionStore() if not dry_run else None
        discovery = SiteDriveDiscovery(client, store=store)
        results = [discovery.discover_site(s, apply=not dry_run) for s in targets]
    finally:
        client.close()

    rows = [r.model_dump() for r in results]
    summary = {
        "total": len(rows),
        "pre_resolved": sum(1 for r in results if r.pre_resolved),
        "resolved": sum(1 for r in results if r.status == "resolved"),
        "pending": sum(1 for r in results if r.status == "pending"),
        "unsupported": sum(1 for r in results if r.status == "unsupported"),
        "error": sum(1 for r in results if r.status == "error"),
    }
    payload = {
        "command": "graph files sites",
        "mode": "dry_run" if dry_run else "apply",
        "ok": summary["error"] == 0,
        "summary": summary,
        "sites": rows,
        "guardrails": _DISCOVERY_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
    raise typer.Exit(0)


@files_site_app.command("resolve")
def files_site_resolve_cmd(
    source: str = typer.Option(..., "--source", help="source_key from the registry."),
    dry_run: bool = typer.Option(
        True, "--dry-run/--apply", help="Default dry-run; --apply persists a discovery receipt."
    ),
    json_out: bool = typer.Option(True, "--json", help="Output JSON (default)."),
) -> None:
    """Resolve a single SharePoint source's site to its canonical Graph site_id."""
    try:
        registry = load_source_registry()
    except (SourceRegistryError, ValidationError) as e:
        _echo_files_error("graph files site resolve", e, json_out)
        return

    matching = [s for s in registry.sources if s.source_key == source]
    if not matching:
        payload = {
            "command": "graph files site resolve",
            "status": "not_found",
            "requested": source,
            "available": [s.source_key for s in registry.sources],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    client, auth_payload = _files_graph_client_or_auth(_FILES_GRAPH_SCOPES)
    if client is None:
        payload = {
            "command": "graph files site resolve",
            "source": source,
            "mode": "dry_run" if dry_run else "apply",
            **auth_payload,
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0)

    try:
        store = ConstructionStore() if not dry_run else None
        discovery = SiteDriveDiscovery(client, store=store)
        result = discovery.discover_site(matching[0], apply=not dry_run)
    finally:
        client.close()

    payload = {
        "command": "graph files site resolve",
        "source": source,
        "mode": "dry_run" if dry_run else "apply",
        "ok": result.status != "error",
        "site": result.model_dump(),
        "guardrails": _DISCOVERY_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
    raise typer.Exit(0)


@files_app.command("drives")
def files_drives_cmd(
    source: str = typer.Option(..., "--source", help="source_key from the registry."),
    dry_run: bool = typer.Option(
        True, "--dry-run/--apply", help="Default dry-run; --apply persists a discovery receipt."
    ),
    json_out: bool = typer.Option(True, "--json", help="Output JSON (default)."),
) -> None:
    """Enumerate a SharePoint site's drives and match the configured source by
    drive_id / list_id / library_name / webUrl. Metadata-only; no content crawl."""
    try:
        registry = load_source_registry()
    except (SourceRegistryError, ValidationError) as e:
        _echo_files_error("graph files drives", e, json_out)
        return

    matching = [s for s in registry.sources if s.source_key == source]
    if not matching:
        payload = {
            "command": "graph files drives",
            "status": "not_found",
            "requested": source,
            "available": [s.source_key for s in registry.sources],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    client, auth_payload = _files_graph_client_or_auth(_FILES_GRAPH_SCOPES)
    if client is None:
        payload = {
            "command": "graph files drives",
            "source": source,
            "mode": "dry_run" if dry_run else "apply",
            **auth_payload,
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0)

    try:
        store = ConstructionStore() if not dry_run else None
        discovery = SiteDriveDiscovery(client, store=store)
        result = discovery.discover_drives(matching[0], apply=not dry_run)
    finally:
        client.close()

    payload = {
        "command": "graph files drives",
        "source": source,
        "mode": "dry_run" if dry_run else "apply",
        "ok": result.status not in {"error"},
        "result": result.model_dump(),
        "guardrails": _DISCOVERY_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
    raise typer.Exit(0)


_ONEDRIVE_SOURCE_KINDS = {
    "onedrive_personal",
    "onedrive_personal_root",
    "onedrive_business_root",
    "onedrive_shared",
    "onedrive_shared_library",
}


@files_app.command("onedrive")
def files_onedrive_cmd(
    source: Optional[str] = typer.Option(None, "--source", help="Resolve only this source key."),
    dry_run: bool = typer.Option(
        True, "--dry-run/--apply", help="Default dry-run; --apply persists discovery receipts."
    ),
    json_out: bool = typer.Option(True, "--json", help="Output JSON (default)."),
) -> None:
    """Discover Bobby's business/personal OneDrive and represent shared libraries
    with structured states (pre_resolved / resolved / pending / unavailable /
    requires_share_url). Read-only, metadata-only; dry-run by default."""
    try:
        registry = load_source_registry()
    except (SourceRegistryError, ValidationError) as e:
        _echo_files_error("graph files onedrive", e, json_out)
        return

    targets = [
        s
        for s in registry.sources
        if s.kind in _ONEDRIVE_SOURCE_KINDS and (source is None or s.source_key == source)
    ]
    if not targets:
        payload = {
            "command": "graph files onedrive",
            "status": "not_found",
            "requested": source,
            "available": [
                s.source_key for s in registry.sources if s.kind in _ONEDRIVE_SOURCE_KINDS
            ],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    client, auth_payload = _files_graph_client_or_auth(_FILES_GRAPH_SCOPES)
    if client is None:
        payload = {
            "command": "graph files onedrive",
            "mode": "dry_run" if dry_run else "apply",
            **auth_payload,
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0)

    try:
        store = ConstructionStore() if not dry_run else None
        discovery = SiteDriveDiscovery(client, store=store)
        results = [discovery.discover_onedrive(s, apply=not dry_run) for s in targets]
    finally:
        client.close()

    rows = [r.model_dump() for r in results]
    summary = {
        "total": len(rows),
        "pre_resolved": sum(1 for r in results if r.status == "pre_resolved"),
        "resolved": sum(1 for r in results if r.status == "resolved"),
        "pending": sum(1 for r in results if r.status == "pending"),
        "unavailable": sum(1 for r in results if r.status == "unavailable"),
        "requires_share_url": sum(1 for r in results if r.status == "requires_share_url"),
        "error": sum(1 for r in results if r.status == "error"),
    }
    payload = {
        "command": "graph files onedrive",
        "mode": "dry_run" if dry_run else "apply",
        "ok": summary["error"] == 0,
        "summary": summary,
        "onedrive": rows,
        "guardrails": _DISCOVERY_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
    raise typer.Exit(0)


@files_app.command("index")
def files_index_cmd(
    source: str = typer.Option(..., "--source", help="source_key from the registry."),
    dry_run: bool = typer.Option(
        True, "--dry-run/--apply", help="Default dry-run; --apply persists canonical driveItems."
    ),
    max_pages: int = typer.Option(5, "--max-pages", help="Hard cap on pages read."),
    json_out: bool = typer.Option(True, "--json", help="Output JSON (default)."),
) -> None:
    """Index rich driveItem metadata into the canonical V5 construction_drive_items
    table (file/folder/package/deleted/parent/sharepoint facets; downloadUrl dropped).
    Read-only, metadata-only; dry-run by default."""
    try:
        registry = load_source_registry()
    except (SourceRegistryError, ValidationError) as e:
        _echo_files_error("graph files index", e, json_out)
        return

    matching = [s for s in registry.sources if s.source_key == source]
    if not matching:
        payload = {
            "command": "graph files index",
            "status": "not_found",
            "requested": source,
            "available": [s.source_key for s in registry.sources],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    client, auth_payload = _files_graph_client_or_auth(_FILES_GRAPH_SCOPES)
    if client is None:
        payload = {
            "command": "graph files index",
            "source": source,
            "mode": "dry_run" if dry_run else "apply",
            **auth_payload,
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0)

    try:
        store = ConstructionStore() if not dry_run else None
        indexer = DriveItemIndexer(client, store=store)
        report = indexer.index(matching[0], dry_run=dry_run, max_pages=max_pages)
    finally:
        client.close()

    guardrails = dict(_DISCOVERY_GUARDRAILS)
    guardrails["download_url_persisted"] = report.download_url_persisted
    payload = {
        "command": "graph files index",
        "source": source,
        "mode": "dry_run" if dry_run else "apply",
        "ok": report.status not in {"error"} and not report.download_url_persisted,
        "result": report.model_dump(),
        "guardrails": guardrails,
    }
    typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
    raise typer.Exit(0)


@files_link_app.command("resolve")
def files_link_resolve_cmd(
    url: str = typer.Option(..., "--url", help="User-provided OneDrive/SharePoint link."),
    source_id: Optional[str] = typer.Option(
        None, "--source-id", help="Associate with a source key."
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--apply",
        help="Default dry-run; --apply persists a redacted resolution row.",
    ),
    json_out: bool = typer.Option(True, "--json", help="Output JSON (default)."),
) -> None:
    """Resolve a user-provided OneDrive/SharePoint link to canonical IDs via the
    read-only Graph Shares API (no sharing-link redemption). Malformed links fail
    before any Graph call; the raw tokenized URL is never persisted. Dry-run default."""
    client, auth_payload = _files_graph_client_or_auth(_FILES_GRAPH_SCOPES)
    graph_available = client is not None
    try:
        store = ConstructionStore() if not dry_run else None
        resolver = LinkResolver(http_client=client, store=store)
        result = resolver.resolve_link(url, dry_run=dry_run, source_id=source_id)
    finally:
        if client is not None:
            client.close()

    payload: Dict[str, Any] = {
        "command": "graph files link resolve",
        "mode": "dry_run" if dry_run else "apply",
        "graph_available": graph_available,
        "ok": result.status in {"resolved", "pending"},
        "result": result.model_dump(),
        "guardrails": {
            "external_systems": "read_only",
            "writeback": "none",
            "sharing_link_redemption": "none",
            "raw_tokenized_url_persisted": False,
            "metadata_only": True,
            "permission_tightening": "deferred",
        },
    }
    if not graph_available and auth_payload is not None:
        # Shares-API resolution was skipped (no token); registry/parse fallbacks ran.
        payload["auth"] = auth_payload
    typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
    raise typer.Exit(0)


@files_app.command("crawl")
def files_crawl_cmd(
    source: str = typer.Option(..., "--source", help="source_key from the registry."),
    dry_run: bool = typer.Option(
        True, "--dry-run/--apply", help="Default dry-run; --apply persists crawl run + driveItems."
    ),
    max_pages: int = typer.Option(5, "--max-pages", help="Hard cap on pages read."),
    max_items: int = typer.Option(500, "--max-items", help="Hard cap on items read."),
    max_seconds: int = typer.Option(300, "--max-seconds", help="Wall-clock budget (seconds)."),
    children: bool = typer.Option(
        False,
        "--children/--no-children",
        help="Children traversal (diagnostics only; default delta).",
    ),
    json_out: bool = typer.Option(True, "--json", help="Output JSON (default)."),
) -> None:
    """Run a bounded, metadata-only baseline crawl for a source (delta-initial by
    default; --children for targeted diagnostics). Records a crawl run + receipt on
    --apply. Read-only; no content; no delta token stored. Dry-run default."""
    try:
        registry = load_source_registry()
    except (SourceRegistryError, ValidationError) as e:
        _echo_files_error("graph files crawl", e, json_out)
        return

    matching = [s for s in registry.sources if s.source_key == source]
    if not matching:
        payload = {
            "command": "graph files crawl",
            "status": "not_found",
            "requested": source,
            "available": [s.source_key for s in registry.sources],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    client, auth_payload = _files_graph_client_or_auth(_FILES_GRAPH_SCOPES)
    if client is None:
        payload = {
            "command": "graph files crawl",
            "source": source,
            "mode": "dry_run" if dry_run else "apply",
            **auth_payload,
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0)

    try:
        store = ConstructionStore() if not dry_run else None
        crawler = BaselineCrawler(client, store=store)
        report = crawler.crawl(
            matching[0],
            dry_run=dry_run,
            max_pages=max_pages,
            max_items=max_items,
            max_seconds=max_seconds,
            children=children,
        )
    finally:
        client.close()

    guardrails = dict(_DISCOVERY_GUARDRAILS)
    guardrails["traversal"] = report.traversal
    guardrails["delta_token_recorded"] = False
    payload = {
        "command": "graph files crawl",
        "source": source,
        "mode": "dry_run" if dry_run else "apply",
        "ok": report.status in {"ok", "partial"},
        "result": report.model_dump(),
        "guardrails": guardrails,
    }
    typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
    raise typer.Exit(0)


@files_app.command("delta")
def files_delta_cmd(
    source: str = typer.Option(..., "--source", help="source_key from the registry."),
    dry_run: bool = typer.Option(
        True, "--dry-run/--apply", help="Default dry-run; --apply persists sync state + driveItems."
    ),
    max_pages: int = typer.Option(50, "--max-pages", help="Hard cap on delta pages."),
    max_items: int = typer.Option(5000, "--max-items", help="Hard cap on items."),
    json_out: bool = typer.Option(True, "--json", help="Output JSON (default)."),
) -> None:
    """Hardened incremental delta sync into the V5 canonical layer: follows nextLink,
    captures the deltaLink (SQLite-only; rendered as a fingerprint), handles the
    deleted facet, and recovers a stale token (410) as requires_rebaseline. Read-only;
    metadata only; dry-run default."""
    try:
        registry = load_source_registry()
    except (SourceRegistryError, ValidationError) as e:
        _echo_files_error("graph files delta", e, json_out)
        return

    matching = [s for s in registry.sources if s.source_key == source]
    if not matching:
        payload = {
            "command": "graph files delta",
            "status": "not_found",
            "requested": source,
            "available": [s.source_key for s in registry.sources],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    client, auth_payload = _files_graph_client_or_auth(_FILES_GRAPH_SCOPES)
    if client is None:
        payload = {
            "command": "graph files delta",
            "source": source,
            "mode": "dry_run" if dry_run else "apply",
            **auth_payload,
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0)

    try:
        # Store passed always: delta must READ prior sync state; writes gated by dry_run.
        store = ConstructionStore()
        delta = DeltaSync(client, store=store)
        report = delta.sync(matching[0], dry_run=dry_run, max_pages=max_pages, max_items=max_items)
    finally:
        client.close()

    guardrails = dict(_DISCOVERY_GUARDRAILS)
    guardrails["delta_token_storage"] = "sqlite_only"
    guardrails["delta_link_rendered"] = "fingerprint_only"
    payload = {
        "command": "graph files delta",
        "source": source,
        "mode": "dry_run" if dry_run else "apply",
        "ok": report.status in {"ok", "partial", "requires_rebaseline"},
        "result": report.model_dump(),
        "guardrails": guardrails,
    }
    typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
    raise typer.Exit(0)


@files_app.command("project-match")
def files_project_match_cmd(
    project: Optional[str] = typer.Option(None, "--project", help="Target project key to report."),
    source: Optional[str] = typer.Option(None, "--source", help="Limit to one source key."),
    dry_run: bool = typer.Option(
        True, "--dry-run/--apply", help="Default dry-run; --apply writes match fields to SQLite."
    ),
    json_out: bool = typer.Option(True, "--json", help="Output JSON (default)."),
) -> None:
    """Match indexed files to projects (deterministic + heuristic) with confidence/
    status/reason, routing low-confidence and unmatched files to review. Operates on
    already-indexed SQLite rows + the source registry — no Graph calls. Dry-run default."""
    try:
        load_source_registry()  # surface registry/schema errors early
    except (SourceRegistryError, ValidationError) as e:
        _echo_files_error("graph files project-match", e, json_out)
        return

    store = ConstructionStore()
    report = FileProjectMatcher(store).match(
        target_project=project, source_id=source, dry_run=dry_run
    )
    payload = {
        "command": "graph files project-match",
        "mode": report.mode,
        "ok": True,
        "result": report.model_dump(),
        "guardrails": {
            "external_systems": "read_only",
            "writeback": "none",
            "graph_calls": "none",
            "review_routing": "review_required_flag",
            "permission_tightening": "deferred",
        },
    }
    typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
    raise typer.Exit(0)


@files_app.command("ingestion-policy")
def files_ingestion_policy_cmd(
    source: Optional[str] = typer.Option(None, "--source", help="Limit to one source key."),
    dry_run: bool = typer.Option(
        True, "--dry-run/--apply", help="Default dry-run; --apply persists ingestion decisions."
    ),
    json_out: bool = typer.Option(True, "--json", help="Output JSON (default)."),
) -> None:
    """Assign each indexed file an ingestion disposition (metadata_only / eligible /
    manual_approval_required / review_required / blocked / low_confidence) BEFORE any
    download or extraction. Sensitive/large/low-confidence files never auto-extract.
    Offline (SQLite + policy); no Graph. Dry-run default."""
    try:
        load_source_registry()
    except (SourceRegistryError, ValidationError) as e:
        _echo_files_error("graph files ingestion-policy", e, json_out)
        return

    store = ConstructionStore()
    report = IngestionEligibilityEvaluator(store).evaluate(source_id=source, dry_run=dry_run)
    payload = {
        "command": "graph files ingestion-policy",
        "mode": report.mode,
        "ok": True,
        "result": report.model_dump(),
        "guardrails": {
            "external_systems": "read_only",
            "writeback": "none",
            "graph_calls": "none",
            "download_default": "none",
            "extract_default": "none",
            "block_review_required_extraction": True,
            "permission_tightening": "deferred",
        },
    }
    typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
    raise typer.Exit(0)


@files_app.command("extract")
def files_extract_cmd(
    source: str = typer.Option(..., "--source", help="source_key from the registry."),
    dry_run: bool = typer.Option(
        True, "--dry-run/--apply", help="Default dry-run (plan only; no download/parse/SQLite)."
    ),
    download: bool = typer.Option(
        False, "--download/--no-download", help="Explicitly enable controlled content download."
    ),
    extract: bool = typer.Option(
        False,
        "--extract/--no-extract",
        help="Explicitly enable bounded parse (requires --download).",
    ),
    retain_cache: bool = typer.Option(
        False,
        "--retain-cache",
        help="Debug: keep the downloaded cache file (default: delete after parse).",
    ),
    max_bytes: int = typer.Option(26214400, "--max-bytes", help="Download size cap (bytes)."),
    json_out: bool = typer.Option(True, "--json", help="Output JSON (default)."),
) -> None:
    """Controlled, drive-aware download + bounded redacted extraction for files the
    ingestion policy marked eligible. Review-required/blocked files are skipped.
    Download/extract require explicit flags; dry-run default. Cache lives outside the
    repo/vault and is deleted after parse; no full text persisted; downloadUrl never used."""
    try:
        registry = load_source_registry()
    except (SourceRegistryError, ValidationError) as e:
        _echo_files_error("graph files extract", e, json_out)
        return

    matching = [s for s in registry.sources if s.source_key == source]
    if not matching:
        payload = {
            "command": "graph files extract",
            "status": "not_found",
            "requested": source,
            "available": [s.source_key for s in registry.sources],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    client: Optional[GraphHttpClient] = None
    auth_payload: Optional[Dict[str, Any]] = None
    # A Graph client is only needed when actually downloading (apply + --download).
    if not dry_run and download:
        client, auth_payload = _files_graph_client_or_auth(_FILES_GRAPH_SCOPES)
        if client is None:
            payload = {
                "command": "graph files extract",
                "source": source,
                "mode": "apply",
                **auth_payload,
            }
            typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
            raise typer.Exit(0)

    try:
        store = ConstructionStore()
        report = ControlledExtractor(client, store).run(
            source,
            dry_run=dry_run,
            do_download=download,
            do_extract=extract,
            retain_cache=retain_cache,
            max_bytes=max_bytes,
        )
    finally:
        if client is not None:
            client.close()

    payload = {
        "command": "graph files extract",
        "source": source,
        "mode": report.mode,
        "ok": True,
        "result": report.model_dump(),
        "guardrails": {
            "external_systems": "read_only",
            "writeback": "none",
            "download_url_cached": False,
            "full_text_persisted": False,
            "source_copied_to_vault": False,
            "cache_outside_repo_and_vault": True,
            "block_review_required_extraction": True,
            "permission_tightening": "deferred",
        },
    }
    typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
    raise typer.Exit(0)


@files_app.command("review-queue")
def files_review_queue_cmd(
    source: Optional[str] = typer.Option(
        None, "--source", help="Limit to one source key (default: every registry source)."
    ),
    dry_run: bool = typer.Option(
        True, "--dry-run/--apply", help="Default dry-run; --apply enqueues review rows."
    ),
    json_out: bool = typer.Option(True, "--json", help="Output JSON (default)."),
) -> None:
    """Route construction-sensitive files (contracts, financials, claims, notices, legal,
    HR/personnel, insurance/bonding, safety, medical, disputes, cost/schedule impact) and
    low-confidence project matches into the review queue before any extraction. Idempotent
    (re-running never duplicates rows). Offline (SQLite + rules); no Graph. Dry-run default.
    Review-routed files cannot extract (enforced by the V18 ingestion CHECK; verified here)."""
    try:
        load_source_registry()  # surface registry/schema errors early
        rules = load_review_rules()
    except (SourceRegistryError, ReviewRulesError, ValidationError) as e:
        _echo_files_error("graph files review-queue", e, json_out)
        return

    store = ConstructionStore()
    router = FileReviewRouter(store, ReviewPolicyEvaluator(rules))
    results = router.route(source_id=source, dry_run=dry_run)
    all_blocked = all(r.extraction_blocked_for_all_routed for r in results)
    payload = {
        "command": "graph files review-queue",
        "mode": "dry_run" if dry_run else "apply",
        "ok": True,
        "results": [r.model_dump() for r in results],
        "guardrails": {
            "external_systems": "read_only",
            "writeback": "none",
            "graph_calls": "none",
            "review_routed_cannot_extract": all_blocked,
            "queue_idempotent": True,
            "permission_tightening": "deferred",
        },
    }
    typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
    raise typer.Exit(0)


@files_app.command("obsidian")
def files_obsidian_cmd(
    source: Optional[str] = typer.Option(None, "--source", help="Limit to one source key."),
    project: Optional[str] = typer.Option(None, "--project", help="Limit to one project key."),
    dry_run: bool = typer.Option(
        True, "--dry-run/--apply", help="Default dry-run (preview paths); --apply writes notes."
    ),
    json_out: bool = typer.Option(True, "--json", help="Output JSON (default)."),
) -> None:
    """Generate low-noise Obsidian notes from indexed SQLite state: per-source manifests,
    per-project file registers, sensitive-file review summaries, and a processing receipt.
    Marker-bounded + idempotent; never one note per file; no raw delta links, tokens, signed
    URLs, or full document text (output-fenced). Offline (SQLite); no Graph. Dry-run default."""
    try:
        load_source_registry()  # surface registry/schema errors early
    except (SourceRegistryError, ValidationError) as e:
        _echo_files_error("graph files obsidian", e, json_out)
        return

    store = ConstructionStore()
    report = FileObsidianProjector(store).project(
        source_id=source, project_key=project, dry_run=dry_run
    )
    payload = {
        "command": "graph files obsidian",
        "mode": "dry_run" if dry_run else "apply",
        "ok": True,
        "result": report.model_dump(),
        "guardrails": report.guardrails,
    }
    typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
    raise typer.Exit(0)


@files_app.command("retrieve")
def files_retrieve_cmd(
    query: str = typer.Option(..., "--query", help="Search query (keywords)."),
    project: Optional[str] = typer.Option(None, "--project", help="Limit to one project key."),
    source: Optional[str] = typer.Option(None, "--source", help="Limit to one source key."),
    limit: int = typer.Option(10, "--limit", min=1, max=100, help="Max hits to return."),
    json_out: bool = typer.Option(True, "--json", help="Output JSON (default)."),
) -> None:
    """Source-linked retrieval over bounded, redacted file excerpts. Deterministic + offline
    (SQLite; no Graph, no embeddings). Each hit links back to drive item identity + web URL,
    project, parser output, and processing receipt. Bounded redacted excerpts only — never full
    document text. Review-routed / sensitive files are excluded from results."""
    try:
        load_source_registry()  # surface registry/schema errors early
    except (SourceRegistryError, ValidationError) as e:
        _echo_files_error("graph files retrieve", e, json_out)
        return

    store = ConstructionStore()
    report = FileRetriever(store).retrieve(
        query=query, project_key=project, source_id=source, limit=limit
    )
    payload = {
        "command": "graph files retrieve",
        "query": query,
        "ok": True,
        "result": report.model_dump(),
        "guardrails": report.guardrails,
    }
    typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
    raise typer.Exit(0)


def _echo_files_error(command: str, exc: Exception, json_out: bool) -> None:
    """Emit a blocking JSON envelope for registry load/validation failures."""
    if isinstance(exc, ValidationError):
        payload: Dict[str, Any] = {
            "command": command,
            "ok": False,
            "error": "schema_validation_failed",
            "detail": exc.errors(),
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    else:
        payload = {
            "command": command,
            "ok": False,
            "error": "source_registry_unavailable",
            "detail": str(exc)[:200],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
    raise typer.Exit(1)


def _classify_source(src: Any) -> Dict[str, Any]:
    """Read-only classification of one registry source for the projection plan.
    No SQLite, no Graph — pure inspection of the loaded model."""
    from hb_assistant.construction.source_projection import _infer_source_system

    status = src.resolution_status or "pending"
    pre_resolved = bool(src.site_id or src.drive_id or src.folder_item_id) or (
        status in {"graph_delta_ready", "resolved"}
    )
    pending = (not pre_resolved) and status.startswith("pending")
    unmatched = src.match_status == "unmatched"
    matched = (src.match_status == "matched") or (src.project_key is not None and not unmatched)
    return {
        "source_id": src.source_key,
        "source_system": src.source_system or _infer_source_system(src.kind),
        "source_scope": src.kind,
        "enabled": bool(src.enabled),
        "resolution_status": status,
        "pre_resolved": pre_resolved,
        "pending": pending,
        "matched": matched,
        "unmatched": unmatched,
        "project_key": src.project_key,
        "review_required": bool(src.review_required),
        "would_project": True,
    }


def _sources_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate classification buckets for the projection plan summary."""

    def _count(pred: Any) -> int:
        return sum(1 for r in rows if pred(r))

    by_system: Dict[str, int] = {}
    by_scope: Dict[str, int] = {}
    for r in rows:
        by_system[r["source_system"]] = by_system.get(r["source_system"], 0) + 1
        by_scope[r["source_scope"]] = by_scope.get(r["source_scope"], 0) + 1
    return {
        "total": len(rows),
        "by_system": by_system,
        "by_scope": by_scope,
        "enabled": _count(lambda r: r["enabled"]),
        "disabled": _count(lambda r: not r["enabled"]),
        "pre_resolved": _count(lambda r: r["pre_resolved"]),
        "pending": _count(lambda r: r["pending"]),
        "matched": _count(lambda r: r["matched"]),
        "unmatched": _count(lambda r: r["unmatched"]),
        "review_required": _count(lambda r: r["review_required"]),
    }


@files_app.command("sources")
def files_sources_cmd(
    apply: bool = typer.Option(
        False, "--apply", help="Persist the canonical V5 projection to SQLite (default: dry-run)."
    ),
    json_out: bool = typer.Option(True, "--json", help="Output JSON (default)."),
) -> None:
    """Project the SharePoint/OneDrive source registry into the canonical V5
    ``construction_source_locations`` table.

    Dry-run by default: classifies/validates every source (enabled / pending /
    pre-resolved / unmatched) and computes the projection plan **without** any
    SQLite write. ``--apply`` persists idempotently. Read-only against Microsoft
    365; no Graph calls. Permission tightening remains deferred.
    """
    try:
        registry = load_source_registry()
    except SourceRegistryError as e:
        payload = {
            "command": "graph files sources",
            "ok": False,
            "error": "source_registry_unavailable",
            "detail": str(e)[:200],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1) from None
    except ValidationError as e:
        payload = {
            "command": "graph files sources",
            "ok": False,
            "error": "schema_validation_failed",
            "detail": e.errors(),
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(1) from None

    rows = [_classify_source(s) for s in registry.sources]
    summary = _sources_summary(rows)
    all_read_only = all(s.read_only is True for s in registry.sources)

    persisted_count: Optional[int] = None
    if apply:
        store = ConstructionStore()
        report = project_registry_to_v5_source_locations(registry, store)
        persisted_count = len(store.list_source_locations(limit=10000))
    else:
        report = project_registry_to_v5_source_locations(registry, dry_run=True)

    summary["projected"] = report.projected
    summary["compat_projected"] = report.compat_projected
    summary["skipped"] = report.skipped

    ok = bool(
        all_read_only
        and report.skipped == 0
        and (report.projected + report.compat_projected) == summary["total"]
        and (persisted_count is None or persisted_count >= summary["total"])
    )

    payload: Dict[str, Any] = {
        "command": "graph files sources",
        "mode": "apply" if apply else "dry_run",
        "ok": ok,
        "summary": summary,
        "sources": rows,
        "persisted_source_location_count": persisted_count,
        "guardrails": {
            "external_systems": "read_only",
            "writeback": "none",
            "metadata_only": True,
            "all_read_only": all_read_only,
            "permission_tightening": "deferred",
        },
    }
    typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
    raise typer.Exit(0 if ok else 1)


@mail_app.command("status")
def status_cmd(
    json_out: bool = typer.Option(False, "--json", help="Output JSON"),
    probe: bool = typer.Option(
        True, "--probe/--no-probe", help="Issue one bounded read-only Graph probe"
    ),
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
            "attachment_content_excluded": "contentBytes"
            not in contract.attachment_metadata_select,
        }
        ok = bool(
            mail_read_present and guardrails["no_mail_write_scopes_requested"] and guard["passed"]
        )

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
        payload = {
            "command": "graph mail status",
            "ok": False,
            "status": "status_error",
            "error": str(e)[:200],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1) from None


@calendar_app.command("status")
def calendar_status_cmd(
    json_out: bool = typer.Option(False, "--json", help="Output JSON"),
    probe: bool = typer.Option(
        True, "--probe/--no-probe", help="Issue one bounded read-only Graph probe"
    ),
) -> None:
    """Report calendar read-only readiness: auth, scopes, endpoint-guard, and a bounded probe.

    The write-capable ``Calendars.ReadWrite.Shared`` scope, when configured, is
    reported as a DEFERRED tightening posture (documented residual risk), not a
    failure: the calendar endpoint guard enforces read-only behavior regardless of
    the granted scope. ``ok`` is driven by the in-process mutation-lockout proof
    plus calendar read capability; the probe is non-fatal.
    """
    try:
        cfg = load_config()
        pp = PathPolicy(cfg)
        configured = list(cfg.identity.delegated_scopes)
        provider = DelegatedAuthProvider(
            cfg.identity.tenant_id, cfg.identity.client_id, configured, path_policy=pp
        )
        contract = load_calendar_endpoint_contract()

        read_capable = {s.lower() for s in _READ_CALENDAR_SCOPES} | {
            s.lower() for s in _WRITE_CAPABLE_CALENDAR_SCOPES
        }
        calendar_read_capability_present = any(s.lower() in read_capable for s in configured)
        write_capable_present = [
            s for s in configured if s.lower() in {x.lower() for x in _WRITE_CAPABLE_CALENDAR_SCOPES}
        ]

        auth_info = provider.status_info()  # safe: no tokens, redacted claims
        guard = run_calendar_no_writeback_self_test(contract)
        calendar_probe = _calendar_probe(provider, contract) if probe else {"attempted": False}

        mutation_blocked = bool(guard["passed"])
        guardrails = {
            "calendar_read_only": True,
            "mutation_endpoints_blocked": mutation_blocked,
            "event_body_excluded": "body" not in contract.event_metadata_select
            and "bodyPreview" not in contract.event_metadata_select,
            "join_url_excluded": "onlineMeeting" not in contract.event_metadata_select,
            "permission_tightening": "deferred",
            "residual_risk": (
                "write-capable scope configured; runtime calendar endpoint guard "
                "enforces read-only behavior"
            ),
            "guardrail_status": "passed" if mutation_blocked else "failed",
        }
        ok = bool(mutation_blocked and calendar_read_capability_present)

        payload: Dict[str, Any] = {
            "command": "graph calendar status",
            "ok": ok,
            "calendar_read_capability_present": calendar_read_capability_present,
            "write_capable_calendar_scopes_present": write_capable_present,
            "auth": auth_info,
            "guard_self_test": guard,
            "calendar_probe": calendar_probe,
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
        payload = {
            "command": "graph calendar status",
            "ok": False,
            "status": "status_error",
            "error": str(e)[:200],
        }
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

        payload: Dict[str, Any] = {
            "command": "graph mail folders",
            "ok": True,
            **result.model_dump(),
        }
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
    project: Optional[str] = typer.Option(
        None, "--project", help="Project key label for this crawl run"
    ),
    lookback_days: int = typer.Option(
        30, "--lookback-days", help="Bounded lookback window in days (1-366)"
    ),
    max_messages: int = typer.Option(
        200, "--max-messages", help="Max messages indexed per folder (bounded)"
    ),
    include_encrypted_body: bool = typer.Option(
        False,
        "--include-encrypted-body",
        help="Also capture full bodies ENCRYPTED at rest (policy-gated; no plaintext persisted)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run/--no-dry-run",
        help="Preview without writing message rows (default: persist)",
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
    project: Optional[str] = typer.Option(
        None, "--project", help="Pilot project key (omit to match all pilot projects)"
    ),
    lookback_days: int = typer.Option(
        30, "--lookback-days", help="Bounded lookback window in days (1-366)"
    ),
    max_messages: int = typer.Option(
        200, "--max-messages", help="Max messages scanned per folder (bounded)"
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="Preview matches without persisting (default); --no-dry-run writes matches",
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

        payload: Dict[str, Any] = {
            "command": "graph mail discover",
            "ok": True,
            **report.model_dump(),
        }
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
    lookback_days: int = typer.Option(
        30, "--lookback-days", help="Bounded lookback window in days (1-366)"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run/--no-dry-run",
        help="Preview without persisting (default: persist candidates)",
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
        payload: Dict[str, Any] = {
            "command": "graph mail relationships",
            "ok": True,
            **report.model_dump(),
        }
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


@mail_app.command("review-queue")
def review_queue_cmd(
    project: Optional[str] = typer.Option(None, "--project", help="Pilot project key"),
    lookback_days: int = typer.Option(
        30, "--lookback-days", help="Bounded lookback window in days (1-366)"
    ),
    max_messages: int = typer.Option(
        200, "--max-messages", help="Max matched messages routed (bounded)"
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="Preview routing decisions without persisting (default); --no-dry-run enqueues review items",
    ),
    json_out: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Route sensitive/low-confidence email to review + compute encrypted-body eligibility.

    Local-only (NO Graph, NO mailbox): reads stored project matches + bounded redacted
    previews, classifies sensitive categories, and decides body-capture eligibility.
    --dry-run previews evidence-safe decisions; --no-dry-run enqueues email_review_queue
    rows with the decision metadata. Full body plaintext is never fetched or emitted.
    """
    try:
        router = ReviewRouter(ConstructionStore())
        report = router.route(
            project_key=project,
            lookback_days=lookback_days,
            dry_run=dry_run,
            max_messages=max_messages,
        )
        payload: Dict[str, Any] = {
            "command": "graph mail review-queue",
            "ok": True,
            **report.model_dump(),
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0)
    except typer.Exit:
        raise
    except Exception as e:
        payload = {
            "command": "graph mail review-queue",
            "ok": False,
            "dry_run": dry_run,
            "status": "review_queue_error",
            "error": str(e)[:200],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1) from None


@mail_app.command("classify")
def classify_cmd(
    project: Optional[str] = typer.Option(None, "--project", help="Pilot project key"),
    lookback_days: int = typer.Option(
        30, "--lookback-days", help="Bounded lookback window in days (1-366)"
    ),
    max_messages: int = typer.Option(
        200, "--max-messages", help="Max matched messages classified (bounded)"
    ),
    use_encrypted_body_context: bool = typer.Option(
        False,
        "--use-encrypted-body-context",
        help="Decrypt stored bodies in-memory for model context (discarded; never persisted)",
    ),
    mock_output: Optional[str] = typer.Option(
        None,
        "--mock-output",
        help="Raw model JSON for offline/testing (bypasses Ollama)",
        hidden=True,
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="Preview classifications without persisting (default); --no-dry-run writes the V14 read model",
    ),
    json_out: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Advisory local-model (Ollama) email classification, local-only.

    Reads stored project matches + bounded redacted previews (and, with
    --use-encrypted-body-context, the encrypted body decrypted IN MEMORY only), runs the
    local model, strictly validates the JSON, and persists ONLY structured advisory output
    (V14 email_model_classifications) + review routing. The model is advisory; deterministic
    review rules govern. NO Graph call, NO mailbox mutation, NO body plaintext emitted.
    """
    try:
        store = ConstructionStore()
        policy = load_email_intelligence_active_policy()
        client = None
        if mock_output is None and policy.ollama_enabled_for_email_intelligence:
            try:
                client = OllamaChatClient(DEFAULT_MODEL_NAME)
            except Exception:
                client = None
        classifier = EmailIntelligenceClassifier(store, policy=policy, client=client)
        report = classifier.classify(
            project_key=project,
            lookback_days=lookback_days,
            use_encrypted_body_context=use_encrypted_body_context,
            dry_run=dry_run,
            max_messages=max_messages,
            mock_output=mock_output,
        )
        payload: Dict[str, Any] = {
            "command": "graph mail classify",
            "ok": True,
            **report.model_dump(),
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0)
    except typer.Exit:
        raise
    except Exception as e:
        payload = {
            "command": "graph mail classify",
            "ok": False,
            "dry_run": dry_run,
            "status": "classify_error",
            "error": str(e)[:200],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1) from None


@mail_app.command("obsidian")
def obsidian_cmd(
    project: Optional[str] = typer.Option(None, "--project", help="Pilot project key"),
    include_encrypted_body_status: bool = typer.Option(
        False,
        "--include-encrypted-body-status",
        help="Include safe encrypted-body availability booleans/counts only (never plaintext/ref)",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="Preview planned notes without writing (default); --no-dry-run writes marker-bounded notes",
    ),
    json_out: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Build safe Prompt 12 email Obsidian projections (local-only, no plaintext body)."""
    try:
        projector = EmailObsidianProjector(ConstructionStore())
        report = projector.project(
            project_key=project,
            include_encrypted_body_status=include_encrypted_body_status,
            dry_run=dry_run,
        )
        payload: Dict[str, Any] = {
            "command": "graph mail obsidian",
            "ok": True,
            **report.model_dump(),
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0)
    except typer.Exit:
        raise
    except Exception as e:
        payload = {
            "command": "graph mail obsidian",
            "ok": False,
            "dry_run": dry_run,
            "status": "obsidian_error",
            "error": str(e)[:200],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1) from None


@mail_app.command("operational-validate")
def operational_validate_cmd(
    project: str = typer.Option("tropical", "--project", help="Pilot project key"),
    lookback_days: int = typer.Option(30, "--lookback-days", help="Pilot lookback days"),
    include_live_index: bool = typer.Option(
        True,
        "--include-live-index/--no-live-index",
        help="Include required non-dry-run index call in the validation chain",
    ),
    write_evidence: bool = typer.Option(
        True,
        "--write-evidence/--no-write-evidence",
        help="Write Prompt 13 evidence artifacts to docs/evidence",
    ),
    json_out: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Run Prompt 13 command-chain validation + aggregate operational metrics."""
    try:
        report = run_operational_validation(
            project_key=project,
            lookback_days=lookback_days,
            include_live_index=include_live_index,
            write_evidence=write_evidence,
        )
        payload: Dict[str, Any] = {
            "command": "graph mail operational-validate",
            "ok": bool(report.metrics.validation_ok),
            **report.model_dump(),
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0 if payload["ok"] else 1)
    except typer.Exit:
        raise
    except Exception as e:
        payload = {
            "command": "graph mail operational-validate",
            "ok": False,
            "status": "operational_validate_error",
            "error": str(e)[:200],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1) from None


@body_app.command("show")
def body_show_cmd(
    message_id: str = typer.Option(
        ..., "--message-id", help="Indexed message id whose encrypted body to read"
    ),
    reason: str = typer.Option(
        ..., "--reason", help="Operator reason for the decrypt (audited locally)"
    ),
    show_plaintext: bool = typer.Option(
        False,
        "--show-plaintext",
        help="Print the decrypted body to THIS terminal only (never to disk/log/evidence)",
    ),
    json_out: bool = typer.Option(
        False, "--json", help="Output JSON (redacted summary; never plaintext)"
    ),
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
            payload = {
                "command": "graph mail body show",
                "ok": True,
                "found": False,
                "message_id": message_id,
            }
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
        payload = {
            "command": "graph mail body show",
            "ok": False,
            "status": "body_show_error",
            "error": str(e)[:200],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1) from None
