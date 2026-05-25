"""FileIngestionService: discovery of attachments/drive links from mail/calendar + full pipeline."""

from __future__ import annotations

from typing import List, Optional

from hb_assistant.graph.drive_item_client import DriveItemClient
from hb_assistant.graph.mail_client import MailClient
from hb_assistant.links.registry import SourceLinkRegistry
from hb_assistant.normalize.attachment import Attachment
from hb_assistant.store.repositories import Store

from .eligibility import EligibilityGate
from .downloader import ControlledDownloader
from .hasher import ContentHasher
from .router import ParserRouter

class FileIngestionService:
    """Orchestrates attachment/drive file link discovery and ingestion."""

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
        self.downloader = ControlledDownloader(drive_client)  # simplified
        self.hasher = ContentHasher()
        self.parser = ParserRouter()

    def discover_and_ingest_pending(self, limit: int = 5) -> List[dict]:
        """Thin discovery: recent mail with attachments -> metadata + eligibility preview.
        Full DL/parse only on explicit ingest (dry-run friendly).
        """
        results = []
        # In real: use mail.list_inbound with has_attachments, then list_attachments
        # For MVP skeleton: return empty or stub (tests will mock)
        return results
