"""FileIngestionService: selective ingestion pipeline (relevance + eligibility + approval + DL + parse + links).

Phase 10: metadata → relevance (Phase 6 signals + heuristics) → eligibility → approval gate → controlled DL (if approved) → hash → bounded parse (full matrix) → persist + SourceLinkRegistry ("parsed_from", "attaches").
Dry-run and mock friendly. Excerpts only; no full content.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from hb_assistant.graph.drive_item_client import DriveItemClient
from hb_assistant.graph.mail_client import MailClient
from hb_assistant.links.registry import SourceLinkRegistry
from hb_assistant.normalize.attachment import Attachment
from hb_assistant.normalize.drive_item import DriveItem
from hb_assistant.store.repositories import Store

from .eligibility import ApprovalGate, EligibilityGate
from .downloader import ControlledDownloader
from .hasher import ContentHasher
from .relevance import FileRelevanceScorer
from .router import ParserRouter

class FileIngestionService:
    """Orchestrates selective file/attachment ingestion with full pipeline + failure isolation."""

    def __init__(
        self,
        drive_client: DriveItemClient,
        mail_client: Optional[MailClient] = None,
        store: Optional[Store] = None,
        registry: Optional[SourceLinkRegistry] = None,
    ):
        self.drive = drive_client
        self.mail = mail_client
        self.store = store or Store()
        self.registry = registry or SourceLinkRegistry(self.store)
        self.gate = EligibilityGate()
        self.approval = ApprovalGate()
        self.relevance = FileRelevanceScorer()
        # downloader expects GraphHttpClient (drive_client.client); tests often mock the downloader or pass http-like
        http = getattr(drive_client, "client", None)
        self.downloader = ControlledDownloader(http or drive_client)
        self.hasher = ContentHasher()
        self.parser = ParserRouter()

    def discover_and_ingest_pending(
        self, limit: int = 5, *, dry_run: bool = True, approved_source_ids: Optional[set[int]] = None
    ) -> List[dict]:
        """Discovery + selective ingest (relevance first).

        If mail_client present: best-effort recent inbound with has_attachments (client-side filter).
        Returns redacted metadata + relevance + eligibility + decision (excerpts only on real ingest).
        For full matrix tests, prefer ingest_items() with explicit DriveItem list + mocks.
        """
        if approved_source_ids:
            self.approval = ApprovalGate(approved_source_ids)

        candidates: List[DriveItem] = []
        if self.mail:
            try:
                for email in self.mail.list_inbound(top=limit * 3):
                    if getattr(email, "has_attachments", False):
                        # attachments metadata (DriveItemClient exposes list_attachments for mail messages)
                        try:
                            atts = self.drive.list_attachments(getattr(email, "id", ""))
                            for a in atts:
                                # Adapt Attachment -> minimal DriveItem-like for pipeline (id, name, size, is_file)
                                di = DriveItem(
                                    id=a.id or f"att-{a.name}",
                                    name=a.name,
                                    size=a.size,
                                    is_file=True,
                                    source_record_id=getattr(email, "source_record_id", None),
                                )
                                candidates.append(di)
                        except Exception:
                            pass  # isolation, continue
            except Exception:
                pass  # no real calls in dry/test if mail not functional

        if not candidates:
            # fallback stub for pure mock tests / no mail
            return []

        return self.ingest_items(candidates[:limit], dry_run=dry_run, approved_source_ids=approved_source_ids)

    def ingest_items(
        self,
        items: List[DriveItem],
        *,
        dry_run: bool = True,
        approved_source_ids: Optional[set[int]] = None,
        classifications_by_source: Optional[Dict[int, List[str]]] = None,
    ) -> List[Dict[str, Any]]:
        """Full selective pipeline for explicit items (used by CLI/tests + discover).

        relevance (signals optional) → eligibility → approval → [if not dry+approved: DL + hash + bounded parse + persist + links]
        All outputs redacted/bounded. Failure isolated per item.
        """
        if approved_source_ids:
            self.approval = ApprovalGate(approved_source_ids)
        classifications_by_source = classifications_by_source or {}

        results: List[Dict[str, Any]] = []
        for item in items:
            rec: Dict[str, Any] = {
                "drive_item_id": item.id,
                "name": item.name,
                "size_mb": round((item.size or 0) / (1024 * 1024), 2),
                "web_url": getattr(item, "web_url", None),
            }
            sid = getattr(item, "source_record_id", None)
            if not sid or sid <= 0:
                rec["decision"] = "blocked_missing_provenance"
                results.append(rec)
                continue
            if not getattr(item, "id", None) or not getattr(item, "name", None) or getattr(item, "size", None) is None:
                rec["decision"] = "blocked_incomplete_graph_metadata"
                results.append(rec)
                continue

            # 1. Relevance (Phase 6 signals if provided via classifications_by_source or store lookup possible later)
            parent_classifs: List[str] = []
            if sid and sid in classifications_by_source:
                parent_classifs = classifications_by_source[sid]
            rel = self.relevance.score(
                item,
                classifications=None,
                parent_classifications=parent_classifs,
                has_attachments=False,
                parent_has_attachments=bool(getattr(item, "has_attachments", False)),
            )
            rec["relevance"] = rel.model_dump()
            if not rel.worth_ingesting:
                rec["decision"] = "skipped_low_relevance"
                results.append(rec)
                continue

            # 2. Eligibility
            elig = self.gate.check(item)
            rec["eligibility"] = {
                "eligible": elig.eligible,
                "reason": elig.reason,
                "requires_manual_approval": elig.requires_manual_approval,
                "size_mb": elig.size_mb,
            }
            if not elig.eligible and not elig.requires_manual_approval:
                rec["decision"] = f"skipped_{elig.reason}"
                results.append(rec)
                continue

            # 3. Approval gate
            approved, approve_reason = self.approval.is_approved(elig, source_record_id=sid)
            if not approved:
                rec["decision"] = "manual_approval_required"
                rec["approval_reason"] = approve_reason
                results.append(rec)
                continue

            if dry_run:
                rec["decision"] = "would_ingest"
                # no DL; could preview parser on sample but skip (no real file)
                results.append(rec)
                continue

            # 4. Real controlled DL + hash + parse + persist + links (only here)
            try:
                max_b = int((elig.size_mb or 50) * 1024 * 1024) + (10 * 1024 * 1024)
                local_path = self.downloader.download(item.id, max_bytes=max_b)
                sha = self.hasher.hash_file(local_path)

                self.store.persist_file(item, sid, sha256=sha, local_cache=str(local_path))
                self.store.update_file_status(sid, download_status="downloaded")

                pmeta = self.parser.parse(local_path)
                excerpt = str(pmeta.get("text_excerpt", ""))[:8000]
                char_c = int(pmeta.get("char_count", 0))
                pstatus = "success" if not pmeta.get("error") else "error"
                self.store.persist_parser_output(
                    sid, "ParserRouter", "1.0.0", sha, excerpt, char_c, status=pstatus
                )

                # Source links (idempotent)
                self.registry.link_sources(sid, sid, link_type="parsed_from", confidence=1.0)
                # if this came from attachment context, caller can have added "attaches" earlier

                self.store.update_file_status(sid, parse_status=pstatus)

                rec["decision"] = "ingested"
                rec["local_cache"] = str(local_path)
                rec["sha256"] = sha[:12] + "..."
                rec["excerpt_preview"] = (excerpt[:180] + "...") if len(excerpt) > 180 else excerpt
                rec["parser_meta"] = {k: v for k, v in pmeta.items() if k != "text_excerpt"}
            except Exception as ex:  # failure isolation
                rec["decision"] = "error"
                rec["error"] = str(ex)[:200]
                try:
                    self.store.update_file_status(sid, download_status="error", parse_status="error")
                except Exception:
                    pass
            results.append(rec)

        return results
